import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { Send, Bot, User as UserIcon, Copy, Check, Info } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { useChatStore, ChatMessage } from '@/stores/chatStore'
import { useAuthStore } from '@/stores/authStore'

import { Badge } from '@/components/common/Badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/common/Tooltip'
import { CitationBadge } from '@/components/chat/CitationBadge'
import { CitationGrid } from '@/components/chat/CitationGrid'

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
  
  // F9.3: Pagination and Scroll Lock
  const isScrolledUp = useRef(false)
  const sentinelRef = useRef<HTMLDivElement>(null)
  const observerRef = useRef<IntersectionObserver | null>(null)
  const chatContainerRef = useRef<HTMLDivElement>(null)
  
  // Guard to prevent store sync from overwriting local optimistic state after stream completes
  const hasOptimisticContent = useRef(false)

  useEffect(() => {
    hasOptimisticContent.current = false
    if (sessionId) {
      if (useChatStore.getState().activeSession?.id !== sessionId) {
        fetchSession(sessionId)
      }
    } else {
      setMessages([])
      useChatStore.getState().setActiveSession(null)
    }
  }, [sessionId, fetchSession])

  useEffect(() => {
    if (activeSession?.messages && !isStreaming && !hasOptimisticContent.current) {
      setMessages(activeSession.messages)
    }
  }, [activeSession, isStreaming])

  // F9.3 Intelligent Scroll Lock
  useEffect(() => {
    if (!isScrolledUp.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, isStreaming])

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

      // eslint-disable-next-line no-constant-condition
      while (true) {
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
              }
            } catch (err) {
              console.error('Failed to parse SSE event', err)
            }
          } else if (eventType === 'error' && eventData) {
            try {
              const errData = JSON.parse(eventData)
              fullAssistantText += `\n\n**Error:** ${errData.message || 'An error occurred.'}`
              setMessages(prev => {
                const newMsgs = [...prev]
                newMsgs[newMsgs.length - 1] = { ...newMsgs[newMsgs.length - 1], message: fullAssistantText }
                return newMsgs
              })
            } catch (err) {
              console.error('Failed to parse error data', err)
            }
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
    if (sessionId && location.state?.initialQuery) {
      const query = location.state.initialQuery
      // Clear the state so we don't re-trigger on refresh
      navigate(location.pathname, { replace: true, state: {} })
      executeStream(sessionId, query)
    }
  }, [sessionId, location.state, navigate])

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

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault()
    if (!input.trim() || isStreaming) return

    if (isIndexing) {
      setMessages(prev => [
        ...prev,
        {
          id: crypto.randomUUID(),
          session_id: sessionId || 'temp',
          role: 'user',
          message: input.trim(),
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
      return
    }

    const currentQuery = input.trim()
    setInput('')

    if (!sessionId) {
      const newSession = await createSession()
      navigate(`/chat/${newSession.id}`, { replace: true, state: { initialQuery: currentQuery } })
      return
    }

    await executeStream(sessionId, currentQuery)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="flex h-[calc(100vh-2rem)] flex-col bg-surface shadow-sm rounded-xl border border-border/50 mx-4 mt-4 overflow-hidden">
      {/* Chat Header */}
      <div className="flex items-center justify-between border-b border-border/50 px-6 py-4 bg-surface/80 backdrop-blur-sm z-10">
        <div>
          <h2 className="text-lg font-semibold text-foreground tracking-tight">AI Chat</h2>
          <p className="text-sm text-muted-foreground">Ask questions based on enterprise knowledge</p>
        </div>
      </div>

      {/* Chat Messages Area */}
      <div 
        ref={chatContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4 py-6 md:px-8 space-y-6"
      >
        {messages.length > 0 && hasMoreMessages && (
          <div ref={sentinelRef} className="h-4 w-full flex items-center justify-center">
             <div className="w-4 h-4 rounded-full border-2 border-primary border-t-transparent animate-spin"></div>
          </div>
        )}
        
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center max-w-2xl mx-auto space-y-8">
            <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center ring-1 ring-primary/20">
              <Bot className="h-8 w-8 text-primary" />
            </div>
            <div className="space-y-2">
              <h3 className="text-xl font-medium text-foreground">How can I help you today?</h3>
              <p className="text-muted-foreground text-sm">Veritas RAG is connected to your enterprise knowledge base. You can ask questions about policies, procedures, and internal documentation.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full">
              {[
                'What is the password policy?',
                'How do I report a security incident?',
                'Explain the leave policy.',
                'What IT resources are available?'
              ].map(q => (
                <button
                  key={q}
                  onClick={() => { setInput(q); setTimeout(() => handleSubmit(), 50) }}
                  className="p-4 rounded-xl border border-border bg-surface hover:bg-muted/50 hover:border-primary/30 transition-all text-left group flex flex-col gap-2"
                >
                  <span className="text-sm font-medium text-foreground group-hover:text-primary transition-colors">{q}</span>
                  <span className="text-xs text-muted-foreground">Click to ask this question</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, i) => (
            <ChatMessageBubble key={msg.id || i} message={msg} />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-surface border-t border-border/50">
        <div className="mx-auto max-w-4xl">
          {isStreaming && (
            <div className="flex justify-center mb-3">
              <button type="button" onClick={() => abortControllerRef.current?.abort()} className="flex items-center gap-2 px-3 py-1.5 bg-background hover:bg-muted text-muted-foreground hover:text-foreground rounded-full text-xs font-medium transition-colors border border-border/60 shadow-sm">
                <span className="w-2 h-2 rounded-sm bg-muted-foreground/70"></span> Stop generating
              </button>
            </div>
          )}
          <form onSubmit={handleSubmit} className="relative flex items-end overflow-hidden rounded-xl border border-border bg-background focus-within:ring-1 focus-within:ring-primary/50 transition-shadow">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message Veritas RAG..."
              className="w-full resize-none bg-transparent py-4 pl-4 pr-12 text-sm outline-none placeholder:text-muted-foreground/60 max-h-40 min-h-[56px]"
              rows={1}
            />
            <button
              type="submit"
              disabled={!input.trim() || isStreaming}
              className="absolute right-2 bottom-2 rounded-lg p-2 text-primary hover:bg-primary/10 disabled:text-muted-foreground disabled:hover:bg-transparent transition-colors"
            >
              <Send className="h-5 w-5" />
            </button>
          </form>
          <div className="text-center mt-2 text-[10px] text-muted-foreground font-medium">
            AI responses may be inaccurate. Verify citations before use.
          </div>
        </div>
      </div>
    </div>
  )
}

function ChatMessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(message.message)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // F9.5 Interactive Citation Links Pre-processing
  let processedMessage = message.message || ''
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

  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'} mx-auto max-w-4xl`}>
      <div className={`flex gap-4 max-w-[85%] ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>

        {/* Avatar */}
        <div className="shrink-0 mt-1">
          <div className={`flex h-8 w-8 items-center justify-center rounded-full ${isUser ? 'bg-indigo-500/10 text-indigo-500 ring-1 ring-indigo-500/20' : 'bg-primary/10 text-primary ring-1 ring-primary/20'}`}>
            {isUser ? <UserIcon className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
          </div>
        </div>

        {/* Content */}
        <div className={`flex flex-col gap-2 ${isUser ? 'items-end' : 'items-start'} min-w-0 w-full`}>
          <div className={`relative px-5 py-3.5 rounded-2xl ${isUser ? 'bg-primary text-primary-foreground rounded-tr-none' : 'bg-muted/50 border border-border/50 rounded-tl-none'}`}>
            <div className={`prose prose-sm max-w-none ${isUser ? 'text-primary-foreground prose-invert' : 'dark:prose-invert text-foreground'}`}>
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
                    return <a href={href} {...props} target="_blank" rel="noopener noreferrer">{children}</a>
                  }
                }}
              >
                {processedMessage}
              </ReactMarkdown>
            </div>
          </div>

          {/* Metadata & Actions (Assistant only) */}
          {!isUser && (message.reliability_score !== undefined || message.citations?.length) && (
            <div className="flex items-center gap-3 px-1">
              {/* F9.4 Badge & Tooltip Rendering */}
              {message.reliability_score !== undefined && (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="flex items-center gap-1.5 cursor-help">
                        <Badge variant={message.reliability_score >= 0.8 ? 'success' : message.reliability_score >= 0.5 ? 'warning' : 'destructive'} className="text-[10px] px-1.5 py-0">
                          <Info className="h-3 w-3 mr-1" />
                          {Math.round(message.reliability_score * 100)}% Reliable
                        </Badge>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent side="top">
                      <p className="max-w-xs text-xs">
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

              <button onClick={handleCopy} className="text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1 text-[11px] font-medium">
                {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                {copied ? 'Copied' : 'Copy'}
              </button>
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
