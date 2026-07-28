import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Send, Bot, User as UserIcon, Copy, Check, Info } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { useChatStore, ChatMessage } from '@/stores/chatStore'
import { supabaseClient } from '@/services/auth/supabaseClient'

import { Badge } from '@/components/common/Badge'

export function AIChatPage() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const { activeSession, fetchSession, createSession } = useChatStore()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
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
    if (activeSession?.messages && !isStreaming) {
      setMessages(activeSession.messages)
    }
  }, [activeSession, isStreaming])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isStreaming])

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
    
    let targetSessionId = sessionId
    if (!targetSessionId) {
      const newSession = await createSession()
      targetSessionId = newSession.id
      navigate(`/chat/${newSession.id}`, { replace: true })
    }

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

    setMessages(prev => [...prev, tempUserMessage, tempAssistantMessage])
    setIsStreaming(true)

    try {
      const { data: sessionData } = await supabaseClient.auth.getSession()
      const token = sessionData.session?.access_token

      const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
      const response = await fetch(`${baseUrl}/api/v1/chat/sessions/${targetSessionId}/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ query: currentQuery })
      })

      if (!response.body) throw new Error('No readable stream')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let fullAssistantText = ''
      let finalCitations = undefined
      let finalReliability = undefined

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunkStr = decoder.decode(value, { stream: true })
        const events = chunkStr.split('\n\n').filter(Boolean)
        
        for (const event of events) {
          if (event.startsWith('data: ')) {
            try {
              const data = JSON.parse(event.slice(6))
              if (data.text_delta) {
                fullAssistantText += data.text_delta
                setMessages(prev => {
                  const newMsgs = [...prev]
                  newMsgs[newMsgs.length - 1] = { ...newMsgs[newMsgs.length - 1], message: fullAssistantText }
                  return newMsgs
                })
              }
              if (data.is_final) {
                finalCitations = data.citations_delta
                finalReliability = data.is_fully_grounded ? 1.0 : 0.5
              }
            } catch (err) {
              console.error('Failed to parse SSE event', err)
            }
          }
        }
      }

      setMessages(prev => {
        const newMsgs = [...prev]
        newMsgs[newMsgs.length - 1] = {
          ...newMsgs[newMsgs.length - 1],
          message: fullAssistantText,
          citations: finalCitations,
          reliability_score: finalReliability
        }
        return newMsgs
      })

      // Refresh sidebar list
      useChatStore.getState().fetchSessions()
    } catch (error) {
      console.error('Streaming error', error)
      setMessages(prev => {
        const newMsgs = [...prev]
        newMsgs[newMsgs.length - 1] = { ...newMsgs[newMsgs.length - 1], message: 'Failed to generate response. Please try again.' }
        return newMsgs
      })
    } finally {
      setIsStreaming(false)
    }
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
      <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8 space-y-6">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center max-w-2xl mx-auto space-y-8">
            <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center ring-1 ring-primary/20">
              <Bot className="h-8 w-8 text-primary" />
            </div>
            <div className="space-y-2">
              <h3 className="text-xl font-medium text-foreground">How can I help you today?</h3>
              <p className="text-muted-foreground text-sm">RAGuard AI is connected to your enterprise knowledge base. You can ask questions about policies, procedures, and internal documentation.</p>
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
          <form onSubmit={handleSubmit} className="relative flex items-end overflow-hidden rounded-xl border border-border bg-background focus-within:ring-1 focus-within:ring-primary/50 transition-shadow">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message RAGuard AI..."
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
        <div className={`flex flex-col gap-2 ${isUser ? 'items-end' : 'items-start'} min-w-0`}>
          <div className={`relative px-5 py-3.5 rounded-2xl ${isUser ? 'bg-primary text-primary-foreground rounded-tr-none' : 'bg-muted/50 border border-border/50 rounded-tl-none'}`}>
            <div className={`prose prose-sm max-w-none ${isUser ? 'text-primary-foreground prose-invert' : 'dark:prose-invert text-foreground'}`}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.message || '...'}
              </ReactMarkdown>
            </div>
          </div>
          
          {/* Metadata & Actions (Assistant only) */}
          {!isUser && (message.reliability_score !== undefined || message.citations?.length) && (
            <div className="flex items-center gap-3 px-1">
              {message.reliability_score !== undefined && (
                <div className="flex items-center gap-1.5">
                  <Badge variant={message.reliability_score >= 0.8 ? 'success' : message.reliability_score >= 0.5 ? 'warning' : 'destructive'} className="text-[10px] px-1.5 py-0">
                    <Info className="h-3 w-3 mr-1" />
                    {message.reliability_score >= 0.8 ? 'Grounded' : 'Partial/Ungrounded'}
                  </Badge>
                </div>
              )}
              
              <button onClick={handleCopy} className="text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1 text-[11px] font-medium">
                {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
          )}
          
          {/* Citations block */}
          {!isUser && message.citations && message.citations.length > 0 && (
            <div className="mt-2 w-full space-y-2">
              <div className="text-xs font-semibold text-muted-foreground px-1">Sources Cited:</div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {(message.citations as { citation_index: number, document_id: string, excerpt: string }[]).map((cite, idx) => (
                  <div key={idx} className="bg-surface border border-border/60 rounded-lg p-2.5 shadow-sm text-xs space-y-1 hover:border-primary/40 transition-colors">
                    <div className="flex items-center gap-1.5 font-medium text-foreground">
                      <span className="bg-primary/10 text-primary px-1 rounded inline-flex items-center justify-center h-4 text-[10px]">[{cite.citation_index}]</span>
                      <span className="truncate">{cite.document_id}</span>
                    </div>
                    <p className="text-muted-foreground line-clamp-2 leading-relaxed" title={cite.excerpt}>
                      "{cite.excerpt}"
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
