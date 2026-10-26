import { useState } from 'react'
import { Check, Copy, Code2 } from 'lucide-react'

interface CodeBlockProps {
  language?: string
  value: string
}

export function CodeBlock({ language, value }: CodeBlockProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy code', err)
    }
  }

  const displayLanguage = language || 'code'

  return (
    <div className="my-3 overflow-hidden rounded-xl border border-border/80 dark:border-border/60 bg-[#16171a] dark:bg-[#151619] text-[#f4f3ef] shadow-sm">
      {/* Code Header Bar */}
      <div className="flex items-center justify-between border-b border-border/60 bg-[#1c1d22] dark:bg-[#1a1b1f] px-4 py-2 text-xs text-muted-foreground">
        <div className="flex items-center gap-1.5 font-mono text-[11px] font-medium tracking-wide text-foreground/85">
          <Code2 className="h-3.5 w-3.5 text-primary" />
          <span>{displayLanguage}</span>
        </div>
        <button
          type="button"
          onClick={handleCopy}
          aria-label={copied ? 'Code copied to clipboard' : 'Copy code to clipboard'}
          className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-medium text-muted-foreground hover:bg-muted/60 hover:text-foreground transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-primary cursor-pointer"
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 text-emerald-400" />
              <span className="text-emerald-400 font-medium">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" />
              <span>Copy code</span>
            </>
          )}
        </button>
      </div>

      {/* Code Content Container */}
      <div className="overflow-x-auto p-4 font-mono text-xs leading-relaxed text-[#f4f3ef] selection:bg-primary/30 selection:text-white">
        <pre className="m-0 p-0 font-mono">
          <code>{value}</code>
        </pre>
      </div>
    </div>
  )
}
