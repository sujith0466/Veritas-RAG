import { useState, useRef, useCallback, useEffect } from 'react'

export type VoiceInputState = 'idle' | 'requesting' | 'recording' | 'processing' | 'error'

export interface UseVoiceInputOptions {
  onTranscriptChange?: (interim: string, final: string) => void
  onError?: (errorMessage: string) => void
}

export function useVoiceInput(options: UseVoiceInputOptions = {}) {
  const { onTranscriptChange, onError } = options
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
  const finalAccumulatedRef = useRef('')

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

    setVolumes([0.1, 0.1, 0.1, 0.1, 0.1])
  }, [])

  const cleanupAll = useCallback(() => {
    cleanupAudio()

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
        if (!analyserRef.current) return
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
      // AudioContext failure (e.g. headless/unsupported) falls back to default visualizer animation
    }
  }, [])

  const startRecording = useCallback(async () => {
    setErrorMessage(null)
    setInterimTranscript('')
    setFinalTranscript('')
    finalAccumulatedRef.current = ''
    isManuallyStoppingRef.current = false

    if (!isSupported) {
      const msg = 'Speech recognition is not supported in this browser.'
      setErrorMessage(msg)
      setState('error')
      onError?.(msg)
      return
    }

    setState('requesting')

    let stream: MediaStream | null = null
    if (navigator.mediaDevices?.getUserMedia) {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        mediaStreamRef.current = stream
        startAudioAnalysis(stream)
      } catch (err: any) {
        let msg = 'Microphone access was denied. Please allow microphone permissions.'
        if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
          msg = 'No microphone device found on your system.'
        }
        setErrorMessage(msg)
        setState('error')
        cleanupAudio()
        onError?.(msg)
        return
      }
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
        setState('recording')
      }

      recognition.onresult = (event: any) => {
        let interim = ''
        let currentFinal = finalAccumulatedRef.current

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcriptSegment = event.results[i][0]?.transcript || ''
          if (event.results[i].isFinal) {
            currentFinal = currentFinal ? `${currentFinal.trim()} ${transcriptSegment.trim()}` : transcriptSegment.trim()
            finalAccumulatedRef.current = currentFinal
          } else {
            interim += transcriptSegment
          }
        }

        setInterimTranscript(interim)
        setFinalTranscript(currentFinal)
        onTranscriptChange?.(interim, currentFinal)
      }

      recognition.onerror = (event: any) => {
        if (isManuallyStoppingRef.current) return

        let msg = 'An error occurred during voice recognition.'
        if (event.error === 'not-allowed') {
          msg = 'Microphone permission denied.'
        } else if (event.error === 'no-speech') {
          msg = 'No speech detected.'
        } else if (event.error === 'audio-capture') {
          msg = 'No microphone available.'
        } else if (event.error === 'network') {
          msg = 'Network error occurred during speech recognition.'
        }

        // 'no-speech' can occur normally on pauses; for fatal errors update state
        if (event.error !== 'no-speech') {
          setErrorMessage(msg)
          setState('error')
          onError?.(msg)
          cleanupAudio()
        }
      }

      recognition.onend = () => {
        cleanupAudio()
        setState('idle')
      }

      recognition.start()
    } catch (err: any) {
      const msg = 'Failed to initialize voice recognition.'
      setErrorMessage(msg)
      setState('error')
      cleanupAudio()
      onError?.(msg)
    }
  }, [isSupported, startAudioAnalysis, cleanupAudio, onError, onTranscriptChange])

  const stopRecording = useCallback((): string => {
    isManuallyStoppingRef.current = true
    setState('idle')

    const finalized = (
      finalAccumulatedRef.current
        ? `${finalAccumulatedRef.current.trim()} ${interimTranscript.trim()}`
        : interimTranscript.trim()
    ).trim()

    cleanupAll()
    setInterimTranscript('')
    setFinalTranscript('')
    finalAccumulatedRef.current = ''

    return finalized
  }, [interimTranscript, cleanupAll])

  const cancelRecording = useCallback(() => {
    isManuallyStoppingRef.current = true
    setState('idle')
    cleanupAll()
    setInterimTranscript('')
    setFinalTranscript('')
    finalAccumulatedRef.current = ''
  }, [cleanupAll])

  // Guaranteed cleanup on unmount
  useEffect(() => {
    return () => {
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
