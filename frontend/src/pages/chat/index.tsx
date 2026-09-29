import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { Send, Mic, X, Check, Bot, User as UserIcon, Copy, ChevronRight, ShieldCheck, Sparkles, FileText, Layers } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

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

export function AIChatPage() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const { activeSession, fetchSession, createSession, hasMoreMessages, loadMoreMessages } = useChatStore()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
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

  // F9.3: Pagination and Scroll Lock
  const isScrolledUp = useRef(false)
  const sentinelRef = useRef<HTMLDivElement>(null)
  const observerRef = useRef<IntersectionObserver | null>(null)
  const chatContainerRef = useRef<HTMLDivElement>(null)

  // Guard to prevent store sync from overwriting local optimistic state after stream completes
  const hasOptimisticContent = useRef(false)
  const handledInitialQueryRef = useRef<string | null>(null)

  useEffect(() => {
    // P2: Abort any active stream when switching sessions or opening a new chat
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setIsStreaming(false)
    hasOptimisticContent.current = false

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
    }

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
        abortControllerRef.current = null
      }
    }
  }, [sessionId, fetchSession, navigate])

  useEffect(() => {
    if (activeSession?.messages && !isStreaming && !hasOptimisticContent.current) {
      setMessages(activeSession.messages)
    } else if (!activeSession && !sessionId && !isStreaming && !hasOptimisticContent.current) {
      setMessages([])
    }
  }, [activeSession, sessionId, isStreaming])

  // F9.3 Intelligent Scroll Lock
  useEffect(() => {
    if (!isScrolledUp.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, isStreaming])

  // Controlled Textarea Auto-Resize (min 52px, max 160px)
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      const scrollH = textareaRef.current.scrollHeight
      const targetH = Math.min(Math.max(scrollH, 52), 160)
      textareaRef.current.style.height = `${targetH}px`
    }
  }, [input])

  const focusComposer = useCallback(() => {
    requestAnimationFrame(() => {
      textareaRef.current?.focus()
    })
    setTimeout(() => {
      textareaRef.current?.focus()
    }, 0)
  }, [])

  // Chat #6: New Query Auto-Focus
  useEffect(() => {
    const isFinePointer = typeof window !== 'undefined' && window.matchMedia('(pointer: fine)').matches
    if ((!sessionId && isFinePointer) || location.state?.autoFocus) {
      focusComposer()
    }
  }, [sessionId, location.state?.autoFocus, focusComposer])

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const target = e.currentTarget
    const isAtBottom = target.scrollHeight - target.scrollTop - target.clientHeight < 50
    isScrolledUp.current = !isAtBottom
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

      let fullAssistantText = ''
      const accumulatedCitations: any[] = []
      let finalReliability: number | undefined = undefined
      let buffer = ''

      let isStreamDone = false
      // eslint-disable-next-line no-constant-condition
      while (!isStreamDone) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        while (buffer.includes('\n\n')) {
          const splitIndex = buffer.indexOf('\n\n')
          const block = buffer.slice(0, splitIndex)
          buffer = buffer.slice(splitIndex + 2)

          const lines = block.split('\n')
          let eventType = 'message'
          let eventData = ''

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7)
            } else if (line.startsWith('data: ')) {
              eventData = line.slice(6)
            }
          }

          if (eventType === 'chunk' && eventData) {
            try {
              const data = JSON.parse(eventData)

              if (data.text_delta) {
                fullAssistantText += data.text_delta
              }

              // F9.5 Progressive Citation Accumulation + Deduplication
              if (data.citations_delta && data.citations_delta.length > 0) {
                for (const cite of data.citations_delta) {
                  if (!accumulatedCitations.some(c => c.citation_index === cite.citation_index)) {
                    accumulatedCitations.push(cite)
                  }
                }
              }

              // Only update if there are meaningful changes
              if (data.text_delta !== undefined || data.citations_delta) {
                setMessages(prev => {
                  const newMsgs = [...prev]
                  newMsgs[newMsgs.length - 1] = {
                    ...newMsgs[newMsgs.length - 1],
                    message: fullAssistantText,
                    citations: accumulatedCitations.length > 0 ? [...accumulatedCitations] : undefined
                  }
                  return newMsgs
                })
              }

              if (data.is_final) {
                // F9.4 True Reliability Score Extraction
                if (data.wrapper_metadata?.reliability_score !== undefined) {
                  finalReliability = data.wrapper_metadata.reliability_score
                } else if (data.is_fully_grounded !== undefined) {
                  finalReliability = data.is_fully_grounded ? 1.0 : 0.5
                }
                isStreamDone = true
              }
            } catch (err) {
              console.error('Failed to parse SSE event', err)
            }
          } else if (eventType === 'error' && eventData) {
            try {
              const errData = JSON.parse(eventData)
              setMessages(prev => {
                const newMsgs = [...prev]
                const lastMsg = newMsgs[newMsgs.length - 1]
                newMsgs[newMsgs.length - 1] = {
                  ...lastMsg,
                  message: fullAssistantText,
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
          }
        }
      }

      setMessages(prev => {
        const newMsgs = [...prev]
        newMsgs[newMsgs.length - 1] = {
          ...newMsgs[newMsgs.length - 1],
          message: fullAssistantText,
          citations: accumulatedCitations.length > 0 ? accumulatedCitations : undefined,
          reliability_score: finalReliability
        }
        return newMsgs
      })

      // Refresh sidebar list
      useChatStore.getState().fetchSessions()
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
      setIsStreaming(false)
      abortControllerRef.current = null
    }
  }

  useEffect(() => {
    if (sessionId && location.state?.initialQuery && handledInitialQueryRef.current !== sessionId) {
      handledInitialQueryRef.current = sessionId
      const query = location.state.initialQuery
      navigate(location.pathname, { replace: true, state: {} })
      executeStream(sessionId, query)
      focusComposer()
    }
  }, [sessionId, location.state, focusComposer, navigate, location.pathname])

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

  const handleStartVoice = useCallback(async () => {
    if (isStreaming) return
    originalInputRef.current = input
    await startRecording()
    focusComposer()
  }, [isStreaming, input, startRecording, focusComposer])

  const handleStopVoice = useCallback(() => {
    const finalSpeech = stopRecording()
    const prefix = originalInputRef.current ? `${originalInputRef.current.trim()} ` : ''
    const finalCombined = `${prefix}${finalSpeech}`.trim()
    setInput(finalCombined)
    focusComposer()
  }, [stopRecording, focusComposer])

  const handleCancelVoice = useCallback(() => {
    cancelRecording()
    setInput(originalInputRef.current)
    focusComposer()
  }, [cancelRecording, focusComposer])

  // Global Escape key listener during active recording
  useEffect(() => {
    if (!isListening) return
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        handleCancelVoice()
      }
    }
    window.addEventListener('keydown', handleGlobalKeyDown)
    return () => window.removeEventListener('keydown', handleGlobalKeyDown)
  }, [isListening, handleCancelVoice])

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
    <div className="relative flex flex-1 min-h-0 flex-col bg-surface/90 backdrop-blur-xl shadow-sm rounded-xl border border-border/60 mx-2 my-2 sm:mx-4 sm:my-3 overflow-hidden">
      <h1 className="sr-only">Enterprise AI Chat</h1>

      {/* Chat Messages Area (Full Canvas Scroll) */}
      <div
        ref={chatContainerRef}
        onScroll={handleScroll}
        className="absolute inset-0 overflow-y-auto px-3 pt-4 sm:px-6 md:px-8 sm:pt-6 pb-36 sm:pb-40 space-y-6"
      >
        {messages.length > 0 && hasMoreMessages && (
          <div ref={sentinelRef} className="h-4 w-full flex items-center justify-center">
             <div className="w-4 h-4 rounded-full border-2 border-primary border-t-transparent animate-spin"></div>
          </div>
        )}

        {messages.length === 0 ? (
          <div className="flex min-h-full flex-col items-center justify-center text-center max-w-2xl mx-auto space-y-8 py-8">
            <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center ring-1 ring-primary/20">
              <Bot className="h-8 w-8 text-primary" />
            </div>
            <div className="space-y-2">
              <h3 className="text-xl font-medium text-foreground">How can I help you today?</h3>
              <p className="text-muted-foreground text-sm">Veritas RAG is connected to your enterprise knowledge base. You can ask questions about policies, procedures, and internal documentation.</p>
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
                  className="p-4 rounded-xl border border-border/80 dark:border-white/[0.08] bg-surface/90 dark:bg-slate-900/60 hover:bg-muted/50 dark:hover:bg-slate-800/60 hover:border-primary/40 dark:hover:border-primary/40 hover:shadow-md transition-all duration-200 text-left group flex flex-col justify-between gap-3 pointer-events-auto shadow-sm cursor-pointer"
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
            <ChatMessageBubble key={msg.id || i} message={msg} isStreaming={isStreaming && i === messages.length - 1} />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Floating Liquid Glass Composer Layer */}
      <div className="absolute bottom-0 inset-x-0 p-3 sm:p-4 z-20 pointer-events-none flex flex-col items-center justify-end">
        <div className="w-full max-w-4xl pointer-events-auto relative">
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
                  className="group relative flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-medium text-foreground bg-white/50 dark:bg-slate-950/40 backdrop-blur-2xl backdrop-saturate-200 border border-slate-900/[0.08] dark:border-white/15 shadow-[0_4px_20px_rgba(0,0,0,0.08),inset_0_1px_1px_0_rgba(255,255,255,0.9)] dark:shadow-[0_4px_20px_rgba(0,0,0,0.35),inset_0_1px_1px_0_rgba(255,255,255,0.15)] hover:border-primary/50 hover:bg-white/70 dark:hover:bg-slate-900/60 transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-primary/40 cursor-pointer"
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
            className={cn(
              "group relative flex items-end rounded-2xl border bg-white/40 dark:bg-slate-950/30 backdrop-blur-2xl backdrop-saturate-200 transition-all duration-200 overflow-hidden",
              isListening
                ? "border-emerald-500/50 dark:border-emerald-500/40 ring-2 ring-emerald-500/20 dark:ring-emerald-500/25 shadow-[0_16px_44px_0_rgba(16,185,129,0.12),0_4px_12px_0_rgba(0,0,0,0.04),inset_0_1px_1px_0_rgba(255,255,255,0.95)] dark:shadow-[0_20px_50px_0_rgba(0,0,0,0.65),0_0_20px_0_rgba(16,185,129,0.25),inset_0_1px_1px_0_rgba(255,255,255,0.22)]"
                : "border-slate-900/[0.08] dark:border-white/[0.12] shadow-[0_10px_30px_0_rgba(0,0,0,0.05),0_1px_2px_0_rgba(0,0,0,0.02),inset_0_1px_1px_0_rgba(255,255,255,0.9),inset_0_0_0_1px_rgba(255,255,255,0.6)] dark:shadow-[0_16px_40px_0_rgba(0,0,0,0.5),0_2px_6px_0_rgba(0,0,0,0.3),inset_0_1px_1px_0_rgba(255,255,255,0.15),inset_0_0_0_1px_rgba(255,255,255,0.04)] focus-within:border-primary/50 dark:focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/20 dark:focus-within:ring-primary/25 focus-within:bg-white/60 dark:focus-within:bg-slate-950/45 focus-within:shadow-[0_16px_44px_0_rgba(15,118,110,0.12),0_4px_12px_0_rgba(0,0,0,0.04),inset_0_1px_1px_0_rgba(255,255,255,0.95)] dark:focus-within:shadow-[0_20px_50px_0_rgba(0,0,0,0.65),0_0_20px_0_rgba(15,118,110,0.25),inset_0_1px_1px_0_rgba(255,255,255,0.22)]"
            )}
          >
            {/* Top Specular Glass Reflection Edge */}
            <div
              className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-white/90 dark:via-white/25 to-transparent pointer-events-none"
              aria-hidden="true"
            />

            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isListening ? "Listening... Speak now" : "Message Veritas RAG..."}
              aria-label="Message Veritas RAG"
              className={cn(
                "w-full resize-none bg-transparent py-3.5 pl-4 sm:pl-5 text-sm outline-none placeholder:text-muted-foreground/60 max-h-40 min-h-[52px] leading-relaxed text-foreground",
                isListening ? "pr-28 sm:pr-32" : "pr-20 sm:pr-24"
              )}
              rows={1}
            />

            {/* Elevated Primary Action Dock */}
            <div className="absolute right-2.5 bottom-2.5 flex items-center gap-1.5">
              <TooltipProvider delayDuration={200}>
                {isListening ? (
                  <>
                    <VoiceVisualizer volumes={volumes} isListening={isListening} />

                    {/* Cancel Recording */}
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button
                          type="button"
                          onClick={handleCancelVoice}
                          aria-label="Cancel dictation"
                          title="Cancel dictation"
                          className="flex h-8 w-8 sm:h-9 sm:w-9 items-center justify-center rounded-xl text-muted-foreground/70 hover:text-foreground hover:bg-slate-900/[0.06] dark:hover:bg-white/[0.08] active:scale-95 transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-destructive cursor-pointer"
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
                          className="flex h-8 w-8 sm:h-9 sm:w-9 items-center justify-center rounded-xl bg-emerald-600 dark:bg-emerald-500 text-white shadow-[0_2px_10px_rgba(16,185,129,0.4)] hover:bg-emerald-500 dark:hover:bg-emerald-400 active:scale-95 transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 cursor-pointer"
                        >
                          <Check className="h-4 w-4 stroke-[2.5]" />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent side="top">
                        <p className="text-xs">Done dictating</p>
                      </TooltipContent>
                    </Tooltip>
                  </>
                ) : (
                  <>
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
                            "flex h-8 w-8 sm:h-9 sm:w-9 items-center justify-center rounded-xl transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-primary",
                            isStreaming
                              ? "text-muted-foreground/30 bg-transparent cursor-not-allowed"
                              : "text-muted-foreground/70 hover:text-foreground hover:bg-slate-900/[0.06] dark:hover:bg-white/[0.08] active:scale-95 cursor-pointer"
                          )}
                        >
                          <Mic className="h-4 w-4" />
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
                        "flex h-8 w-8 sm:h-9 sm:w-9 items-center justify-center rounded-xl transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-primary",
                        !input.trim() || isStreaming
                          ? "text-muted-foreground/30 bg-muted/40 dark:bg-white/[0.04] border border-transparent dark:border-white/[0.04] cursor-not-allowed"
                          : "bg-primary text-primary-foreground shadow-[0_2px_10px_rgba(15,118,110,0.4)] hover:shadow-[0_4px_16px_rgba(15,118,110,0.5)] hover:bg-primary-hover active:scale-95 cursor-pointer"
                      )}
                    >
                      <Send className="h-4 w-4" />
                    </motion.button>
                  </>
                )}
              </TooltipProvider>
            </div>
          </form>
          <div className="text-center mt-2 text-[11px] text-muted-foreground/70 font-medium tracking-tight pointer-events-none select-none">
            AI responses may be inaccurate. Verify citations before use.
          </div>
        </div>
      </div>
    </div>
  )
}

