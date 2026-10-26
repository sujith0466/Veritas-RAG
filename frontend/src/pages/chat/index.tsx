import { useState, useEffect, useRef, useCallback, memo } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { Send, Mic, X, Check, User as UserIcon, ChevronRight, ChevronDown, ShieldCheck, Sparkles, FileText, Layers } from 'lucide-react'
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { useChatStore, ChatMessage } from '@/stores/chatStore'
import { useAuthStore } from '@/stores/authStore'
import { useToast } from '@/hooks/useToast'
import { useVoiceInput } from '@/hooks/useVoiceInput'
import { cn } from '@/utils/cn'

import { Badge } from '@/components/common/Badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/common/Tooltip'
import { CitationBadge } from '@/components/chat/CitationBadge'
import { CitationGrid } from '@/components/chat/CitationGrid'
import { CodeBlock } from '@/components/chat/CodeBlock'
import { VoiceVisualizer } from '@/components/chat/VoiceVisualizer'
import { UserMessageActions } from '@/components/chat/UserMessageActions'
import { AssistantMessageActions } from '@/components/chat/AssistantMessageActions'
import { MessageEditInput } from '@/components/chat/MessageEditInput'
import { ShareModal } from '@/components/chat/ShareModal'

export interface ParsedSSEEvent {
  eventType: string
  eventData: string
  id?: string
}

export function parseSSEBlock(block: string): ParsedSSEEvent {
  const lines = block.split('\n')
  let eventType = 'message'
  let eventData = ''
  let id: string | undefined = undefined

  for (const line of lines) {
    if (line.startsWith('event: ')) {
      eventType = line.slice(7)
    } else if (line.startsWith('data: ')) {
      eventData = line.slice(6)
    } else if (line.startsWith('id: ')) {
      id = line.slice(4)
    }
  }

  return { eventType, eventData, id }
}

export interface ProgressUpdateParams {
  isAborted: boolean
  isTerminal?: boolean
  accumulatedText?: string
}

export function applyProgressUpdate(
  messages: ChatMessage[],
  eventData: string,
  params: ProgressUpdateParams
): ChatMessage[] {
  try {
    const data = JSON.parse(eventData)
    if (!data.message) return messages
    if (messages.length === 0) return messages

    const newMsgs = [...messages]
    const lastMsg = newMsgs[newMsgs.length - 1]

    // Explicit terminal state check:
    // 1. Explicit terminal stream flag (stream marked done, reader finished, or inactive)
    const isTerminal = Boolean(params.isTerminal)
    // 2. Explicit error status in metadata
    const isExplicitError = (lastMsg.metadata_json as any)?.status === 'ERROR'
    // 3. Cancellation initiated on abortController
    const isAborted = Boolean(params.isAborted)
    // 4. Answer text has already begun streaming into accumulatedText or message
    const hasAnswerText = Boolean(params.accumulatedText) || Boolean(lastMsg.message && lastMsg.message.trim().length > 0)

    // Only update active assistant placeholder if not in a terminal state and no answer text has arrived
    if (lastMsg.role === 'assistant' && !isTerminal && !isExplicitError && !isAborted && !hasAnswerText) {
      newMsgs[newMsgs.length - 1] = {
        ...lastMsg,
        metadata_json: {
          ...(lastMsg.metadata_json as Record<string, any> || {}),
          progress_stage: data.stage,
          progress_message: data.message,
        },
      }
    }
    return newMsgs
  } catch (err) {
    console.error('Failed to parse progress SSE event', err)
    return messages
  }
}

