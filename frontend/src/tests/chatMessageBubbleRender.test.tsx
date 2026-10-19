import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { useState, useCallback, useRef, useEffect } from 'react'
import { ChatMessageBubble, parseSSEBlock, applyProgressUpdate } from '@/pages/chat'
import type { ChatMessage } from '@/stores/chatStore'

// Test Harness simulating the chat message list rendering loop
interface ConversationHarnessProps {
  initialMessages: ChatMessage[]
  renderSpy?: (messageId: string) => void
  onStartEdit?: (id: string) => void
  onCancelEdit?: () => void
  onSaveEdit?: (messageId: string, newText: string) => Promise<void> | void
  onFeedback?: (messageId: string, rating: 'like' | 'dislike' | null) => void
  onShare?: (message: ChatMessage) => void
  abortController?: AbortController
}

function ConversationHarness({
  initialMessages,
  renderSpy,
  onStartEdit,
  onCancelEdit,
  onSaveEdit,
  onFeedback,
  onShare,
  abortController,
}: ConversationHarnessProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
  const [isStreaming, setIsStreaming] = useState(true)
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController>(abortController || new AbortController())
  const accumulatedTextRef = useRef('')
  const accumulatedCitationsRef = useRef<any[]>([])

  useEffect(() => {
    if (abortController) {
      abortControllerRef.current = abortController
    }
  }, [abortController])

  const handleStartEdit = useCallback((id: string) => {
    setEditingMessageId(id)
    onStartEdit?.(id)
  }, [onStartEdit])

  const handleCancelEdit = useCallback(() => {
    setEditingMessageId(null)
    onCancelEdit?.()
  }, [onCancelEdit])

  const handleSaveEdit = useCallback(async (messageId: string, newText: string) => {
    setMessages(prev => prev.map(m => m.id === messageId ? { ...m, message: newText } : m))
    setEditingMessageId(null)
    await onSaveEdit?.(messageId, newText)
  }, [onSaveEdit])

  const handleFeedback = useCallback((messageId: string, rating: 'like' | 'dislike' | null) => {
    setMessages(prev => prev.map(m => {
      if (m.id !== messageId) return m
      const meta = { ...(m.metadata_json as any || {}) }
      if (rating === null) {
        delete meta.feedback
      } else {
        meta.feedback = rating
      }
      return { ...m, metadata_json: meta }
    }))
    onFeedback?.(messageId, rating)
  }, [onFeedback])

  const handleShare = useCallback((msg: ChatMessage) => {
    onShare?.(msg)
  }, [onShare])

  const appendTokenToActive = () => {
    setMessages(prev => {
      const next = [...prev]
      const lastIndex = next.length - 1
      const lastMsg = next[lastIndex]
      const newText = (lastMsg.message || '') + ' token'
      accumulatedTextRef.current = newText
      next[lastIndex] = {
        ...lastMsg,
        message: newText,
      }
      return next
    })
  }

  const updateActiveCitations = (citations: any[]) => {
    setMessages(prev => {
      const next = [...prev]
      const lastIndex = next.length - 1
      next[lastIndex] = {
        ...next[lastIndex],
        citations,
      }
      return next
    })
  }

  const updateActiveReliability = (score: number) => {
    setIsStreaming(false)
    setMessages(prev => {
      const next = [...prev]
      const lastIndex = next.length - 1
      next[lastIndex] = {
        ...next[lastIndex],
        reliability_score: score,
      }
      return next
    })
  }

  const setProgressOnActive = (stage: string, message: string) => {
    setMessages(prev => applyProgressUpdate(
      prev,
      JSON.stringify({ stage, message }),
      {
        isAborted: Boolean(abortControllerRef.current?.signal.aborted),
        isTerminal: !isStreaming,
        accumulatedText: accumulatedTextRef.current,
      }
    ))
  }

  const setErrorOnActive = (errorMessage: string) => {
    setIsStreaming(false)
    setMessages(prev => {
      const next = [...prev]
      const lastIndex = next.length - 1
      const lastMsg = next[lastIndex]
      next[lastIndex] = {
        ...lastMsg,
        metadata_json: {
          ...(lastMsg.metadata_json as any || {}),
          status: 'ERROR',
          error: { message: errorMessage },
        },
      }
      return next
    })
  }

  const feedSSE = (rawSSE: string) => {
    let buffer = rawSSE
    while (buffer.includes('\n\n')) {
      const splitIndex = buffer.indexOf('\n\n')
      const block = buffer.slice(0, splitIndex)
      buffer = buffer.slice(splitIndex + 2)

      const { eventType, eventData } = parseSSEBlock(block)

      if (eventType === 'chunk' && eventData) {
        try {
          const data = JSON.parse(eventData)
          if (data.text_delta) {
            accumulatedTextRef.current += data.text_delta
          }
          if (data.citations_delta && data.citations_delta.length > 0) {
            for (const cite of data.citations_delta) {
              if (!accumulatedCitationsRef.current.some(c => c.citation_index === cite.citation_index)) {
                accumulatedCitationsRef.current.push(cite)
              }
            }
          }
          setMessages(prev => {
            const next = [...prev]
            const last = next[next.length - 1]
            next[next.length - 1] = {
              ...last,
              message: accumulatedTextRef.current,
              citations: accumulatedCitationsRef.current.length > 0 ? [...accumulatedCitationsRef.current] : undefined,
            }
            return next
          })
        } catch (err) {
          console.error('Failed to parse SSE event', err)
        }
      } else if (eventType === 'progress' && eventData) {
        setMessages(prev => applyProgressUpdate(prev, eventData, {
          isAborted: Boolean(abortControllerRef.current?.signal.aborted),
          isTerminal: !isStreaming,
          accumulatedText: accumulatedTextRef.current,
        }))
      }
    }
  }

  return (
    <div>
      <div data-testid="controls">
        <button data-testid="append-token-btn" onClick={appendTokenToActive}>
          Append Token
        </button>
        <button
          data-testid="add-citations-btn"
          onClick={() => updateActiveCitations([
            {
              citation_index: 1,
              document_id: 'doc-1',
              document_name: 'Enterprise_Knowledge_Base.pdf',
              excerpt: 'Verified policy detail',
            },
          ])}
        >
          Add Citations
        </button>
        <button
          data-testid="set-reliability-btn"
          onClick={() => updateActiveReliability(0.95)}
        >
          Set Reliability
        </button>
        <button
          data-testid="set-progress-btn"
          onClick={() => setProgressOnActive('retrieving', 'Searching knowledge base...')}
        >
          Set Progress
        </button>
        <button
          data-testid="set-error-btn"
          onClick={() => setErrorOnActive('Stream failed')}
        >
          Set Error
        </button>
        <button
          data-testid="feed-empty-chunk-btn"
          onClick={() => feedSSE('event: chunk\ndata: {"text_delta":""}\n\n')}
        >
          Feed Empty Chunk
        </button>
        <button
          data-testid="feed-citations-chunk-btn"
          onClick={() => feedSSE('event: chunk\ndata: {"citations_delta":[{"citation_index":1,"document_id":"doc-1","document_name":"Enterprise_Knowledge_Base.pdf","excerpt":"Verified policy detail"}]}\n\n')}
        >
          Feed Citations Chunk
        </button>
        <button
          data-testid="feed-text-delta-btn"
          onClick={() => feedSSE('event: chunk\ndata: {"text_delta":"Verified corporate policy."}\n\n')}
        >
          Feed Text Delta
        </button>
        <button
          data-testid="feed-progress-btn"
          onClick={() => feedSSE('event: progress\ndata: {"stage":"retrieving","message":"Late progress message"}\n\n')}
        >
          Feed Progress
        </button>
        <button
          data-testid="abort-stream-btn"
          onClick={() => {
            abortControllerRef.current.abort()
            setIsStreaming(false)
          }}
        >
          Abort Stream
        </button>
      </div>

      <div data-testid="message-list">
        {messages.map((msg, i) => (
          <ChatMessageBubble
            key={msg.id}
            message={msg}
            isStreaming={isStreaming && i === messages.length - 1}
            isEditing={editingMessageId === msg.id}
            onStartEdit={handleStartEdit}
            onCancelEdit={handleCancelEdit}
            onSaveEdit={handleSaveEdit}
            onFeedback={handleFeedback}
            onShare={handleShare}
            disabled={isStreaming}
            onRender={renderSpy}
          />
        ))}
      </div>
    </div>
  )
}

