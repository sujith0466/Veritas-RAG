import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { useState, useCallback } from 'react'
import { ChatMessageBubble } from '@/pages/chat'
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
}

function ConversationHarness({
  initialMessages,
  renderSpy,
  onStartEdit,
  onCancelEdit,
  onSaveEdit,
  onFeedback,
  onShare,
}: ConversationHarnessProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
  const [isStreaming, setIsStreaming] = useState(true)
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null)

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
      next[lastIndex] = {
        ...lastMsg,
        message: (lastMsg.message || '') + ' token',
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
})
