import { useState, useEffect, useMemo } from 'react'
import {
  Brain,
  Sliders,
  MessageSquare,
  Loader2,
  Sparkles,
  Zap,
  Info,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react'
import { Card, Label, Button, SectionHeader } from '@/components/common'
import { useToast } from '@/hooks/useToast'
import { userService } from '@/services/userService'
import { useAuthStore } from '@/stores/authStore'
import { cn } from '@/utils/cn'

interface AIModelOption {
  id: string
  name: string
  provider: 'Gemini' | 'OpenRouter'
  description: string
  badge: string
  recommended?: boolean
}

const AVAILABLE_MODELS: AIModelOption[] = [
  {
    id: 'gemini-2.0-flash',
    name: 'Gemini 2.0 Flash',
    provider: 'Gemini',
    description: 'High-speed reasoning model optimized for sub-second grounded RAG and low latency.',
    badge: 'Recommended',
    recommended: true,
  },
  {
    id: 'gemini-2.0-flash-lite',
    name: 'Gemini 2.0 Flash Lite',
    provider: 'Gemini',
    description: 'Ultra-lightweight model designed for rapid citation extraction and basic queries.',
    badge: 'Ultra Fast',
  },
  {
    id: 'meta-llama/llama-3.3-70b-instruct',
    name: 'Llama 3.3 70B Instruct',
    provider: 'OpenRouter',
    description: 'State-of-the-art open-weights model with exceptional instruction following.',
    badge: 'Open Weights',
  },
  {
    id: 'openai/gpt-4o-mini',
    name: 'GPT-4o Mini',
    provider: 'OpenRouter',
    description: 'Balanced performance and speed for enterprise factual synthesis.',
    badge: 'Cost Efficient',
  },
]

const DEFAULT_PREFERENCES = {
  default_model: 'gemini-2.0-flash',
  temperature: 0.2,
  system_prompt: '',
}

export function AIPrefSettings() {
  const { toast } = useToast()
  const user = useAuthStore((s) => s.user)
  const setAuth = useAuthStore((s) => s.setAuth)
  const token = useAuthStore((s) => s.token)

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  // Baseline loaded from backend
  const [initialData, setInitialData] = useState(DEFAULT_PREFERENCES)
  // Current working form data
  const [formData, setFormData] = useState(DEFAULT_PREFERENCES)

  useEffect(() => {
    loadPreferences()
  }, [])

  const loadPreferences = async () => {
    try {
      const { data } = await userService.getProfile()
      const prefs = data.preferences?.ai || {}
      const loaded = {
        default_model: prefs.default_model || DEFAULT_PREFERENCES.default_model,
        temperature: prefs.temperature ?? DEFAULT_PREFERENCES.temperature,
        system_prompt: prefs.system_prompt || '',
      }
      setInitialData(loaded)
      setFormData(loaded)
    } catch {
      toast({ title: 'Error', message: 'Failed to load AI preferences', type: 'error' })
    } finally {
      setLoading(false)
    }
  }

  // Detect dirty state
  const isDirty = useMemo(() => {
    return (
      formData.default_model !== initialData.default_model ||
      Math.abs(formData.temperature - initialData.temperature) > 0.001 ||
      formData.system_prompt !== initialData.system_prompt
    )
  }, [formData, initialData])

  const handleModelSelect = (modelId: string) => {
    setFormData((prev) => ({ ...prev, default_model: modelId }))
  }

  const handleTemperatureChange = (val: number) => {
    const clamped = Math.max(0.0, Math.min(1.0, parseFloat(val.toFixed(2))))
    setFormData((prev) => ({ ...prev, temperature: clamped }))
  }

  const handlePromptChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setFormData((prev) => ({ ...prev, system_prompt: e.target.value.slice(0, 10000) }))
  }

  const handleReset = () => {
    setFormData(initialData)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const { data } = await userService.updatePreferences({
        preferences: {
          ...user?.preferences,
          ai: formData,
        },
      })

      if (user && token) {
        setAuth({ ...user, ...data }, token)
      }

      setInitialData(formData)
      toast({ title: 'Success', message: 'AI preferences updated and applied to pipeline', type: 'success' })
    } catch {
      toast({ title: 'Error', message: 'Failed to update AI preferences', type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="animate-spin text-primary h-8 w-8" />
      </div>
    )
  }

  const getTemperatureBadge = (temp: number) => {
    if (temp <= 0.15) return { label: 'Strictly Factual & Deterministic', color: 'text-emerald-500 bg-emerald-500/10' }
    if (temp <= 0.4) return { label: 'Balanced RAG & Synthesis', color: 'text-primary bg-primary/10' }
    if (temp <= 0.7) return { label: 'Moderate Exploratory', color: 'text-amber-500 bg-amber-500/10' }
    return { label: 'High Creativity (Increased Hallucination Risk)', color: 'text-red-500 bg-red-500/10' }
  }

  const tempBadge = getTemperatureBadge(formData.temperature)

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500 pb-20">
      <SectionHeader
        title="AI Preferences"
        description="Configure runtime model routing, hallucination guardrails, and persistent system prompt overrides."
      />

      {/* Model Selection Catalogue */}
      <Card className="p-6 space-y-6">
        <div className="flex items-center gap-3 border-b border-border/80 pb-4">
          <div className="p-2 bg-primary/10 rounded-xl text-primary">
            <Brain className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-semibold text-foreground text-sm">Default Language Model</h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Select the active LLM router for conversational answers, grounded citations, and chat queries.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {AVAILABLE_MODELS.map((model) => {
            const isSelected = formData.default_model === model.id
            return (
              <div
                key={model.id}
                role="button"
                tabIndex={0}
                onClick={() => handleModelSelect(model.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    handleModelSelect(model.id)
                  }
                }}
                className={cn(
                  'relative flex flex-col justify-between p-4 rounded-xl border-2 cursor-pointer transition-all duration-200 text-left outline-none focus-visible:ring-2 focus-visible:ring-primary',
                  isSelected
                    ? 'border-primary bg-primary/[0.04] shadow-sm'
                    : 'border-border/80 hover:border-border hover:bg-muted/40'
                )}
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span className="font-semibold text-sm text-foreground">{model.name}</span>
                    <span
                      className={cn(
                        'text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider',
                        model.recommended
                          ? 'bg-primary/20 text-primary'
                          : 'bg-muted text-muted-foreground'
                      )}
                    >
                      {model.badge}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">{model.description}</p>
                </div>
                <div className="flex items-center justify-between mt-4 pt-2 border-t border-border/40 text-[11px] text-muted-foreground">
                  <span className="font-medium">Provider: {model.provider}</span>
                  {isSelected && (
                    <span className="flex items-center gap-1 text-primary font-semibold text-xs">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Active
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </Card>

      {/* Temperature & Creativity Slider */}
      <Card className="p-6 space-y-6">
        <div className="flex items-center justify-between border-b border-border/80 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/10 rounded-xl text-amber-500">
              <Sliders className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground text-sm">Temperature & Creativity</h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Controls randomness. Lower values adhere strictly to grounded knowledge facts.
              </p>
            </div>
          </div>
          <span className={cn('text-xs font-semibold px-2.5 py-1 rounded-full', tempBadge.color)}>
            {tempBadge.label}
          </span>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="temperature" className="text-xs text-muted-foreground">
              Current Temperature
            </Label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="0.0"
                max="1.0"
                step="0.05"
                value={formData.temperature}
                onChange={(e) => handleTemperatureChange(parseFloat(e.target.value) || 0)}
                className="w-18 px-2 py-1 text-center font-mono text-sm font-semibold rounded-lg border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
          </div>

          <input
            id="temperature"
            name="temperature"
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={formData.temperature}
            onChange={(e) => handleTemperatureChange(parseFloat(e.target.value))}
            className="w-full accent-primary h-2 bg-muted rounded-lg appearance-none cursor-pointer"
          />

          <div className="flex justify-between text-[11px] text-muted-foreground font-medium">
            <div className="text-left">
              <span className="block font-semibold text-foreground">0.0 — Factual RAG</span>
              <span>Near-zero hallucination, verbatim facts</span>
            </div>
            <div className="text-right">
              <span className="block font-semibold text-foreground">1.0 — Exploratory</span>
              <span>High conversational freedom</span>
            </div>
          </div>
        </div>
      </Card>

      {/* Global System Prompt */}
      <Card className="p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-border/80 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/10 rounded-xl text-blue-500">
              <MessageSquare className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground text-sm">Workspace System Prompt</h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Custom instructions prepended to the evidence block during grounding and generation.
              </p>
            </div>
          </div>
          <span className="text-xs text-muted-foreground font-mono">
            {formData.system_prompt.length} / 10,000 chars
          </span>
        </div>

        <div className="space-y-2">
          <textarea
            id="system_prompt"
            name="system_prompt"
            rows={5}
            value={formData.system_prompt}
            onChange={handlePromptChange}
            placeholder="e.g. Always respond concisely in enterprise business terminology. If retrieved evidence does not explicitly address the question, clearly state that rather than assuming..."
            className="w-full min-h-[140px] rounded-xl border border-border/80 bg-background px-3.5 py-3 text-xs leading-relaxed placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent resize-y"
          />
          <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <Info className="w-3.5 h-3.5 text-muted-foreground/70" />
            <span>Instructions are combined with strict anti-jailbreak filters and evidence delimiters.</span>
          </div>
        </div>
      </Card>

      {/* Floating Sticky Save Bar (appears when changes are unsaved) */}
      {isDirty && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 w-11/12 max-w-2xl bg-background/95 backdrop-blur-md border border-primary/30 shadow-2xl rounded-2xl p-3.5 flex items-center justify-between gap-4 animate-in slide-in-from-bottom-5">
          <div className="flex items-center gap-2 pl-2">
            <Sparkles className="w-4 h-4 text-primary animate-pulse" />
            <span className="text-xs font-semibold text-foreground">
              You have unsaved changes in AI Preferences
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleReset}
              disabled={saving}
              className="h-8 px-3 text-xs text-muted-foreground hover:text-foreground"
            >
              <RotateCcw className="w-3.5 h-3.5 mr-1" />
              Reset
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              isLoading={saving}
              className="h-8 px-4 text-xs font-semibold shadow-sm"
            >
              Save Changes
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
