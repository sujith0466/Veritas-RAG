import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'
import { useState, useCallback, useRef, useEffect } from 'react'
import { ChatMessageBubble } from '@/pages/chat'
import type { ChatMessage, ChatSession } from '@/stores/chatStore'

// Test Harness mirroring the chat/index.tsx optimistic state machine
interface HarnessProps {
  onFeedbackCall: (sessionId: string, messageId: string, rating: 'like' | 'dislike' | null) => void
  simulateOldBug?: boolean // If true, omits resetting hasOptimisticContent.current = false in finally block
}

function OptimisticReconciliationHarness({ onFeedbackCall, simulateOldBug = false }: HarnessProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [activeSession, setActiveSession] = useState<ChatSession | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const hasOptimisticContent = useRef(false)
  const sessionId = 'session-123'

  // Mirroring chat/index.tsx lines 284-296
  useEffect(() => {
    if (activeSession?.messages && !isStreaming && !hasOptimisticContent.current) {
      setMessages(activeSession.messages)
    }
  }, [activeSession, isStreaming])

  // Mirroring handleFeedbackMessage (lines 694-715)
  const handleFeedback = useCallback((messageId: string, rating: 'like' | 'dislike' | null) => {
    onFeedbackCall(sessionId, messageId, rating)
  }, [onFeedbackCall])

  // Mirroring executeStream starting stream
  const startStream = () => {
    hasOptimisticContent.current = true
    setIsStreaming(true)
    setMessages([
      {
        id: 'client-temp-user-uuid',
        session_id: sessionId,
        role: 'user',
        message: 'What is Veritas-RAG?',
        created_at: new Date().toISOString(),
      },
      {
        id: 'client-temp-asst-uuid',
        session_id: sessionId,
        role: 'assistant',
        message: 'Veritas-RAG is a verified RAG system.',
        created_at: new Date().toISOString(),
      },
    ])
  }

  // Mirroring executeStream finally block (lines 585-595)
  const finishStream = () => {
    setIsStreaming(false)
    if (!simulateOldBug) {
      // CHAT-001 FIX: Reset optimistic guard ref in finally block
      hasOptimisticContent.current = false
    }

    // Server responds with canonical DB message IDs
    setActiveSession({
      id: sessionId,
      title: 'Session Title',
      workspace_id: 'ws-1',
      tenant_id: 'tenant-1',
      user_id: 'user-1',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      messages: [
        {
          id: 'server-canonical-user-uuid',
          session_id: sessionId,
          role: 'user',
          message: 'What is Veritas-RAG?',
          created_at: new Date().toISOString(),
        },
        {
          id: 'server-canonical-asst-uuid',
          session_id: sessionId,
          role: 'assistant',
          message: 'Veritas-RAG is a verified RAG system.',
          created_at: new Date().toISOString(),
        },
      ],
    })
  }

  return (
    <div>
      <button data-testid="start-stream-btn" onClick={startStream}>Start Stream</button>
      <button data-testid="finish-stream-btn" onClick={finishStream}>Finish Stream</button>
      <div data-testid="messages-container">
        {messages.map(message => (
          <ChatMessageBubble
            key={message.id}
            message={message}
            onFeedback={handleFeedback}
            disabled={isStreaming}
          />
        ))}
      </div>
    </div>
  )
}

describe('CHAT-001: Frontend Optimistic Message ID Reconciliation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('reconciles optimistic client message ID to canonical server ID after stream completion', async () => {
    const onFeedbackCall = vi.fn()

    render(<OptimisticReconciliationHarness onFeedbackCall={onFeedbackCall} />)

    // 1. User sends message -> stream starts with temporary client UUIDs
    act(() => {
      fireEvent.click(screen.getByTestId('start-stream-btn'))
    })

    expect(screen.getByText('Veritas-RAG is a verified RAG system.')).toBeInTheDocument()

    // 2. Stream finishes -> finally block executes and resets hasOptimisticContent.current = false
    act(() => {
      fireEvent.click(screen.getByTestId('finish-stream-btn'))
    })

    // 3. User clicks Like feedback on the assistant message
    const likeButton = await screen.findByRole('button', { name: /^like response$/i })
    act(() => {
      fireEvent.click(likeButton)
    })

    // 4. Verify onFeedbackCall was invoked with CANONICAL SERVER ID, not client temporary ID
    expect(onFeedbackCall).toHaveBeenCalledTimes(1)
    expect(onFeedbackCall).toHaveBeenCalledWith(
      'session-123',
      'server-canonical-asst-uuid', // Canonical server UUID
      'like'
    )
    expect(onFeedbackCall).not.toHaveBeenCalledWith(
      'session-123',
      'client-temp-asst-uuid', // Must NEVER submit client random UUID
      expect.anything()
    )
  })

  it('demonstrates that omitting the finally block reset causes client UUID submission (pre-remediation bug)', async () => {
    const onFeedbackCall = vi.fn()

    // Render with simulateOldBug = true (pre-remediation bug behavior)
    render(<OptimisticReconciliationHarness onFeedbackCall={onFeedbackCall} simulateOldBug={true} />)

    act(() => {
      fireEvent.click(screen.getByTestId('start-stream-btn'))
    })

    act(() => {
      fireEvent.click(screen.getByTestId('finish-stream-btn'))
    })

    const likeButton = await screen.findByRole('button', { name: /^like response$/i })
    act(() => {
      fireEvent.click(likeButton)
    })

    // Pre-remediation bug: submitted client temporary UUID, which failed with 404 on backend
    expect(onFeedbackCall).toHaveBeenCalledWith(
      'session-123',
      'client-temp-asst-uuid',
      'like'
    )
  })
})