function ChatMessageBubble({ message, isStreaming = false }: { message: ChatMessage; isStreaming?: boolean }) {
  const isUser = message.role === 'user'
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(message.message)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

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
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'} mx-auto max-w-4xl`}>
      <div className={`flex gap-3 sm:gap-4 max-w-[88%] sm:max-w-[85%] ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>

        {/* Avatar */}
        <div className="shrink-0 mt-1">
          <div className={`flex h-8 w-8 items-center justify-center rounded-full ${isUser ? 'bg-primary/15 text-primary border border-primary/20 ring-1 ring-primary/20' : 'bg-primary/10 text-primary border border-primary/20 ring-1 ring-primary/20'}`}>
            {isUser ? <UserIcon className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
          </div>
        </div>

        {/* Content */}
        <div className={`flex flex-col gap-2 ${isUser ? 'items-end' : 'items-start'} min-w-0 w-full`}>
          <div className={cn(
            "relative px-4.5 py-3 sm:px-5 sm:py-3.5 rounded-2xl text-sm leading-relaxed transition-all",
            isUser
              ? "bg-primary text-primary-foreground rounded-tr-sm shadow-[0_2px_10px_rgba(15,118,110,0.25)] border border-primary-hover/20"
              : "bg-surface/90 dark:bg-slate-900/70 border border-border/80 dark:border-white/[0.08] rounded-tl-sm shadow-sm dark:shadow-[0_4px_24px_rgba(0,0,0,0.25)] text-foreground"
          )}>
            {isRetrieving ? (
              <div className="flex items-center gap-2.5 py-1 text-muted-foreground text-xs font-medium" role="status" aria-live="polite">
                <div className="flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
                  <span className="h-1.5 w-1.5 rounded-full bg-primary/80 animate-pulse [animation-delay:200ms]" />
                  <span className="h-1.5 w-1.5 rounded-full bg-primary/60 animate-pulse [animation-delay:400ms]" />
                </div>
                <span className="text-xs text-muted-foreground/90 font-medium tracking-tight">Searching knowledge base...</span>
              </div>
            ) : (
              <div className={cn(
                "prose prose-sm max-w-none leading-relaxed",
                isUser
                  ? "text-primary-foreground prose-invert selection:bg-white/20 selection:text-white"
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
                          className={isUser ? "underline underline-offset-2 font-medium" : "text-primary underline underline-offset-2 hover:text-primary-hover font-medium transition-colors"}
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
                              ? "bg-black/20 text-primary-foreground"
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
                    thead: ({ children }) => <thead className="bg-muted/50 font-semibold text-foreground">{children}</thead>,
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

          {/* Metadata & Actions (Assistant only) */}
          {!isUser && !isStreaming && (message.reliability_score !== undefined || message.citations?.length || processedMessage) && (
            <div className="flex items-center gap-2.5 px-1 pt-0.5">
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
                    <TooltipContent side="top" className="max-w-xs text-xs p-2.5 bg-surface/95 dark:bg-slate-900/95 backdrop-blur-md border border-border/80 shadow-lg rounded-xl">
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

              {processedMessage && (
                <button
                  type="button"
                  onClick={handleCopy}
                  aria-label={copied ? "Answer copied" : "Copy answer"}
                  className="text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1.5 text-[11px] font-medium px-2 py-0.5 rounded-md hover:bg-muted/60 cursor-pointer focus:outline-none focus-visible:ring-1 focus-visible:ring-primary"
                >
                  {copied ? (
                    <>
                      <Check className="h-3 w-3 text-emerald-500" />
                      <span className="text-emerald-500">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-3 w-3" />
                      <span>Copy</span>
                    </>
                  )}
                </button>
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
}
