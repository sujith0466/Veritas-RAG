import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Input, Label, Button, SectionHeader } from '@/components/common'
import { useToast } from '@/hooks/useToast'
import { userService } from '@/services/userService'
import { workspaceSettingsService, WorkspaceSettingsData } from '@/services/workspaceSettingsService'
import { useAuthStore } from '@/stores/authStore'
import { Briefcase, Database, Users, Loader2, Download, Calendar } from 'lucide-react'

export function WorkspaceSettings() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const user = useAuthStore(s => s.user)
  const setAuth = useAuthStore(s => s.setAuth)
  const token = useAuthStore(s => s.token)

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [settingsData, setSettingsData] = useState<WorkspaceSettingsData | null>(null)
  const [expectedUpdatedAt, setExpectedUpdatedAt] = useState<string>('')
  const [formData, setFormData] = useState({
    workspace_name: '',
    retention_policy: '90',
  })

  // Export State
  const [exportFormat, setExportFormat] = useState('json')
  const [exportStartDate, setExportStartDate] = useState('')
  const [exportEndDate, setExportEndDate] = useState('')
  const [exporting, setExporting] = useState(false)

  const workspaceId = user?.workspace_id || user?.tenant_id || ''

  const handleExport = async () => {
    if (!workspaceId) {
      toast({ title: 'Error', message: 'No workspace context found', type: 'error' })
      return
    }

    setExporting(true)
    try {
      const query = new URLSearchParams({ format: exportFormat })
      if (exportStartDate) query.append('start_date', exportStartDate)
      if (exportEndDate) query.append('end_date', exportEndDate)

      const res = await fetch(`/api/v1/workspaces/${workspaceId}/chat/export?${query.toString()}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })

      if (!res.ok) {
        if (res.status === 403) {
          throw new Error("Insufficient permissions to export workspace data.")
        }
        throw new Error('Export failed')
      }

      const blob = await res.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const contentDisposition = res.headers.get('content-disposition')
      let filename = `chat_export_${workspaceId}.${exportFormat}`
      if (contentDisposition && contentDisposition.includes('filename=')) {
        filename = contentDisposition.split('filename=')[1].replace(/"/g, '')
      }
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)

      toast({ title: 'Success', message: 'Export completed successfully', type: 'success' })
    } catch (err: any) {
      toast({ title: 'Export Error', message: err.message, type: 'error' })
    } finally {
      setExporting(false)
    }
  }

  useEffect(() => {
    loadWorkspace()
  }, [workspaceId])

  const loadWorkspace = async () => {
    try {
      setLoading(true)
      let currentWsName = user?.workspace_name && !user?.workspace_name.includes('-') ? user.workspace_name : 'Default Workspace'

      // 1. Fetch user profile for name if available
      try {
        const { data: profile } = await userService.getProfile()
        if (profile?.profile_data?.workspace_name) {
          currentWsName = profile.profile_data.workspace_name
        }
      } catch {
        // Fallback to user auth context name
      }

      // 2. Fetch canonical settings from /api/v1/workspaces/{id}/settings
      if (workspaceId) {
        try {
          const res = await workspaceSettingsService.getSettings(workspaceId)
          if (res?.data) {
            setSettingsData(res.data)
            setExpectedUpdatedAt(res.data.updated_at)
            const retentionDays = res.data.settings?.general?.retention_days ?? 90
            setFormData({
              workspace_name: currentWsName,
              retention_policy: String(retentionDays),
            })
            return
          }
        } catch (settingsErr) {
          console.warn('Could not fetch canonical settings, falling back to profile defaults', settingsErr)
        }
      }

      setFormData({
        workspace_name: currentWsName,
        retention_policy: '90',
      })
    } catch (error) {
      toast({ title: 'Error', message: 'Failed to load workspace settings', type: 'error' })
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }))
  }

  const handleSave = async () => {
    if (!formData.workspace_name.trim()) {
      toast({ title: 'Error', message: 'Workspace Name is required', type: 'error' })
      return
    }

    setSaving(true)
    try {
      const retentionDays = parseInt(formData.retention_policy, 10) || 90

      // 1. Save canonical workspace settings if workspaceId exists
      if (workspaceId && expectedUpdatedAt) {
        try {
          const res = await workspaceSettingsService.patchSettings(
            workspaceId,
            expectedUpdatedAt,
            {
              general: {
                retention_days: retentionDays,
              }
            }
          )
          if (res?.data) {
            setSettingsData(res.data)
            setExpectedUpdatedAt(res.data.updated_at)
          }
        } catch (patchErr: any) {
          if (patchErr?.response?.status === 409 || patchErr?.status === 409) {
            toast({
              title: 'Conflict Detected',
              message: 'Settings were modified by another user. Reloading fresh settings...',
              type: 'error',
            })
            await loadWorkspace()
            return
          }
          throw patchErr
        }
      }

      // 2. Synchronize workspace name across profile
      await userService.updateProfile({
        profile_data: {
          ...user?.profile_data,
          workspace_name: formData.workspace_name
        }
      })

      if (user && token) {
        setAuth({
          ...user,
          workspace_name: formData.workspace_name,
          profile_data: { ...user.profile_data, workspace_name: formData.workspace_name }
        }, token)
      }

      toast({ title: 'Success', message: 'Workspace settings updated successfully', type: 'success' })
    } catch (error: any) {
      const message = error?.response?.data?.detail || error.message || 'Failed to update workspace settings'
      toast({ title: 'Error', message, type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="flex justify-center items-center h-64"><Loader2 className="animate-spin text-primary h-8 w-8" /></div>
  }

  const role = String(user?.role || '').trim().toLowerCase()
  const canExport = ['admin', 'owner', 'platform_admin'].includes(role)

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <SectionHeader
        title="Workspace Configuration"
        description="Manage your enterprise workspace identity and data policies."
      />

      <div className="grid gap-8">
        <Card className="p-6 space-y-6">
          <div className="flex items-center gap-3 border-b border-border pb-4 mb-4">
            <div className="p-2 bg-primary/10 rounded-lg text-primary">
              <Briefcase className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">General Info</h3>
              <p className="text-sm text-muted-foreground">Basic workspace identity details.</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <Label htmlFor="workspace_name">Workspace Name</Label>
              <Input
                id="workspace_name"
                name="workspace_name"
                value={formData.workspace_name}
                onChange={handleChange}
                placeholder="Acme Corp"
              />
            </div>

            <div className="space-y-2">
              <Label>Tenant ID</Label>
              <Input
                value={workspaceId || 'Not Assigned'}
                readOnly
                className="bg-muted cursor-not-allowed font-mono text-xs"
              />
              <p className="text-xs text-muted-foreground mt-1">Unique isolation identifier.</p>
            </div>
          </div>
        </Card>

        <Card className="p-6 space-y-6">
          <div className="flex items-center gap-3 border-b border-border pb-4 mb-4">
            <div className="p-2 bg-primary/10 rounded-lg text-primary">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">Data Management</h3>
              <p className="text-sm text-muted-foreground">Compliance and retention configurations.</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pb-6 border-b border-border">
            <div className="space-y-3">
              <Label htmlFor="retention_policy">Log Retention Policy</Label>
              <select
                id="retention_policy"
                name="retention_policy"
                value={formData.retention_policy}
                onChange={handleChange}
                className="w-full flex h-10 items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              >
                <option value="30">30 Days</option>
                <option value="90">90 Days</option>
                <option value="180">180 Days</option>
                <option value="365">1 Year (365 Days)</option>
              </select>
              <p className="text-xs text-muted-foreground">Audit logs and query telemetry will be archived after this duration.</p>
            </div>

            {settingsData && (
              <div className="space-y-3">
                <Label>Canonical Settings Version</Label>
                <div className="h-10 px-3 py-2 rounded-md bg-muted/50 border border-border flex items-center justify-between text-xs font-mono text-muted-foreground">
                  <span>Version {settingsData.version} (v{settingsData.schema_version})</span>
                  <span className="truncate max-w-[120px]">{settingsData.settings_hash.slice(0, 12)}…</span>
                </div>
                <p className="text-xs text-muted-foreground">Backed by canonical JSON document versioning.</p>
              </div>
            )}
          </div>

          <div className="space-y-4 pt-2">
            <div>
              <h4 className="text-sm font-semibold text-foreground">Chat History Export</h4>
              <p className="text-xs text-muted-foreground mb-4 mt-1">Export full workspace chat history for compliance or analytics. Available to Owners and Admins.</p>
            </div>

            <div className="flex flex-col md:flex-row gap-4 items-end">
              <div className="space-y-2 flex-1 w-full">
                <Label htmlFor="export_format">Format</Label>
                <select
                  id="export_format"
                  value={exportFormat}
                  onChange={e => setExportFormat(e.target.value)}
                  className="w-full flex h-10 items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                >
                  <option value="json">JSON</option>
                  <option value="csv">CSV</option>
                </select>
              </div>

              <div className="space-y-2 flex-1 w-full">
                <Label htmlFor="export_start">Start Date (Optional)</Label>
                <div className="relative">
                  <Calendar className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="export_start"
                    type="date"
                    className="pl-9"
                    value={exportStartDate}
                    onChange={e => setExportStartDate(e.target.value)}
                  />
                </div>
              </div>

              <div className="space-y-2 flex-1 w-full">
                <Label htmlFor="export_end">End Date (Optional)</Label>
                <div className="relative">
                  <Calendar className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="export_end"
                    type="date"
                    className="pl-9"
                    value={exportEndDate}
                    onChange={e => setExportEndDate(e.target.value)}
                  />
                </div>
              </div>

              <div className="w-full md:w-auto mt-4 md:mt-0">
                <Button
                  onClick={handleExport}
                  disabled={exporting || !canExport}
                  className="w-full"
                >
                  {exporting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
                  Export
                </Button>
              </div>
            </div>
          </div>
        </Card>

        <Card className="p-6 space-y-6">
          <div className="flex items-center justify-between border-b border-border pb-4 mb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary/10 rounded-lg text-primary">
                <Users className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-semibold text-foreground">Workspace Members</h3>
                <p className="text-sm text-muted-foreground">Invite and manage users in this tenant.</p>
              </div>
            </div>
            <Button variant="outline" onClick={() => navigate('/admin/members')}>
              Manage Team
            </Button>
          </div>

          <div className="bg-surface-elevated rounded-lg p-4 text-center border border-border">
            <p className="text-sm text-muted-foreground">
              Configure team roles, active member invitations, and workspace security boundaries in the Members portal.
            </p>
          </div>
        </Card>
      </div>

      <div className="flex justify-end pt-4">
        <Button onClick={handleSave} isLoading={saving}>
          Save Workspace Settings
        </Button>
      </div>
    </div>
  )
}
