import { useState, useEffect } from 'react'
import { Card, Label, Button, SectionHeader } from '@/components/common'
import { useToast } from '@/hooks/useToast'
import { userService } from '@/services/userService'
import { useAuthStore } from '@/stores/authStore'
import { Brain, Sliders, MessageSquare, Loader2 } from 'lucide-react'

export function AIPrefSettings() {
  const { toast } = useToast()
  const user = useAuthStore(s => s.user)
  const setAuth = useAuthStore(s => s.setAuth)
  const token = useAuthStore(s => s.token)
  
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [formData, setFormData] = useState({
    default_model: 'gpt-4o',
    temperature: 0.2,
    system_prompt: '',
  })

  useEffect(() => {
    loadPreferences()
  }, [])

  const loadPreferences = async () => {
    try {
      const { data } = await userService.getProfile()
      const prefs = data.preferences?.ai || {}
      setFormData({
        default_model: prefs.default_model || 'gpt-4o',
        temperature: prefs.temperature ?? 0.2,
        system_prompt: prefs.system_prompt || '',
      })
    } catch (error) {
      toast({ title: 'Error', message: 'Failed to load AI preferences', type: 'error' })
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const value = e.target.type === 'number' ? parseFloat(e.target.value) : e.target.value
    setFormData(prev => ({ ...prev, [e.target.name]: value }))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const { data } = await userService.updatePreferences({
        preferences: {
          ...user?.preferences,
          ai: formData
        }
      })
      
      if (user && token) {
        setAuth({ ...user, ...data }, token)
      }
      
      toast({ title: 'Success', message: 'AI preferences updated successfully', type: 'success' })
    } catch (error) {
      toast({ title: 'Error', message: 'Failed to update AI preferences', type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="flex justify-center items-center h-64"><Loader2 className="animate-spin text-primary h-8 w-8" /></div>
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <SectionHeader 
        title="AI Preferences" 
        description="Configure default generation settings, model routing, and core behavior." 
      />
      
      <div className="grid gap-8">
        <Card className="p-6 space-y-6">
          <div className="flex items-center gap-3 border-b border-border pb-4 mb-4">
            <div className="p-2 bg-primary/10 rounded-lg text-primary">
              <Brain className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">Generation Settings</h3>
              <p className="text-sm text-muted-foreground">Select the default LLM and parameter configurations.</p>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="space-y-3">
              <Label htmlFor="default_model">Default Language Model</Label>
              <div className="relative">
                <select 
                  id="default_model" 
                  name="default_model" 
                  value={formData.default_model}
                  onChange={handleChange}
                  className="w-full flex h-10 items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                >
                  <option value="gpt-4o">GPT-4o (OpenAI)</option>
                  <option value="gpt-4-turbo">GPT-4 Turbo (OpenAI)</option>
                  <option value="claude-3-5-sonnet">Claude 3.5 Sonnet (Anthropic)</option>
                  <option value="claude-3-opus">Claude 3 Opus (Anthropic)</option>
                  <option value="gemini-1.5-pro">Gemini 1.5 Pro (Google)</option>
                </select>
              </div>
              <p className="text-xs text-muted-foreground">This model will be used when a specific agent doesn't enforce one.</p>
            </div>
            
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label htmlFor="temperature">Temperature: {formData.temperature.toFixed(2)}</Label>
                <Sliders className="w-4 h-4 text-muted-foreground" />
              </div>
              <input 
                id="temperature" 
                name="temperature"
                type="range" 
                min="0" 
                max="1" 
                step="0.05" 
                value={formData.temperature} 
                onChange={handleChange}
                className="w-full accent-primary h-2 bg-muted rounded-lg appearance-none cursor-pointer" 
              />
              <div className="flex justify-between text-[10px] text-muted-foreground font-medium uppercase tracking-wider">
                <span>Deterministic</span>
                <span>Creative</span>
              </div>
            </div>
          </div>
        </Card>
        
        <Card className="p-6 space-y-6">
          <div className="flex items-center gap-3 border-b border-border pb-4 mb-4">
            <div className="p-2 bg-primary/10 rounded-lg text-primary">
              <MessageSquare className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">Global System Prompt</h3>
              <p className="text-sm text-muted-foreground">Add custom instructions appended to all queries in your workspace.</p>
            </div>
          </div>
          
          <div className="space-y-2">
            <textarea 
              id="system_prompt" 
              name="system_prompt"
              rows={5}
              value={formData.system_prompt}
              onChange={handleChange}
              placeholder="e.g., Always respond in a professional tone. Never use markdown headers..."
              className="w-full min-h-[120px] rounded-md border border-input bg-transparent px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-y"
            />
          </div>
        </Card>
      </div>
      
      <div className="flex justify-end pt-4">
        <Button onClick={handleSave} isLoading={saving}>
          Save AI Preferences
        </Button>
      </div>
    </div>
  )
}
