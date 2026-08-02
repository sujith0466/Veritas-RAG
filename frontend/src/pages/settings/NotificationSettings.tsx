import { useState, useEffect } from 'react'
import { Card, Button, SectionHeader } from '@/components/common'
import { useToast } from '@/hooks/useToast'
import { userService } from '@/services/userService'
import { useAuthStore } from '@/stores/authStore'
import { Bell, ShieldAlert, FileText, Loader2 } from 'lucide-react'

export function NotificationSettings() {
  const { toast } = useToast()
  const user = useAuthStore(s => s.user)
  const setAuth = useAuthStore(s => s.setAuth)
  const token = useAuthStore(s => s.token)

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [preferences, setPreferences] = useState({
    email_alerts: true,
    security_alerts: true,
    weekly_reports: false,
  })

  useEffect(() => {
    loadPreferences()
  }, [])

  const loadPreferences = async () => {
    try {
      const { data } = await userService.getProfile()
      const prefs = data.preferences?.notifications || {}
      setPreferences({
        email_alerts: prefs.email_alerts ?? true,
        security_alerts: prefs.security_alerts ?? true,
        weekly_reports: prefs.weekly_reports ?? false,
      })
    } catch (error) {
      toast({ title: 'Error', message: 'Failed to load notification preferences', type: 'error' })
    } finally {
      setLoading(false)
    }
  }

  const handleToggle = (key: keyof typeof preferences) => {
    setPreferences(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const { data } = await userService.updatePreferences({
        preferences: {
          ...user?.preferences,
          notifications: preferences
        }
      })

      if (user && token) {
        setAuth({ ...user, ...data }, token)
      }

      toast({ title: 'Success', message: 'Notification preferences updated successfully', type: 'success' })
    } catch (error) {
      toast({ title: 'Error', message: 'Failed to update preferences', type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="flex justify-center items-center h-64"><Loader2 className="animate-spin text-primary h-8 w-8" /></div>
  }

  const renderSwitch = (checked: boolean, onChange: () => void) => (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={onChange}
      className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 ${checked ? 'bg-primary' : 'bg-muted'}`}
    >
      <span
        aria-hidden="true"
        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${checked ? 'translate-x-5' : 'translate-x-0'}`}
      />
    </button>
  )

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <SectionHeader
        title="Notification Settings"
        description="Choose what events and alerts you want to be notified about."
      />

      <Card className="p-0 overflow-hidden divide-y divide-border/50">
        <div className="flex items-center justify-between p-6">
          <div className="flex items-start gap-4">
            <div className="p-2 bg-primary/10 rounded-lg text-primary mt-1">
              <Bell className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">General Email Alerts</h3>
              <p className="text-sm text-muted-foreground mt-1 max-w-md">
                Receive notifications when documents finish indexing, chunking, or embedding.
              </p>
            </div>
          </div>
          {renderSwitch(preferences.email_alerts, () => handleToggle('email_alerts'))}
        </div>

        <div className="flex items-center justify-between p-6">
          <div className="flex items-start gap-4">
            <div className="p-2 bg-danger/10 rounded-lg text-danger mt-1">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">Security & Hallucination Alerts</h3>
              <p className="text-sm text-muted-foreground mt-1 max-w-md">
                Get immediate alerts if a high-severity security intervention occurs during LLM generation.
              </p>
            </div>
          </div>
          {renderSwitch(preferences.security_alerts, () => handleToggle('security_alerts'))}
        </div>

        <div className="flex items-center justify-between p-6">
          <div className="flex items-start gap-4">
            <div className="p-2 bg-info/10 rounded-lg text-info mt-1">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">Weekly Digest</h3>
              <p className="text-sm text-muted-foreground mt-1 max-w-md">
                Receive a weekly summary of workspace queries, average reliability scores, and active usage.
              </p>
            </div>
          </div>
          {renderSwitch(preferences.weekly_reports, () => handleToggle('weekly_reports'))}
        </div>
      </Card>

      <div className="flex justify-end">
        <Button onClick={handleSave} isLoading={saving}>
          Save Preferences
        </Button>
      </div>
    </div>
  )
}
