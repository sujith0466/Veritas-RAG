import { useState, useRef, useCallback, useEffect } from 'react'

export type VoiceInputState = 'idle' | 'requesting' | 'recording' | 'processing' | 'error'

export interface UseVoiceInputOptions {
  onTranscriptChange?: (interim: string, final: string) => void
  onError?: (errorMessage: string) => void
}

export function useVoiceInput(options: UseVoiceInputOptions = {}) {
  const { onTranscriptChange, onError } = options
  const onTranscriptChangeRef = useRef(onTranscriptChange)
  const onErrorRef = useRef(onError)

  useEffect(() => {
    onTranscriptChangeRef.current = onTranscriptChange
    onErrorRef.current = onError
  }, [onTranscriptChange, onError])

  const [state, setState] = useState<VoiceInputState>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [interimTranscript, setInterimTranscript] = useState('')
  const [finalTranscript, setFinalTranscript] = useState('')
  const [volumes, setVolumes] = useState<number[]>([0.1, 0.1, 0.1, 0.1, 0.1])

  const recognitionRef = useRef<any>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const animationFrameRef = useRef<number | null>(null)
  const isManuallyStoppingRef = useRef(false)
  const hasFatalErrorRef = useRef(false)
  const restartCountRef = useRef(0)
  const restartTimerRef = useRef<NodeJS.Timeout | null>(null)
  const isMountedRef = useRef(true)

  // Accumulation across natural speech pause auto-restarts
  const sessionFinalPrefixRef = useRef('')
  const finalAccumulatedRef = useRef('')
  const interimAccumulatedRef = useRef('')

  const isSupported = typeof window !== 'undefined' && (
    'SpeechRecognition' in window || 'webkitSpeechRecognition' in window
  )

  const cleanupAudio = useCallback(() => {
    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current)
      animationFrameRef.current = null
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => {
        try {
          track.stop()
        } catch (_) {
          // ignore
        }
      })
      mediaStreamRef.current = null
    }

    if (analyserRef.current) {
      try {
        analyserRef.current.disconnect()
      } catch (_) {
        // ignore
      }
      analyserRef.current = null
    }

    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      try {
        audioContextRef.current.close().catch(() => {})
      } catch (_) {
        // ignore
      }
      audioContextRef.current = null
    }

    if (isMountedRef.current) {
      setVolumes([0.1, 0.1, 0.1, 0.1, 0.1])
    }
  }, [])

  const cleanupAll = useCallback(() => {
    cleanupAudio()

    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current)
      restartTimerRef.current = null
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.onstart = null
        recognitionRef.current.onresult = null
        recognitionRef.current.onerror = null
        recognitionRef.current.onend = null
        recognitionRef.current.abort()
      } catch (_) {
        // ignore
      }
      recognitionRef.current = null
    }
  }, [cleanupAudio])

  const startAudioAnalysis = useCallback((stream: MediaStream) => {
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext
      if (!AudioCtx) return

      const audioCtx = new AudioCtx()
      if (audioCtx.state === 'suspended') {
        audioCtx.resume().catch(() => {})
      }
      audioContextRef.current = audioCtx

      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = 64
      analyser.smoothingTimeConstant = 0.75
      analyserRef.current = analyser

      const source = audioCtx.createMediaStreamSource(stream)
      source.connect(analyser)

      const bufferLength = analyser.frequencyBinCount
      const dataArray = new Uint8Array(bufferLength)

      const updateVolumes = () => {
        if (!analyserRef.current || !isMountedRef.current) return
        analyserRef.current.getByteFrequencyData(dataArray)

        // Sample 5 frequency bands across the spectrum
        const step = Math.max(1, Math.floor(bufferLength / 5))
        const bands = [0, 1, 2, 3, 4].map((i) => {
          const val = dataArray[i * step] || 0
          // Normalize to [0.1, 1.0] for responsive visualizer scale
          return Math.max(0.12, Math.min(1.0, val / 200))
        })

        setVolumes(bands)
        animationFrameRef.current = requestAnimationFrame(updateVolumes)
      }

      animationFrameRef.current = requestAnimationFrame(updateVolumes)
    } catch (_) {
      // AudioContext failure falls back gracefully
    }
  }, [])

  const startRecording = useCallback(async () => {
    // If a session was already active or stopping, clean up completely first
    cleanupAll()

    setErrorMessage(null)
    setInterimTranscript('')
    setFinalTranscript('')
    sessionFinalPrefixRef.current = ''
    finalAccumulatedRef.current = ''
    interimAccumulatedRef.current = ''
    isManuallyStoppingRef.current = false
    hasFatalErrorRef.current = false
    restartCountRef.current = 0

    if (!isSupported) {
      const msg = 'Speech recognition is not supported in this browser.'
      setErrorMessage(msg)
      setState('error')
      onErrorRef.current?.(msg)
      return
    }

    setState('requesting')

    let stream: MediaStream | null = null
    if (navigator.mediaDevices?.getUserMedia) {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        if (isManuallyStoppingRef.current || !isMountedRef.current) {
          // Cancelled while waiting for permission/stream
          stream.getTracks().forEach((track) => track.stop())
          return
        }
        mediaStreamRef.current = stream
        startAudioAnalysis(stream)
      } catch (err: any) {
        if (isManuallyStoppingRef.current || !isMountedRef.current) return
        console.warn('Audio visualization stream unavailable, continuing with speech recognition', err)
      }
    }

    if (isManuallyStoppingRef.current || !isMountedRef.current) {
      cleanupAudio()
      return
    }

    try {
      const SpeechRecognitionClass = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
      const recognition = new SpeechRecognitionClass()
      recognitionRef.current = recognition

      recognition.continuous = true
      recognition.interimResults = true
      recognition.lang = typeof navigator !== 'undefined' && navigator.language ? navigator.language : 'en-US'
      recognition.maxAlternatives = 1

      recognition.onstart = () => {
        if (isMountedRef.current && !isManuallyStoppingRef.current) {
          setState('recording')
        }
      }

      recognition.onresult = (event: any) => {
        if (isManuallyStoppingRef.current) return

        let interim = ''
        let currentInstanceFinal = ''

        for (let i = 0; i < event.results.length; i++) {
          const transcriptSegment = event.results[i][0]?.transcript || ''
          if (event.results[i].isFinal) {
            currentInstanceFinal = currentInstanceFinal
              ? `${currentInstanceFinal.trim()} ${transcriptSegment.trim()}`
              : transcriptSegment.trim()
          } else {
            interim += transcriptSegment
          }
        }

        // Combine with previously committed sessions (across natural pauses)
        const prefix = sessionFinalPrefixRef.current.trim()
        const fullFinal = prefix
          ? (currentInstanceFinal ? `${prefix} ${currentInstanceFinal.trim()}` : prefix)
          : currentInstanceFinal.trim()

        finalAccumulatedRef.current = fullFinal
        interimAccumulatedRef.current = interim

        // Reset restart counter upon receiving valid speech
        restartCountRef.current = 0

        if (isMountedRef.current) {
          setInterimTranscript(interim)
          setFinalTranscript(fullFinal)
        }
        onTranscriptChangeRef.current?.(interim, fullFinal)
      }

      recognition.onerror = (event: any) => {
        if (isManuallyStoppingRef.current) return

        // Aborted is an expected lifecycle outcome when stopped/cancelled
        if (event.error === 'aborted') {
          return
        }

        let msg = 'An error occurred during voice recognition.'
        let isFatal = false

        if (event.error === 'not-allowed') {
          msg = 'Microphone permission denied.'
          isFatal = true
        } else if (event.error === 'service-not-allowed') {
          msg = 'Speech recognition service is not allowed or unavailable.'
          isFatal = true
        } else if (event.error === 'audio-capture') {
          msg = 'No microphone available.'
          isFatal = true
        } else if (event.error === 'network') {
          msg = 'Network error occurred during speech recognition.'
          isFatal = true
        } else if (event.error === 'no-speech') {
          msg = 'No speech detected.'
          isFatal = false // Non-fatal pause
        } else if (event.error === 'language-not-supported') {
          msg = 'Speech language is not supported.'
          isFatal = true
        } else if (event.error === 'bad-grammar') {
          msg = 'Speech grammar error occurred.'
          isFatal = true
        }

        if (isFatal) {
          hasFatalErrorRef.current = true
          cleanupAudio()
          if (isMountedRef.current) {
            setErrorMessage(msg)
            setState('error')
          }
          onErrorRef.current?.(msg)
        }
      }

      recognition.onend = () => {
        if (isManuallyStoppingRef.current || hasFatalErrorRef.current || !isMountedRef.current) {
          cleanupAudio()
          if (isMountedRef.current && !hasFatalErrorRef.current) {
            setState('idle')
          }
          return
        }

        // Preserve finalized text accumulated before pause
        if (finalAccumulatedRef.current) {
          sessionFinalPrefixRef.current = finalAccumulatedRef.current
        }

        // Auto-restart recognition across natural pauses if under restart budget
        if (restartCountRef.current < 5) {
          restartCountRef.current += 1
          try {
            recognition.start()
          } catch (_) {
            cleanupAudio()
            if (isMountedRef.current) {
              setState('idle')
            }
          }
        } else {
          // Exceeded restart budget without speech; cleanly finish session
          cleanupAudio()
          if (isMountedRef.current) {
            setState('idle')
          }
        }
      }

      recognition.start()
    } catch (err: any) {
      const msg = 'Failed to initialize voice recognition.'
      cleanupAudio()
      if (isMountedRef.current) {
        setErrorMessage(msg)
        setState('error')
      }
      onErrorRef.current?.(msg)
    }
  }, [isSupported, startAudioAnalysis, cleanupAudio, cleanupAll])

  const stopRecording = useCallback((): string => {
    isManuallyStoppingRef.current = true

    // Compute complete finalized transcript synchronously from refs
    const finalPart = finalAccumulatedRef.current.trim()
    const interimPart = interimAccumulatedRef.current.trim()
    const finalized = (finalPart ? (interimPart ? `${finalPart} ${interimPart}` : finalPart) : interimPart).trim()

    cleanupAll()

    sessionFinalPrefixRef.current = ''
    finalAccumulatedRef.current = ''
    interimAccumulatedRef.current = ''

    if (isMountedRef.current) {
      setState('idle')
      setInterimTranscript('')
      setFinalTranscript('')
    }

    return finalized
  }, [cleanupAll])

  const cancelRecording = useCallback(() => {
    isManuallyStoppingRef.current = true

    cleanupAll()

    sessionFinalPrefixRef.current = ''
    finalAccumulatedRef.current = ''
    interimAccumulatedRef.current = ''

    if (isMountedRef.current) {
      setState('idle')
      setInterimTranscript('')
      setFinalTranscript('')
    }
  }, [cleanupAll])

  // Guaranteed cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
      cleanupAll()
    }
  }, [cleanupAll])

  return {
    state,
    isListening: state === 'recording' || state === 'requesting',
    isSupported,
    volumes,
    interimTranscript,
    finalTranscript,
    errorMessage,
    startRecording,
    stopRecording,
    cancelRecording,
    clearError: () => setErrorMessage(null),
  }
}