export function AIChatPage() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const {
    activeSession,
    fetchSession,
    createSession,
    hasMoreMessages,
    loadMoreMessages,
    rewindSession,
    updateMessageFeedback,
  } = useChatStore()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null)
  const [shareMessage, setShareMessage] = useState<ChatMessage | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const originalInputRef = useRef<string>('')
  const { toast } = useToast()

  const handleTranscriptChange = useCallback((interim: string, final: string) => {
    const combinedSpeech = final ? (interim ? `${final} ${interim}` : final) : interim
    const prefix = originalInputRef.current ? `${originalInputRef.current.trim()} ` : ''
    setInput(`${prefix}${combinedSpeech}`.trimStart())
  }, [])

  const handleVoiceError = useCallback((errMsg: string) => {
    toast({
      title: 'Voice Input',
      message: errMsg,
      type: 'warning',
      duration: 4000
    })
  }, [toast])

  const {
    isListening,
    isSupported,
    volumes,
    startRecording,
    stopRecording,
    cancelRecording
  } = useVoiceInput({
    onTranscriptChange: handleTranscriptChange,
    onError: handleVoiceError
  })

  // Chat #10 Scroll Architecture State & Refs
  const shouldReduceMotion = useReducedMotion()
  const isScrolledUpRef = useRef(false)
  const isProgrammaticScrollRef = useRef(false)
  const programmaticScrollTimerRef = useRef<NodeJS.Timeout | null>(null)
  const [showScrollToBottom, setShowScrollToBottom] = useState(false)
  const [isUserScrolledUp, setIsUserScrolledUp] = useState(false)
  const [isComposerFocused, setIsComposerFocused] = useState(false)
  const rafIdRef = useRef<number | null>(null)
  const [composerHeight, setComposerHeight] = useState<number>(115)
  const composerContainerRef = useRef<HTMLDivElement>(null)
  const hasInitiallyAnchoredRef = useRef(false)
  const sentinelRef = useRef<HTMLDivElement>(null)
  const observerRef = useRef<IntersectionObserver | null>(null)
  const chatContainerRef = useRef<HTMLDivElement>(null)

  const isCompact = isUserScrolledUp && !isComposerFocused && !isListening && !input.trim() && messages.length > 0

  // AUD-014: Stream token buffering refs to coalesce high-frequency SSE re-renders into rAF batches
  const streamFrameIdRef = useRef<number | null>(null)
  const accumulatedTextRef = useRef<string>('')
  const accumulatedCitationsRef = useRef<any[]>([])
  const flushScheduledRef = useRef<boolean>(false)

  // Guard to prevent store sync from overwriting local optimistic state after stream completes
  const hasOptimisticContent = useRef(false)
  const handledInitialQueryRef = useRef<string | null>(null)

  // Dynamic Composer Clearance via ResizeObserver
  useEffect(() => {
    if (!composerContainerRef.current) return
    const el = composerContainerRef.current

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const height = entry.contentRect.height
        if (height > 0) {
          const totalClearance = Math.round(height + 24)
          setComposerHeight(totalClearance)
          if (!isScrolledUpRef.current && chatContainerRef.current) {
            chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight
          }
        }
      }
    })

    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const scrollToBottom = useCallback((instant = false) => {
    const container = chatContainerRef.current
    if (!container) return

    const prefersReducedMotion = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const shouldBeInstant = instant || prefersReducedMotion

    isProgrammaticScrollRef.current = true
    isScrolledUpRef.current = false
    setShowScrollToBottom(false)
    setIsUserScrolledUp(false)

    if (programmaticScrollTimerRef.current) {
      clearTimeout(programmaticScrollTimerRef.current)
      programmaticScrollTimerRef.current = null
    }

    if (shouldBeInstant) {
      container.scrollTop = container.scrollHeight
      requestAnimationFrame(() => {
        if (container) container.scrollTop = container.scrollHeight
        isProgrammaticScrollRef.current = false
      })
    } else {
      container.scrollTo({
        top: container.scrollHeight,
        behavior: 'smooth'
      })

      // As composer transitions/expands (220ms), ensure follow-through reaches actual bottom
      const step1 = setTimeout(() => {
        if (container) {
          container.scrollTo({
            top: container.scrollHeight,
            behavior: 'smooth'
          })
        }
      }, 120)

      programmaticScrollTimerRef.current = setTimeout(() => {
        clearTimeout(step1)
        if (container) {
          container.scrollTop = container.scrollHeight
        }
        isProgrammaticScrollRef.current = false
        programmaticScrollTimerRef.current = null
      }, 350)
    }
  }, [])

  // Batched RAF-based Streaming Bottom Anchor Scheduler
  const scheduleScrollToBottom = useCallback(() => {
    if (isScrolledUpRef.current) return
    if (rafIdRef.current !== null) return

    rafIdRef.current = requestAnimationFrame(() => {
      rafIdRef.current = null
      if (!isScrolledUpRef.current && chatContainerRef.current) {
        chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight
      }
    })
  }, [])

  useEffect(() => {
    return () => {
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current)
        rafIdRef.current = null
      }
      if (streamFrameIdRef.current !== null) {
        cancelAnimationFrame(streamFrameIdRef.current)
        streamFrameIdRef.current = null
        flushScheduledRef.current = false
      }
      if (programmaticScrollTimerRef.current) {
        clearTimeout(programmaticScrollTimerRef.current)
        programmaticScrollTimerRef.current = null
      }
    }
  }, [])

  useEffect(() => {
    // P2: Abort any active stream when switching sessions or opening a new chat
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    if (streamFrameIdRef.current !== null) {
      cancelAnimationFrame(streamFrameIdRef.current)
      streamFrameIdRef.current = null
      flushScheduledRef.current = false
    }
    setIsStreaming(false)
    hasOptimisticContent.current = false
    hasInitiallyAnchoredRef.current = false

    if (sessionId) {
      if (useChatStore.getState().activeSession?.id !== sessionId) {
        fetchSession(sessionId).catch(() => {
          setMessages([])
          navigate('/chat', { replace: true })
        })
      }
    } else {
      setMessages([])
      useChatStore.getState().setActiveSession(null)
      if (chatContainerRef.current) {
        chatContainerRef.current.scrollTop = 0
      }
      isScrolledUpRef.current = false
      setShowScrollToBottom(false)
      setIsUserScrolledUp(false)
    }

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
        abortControllerRef.current = null
      }
      if (streamFrameIdRef.current !== null) {
        cancelAnimationFrame(streamFrameIdRef.current)
        streamFrameIdRef.current = null
        flushScheduledRef.current = false
      }
    }
  }, [sessionId, fetchSession, navigate])

  useEffect(() => {
    if (activeSession?.messages && !isStreaming && !hasOptimisticContent.current) {
      setMessages(activeSession.messages)
      if (!hasInitiallyAnchoredRef.current) {
        hasInitiallyAnchoredRef.current = true
        requestAnimationFrame(() => {
          scrollToBottom(true)
        })
      }
    } else if (!activeSession && !sessionId && !isStreaming && !hasOptimisticContent.current) {
      setMessages([])
    }
  }, [activeSession, sessionId, isStreaming, scrollToBottom])

  // Chat #10: Streaming & Dynamic Content Anchor
  useEffect(() => {
    if (!isScrolledUpRef.current) {
      scheduleScrollToBottom()
    }
  }, [messages, isStreaming, scheduleScrollToBottom])

  // Controlled Textarea Auto-Resize (min 38px, max 160px when expanded)
  useEffect(() => {
    if (textareaRef.current) {
      if (isCompact || isListening) {
        textareaRef.current.style.height = ''
        return
      }
      textareaRef.current.style.height = 'auto'
      const scrollH = textareaRef.current.scrollHeight
      const targetH = Math.min(Math.max(scrollH, 38), 160)
      textareaRef.current.style.height = `${targetH}px`
    }
  }, [input, isCompact, isListening])

  const focusComposer = useCallback(() => {
    const focusAndPlaceCursor = () => {
      const el = textareaRef.current
      if (el) {
        el.focus()
        const len = el.value.length
        try {
          el.setSelectionRange(len, len)
        } catch (_) {
          // ignore in unsupported input types
        }
      }
    }
    requestAnimationFrame(() => {
      focusAndPlaceCursor()
      requestAnimationFrame(focusAndPlaceCursor)
    })
    setTimeout(focusAndPlaceCursor, 50)
  }, [])

  // Chat #6: New Query Auto-Focus
  useEffect(() => {
    const isFinePointer = typeof window !== 'undefined' && window.matchMedia('(pointer: fine)').matches
    if ((!sessionId && isFinePointer) || location.state?.autoFocus) {
      focusComposer()
    }
  }, [sessionId, location.state?.autoFocus, focusComposer])

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    if (isProgrammaticScrollRef.current) return

    const target = e.currentTarget
    const distanceFromBottom = target.scrollHeight - target.scrollTop - target.clientHeight
    const isAway = distanceFromBottom > 80

    isScrolledUpRef.current = isAway
    setShowScrollToBottom(isAway)

    // Scroll-aware hysteresis for compact composer (avoids small jitter/streaming noise)
    if (distanceFromBottom > 160) {
      setIsUserScrolledUp(true)
    } else if (distanceFromBottom < 60) {
      setIsUserScrolledUp(false)
    }
  }

  // F9.3 Native Infinite Scroll
  useEffect(() => {
    if (isStreaming) return // Avoid loading history while streaming

    const observer = new IntersectionObserver((entries) => {
      const first = entries[0]
      if (first.isIntersecting && hasMoreMessages && sessionId) {
        const container = chatContainerRef.current
        const previousScrollHeight = container?.scrollHeight || 0

        loadMoreMessages(sessionId).then(() => {
          if (container) {
            requestAnimationFrame(() => {
              container.scrollTop += container.scrollHeight - previousScrollHeight
            })
          }
        })
      }
    }, { threshold: 0.1 })

    if (sentinelRef.current) observer.observe(sentinelRef.current)
    observerRef.current = observer

    return () => {
      if (observerRef.current) observerRef.current.disconnect()
    }
  }, [hasMoreMessages, sessionId, isStreaming, loadMoreMessages])

  const executeStream = async (targetSessionId: string, currentQuery: string) => {
    const tempUserMessage: ChatMessage = {
      id: crypto.randomUUID(),
      session_id: targetSessionId,
      role: 'user',
      message: currentQuery,
      created_at: new Date().toISOString()
    }

    const tempAssistantMessage: ChatMessage = {
      id: crypto.randomUUID(),
      session_id: targetSessionId,
      role: 'assistant',
      message: '',
      created_at: new Date().toISOString()
    }

    hasOptimisticContent.current = true
    setMessages(prev => [...prev, tempUserMessage, tempAssistantMessage])
    setIsStreaming(true)

    abortControllerRef.current = new AbortController()

    try {
      const token = useAuthStore.getState().token

      const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
      const response = await fetch(`${baseUrl}/api/v1/chat/sessions/${targetSessionId}/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ query: currentQuery }),
        signal: abortControllerRef.current.signal
      })

      if (!response.body) throw new Error('No readable stream')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      accumulatedTextRef.current = ''
      accumulatedCitationsRef.current = []
      flushScheduledRef.current = false
      let finalReliability: number | undefined = undefined
      let buffer = ''

      const scheduleFlush = () => {
        if (flushScheduledRef.current) return
        flushScheduledRef.current = true
        streamFrameIdRef.current = requestAnimationFrame(() => {
          flushScheduledRef.current = false
          streamFrameIdRef.current = null
          setMessages(prev => {
            const newMsgs = [...prev]
            if (newMsgs.length === 0) return prev
            newMsgs[newMsgs.length - 1] = {
              ...newMsgs[newMsgs.length - 1],
              message: accumulatedTextRef.current,
              citations: accumulatedCitationsRef.current.length > 0 ? [...accumulatedCitationsRef.current] : undefined
            }
            return newMsgs
          })
          scheduleScrollToBottom()
        })
      }

      const flushImmediately = (reliabilityScore?: number) => {
        if (streamFrameIdRef.current !== null) {
          cancelAnimationFrame(streamFrameIdRef.current)
          streamFrameIdRef.current = null
          flushScheduledRef.current = false
        }
        setMessages(prev => {
          const newMsgs = [...prev]
          if (newMsgs.length === 0) return prev
          newMsgs[newMsgs.length - 1] = {
            ...newMsgs[newMsgs.length - 1],
            message: accumulatedTextRef.current,
            citations: accumulatedCitationsRef.current.length > 0 ? [...accumulatedCitationsRef.current] : undefined,
            reliability_score: reliabilityScore !== undefined ? reliabilityScore : finalReliability
          }
          return newMsgs
        })
        scheduleScrollToBottom()
      }

      let isStreamDone = false
      // eslint-disable-next-line no-constant-condition
      while (!isStreamDone) {
        const { done, value } = await reader.read()
        if (done) {
          isStreamDone = true
          break
        }

        buffer += decoder.decode(value, { stream: true })

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

              // F9.5 Progressive Citation Accumulation + Deduplication
              if (data.citations_delta && data.citations_delta.length > 0) {
                for (const cite of data.citations_delta) {
                  if (!accumulatedCitationsRef.current.some(c => c.citation_index === cite.citation_index)) {
                    accumulatedCitationsRef.current.push(cite)
                  }
                }
              }

              if (data.is_final) {
                // F9.4 True Reliability Score Extraction
                if (data.wrapper_metadata?.reliability_score !== undefined) {
                  finalReliability = data.wrapper_metadata.reliability_score
                } else if (data.is_fully_grounded !== undefined) {
                  finalReliability = data.is_fully_grounded ? 1.0 : 0.5
                }
                flushImmediately(finalReliability)
                isStreamDone = true
              } else if (data.text_delta !== undefined || data.citations_delta) {
                scheduleFlush()
              }
            } catch (err) {
              console.error('Failed to parse SSE event', err)
            }
          } else if (eventType === 'error' && eventData) {
            try {
              if (streamFrameIdRef.current !== null) {
                cancelAnimationFrame(streamFrameIdRef.current)
                streamFrameIdRef.current = null
                flushScheduledRef.current = false
              }
              const errData = JSON.parse(eventData)
              setMessages(prev => {
                const newMsgs = [...prev]
                const lastMsg = newMsgs[newMsgs.length - 1]
                newMsgs[newMsgs.length - 1] = {
                  ...lastMsg,
                  message: accumulatedTextRef.current,
                  metadata_json: {
                    ...(lastMsg.metadata_json as any || {}),
                    status: 'ERROR',
                    error: errData
                  }
                }
                return newMsgs
              })
            } catch (err) {
              console.error('Failed to parse error data', err)
            }
            isStreamDone = true
          } else if (eventType === 'progress' && eventData) {
            setMessages(prev => applyProgressUpdate(prev, eventData, {
              isAborted: Boolean(abortControllerRef.current?.signal.aborted),
              isTerminal: isStreamDone,
              accumulatedText: accumulatedTextRef.current,
            }))
          }
        }
      }

      flushImmediately(finalReliability)
      setMessages(prev => {
        const newMsgs = [...prev]
        if (newMsgs.length > 0) {
          newMsgs[newMsgs.length - 1] = {
            ...newMsgs[newMsgs.length - 1],
            message: accumulatedTextRef.current,
            citations: accumulatedCitationsRef.current.length > 0 ? [...accumulatedCitationsRef.current] : undefined,
            reliability_score: finalReliability
          }
        }
        useChatStore.setState(state => {
          if (!state.activeSession || state.activeSession.id !== targetSessionId) return state
          return {
            activeSession: {
              ...state.activeSession,
              messages: newMsgs
            }
          }
        })
        return newMsgs
      })

      // Refresh sidebar list and sync canonical session messages from backend
      useChatStore.getState().fetchSessions()
      fetchSession(targetSessionId).catch(console.error)
    } catch (error: any) {
      if (error.name === 'AbortError') {
        console.log('Stream aborted by user')
      } else {
        console.error('Streaming error', error)
        setMessages(prev => {
          const newMsgs = [...prev]
          newMsgs[newMsgs.length - 1] = { ...newMsgs[newMsgs.length - 1], message: 'Failed to generate response. Please try again.' }
          return newMsgs
        })
      }
    } finally {
      // CHAT-001: Reset optimistic flag so subsequent fetchSession syncs canonical server message IDs
      hasOptimisticContent.current = false
      if (streamFrameIdRef.current !== null) {
        cancelAnimationFrame(streamFrameIdRef.current)
        streamFrameIdRef.current = null
        flushScheduledRef.current = false
      }
      setIsStreaming(false)
      abortControllerRef.current = null
    }
  }

  useEffect(() => {
    // SSE-003: Guarded execution against duplicate initial query navigation races
    if (sessionId && location.state?.initialQuery && handledInitialQueryRef.current !== sessionId) {
      handledInitialQueryRef.current = sessionId
      const query = location.state.initialQuery
      navigate(location.pathname, { replace: true, state: {} })
      executeStream(sessionId, query)
      focusComposer()
    }
  }, [sessionId, location.state?.initialQuery, focusComposer, navigate, location.pathname])

  const [isIndexing, setIsIndexing] = useState(false)

  useEffect(() => {
    // Check indexing status every 5 seconds if we are indexing, or just once on load
    const checkStatus = async () => {
      try {
        const { documentService } = await import('@/services/documentService')
        const docs = await documentService.listDocuments(1, 100)
        const processing = docs.items.some(d => d.status === 'processing' || d.status === 'pending')
        setIsIndexing(processing)
      } catch (e) {
        console.error(e)
      }
    }
    checkStatus()
    const interval = setInterval(checkStatus, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleSubmit = async (eOrQuery?: React.FormEvent | string) => {
    if (eOrQuery && typeof eOrQuery === 'object' && 'preventDefault' in eOrQuery) {
      eOrQuery.preventDefault()
    }
    const queryOverride = typeof eOrQuery === 'string' ? eOrQuery : undefined
    const currentQuery = (queryOverride !== undefined ? queryOverride : input).trim()

    if (!currentQuery || isStreaming) return

    scrollToBottom(false)

    if (isIndexing) {
      setMessages(prev => [
        ...prev,
        {
          id: crypto.randomUUID(),
          session_id: sessionId || 'temp',
          role: 'user',
          message: currentQuery,
          created_at: new Date().toISOString()
        },
        {
          id: crypto.randomUUID(),
          session_id: sessionId || 'temp',
          role: 'assistant',
          message: "Your enterprise knowledge base is still being prepared. You can begin exploring the workspace now, and AI responses will become available once indexing finishes.",
          created_at: new Date().toISOString()
        }
      ])
      setInput('')
      focusComposer()
      return
    }

    setInput('')
    focusComposer()

    if (!sessionId) {
      const newSession = await createSession()
      navigate(`/chat/${newSession.id}`, { replace: true, state: { initialQuery: currentQuery } })
      focusComposer()
      return
    }

    await executeStream(sessionId, currentQuery)
    focusComposer()
  }

  const handleEditMessage = useCallback(async (messageId: string, newText: string) => {
    if (isStreaming || !sessionId) return
    try {
      hasOptimisticContent.current = true
      await rewindSession(sessionId, messageId)
      setMessages(prev => {
        const idx = prev.findIndex(m => m.id === messageId)
        return idx !== -1 ? prev.slice(0, idx) : prev
      })
      setEditingMessageId(null)
      await executeStream(sessionId, newText)
    } catch (err: any) {
      console.error('Failed to edit and rewind message', err)
      toast({
        title: 'Edit Failed',
        message: err.message || 'Failed to update message',
        type: 'error',
      })
    } finally {
      hasOptimisticContent.current = false
    }
  }, [isStreaming, sessionId, rewindSession, toast])

  const handleFeedbackMessage = useCallback(async (messageId: string, rating: 'like' | 'dislike' | null) => {
    if (!sessionId) return
    setMessages(prev => prev.map(m => {
      if (m.id !== messageId) return m
      const meta = { ...(m.metadata_json as any || {}) }
      if (rating === null) {
        delete meta.feedback
        delete meta.feedback_at
        delete meta.feedback_by
      } else {
        meta.feedback = rating
        meta.feedback_at = new Date().toISOString()
      }
      return { ...m, metadata_json: meta }
    }))

    try {
      await updateMessageFeedback(sessionId, messageId, rating)
    } catch (err) {
      console.error('Failed to update feedback', err)
    }
  }, [sessionId, updateMessageFeedback])

  const handleShareMessage = useCallback((msg: ChatMessage) => {
    setShareMessage(msg)
  }, [])

  const handleStartEdit = useCallback((id: string) => {
    setEditingMessageId(id)
  }, [])

  const handleCancelEdit = useCallback(() => {
    setEditingMessageId(null)
  }, [])

  const handleStartVoice = useCallback(async () => {
    if (isStreaming) return
    originalInputRef.current = input
    await startRecording()
  }, [isStreaming, input, startRecording])

  const handleStopVoice = useCallback(() => {
    const finalSpeech = stopRecording()
    if (finalSpeech) {
      const prefix = originalInputRef.current ? `${originalInputRef.current.trim()} ` : ''
      const finalCombined = `${prefix}${finalSpeech}`.trim()
      setInput(finalCombined)
    }
    focusComposer()
  }, [stopRecording, focusComposer])

  const handleCancelVoice = useCallback(() => {
    cancelRecording()
    setInput(originalInputRef.current)
    focusComposer()
  }, [cancelRecording, focusComposer])

  // Global Enter and Escape key listener during active recording
  useEffect(() => {
    if (!isListening) return
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        handleCancelVoice()
      } else if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleStopVoice()
      }
    }
    window.addEventListener('keydown', handleGlobalKeyDown)
    return () => window.removeEventListener('keydown', handleGlobalKeyDown)
  }, [isListening, handleCancelVoice, handleStopVoice])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Escape' && isListening) {
      e.preventDefault()
      handleCancelVoice()
      return
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      if (isListening) {
        e.preventDefault()
        handleStopVoice()
        return
      }
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="relative flex flex-1 min-h-0 flex-col bg-background overflow-hidden w-full h-full">
      <h1 className="sr-only">Enterprise AI Chat</h1>

      {/* Chat Messages Area (Full Canvas Scroll) */}
      <div
        ref={chatContainerRef}
        onScroll={handleScroll}
        data-testid="chat-messages-container"
        className="absolute inset-0 overflow-y-auto px-4 pt-4 sm:px-6 md:px-8 sm:pt-6 space-y-6"
      >
        {messages.length > 0 && hasMoreMessages && (
          <div ref={sentinelRef} className="h-4 w-full flex items-center justify-center">
             <div className="w-4 h-4 rounded-full border-2 border-primary border-t-transparent animate-spin"></div>
          </div>
        )}

        {messages.length === 0 ? (
          <div className="flex min-h-full flex-col items-center justify-center text-center max-w-2xl mx-auto space-y-8 py-8">
            <div className="h-14 w-14 rounded-2xl bg-primary/10 dark:bg-primary/15 flex items-center justify-center border border-primary/25 shadow-xs">
              <Sparkles className="h-7 w-7 text-primary" />
            </div>
            <div className="space-y-2">
              <h3 className="text-xl font-semibold tracking-tight text-foreground font-sans">Veritas Enterprise Intelligence</h3>
              <p className="text-muted-foreground text-sm max-w-lg leading-relaxed">Enterprise knowledge synthesis with verified grounding. Query internal policies, architecture specifications, and compliance records with source attribution.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full">
              {[
                { category: 'Security & Access', icon: ShieldCheck, question: 'What is the password policy?' },
                { category: 'Incident Response', icon: Sparkles, question: 'How do I report a security incident?' },
                { category: 'HR & Operations', icon: FileText, question: 'Explain the leave policy.' },
                { category: 'Infrastructure', icon: Layers, question: 'What IT resources are available?' }
              ].map(({ category, icon: Icon, question: q }) => (
                <button
                  key={q}
                  onClick={() => handleSubmit(q)}
                  className="p-4 rounded-xl border border-border/80 dark:border-border/60 bg-surface/90 dark:bg-[#1a1b1e] hover:bg-muted/50 dark:hover:bg-surface-elevated hover:border-primary/40 dark:hover:border-primary/40 hover:shadow-md transition-all duration-200 text-left group flex flex-col justify-between gap-3 pointer-events-auto shadow-xs cursor-pointer"
                >
                  <div className="flex items-center justify-between w-full">
                    <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold tracking-tight text-primary uppercase font-mono">
                      <Icon className="h-3 w-3 text-primary shrink-0" />
                      {category}
                    </span>
                    <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/40 group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
                  </div>
                  <div>
                    <span className="text-sm font-medium text-foreground group-hover:text-primary transition-colors line-clamp-2">{q}</span>
                    <span className="text-[11px] text-muted-foreground mt-0.5 block">Click to ask this question</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, i) => (
            <ChatMessageBubble
              key={msg.id || i}
              message={msg}
              isStreaming={isStreaming && i === messages.length - 1}
              isEditing={editingMessageId === msg.id}
              onStartEdit={handleStartEdit}
              onCancelEdit={handleCancelEdit}
              onSaveEdit={handleEditMessage}
              onFeedback={handleFeedbackMessage}
              onShare={handleShareMessage}
              disabled={isStreaming}
            />
          ))
        )}
        <div ref={messagesEndRef} />
        {/* Dynamic Composer Clearance Spacer */}
        <div style={{ height: `${composerHeight}px` }} aria-hidden="true" className="shrink-0 transition-[height] duration-150" />
      </div>

      {/* Floating Liquid Glass Composer Layer */}
      <div className="absolute bottom-0 inset-x-0 p-2.5 sm:p-3 z-20 pointer-events-none flex flex-col items-center justify-end">
        {/* Floating Scroll to Bottom Affordance */}
        <AnimatePresence>
          {showScrollToBottom && (
            <motion.div
              initial={{ opacity: 0, y: 10, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.9 }}
              transition={{ duration: 0.16, ease: [0.16, 1, 0.3, 1] }}
              className="pointer-events-auto mb-2.5"
            >
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  scrollToBottom(false)
                }}
                aria-label="Scroll to bottom"
                title="Scroll to bottom"
                className="group flex h-8 w-8 sm:h-9 sm:w-9 items-center justify-center rounded-full text-foreground bg-white/70 dark:bg-[#18191c]/80 backdrop-blur-xl border border-border/70 dark:border-white/10 shadow-md hover:shadow-lg hover:border-primary/50 hover:bg-white/90 dark:hover:bg-[#202226]/90 active:scale-95 transition-all duration-150 outline-none focus-visible:ring-2 focus-visible:ring-primary/40 cursor-pointer"
              >
                <ChevronDown className="h-4 w-4 text-primary group-hover:translate-y-0.5 motion-reduce:group-hover:translate-y-0 transition-transform" />
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        <motion.div
          ref={composerContainerRef}
          layout={!shouldReduceMotion}
          transition={{ duration: shouldReduceMotion ? 0 : 0.22, ease: [0.16, 1, 0.3, 1] }}
          className={cn(
            "pointer-events-auto relative w-full transition-all duration-200",
            isCompact ? "max-w-md sm:max-w-lg" : "max-w-3xl"
          )}
        >
          <AnimatePresence>
            {isStreaming && (
              <motion.div
                initial={{ opacity: 0, y: 6, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 6, scale: 0.95 }}
                transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
                className="flex justify-center mb-2.5"
              >
                <button
                  type="button"
                  onClick={() => abortControllerRef.current?.abort()}
                  className="group relative flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-medium text-foreground bg-white/70 dark:bg-[#18191c]/75 backdrop-blur-xl border border-border/80 dark:border-white/10 shadow-sm hover:border-primary/50 hover:bg-white/90 dark:hover:bg-[#202226]/90 active:scale-95 transition-all duration-150 outline-none focus-visible:ring-2 focus-visible:ring-primary/40 cursor-pointer"
                  aria-label="Stop generating response"
                >
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                  </span>
                  <span>Stop generating</span>
                </button>
              </motion.div>
            )}
          </AnimatePresence>
          <form
            onSubmit={handleSubmit}
            onClick={() => {
              if (isCompact) {
                setIsComposerFocused(true)
                focusComposer()
              }
            }}
            className={cn(
              "group relative rounded-2xl border transition-all duration-200 overflow-hidden",
              "bg-white/60 dark:bg-[#18191c]/60 backdrop-blur-xl",
              "border-border/70 dark:border-white/10 shadow-lg dark:shadow-[0_8px_32px_rgba(0,0,0,0.36)]",
              "hover:border-border dark:hover:border-white/15",
              isListening
                ? "border-primary/60 dark:border-primary/60 ring-1 ring-primary/25 shadow-md"
                : "focus-within:border-primary/50 dark:focus-within:border-primary/50 focus-within:ring-1 focus-within:ring-primary/25",
              isCompact ? "cursor-pointer" : ""
            )}
          >
            {isListening ? (
              <div className="flex items-center w-full px-3.5 py-2 sm:px-4 sm:py-2.5 gap-3 min-h-[46px]">
                {/* Listening Pulse Indicator & Waveform Visualizer */}
                <div className="flex items-center gap-2.5 shrink-0">
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-primary" />
                  </span>
                  <VoiceVisualizer volumes={volumes} isListening={isListening} />
                </div>

                {/* Real-time speech transcript or placeholder */}
                <div className="flex-1 min-w-0">
                  {input.trim() ? (
                    <p className="text-foreground text-sm font-medium truncate select-none leading-normal">
                      {input}
                    </p>
                  ) : (
                    <p className="text-muted-foreground/75 italic select-none text-xs sm:text-sm animate-pulse">
                      Listening... Speak now
                    </p>
                  )}
                </div>

                {/* Primary Voice Actions: Cancel & Done */}
                <div className="flex items-center gap-1.5 shrink-0">
                  <TooltipProvider delayDuration={200}>
                    {/* Cancel Recording */}
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button
                          type="button"
                          onClick={handleCancelVoice}
                          aria-label="Cancel dictation"
                          title="Cancel dictation"
                          className="flex h-8 w-8 items-center justify-center rounded-xl text-muted-foreground/70 hover:text-foreground hover:bg-muted/80 dark:hover:bg-muted/80 active:scale-95 transition-all duration-150 outline-none focus-visible:ring-2 focus-visible:ring-destructive cursor-pointer"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent side="top">
                        <p className="text-xs">Cancel (Esc)</p>
                      </TooltipContent>
                    </Tooltip>

                    {/* Stop Recording / Finalize */}
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button
                          type="button"
                          onClick={handleStopVoice}
                          aria-label="Stop dictation and insert text"
                          title="Stop dictation and insert text"
                          className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-xs hover:bg-primary-hover active:scale-95 transition-all duration-150 outline-none focus-visible:ring-2 focus-visible:ring-primary cursor-pointer"
                        >
                          <Check className="h-4 w-4 stroke-[2.5]" />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent side="top">
                        <p className="text-xs">Done dictating</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
              </div>
            ) : (
              <div className={cn(
                "flex w-full transition-all duration-150",
                isCompact
                  ? "items-center py-1.5 px-3 gap-2"
                  : "items-end py-1.5 pl-4 sm:pl-5 pr-2 gap-2"
              )}>
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  onFocus={() => setIsComposerFocused(true)}
                  onBlur={() => setIsComposerFocused(false)}
                  placeholder={isCompact ? "Ask a question..." : "Message Veritas RAG..."}
                  aria-label="Message Veritas RAG"
                  className={cn(
                    "flex-1 min-w-0 resize-none bg-transparent placeholder:text-muted-foreground/60 text-foreground transition-all duration-150",
                    "border-none outline-none focus:outline-none focus-visible:outline-none ring-0 focus:ring-0 focus-visible:ring-0 ring-offset-0 focus:ring-offset-0 focus-visible:ring-offset-0",
                    isCompact
                      ? "py-1 pl-1 pr-1 text-xs sm:text-sm h-7 max-h-7 leading-normal overflow-hidden cursor-pointer"
                      : "py-1.5 pr-2 text-sm min-h-[38px] max-h-40 leading-relaxed"
                  )}
                  rows={1}
                />

                {/* Primary Action Dock */}
                <div className={cn(
                  "flex items-center gap-1.5 shrink-0 transition-all duration-150",
                  isCompact ? "self-center" : "self-end mb-1"
                )}>
                  <TooltipProvider delayDuration={200}>
                    {/* Voice Input Trigger */}
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button
                          type="button"
                          disabled={isStreaming}
                          onClick={handleStartVoice}
                          aria-label="Dictate query"
                          title="Dictate query"
                          className={cn(
                            "flex items-center justify-center rounded-xl transition-all duration-150 outline-none focus-visible:ring-2 focus-visible:ring-primary",
                            isCompact ? "h-7 w-7" : "h-8 w-8",
                            isStreaming
                              ? "text-muted-foreground/30 bg-transparent cursor-not-allowed"
                              : "text-muted-foreground hover:text-foreground hover:bg-muted/80 active:scale-95 cursor-pointer"
                          )}
                        >
                          <Mic className={isCompact ? "h-3.5 w-3.5" : "h-4 w-4"} />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent side="top">
                        <p className="text-xs">{isSupported ? 'Voice input' : 'Voice input not supported in this browser'}</p>
                      </TooltipContent>
                    </Tooltip>

                    {/* Send Button */}
                    <motion.button
                      whileHover={!input.trim() || isStreaming ? {} : { scale: 1.05 }}
                      whileTap={!input.trim() || isStreaming ? {} : { scale: 0.95 }}
                      type="submit"
                      disabled={!input.trim() || isStreaming}
                      aria-label="Send message"
                      title="Send message"
                      className={cn(
                        "flex items-center justify-center rounded-xl transition-all duration-150 outline-none focus-visible:ring-2 focus-visible:ring-primary",
                        isCompact ? "h-7 w-7" : "h-8 w-8",
                        !input.trim() || isStreaming
                          ? "text-muted-foreground/30 bg-muted/40 dark:bg-muted/20 border border-transparent cursor-not-allowed"
                          : "bg-primary text-primary-foreground shadow-xs hover:bg-primary-hover active:scale-95 cursor-pointer"
                      )}
                    >
                      <Send className={isCompact ? "h-3.5 w-3.5" : "h-4 w-4"} />
                    </motion.button>
                  </TooltipProvider>
                </div>
              </div>
            )}
          </form>
          {!isCompact && (
            <div className="text-center mt-2 text-[11px] text-muted-foreground/70 font-medium tracking-tight pointer-events-none select-none transition-opacity duration-200">
              AI responses may be inaccurate. Verify citations before use.
            </div>
          )}
        </motion.div>
      </div>

      <ShareModal
        isOpen={!!shareMessage}
        onClose={() => setShareMessage(null)}
        message={shareMessage}
        sessionId={sessionId || null}
      />
    </div>
  )
}

function AssistantIndicator({ isGenerating }: { isGenerating?: boolean }) {
  const shouldReduceMotion = useReducedMotion()

  if (isGenerating) {
    return (
      <div className="relative flex h-4 w-4 items-center justify-center" role="status" aria-label="Generating response">
        {!shouldReduceMotion && (
          <motion.span
            className="absolute inset-0 rounded-full border border-primary/60 border-t-transparent"
            animate={{ rotate: 360 }}
            transition={{ duration: 1.6, repeat: Infinity, ease: 'linear' }}
          />
        )}
        <motion.span
          className="h-1.5 w-1.5 rounded-full bg-primary"
          animate={shouldReduceMotion ? { opacity: [0.6, 1, 0.6] } : { scale: [0.85, 1.25, 0.85], opacity: [0.6, 1, 0.6] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
        />
      </div>
    )
  }

  return <Sparkles className="h-3.5 w-3.5 text-primary/80" aria-hidden="true" />
}

export interface ChatMessageBubbleProps {
  message: ChatMessage
  isStreaming?: boolean
  isEditing?: boolean
  onStartEdit?: (messageId: string) => void
  onCancelEdit?: () => void
  onSaveEdit?: (messageId: string, newText: string) => Promise<void> | void
  onFeedback?: (messageId: string, rating: 'like' | 'dislike' | null) => void
  onShare?: (message: ChatMessage) => void
  disabled?: boolean
  onRender?: (messageId: string) => void
}

export const ChatMessageBubble = memo(function ChatMessageBubble({
  message,
  isStreaming = false,
  isEditing = false,
  onStartEdit,
  onCancelEdit,
  onSaveEdit,
  onFeedback,
  onShare,
  disabled = false,
  onRender,
}: ChatMessageBubbleProps) {
  onRender?.(message.id)
  const isUser = message.role === 'user'

  const handleStartEdit = useCallback(() => {
    onStartEdit?.(message.id)
  }, [onStartEdit, message.id])

  const handleSaveEdit = useCallback((newText: string) => {
    return onSaveEdit?.(message.id, newText)
  }, [onSaveEdit, message.id])

  const handleFeedback = useCallback((rating: 'like' | 'dislike' | null) => {
    onFeedback?.(message.id, rating)
  }, [onFeedback, message.id])

  const handleShare = useCallback(() => {
    onShare?.(message)
  }, [onShare, message])

  // F9.5 Interactive Citation Links Pre-processing
  let processedMessage = message.message || ''

  // Reconstruct error state if present in metadata
  const meta = message.metadata_json as any
  if (meta?.status === 'ERROR' && meta?.error?.message) {
    processedMessage += `\n\n**Error:** ${meta.error.message}`
  }

  if (message.citations && message.citations.length > 0) {
    const validCitationIndices = new Set((message.citations as any[]).map(c => c.citation_index))
    processedMessage = processedMessage.replace(/\[(\d+)\]/g, (match, p1) => {
      const idx = parseInt(p1, 10)
      if (validCitationIndices.has(idx)) {
        return `[${idx}](#cite-${idx})`
      }
      return match // Leave invalid citations as raw text
    })
  }

  const isRetrieving = !isUser && isStreaming && !processedMessage

  return (
    <div className={cn("group flex w-full mx-auto max-w-4xl", isUser ? "justify-end" : "justify-start")}>
      <div className={cn(
        "flex gap-3 sm:gap-4 items-start",
        isUser
          ? "flex-row-reverse max-w-[85%] sm:max-w-[78%] md:max-w-[72%] ml-auto"
          : "flex-row w-full max-w-full"
      )}>

        {/* Avatar */}
        <div className="shrink-0 mt-1">
          <div className={`flex h-8 w-8 items-center justify-center rounded-full ${isUser ? 'bg-primary/15 text-primary border border-primary/20 ring-1 ring-primary/20' : 'bg-primary/10 text-primary border border-primary/20 ring-1 ring-primary/20'}`}>
            {isUser ? <UserIcon className="h-4 w-4" /> : <AssistantIndicator isGenerating={isStreaming} />}
          </div>
        </div>

        {/* Content */}
        <div className={cn("flex flex-col gap-1.5 min-w-0", isUser ? "items-end w-auto" : "items-start w-full")}>
          {isUser && isEditing ? (
            <MessageEditInput
              initialContent={message.message}
              onSave={handleSaveEdit}
              onCancel={onCancelEdit!}
              disabled={disabled || isStreaming}
              className="w-full min-w-[280px] sm:min-w-[400px]"
            />
          ) : (
            <>
              <div className={cn(
                "relative text-sm leading-relaxed transition-all",
                isUser
                  ? "px-4.5 py-3 sm:px-5 sm:py-3.5 rounded-2xl rounded-tr-sm bg-emerald-50/80 border border-emerald-200/80 text-foreground shadow-[0_1px_2px_rgba(16,185,129,0.06)] dark:bg-surface-elevated dark:border-border/80 dark:text-foreground dark:shadow-xs"
                  : "px-1 py-1 sm:px-1.5 sm:py-1.5 bg-transparent border-0 shadow-none text-foreground"
              )}>
                {isRetrieving ? (
                  <div className="inline-flex items-center gap-2.5 py-1.5 px-3 rounded-lg border border-border/60 bg-surface/80 dark:bg-surface-elevated/80 text-muted-foreground text-xs font-medium backdrop-blur-xs" role="status" aria-live="polite">
                    <div className="flex items-center gap-1">
                      <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
                      <span className="h-1.5 w-1.5 rounded-full bg-primary/80 animate-pulse [animation-delay:200ms]" />
                      <span className="h-1.5 w-1.5 rounded-full bg-primary/60 animate-pulse [animation-delay:400ms]" />
                    </div>
                    <span className="text-xs text-muted-foreground/90 font-medium tracking-tight">
                      {(message.metadata_json as any)?.progress_message || "Searching knowledge base..."}
                    </span>
                  </div>
                ) : (
                  <div className={cn(
                    "prose prose-sm max-w-none leading-relaxed",
                    isUser
                      ? "text-foreground dark:text-foreground dark:prose-invert prose-p:my-2 prose-p:first:mt-0 prose-p:last:mb-0"
                      : "dark:prose-invert text-foreground prose-p:my-2 prose-p:first:mt-0 prose-p:last:mb-0 prose-headings:font-semibold prose-headings:text-foreground prose-headings:tracking-tight prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5"
                  )}>
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        a: ({ href, children, ...props }) => {
                          if (href?.startsWith('#cite-')) {
                            const citeIndex = parseInt(href.replace('#cite-', ''), 10)
                            const citation = (message.citations as any[])?.find(c => c.citation_index === citeIndex)
                            if (citation) {
                              return <CitationBadge citation={citation} />
                            }
                            return <span>[{citeIndex}]</span>
                          }
                          return (
                            <a
                              href={href}
                              {...props}
                              target="_blank"
                              rel="noopener noreferrer"
                              className={isUser ? "underline underline-offset-2 font-medium text-emerald-800 dark:text-primary hover:opacity-80 transition-opacity" : "text-primary underline underline-offset-2 hover:text-primary-hover font-medium transition-colors"}
                            >
                              {children}
                            </a>
                          )
                        },
                        code: ({ inline, className, children, ...props }: any) => {
                          const match = /language-(\w+)/.exec(className || '')
                          const codeString = String(children).replace(/\n$/, '')
                          if (!inline && (match || codeString.includes('\n'))) {
                            return <CodeBlock language={match ? match[1] : undefined} value={codeString} />
                          }
                          return (
                            <code
                              className={cn(
                                "rounded font-mono text-[12px] font-medium px-1.5 py-0.5",
                                isUser
                                  ? "bg-emerald-500/10 text-emerald-900 dark:bg-muted/80 dark:text-foreground border border-emerald-500/20 dark:border-border/50"
                                  : "bg-muted/80 text-primary dark:text-teal-300 border border-border/50"
                              )}
                              {...props}
                            >
                              {children}
                            </code>
                          )
                        },
                        table: ({ children }) => (
                          <div className="my-3 overflow-x-auto rounded-lg border border-border/60">
                            <table className="min-w-full divide-y divide-border/60 text-xs">{children}</table>
                          </div>
                        ),
                        thead: ({ children }) => <thead className="bg-muted/50 dark:bg-surface-elevated font-semibold text-foreground">{children}</thead>,
                        th: ({ children }) => <th className="px-3 py-2 text-left font-semibold text-foreground">{children}</th>,
                        td: ({ children }) => <td className="px-3 py-2 border-t border-border/40 text-foreground/90">{children}</td>,
                        blockquote: ({ children }) => (
                          <blockquote className="my-2.5 border-l-2 border-primary/70 pl-3.5 italic text-muted-foreground text-xs">
                            {children}
                          </blockquote>
                        )
                      }}
                    >
                      {processedMessage}
                    </ReactMarkdown>
                    {isStreaming && !isUser && (
                      <span className="inline-block w-1.5 h-3.5 ml-1 bg-primary/80 rounded-sm animate-pulse align-middle" aria-hidden="true" />
                    )}
                  </div>
                )}
              </div>

              {/* User Message Action Bar (Icon-only: Edit, Copy) */}
              {isUser && !isStreaming && onStartEdit && (
                <div className="flex items-center justify-end mt-0.5">
                  <UserMessageActions
                    content={message.message}
                    onEdit={handleStartEdit}
                    disabled={disabled || isStreaming}
                    className="opacity-90 sm:opacity-0 sm:group-hover:opacity-100 sm:focus-within:opacity-100 transition-opacity"
                  />
                </div>
              )}
            </>
          )}

          {/* Metadata & Actions (Assistant only) */}
          {!isUser && !isStreaming && (message.reliability_score !== undefined || message.citations?.length || processedMessage) && (
            <div className="flex flex-wrap items-center justify-start gap-2.5 px-1 pt-0.5 w-full">
              {/* F9.4 Badge & Tooltip Rendering */}
              {message.reliability_score !== undefined && (
                <TooltipProvider delayDuration={200}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="flex items-center cursor-help">
                        <Badge
                          variant="outline"
                          className={cn(
                            "text-[10px] font-medium px-2 py-0.5 rounded-full flex items-center gap-1 transition-colors",
                            message.reliability_score >= 0.8
                              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                              : message.reliability_score >= 0.5
                                ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20"
                                : "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20"
                          )}
                        >
                          <ShieldCheck className="h-3 w-3 shrink-0" />
                          <span>{Math.round(message.reliability_score * 100)}% Reliable</span>
                        </Badge>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="max-w-xs text-xs p-2.5 bg-surface/95 dark:bg-surface-elevated/95 backdrop-blur-md border border-border/80 shadow-lg rounded-xl">
                      <p className="leading-relaxed">
                        {message.reliability_score >= 0.8
                          ? 'The AI is highly confident in this response based on the provided enterprise context.'
                          : message.reliability_score >= 0.5
                            ? 'The AI is partially confident, some claims may not be fully supported by the context.'
                            : 'The AI could not confidently ground this response in the enterprise context.'}
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}

              {/* Assistant Action Bar (Icon-only: Copy, Like, Dislike, Share) */}
              {processedMessage && (
                <AssistantMessageActions
                  content={processedMessage}
                  feedback={(message.metadata_json as any)?.feedback || null}
                  onFeedback={handleFeedback}
                  onShare={handleShare}
                  disabled={disabled || isStreaming}
                  className="opacity-90 sm:opacity-0 sm:group-hover:opacity-100 sm:focus-within:opacity-100 transition-opacity"
                />
              )}
            </div>
          )}

          {/* Citations block */}
          {!isUser && message.citations && message.citations.length > 0 && (
            <CitationGrid citations={message.citations as any[]} />
          )}
        </div>
      </div>
    </div>
  )
})