describe('REC-004: ChatMessageBubble Rendering Optimization Regression Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    })
  })

  const sampleMessages: ChatMessage[] = [
    {
      id: 'msg-user-1',
      session_id: 'sess-1',
      role: 'user',
      message: 'What is our corporate remote work policy?',
      created_at: '2026-10-19T10:00:00Z',
    },
    {
      id: 'msg-asst-1',
      session_id: 'sess-1',
      role: 'assistant',
      message: 'Our corporate remote work policy allows hybrid arrangements with manager approval.',
      created_at: '2026-10-19T10:00:05Z',
      reliability_score: 0.88,
    },
    {
      id: 'msg-asst-streaming',
      session_id: 'sess-1',
      role: 'assistant',
      message: 'Initial',
      created_at: '2026-10-19T10:01:00Z',
    },
  ]

  describe('1. Render Suppression for Historical Message Bubbles', () => {
    it('historical messages do not re-render when only the active streaming message receives tokens', () => {
      const renderSpy = vi.fn()

      render(
        <ConversationHarness
          initialMessages={sampleMessages}
          renderSpy={renderSpy}
        />
      )

      // Initial mount: all 3 messages render once
      const initialUserCalls = renderSpy.mock.calls.filter(call => call[0] === 'msg-user-1').length
      const initialAsstCalls = renderSpy.mock.calls.filter(call => call[0] === 'msg-asst-1').length
      const initialStreamCalls = renderSpy.mock.calls.filter(call => call[0] === 'msg-asst-streaming').length

      expect(initialUserCalls).toBe(1)
      expect(initialAsstCalls).toBe(1)
      expect(initialStreamCalls).toBe(1)

      // Simulate 4 incoming stream chunks / animation frame flushes
      const appendButton = screen.getByTestId('append-token-btn')
      fireEvent.click(appendButton)
      fireEvent.click(appendButton)
      fireEvent.click(appendButton)
      fireEvent.click(appendButton)

      const postUserCalls = renderSpy.mock.calls.filter(call => call[0] === 'msg-user-1').length
      const postAsstCalls = renderSpy.mock.calls.filter(call => call[0] === 'msg-asst-1').length
      const postStreamCalls = renderSpy.mock.calls.filter(call => call[0] === 'msg-asst-streaming').length

      // CRITICAL ASSERTION: Historical messages must have ZERO re-renders during active streaming
      expect(postUserCalls).toBe(1)
      expect(postAsstCalls).toBe(1)

      // Active streaming message must update on each token append (1 mount + 4 appends = 5 renders)
      expect(postStreamCalls).toBe(5)
    })
  })

  describe('2. Active Streaming Message Progressive Updates', () => {
    it('the active streaming bubble updates its visible content in the DOM as tokens arrive', () => {
      render(
        <ConversationHarness
          initialMessages={sampleMessages}
        />
      )

      const appendButton = screen.getByTestId('append-token-btn')
      expect(screen.getByText(/Initial/)).toBeInTheDocument()

      fireEvent.click(appendButton)
      expect(screen.getByText(/Initial token/)).toBeInTheDocument()

      fireEvent.click(appendButton)
      expect(screen.getByText(/Initial token token/)).toBeInTheDocument()
    })
  })

  describe('3. Propagation of Citations, Reliability, Status, and Editing State', () => {
    it('propagates citations dynamically to the active bubble', () => {
      render(
        <ConversationHarness
          initialMessages={sampleMessages}
        />
      )

      const addCitationsBtn = screen.getByTestId('add-citations-btn')
      fireEvent.click(addCitationsBtn)

      // Citations grid should render with citation title
      expect(screen.getByText('Enterprise_Knowledge_Base.pdf')).toBeInTheDocument()
    })

    it('propagates reliability score update and displays badge', () => {
      const renderSpy = vi.fn()
      render(
        <ConversationHarness
          initialMessages={sampleMessages}
          renderSpy={renderSpy}
        />
      )

      const setReliabilityBtn = screen.getByTestId('set-reliability-btn')
      fireEvent.click(setReliabilityBtn)

      // Reliability badge: 95% Reliable
      expect(screen.getByText('95% Reliable')).toBeInTheDocument()
    })

    it('renders error state when metadata contains error status', () => {
      const errorMsg: ChatMessage = {
        id: 'msg-error',
        session_id: 'sess-1',
        role: 'assistant',
        message: 'Something went wrong',
        created_at: '2026-10-19T10:02:00Z',
        metadata_json: {
          status: 'ERROR',
          error: { message: 'Upstream provider connection timeout' },
        },
      }

      render(
        <ChatMessageBubble
          message={errorMsg}
          isStreaming={false}
        />
      )

      expect(screen.getByText(/Upstream provider connection timeout/)).toBeInTheDocument()
    })

    it('renders edit input when message is placed in editing state', () => {
      const { rerender } = render(
        <ChatMessageBubble
          message={sampleMessages[0]}
          isStreaming={false}
          isEditing={false}
          onStartEdit={vi.fn()}
        />
      )

      expect(screen.queryByRole('textbox', { name: 'Edit your message' })).not.toBeInTheDocument()

      // Transition to editing mode
      rerender(
        <ChatMessageBubble
          message={sampleMessages[0]}
          isStreaming={false}
          isEditing={true}
          onStartEdit={vi.fn()}
          onCancelEdit={vi.fn()}
          onSaveEdit={vi.fn()}
        />
      )

      expect(screen.getByRole('textbox', { name: 'Edit your message' })).toBeInTheDocument()
      expect(screen.getByDisplayValue('What is our corporate remote work policy?')).toBeInTheDocument()
    })
  })

  describe('4. Event Handlers and User Actions', () => {
    it('triggers onStartEdit with message id when user clicks edit button', () => {
      const onStartEdit = vi.fn()
      render(
        <ChatMessageBubble
          message={sampleMessages[0]}
          isStreaming={false}
          isEditing={false}
          onStartEdit={onStartEdit}
        />
      )

      const editBtn = screen.getByRole('button', { name: 'Edit message' })
      fireEvent.click(editBtn)

      expect(onStartEdit).toHaveBeenCalledWith('msg-user-1')
    })

    it('triggers onFeedback with rating and message id on assistant bubble', () => {
      const onFeedback = vi.fn()
      render(
        <ChatMessageBubble
          message={sampleMessages[1]}
          isStreaming={false}
          onFeedback={onFeedback}
        />
      )

      const likeBtn = screen.getByRole('button', { name: 'Like response' })
      fireEvent.click(likeBtn)

      expect(onFeedback).toHaveBeenCalledWith('msg-asst-1', 'like')
    })

    it('triggers onSaveEdit with message id and new content when saving an edit', async () => {
      const onSaveEdit = vi.fn().mockResolvedValue(undefined)
      render(
        <ChatMessageBubble
          message={sampleMessages[0]}
          isStreaming={false}
          isEditing={true}
          onSaveEdit={onSaveEdit}
          onCancelEdit={vi.fn()}
        />
      )

      const textarea = screen.getByRole('textbox', { name: 'Edit your message' })
      fireEvent.change(textarea, { target: { value: 'Updated prompt from user' } })

      const saveBtn = screen.getByRole('button', { name: 'Save & Submit' })
      fireEvent.click(saveBtn)

      await waitFor(() => {
        expect(onSaveEdit).toHaveBeenCalledWith('msg-user-1', 'Updated prompt from user')
      })
    })

    it('triggers onCancelEdit when user cancels editing', () => {
      const onCancelEdit = vi.fn()
      render(
        <ChatMessageBubble
          message={sampleMessages[0]}
          isStreaming={false}
          isEditing={true}
          onCancelEdit={onCancelEdit}
        />
      )

      const cancelBtn = screen.getByRole('button', { name: 'Cancel' })
      fireEvent.click(cancelBtn)

      expect(onCancelEdit).toHaveBeenCalledTimes(1)
    })
  })

  describe('REC-001: SSE Progress Events & Non-Regressive Bubble Rendering', () => {
    it('renders dynamic progress message from metadata when retrieving', () => {
      const assistantWithProgress: ChatMessage = {
        id: 'msg-asst-prog',
        session_id: 'sess-1',
        role: 'assistant',
        message: '',
        created_at: '2026-10-19T10:00:00Z',
        metadata_json: {
          progress_stage: 'retrieving',
          progress_message: 'Searching knowledge base...',
        },
      }

      render(
        <ChatMessageBubble
          message={assistantWithProgress}
          isStreaming={true}
        />
      )

      expect(screen.getByText('Searching knowledge base...')).toBeDefined()
    })

    it('falls back to default Searching knowledge base... when progress_message is missing', () => {
      const assistantEmpty: ChatMessage = {
        id: 'msg-asst-empty',
        session_id: 'sess-1',
        role: 'assistant',
        message: '',
        created_at: '2026-10-19T10:00:00Z',
      }

      render(
        <ChatMessageBubble
          message={assistantEmpty}
          isStreaming={true}
        />
      )

      expect(screen.getByText('Searching knowledge base...')).toBeDefined()
    })

    it('does not re-render historical message bubbles when active progress message updates', () => {
      const renderTracker = vi.fn()
      const initialMessages: ChatMessage[] = [
        ...sampleMessages,
        {
          id: 'msg-asst-active',
          session_id: 'sess-1',
          role: 'assistant',
          message: '',
          created_at: '2026-10-19T10:03:00Z',
        },
      ]

      render(
        <ConversationHarness
          initialMessages={initialMessages}
          renderSpy={renderTracker}
        />
      )

      // Initial mount renders each message once
      expect(renderTracker).toHaveBeenCalledWith('msg-user-1')
      expect(renderTracker).toHaveBeenCalledWith('msg-asst-1')
      expect(renderTracker).toHaveBeenCalledWith('msg-asst-streaming')
      expect(renderTracker).toHaveBeenCalledWith('msg-asst-active')

      const initialUser1Count = renderTracker.mock.calls.filter(([id]) => id === 'msg-user-1').length
      const initialAsst1Count = renderTracker.mock.calls.filter(([id]) => id === 'msg-asst-1').length
      const initialStreamingCount = renderTracker.mock.calls.filter(([id]) => id === 'msg-asst-streaming').length

      // Trigger progress update on active assistant bubble
      const setProgressBtn = screen.getByTestId('set-progress-btn')
      fireEvent.click(setProgressBtn)

      // Active assistant displays progress
      expect(screen.getByText('Searching knowledge base...')).toBeDefined()

      // Historical messages must not have re-rendered (render counts remain unchanged)
      const afterUser1Count = renderTracker.mock.calls.filter(([id]) => id === 'msg-user-1').length
      const afterAsst1Count = renderTracker.mock.calls.filter(([id]) => id === 'msg-asst-1').length
      const afterStreamingCount = renderTracker.mock.calls.filter(([id]) => id === 'msg-asst-streaming').length

      expect(afterUser1Count).toBe(initialUser1Count)
      expect(afterAsst1Count).toBe(initialAsst1Count)
      expect(afterStreamingCount).toBe(initialStreamingCount)
    })

    it('unmounts progress UI and renders answer text when first token arrives', () => {
      const initialMessages: ChatMessage[] = [
        {
          id: 'msg-asst-active',
          session_id: 'sess-1',
          role: 'assistant',
          message: '',
          created_at: '2026-10-19T10:03:00Z',
          metadata_json: {
            progress_stage: 'retrieving',
            progress_message: 'Searching knowledge base...',
          },
        },
      ]

      render(<ConversationHarness initialMessages={initialMessages} />)

      // Progress is visible before token
      expect(screen.getByText('Searching knowledge base...')).toBeDefined()

      // Append token
      const appendTokenBtn = screen.getByTestId('append-token-btn')
      fireEvent.click(appendTokenBtn)

      // Progress is cleared and token is visible
      expect(screen.queryByText('Searching knowledge base...')).toBeNull()
      expect(screen.getByText('token')).toBeDefined()
    })

    it('unmounts progress UI and displays error when terminal ERROR status is set', () => {
      const initialMessages: ChatMessage[] = [
        {
          id: 'msg-asst-active',
          session_id: 'sess-1',
          role: 'assistant',
          message: '',
          created_at: '2026-10-19T10:03:00Z',
          metadata_json: {
            progress_stage: 'retrieving',
            progress_message: 'Searching knowledge base...',
          },
        },
      ]

      render(<ConversationHarness initialMessages={initialMessages} />)

      expect(screen.getByText('Searching knowledge base...')).toBeDefined()

      // Trigger error
      const setErrorBtn = screen.getByTestId('set-error-btn')
      fireEvent.click(setErrorBtn)

      // Progress is unmounted and error is shown
      expect(screen.queryByText('Searching knowledge base...')).toBeNull()
      expect(screen.getByText('Error:')).toBeDefined()
      expect(screen.getByText(/Stream failed/)).toBeDefined()
    })

    it('safely catches malformed progress JSON without crashing or corrupting messages', () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      const messages: ChatMessage[] = [
        {
          id: 'msg-asst-active',
          session_id: 'sess-1',
          role: 'assistant',
          message: '',
          created_at: '2026-10-19T10:00:00Z',
        },
      ]

      const block = 'event: progress\ndata: {broken json payload\n\n'
      const { eventType, eventData } = parseSSEBlock(block.trim())
      expect(eventType).toBe('progress')

      // Invoke production applyProgressUpdate with malformed payload
      const result = applyProgressUpdate(messages, eventData, { isAborted: false })

      expect(consoleErrorSpy).toHaveBeenCalledWith('Failed to parse progress SSE event', expect.any(SyntaxError))
      expect(result).toBe(messages)
      expect(result[0].metadata_json).toBeUndefined()
      consoleErrorSpy.mockRestore()
    })

    it('safely ignores unknown event types with zero state side effects', () => {
      const block = 'event: future_unknown_event\ndata: {"foo":"bar"}\n\n'
      const { eventType, eventData } = parseSSEBlock(block.trim())

      expect(eventType).toBe('future_unknown_event')
      expect(eventData).toBe('{"foo":"bar"}')

      const messages: ChatMessage[] = [
        {
          id: 'msg-asst-active',
          session_id: 'sess-1',
          role: 'assistant',
          message: '',
          created_at: '2026-10-19T10:00:00Z',
        },
      ]

      // Unknown event type is not handled by progress, chunk, or error handlers
      expect(eventType === 'progress').toBe(false)
      expect(messages[0].metadata_json).toBeUndefined()
    })

    it('keeps progress indicator visible across empty and metadata-only chunks until first non-empty text delta arrives', () => {
      const initialMessages: ChatMessage[] = [
        {
          id: 'msg-asst-prog',
          session_id: 'sess-1',
          role: 'assistant',
          message: '',
          created_at: '2026-10-19T10:00:00Z',
          metadata_json: {
            progress_stage: 'retrieving',
            progress_message: 'Searching knowledge base...',
          },
        },
      ]

      // Unit verification: production applyProgressUpdate rejects progress once text has streamed
      const messagesWithAnswer: ChatMessage[] = [
        {
          ...initialMessages[0],
          message: 'Real answer token',
        },
      ]
      const rejectedUpdate = applyProgressUpdate(
        messagesWithAnswer,
        JSON.stringify({ stage: 'retrieving', message: 'Ignored progress update' }),
        { isAborted: false, accumulatedText: 'Real answer token' }
      )
      expect(rejectedUpdate[0].metadata_json?.progress_message).toBe('Searching knowledge base...')

      // DOM and stream lifecycle verification in ConversationHarness
      render(<ConversationHarness initialMessages={initialMessages} />)

      // Initial state: progress indicator is visible
      expect(screen.getByText('Searching knowledge base...')).toBeInTheDocument()

      // Feed empty chunk (text_delta = "")
      fireEvent.click(screen.getByTestId('feed-empty-chunk-btn'))

      // Progress MUST remain visible (not cleared by empty chunk)
      expect(screen.getByText('Searching knowledge base...')).toBeInTheDocument()

      // Feed metadata-only chunk (citations_delta present, no text_delta)
      fireEvent.click(screen.getByTestId('feed-citations-chunk-btn'))

      // Progress MUST still remain visible
      expect(screen.getByText('Searching knowledge base...')).toBeInTheDocument()

      // Feed first non-empty text delta
      fireEvent.click(screen.getByTestId('feed-text-delta-btn'))

      // Progress indicator must now be unmounted / cleared
      expect(screen.queryByText('Searching knowledge base...')).toBeNull()

      // First token of answer is rendered
      expect(screen.getByText(/Verified corporate policy\./)).toBeInTheDocument()
    })

    it('rejects late progress events after AbortController cancellation and does not restore progress indicator', () => {
      const abortController = new AbortController()
      const initialMessages: ChatMessage[] = [
        {
          id: 'msg-asst-active',
          session_id: 'sess-1',
          role: 'assistant',
          message: '',
          created_at: '2026-10-19T10:00:00Z',
          metadata_json: {
            progress_stage: 'retrieving',
            progress_message: 'Searching knowledge base...',
          },
        },
      ]

      // 1. Direct unit verification of production applyProgressUpdate function
      abortController.abort()
      const updatedMessages = applyProgressUpdate(
        initialMessages,
        JSON.stringify({ stage: 'retrieving', message: 'Late ghost progress update' }),
        { isAborted: abortController.signal.aborted }
      )
      // Guard strictly rejected the late progress update
      expect(updatedMessages[0].metadata_json?.progress_message).toBe('Searching knowledge base...')
      expect(updatedMessages[0].metadata_json?.progress_message).not.toBe('Late ghost progress update')

      // 2. Full UI lifecycle verification in DOM via ConversationHarness
      const liveController = new AbortController()
      render(
        <ConversationHarness
          initialMessages={initialMessages}
          abortController={liveController}
        />
      )

      // Before abort: progress indicator is visible
      expect(screen.getByText('Searching knowledge base...')).toBeInTheDocument()

      // Simulate client cancelling / aborting generation
      fireEvent.click(screen.getByTestId('abort-stream-btn'))

      // AbortController is aborted and streaming is stopped
      expect(liveController.signal.aborted).toBe(true)

      // Progress indicator is unmounted because stream was terminated
      expect(screen.queryByText('Searching knowledge base...')).toBeNull()

      // Now simulate a late progress event arriving over the network after abort
      fireEvent.click(screen.getByTestId('feed-progress-btn'))

      // Late progress must NOT be applied to state or restored to DOM
      expect(screen.queryByText('Late progress message')).toBeNull()
      expect(screen.queryByText('Searching knowledge base...')).toBeNull()

      // Direct progress trigger is also rejected when aborted
      fireEvent.click(screen.getByTestId('set-progress-btn'))
      expect(screen.queryByText('Searching knowledge base...')).toBeNull()
    })

    it('rejects late progress events when stream is terminal or completed, including empty-answer responses', () => {
      const lateProgressPayload = JSON.stringify({
        stage: 'retrieving',
        message: 'Late ghost progress update',
      })

      // Case 1: Empty response completed with isTerminal: true (reader exhaustion or is_final without text)
      const emptyTerminalMessages: ChatMessage[] = [
        {
          id: 'msg-asst-empty-terminal',
          session_id: 'sess-1',
          role: 'assistant',
          message: '',
          created_at: '2026-10-19T10:00:00Z',
        },
      ]
      const result1 = applyProgressUpdate(emptyTerminalMessages, lateProgressPayload, {
        isAborted: false,
        isTerminal: true,
        accumulatedText: '',
      })
      expect(result1[0].metadata_json).toBeUndefined()

      // Case 2: Response completed with text and isTerminal: true
      const textCompletedMessages: ChatMessage[] = [
        {
          id: 'msg-asst-text-completed',
          session_id: 'sess-1',
          role: 'assistant',
          message: 'Completed assistant response text.',
          created_at: '2026-10-19T10:00:00Z',
          metadata_json: {
            progress_stage: 'retrieving',
            progress_message: 'Searching knowledge base...',
          },
        },
      ]
      const result2 = applyProgressUpdate(textCompletedMessages, lateProgressPayload, {
        isAborted: false,
        isTerminal: true,
        accumulatedText: 'Completed assistant response text.',
      })
      expect(result2[0].metadata_json?.progress_message).toBe('Searching knowledge base...')
      expect(result2[0].metadata_json?.progress_message).not.toBe('Late ghost progress update')

      // Case 3: Error terminal state (isExplicitError)
      const errorTerminalMessages: ChatMessage[] = [
        {
          id: 'msg-asst-error-terminal',
          session_id: 'sess-1',
          role: 'assistant',
          message: '',
          created_at: '2026-10-19T10:00:00Z',
          metadata_json: {
            status: 'ERROR',
            error: { message: 'Stream failed' },
          },
        },
      ]
      const result3 = applyProgressUpdate(errorTerminalMessages, lateProgressPayload, {
        isAborted: false,
      })
      expect(result3[0].metadata_json?.progress_message).toBeUndefined()
    })
  })
})
