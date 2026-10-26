import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useVoiceInput } from '@/hooks/useVoiceInput'

describe('useVoiceInput and Chat Composer Voice Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    delete (window as any).SpeechRecognition
    delete (window as any).webkitSpeechRecognition
  })

  it('initializes in idle state with default volumes when speech recognition is unavailable', () => {
    const { result } = renderHook(() => useVoiceInput())

    expect(result.current.state).toBe('idle')
    expect(result.current.isListening).toBe(false)
    expect(result.current.isSupported).toBe(false)
    expect(result.current.volumes).toHaveLength(5)
    expect(result.current.errorMessage).toBeNull()
  })

  it('sets error state gracefully when startRecording is invoked on an unsupported platform', async () => {
    const onError = vi.fn()
    const { result } = renderHook(() => useVoiceInput({ onError }))

    await act(async () => {
      await result.current.startRecording()
    })

    expect(result.current.state).toBe('error')
    expect(result.current.errorMessage).toContain('not supported in this browser')
    expect(onError).toHaveBeenCalledWith(expect.stringContaining('not supported'))
  })

  it('correctly processes recognition events with final and interim transcripts without duplication', async () => {
    let mockOnResult: any = null

    class MockSpeechRecognition {
      continuous = false
      interimResults = false
      lang = 'en-US'
      maxAlternatives = 1
      onstart: any = null
      onresult: any = null
      onerror: any = null
      onend: any = null

      start() {
        mockOnResult = this.onresult
        if (this.onstart) this.onstart()
      }
      abort() {}
    }

    ;(window as any).webkitSpeechRecognition = MockSpeechRecognition

    const onTranscriptChange = vi.fn()
    const { result } = renderHook(() => useVoiceInput({ onTranscriptChange }))

    expect(result.current.isSupported).toBe(true)

    await act(async () => {
      await result.current.startRecording()
    })

    expect(result.current.state).toBe('recording')
    expect(result.current.isListening).toBe(true)

    // Simulate first interim speech
    act(() => {
      mockOnResult({
        resultIndex: 0,
        results: [
          Object.assign([{ transcript: 'how to' }], { isFinal: false }),
        ],
      })
    })

    expect(result.current.interimTranscript).toBe('how to')
    expect(onTranscriptChange).toHaveBeenCalledWith('how to', '')

    // Simulate finalization of first chunk and second chunk arriving
    act(() => {
      mockOnResult({
        resultIndex: 0,
        results: [
          Object.assign([{ transcript: 'how to' }], { isFinal: true }),
          Object.assign([{ transcript: 'configure RAG' }], { isFinal: true }),
        ],
      })
    })

    expect(result.current.finalTranscript).toBe('how to configure RAG')
    expect(result.current.interimTranscript).toBe('')
    expect(onTranscriptChange).toHaveBeenCalledWith('', 'how to configure RAG')

    // Stop recording and verify finalized string is returned
    let finalized = ''
    act(() => {
      finalized = result.current.stopRecording()
    })

    expect(finalized).toBe('how to configure RAG')
    expect(result.current.isListening).toBe(false)
  })

  it('preserves previous finalized text across pause auto-restarts', async () => {
    let currentInstance: any = null
    let startCallCount = 0

    class MockSpeechRecognition {
      continuous = true
      interimResults = true
      lang = 'en-US'
      maxAlternatives = 1
      onstart: any = null
      onresult: any = null
      onerror: any = null
      onend: any = null

      start() {
        startCallCount += 1
        currentInstance = this
        if (this.onstart) this.onstart()
      }
      abort() {}
    }

    ;(window as any).webkitSpeechRecognition = MockSpeechRecognition

    const onTranscriptChange = vi.fn()
    const { result } = renderHook(() => useVoiceInput({ onTranscriptChange }))

    await act(async () => {
      await result.current.startRecording()
    })

    expect(startCallCount).toBe(1)

    // First session receives speech
    act(() => {
      currentInstance.onresult({
        results: [
          Object.assign([{ transcript: 'first sentence' }], { isFinal: true }),
        ],
      })
    })

    expect(result.current.finalTranscript).toBe('first sentence')
    expect(onTranscriptChange).toHaveBeenLastCalledWith('', 'first sentence')

    // Natural pause triggers onend
    act(() => {
      currentInstance.onend()
    })

    // Recognition restarted automatically
    expect(startCallCount).toBe(2)

    // Second session receives speech after pause (new results array starting at index 0)
    act(() => {
      currentInstance.onresult({
        results: [
          Object.assign([{ transcript: 'second sentence' }], { isFinal: true }),
        ],
      })
    })

    // Both sentences must be preserved seamlessly
    expect(result.current.finalTranscript).toBe('first sentence second sentence')
    expect(onTranscriptChange).toHaveBeenLastCalledWith('', 'first sentence second sentence')

    // Stop recording returns combined text
    let finalized = ''
    act(() => {
      finalized = result.current.stopRecording()
    })

    expect(finalized).toBe('first sentence second sentence')
  })

  it('finalizes immediately recognized interim speech on stopRecording without dropping words', async () => {
    let currentInstance: any = null

    class MockSpeechRecognition {
      start() {
        currentInstance = this
        if (this.onstart) this.onstart()
      }
      abort() {}
      onstart: any = null
      onresult: any = null
      onerror: any = null
      onend: any = null
    }

    ;(window as any).webkitSpeechRecognition = MockSpeechRecognition

    const { result } = renderHook(() => useVoiceInput())

    await act(async () => {
      await result.current.startRecording()
    })

    // User is actively speaking an interim phrase right when Done is clicked
    act(() => {
      currentInstance.onresult({
        results: [
          Object.assign([{ transcript: 'urgent interim question' }], { isFinal: false }),
        ],
      })
    })

    let finalized = ''
    act(() => {
      finalized = result.current.stopRecording()
    })

    expect(finalized).toBe('urgent interim question')
    expect(result.current.isListening).toBe(false)
  })

  it('cancelRecording discards accumulated text and resets state to idle', async () => {
    let currentInstance: any = null

    class MockSpeechRecognition {
      start() {
        currentInstance = this
        if (this.onstart) this.onstart()
      }
      abort = vi.fn()
      onstart: any = null
      onresult: any = null
      onerror: any = null
      onend: any = null
    }

    ;(window as any).webkitSpeechRecognition = MockSpeechRecognition

    const { result } = renderHook(() => useVoiceInput())

    await act(async () => {
      await result.current.startRecording()
    })

    expect(result.current.isListening).toBe(true)

    act(() => {
      currentInstance.onresult({
        results: [
          Object.assign([{ transcript: 'discard this text' }], { isFinal: true }),
        ],
      })
    })

    act(() => {
      result.current.cancelRecording()
    })

    expect(result.current.isListening).toBe(false)
    expect(result.current.finalTranscript).toBe('')
    expect(result.current.interimTranscript).toBe('')
  })

  it('handles fatal errors by setting error state and preventing restart loops', async () => {
    let currentInstance: any = null
    let startCallCount = 0

    class MockSpeechRecognition {
      start() {
        startCallCount += 1
        currentInstance = this
        if (this.onstart) this.onstart()
      }
      abort() {}
      onstart: any = null
      onresult: any = null
      onerror: any = null
      onend: any = null
    }

    ;(window as any).webkitSpeechRecognition = MockSpeechRecognition

    const onError = vi.fn()
    const { result } = renderHook(() => useVoiceInput({ onError }))

    await act(async () => {
      await result.current.startRecording()
    })

    expect(startCallCount).toBe(1)

    // Simulate fatal not-allowed error
    act(() => {
      currentInstance.onerror({ error: 'not-allowed' })
      currentInstance.onend()
    })

    // Must transition to error, call onError, and NOT attempt to restart
    expect(result.current.state).toBe('error')
    expect(result.current.errorMessage).toContain('permission denied')
    expect(onError).toHaveBeenCalledWith(expect.stringContaining('permission denied'))
    expect(startCallCount).toBe(1) // No second start
  })

  it('ignores aborted error events gracefully without error state', async () => {
    let currentInstance: any = null

    class MockSpeechRecognition {
      start() {
        currentInstance = this
        if (this.onstart) this.onstart()
      }
      abort() {}
      onstart: any = null
      onresult: any = null
      onerror: any = null
      onend: any = null
    }

    ;(window as any).webkitSpeechRecognition = MockSpeechRecognition

    const onError = vi.fn()
    const { result } = renderHook(() => useVoiceInput({ onError }))

    await act(async () => {
      await result.current.startRecording()
    })

    // Simulate aborted event (normal outcome of abort())
    act(() => {
      currentInstance.onerror({ error: 'aborted' })
    })

    expect(result.current.state).toBe('recording')
    expect(result.current.errorMessage).toBeNull()
    expect(onError).not.toHaveBeenCalled()
  })
})
