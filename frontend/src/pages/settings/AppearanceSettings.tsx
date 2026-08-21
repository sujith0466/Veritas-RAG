import { useState, useEffect } from 'react'
import { Card, Label, Button, SectionHeader } from '@/components/common'
import { useAuthStore } from '@/stores/authStore'
import { userService } from '@/services/userService'
import { useToast } from '@/hooks/useToast'
import { Loader2, Moon, Sun, Monitor } from 'lucide-react'

export function AppearanceSettings() {
  const user = useAuthStore(s => s.user)
  const setAuth = useAuthStore(s => s.setAuth)
  const token = useAuthStore(s => s.token)
  const { toast } = useToast()

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const [preferences, setPreferences] = useState({
    theme: 'system',
    density: 'comfortable',
    animations: true,
  })

  useEffect(() => {
    loadPreferences()
  }, [])

  const loadPreferences = async () => {
    try {
      const { data } = await userService.getProfile()
      setPreferences({
        theme: data.preferences?.theme || 'system',
        density: data.preferences?.density || 'comfortable',
        animations: data.preferences?.animations ?? true,
      })
    } catch (error) {
      toast({ title: 'Error', message: 'Failed to load preferences', type: 'error' })
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const { data } = await userService.updatePreferences({ preferences })
      if (user && token) {
        setAuth({ ...user, ...data }, token)
      }
      toast({ title: 'Success', message: 'Appearance updated successfully', type: 'success' })
    } catch (error) {
      toast({ title: 'Error', message: 'Failed to update appearance', type: 'error' })
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
        title="Appearance"
        description="Customize how the Veritas RAG workspace looks and feels on this device."
      />

      <Card className="p-6 space-y-8">
        {/* Theme Selection */}
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-medium">Theme</h3>
            <p className="text-sm text-muted-foreground">Select or customize your UI theme.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <button
              onClick={() => setPreferences(p => ({ ...p, theme: 'light' }))}
              className={`flex flex-col items-center p-4 border rounded-lg transition-colors ${preferences.theme === 'light' ? 'border-primary bg-primary/5' : 'border-border hover:bg-muted'}`}
            >
              <Sun className="h-6 w-6 mb-2" />
              <span className="text-sm font-medium">Light</span>
            </button>
            <button
              onClick={() => setPreferences(p => ({ ...p, theme: 'dark' }))}
              className={`flex flex-col items-center p-4 border rounded-lg transition-colors ${preferences.theme === 'dark' ? 'border-primary bg-primary/5' : 'border-border hover:bg-muted'}`}
            >
              <Moon className="h-6 w-6 mb-2" />
              <span className="text-sm font-medium">Dark</span>
            </button>
            <button
              onClick={() => setPreferences(p => ({ ...p, theme: 'system' }))}
              className={`flex flex-col items-center p-4 border rounded-lg transition-colors ${preferences.theme === 'system' ? 'border-primary bg-primary/5' : 'border-border hover:bg-muted'}`}
            >
              <Monitor className="h-6 w-6 mb-2" />
              <span className="text-sm font-medium">System</span>
            </button>
          </div>
        </div>

        {/* Animations */}
        <div className="flex items-center justify-between border-t border-border pt-6">
          <div className="space-y-0.5">
            <Label className="text-base">UI Animations</Label>
            <p className="text-sm text-muted-foreground">Enable micro-interactions and transitions.</p>
          </div>
          <button
            onClick={() => setPreferences(p => ({ ...p, animations: !p.animations }))}
            className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 ${preferences.animations ? 'bg-primary' : 'bg-input'}`}
          >
            <span
              className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${preferences.animations ? 'translate-x-5' : 'translate-x-0'}`}
            />
          </button>
        </div>
      </Card>

      <div className="flex justify-end">
        <Button onClick={handleSave} isLoading={saving}>Save Preferences</Button>
      </div>
    </div>
  )
}
