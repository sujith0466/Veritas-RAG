import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, useReducedMotion } from 'framer-motion'
import { Card, Input, Label, Button } from '@/components/common'
import { AdminPageHeader } from '@/components/admin/AdminPageHeader'
import { useToast } from '@/hooks/useToast'
import { userService } from '@/services/userService'
import { workspaceSettingsService, WorkspaceSettingsData } from '@/services/workspaceSettingsService'
import { useAuthStore } from '@/stores/authStore'
import {
  Briefcase,
  Database,
  Users,
  Loader2,
  Download,
  Calendar,
  Copy,
  Check,
  ShieldCheck,
  AlertCircle,
  FileText,
} from 'lucide-react'

export function WorkspaceSettings() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const user = useAuthStore(s => s.user)
  const setAuth = useAuthStore(s => s.setAuth)
  const token = useAuthStore(s => s.token)
  const shouldReduceMotion = useReducedMotion()

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [settingsData, setSettingsData] = useState<WorkspaceSettingsData | null>(null)
  const [expectedUpdatedAt, setExpectedUpdatedAt] = useState<string>('')
  const [copiedId, setCopiedId] = useState(false)
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

  const handleCopyId = () => {
    if (!workspaceId) return
    navigator.clipboard.writeText(workspaceId)
    setCopiedId(true)
    toast({ title: 'Copied', message: 'Workspace ID copied to clipboard', type: 'info' })
    setTimeout(() => setCopiedId(false), 2000)
  }

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
        headers: { Authorization: `Bearer ${token}` },
      })

      if (!res.ok) {
        if (res.status === 403) {
          throw new Error('Insufficient permissions to export workspace data.')
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
      let currentWsName =
        user?.workspace_name && !user?.workspace_name.includes('-') ? user.workspace_name : 'Default Workspace'

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
              },
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
          workspace_name: formData.workspace_name,
        },
      })

      if (user && token) {
        setAuth(
          {
            ...user,
            workspace_name: formData.workspace_name,
            profile_data: { ...user.profile_data, workspace_name: formData.workspace_name },
          },
          token
        )
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
    return (
      <div className="flex flex-col justify-center items-center h-64 gap-3">
        <Loader2 className="animate-spin text-primary h-8 w-8" />
        <span className="text-xs text-muted-foreground font-mono">Loading canonical settings...</span>
      </div>
    )
  }

  const role = String(user?.role || '').trim().toLowerCase()
  const canExport = ['admin', 'owner', 'platform_admin'].includes(role)

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      <AdminPageHeader
        eyebrow="ADMINISTRATION / WORKSPACE"
        title="Workspace Configuration"
        description="Manage your enterprise workspace identity, data compliance policies, and compliance export pipelines."
        badge={
          settingsData ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-2xs font-mono font-medium bg-primary/10 text-primary border border-primary/20">
              <ShieldCheck className="h-3 w-3" />
              Version {settingsData.version}
            </span>
          ) : undefined
        }
      />

      <div className="grid gap-6">
        {/* Workspace Identity Card */}
        <motion.div
          initial={shouldReduceMotion ? false : { opacity: 0, y: 12 }}
          animate={shouldReduceMotion ? false : { opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
        >
          <Card className="p-6 border border-border/80 shadow-xs hover:border-border transition-colors">
            <div className="flex items-center gap-3 border-b border-border/60 pb-4 mb-5">
              <div className="p-2.5 bg-primary/10 rounded-lg text-primary">
                <Briefcase className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-semibold text-foreground text-base">General Information</h3>
                <p className="text-xs text-muted-foreground">Primary identity and identifier for this enterprise tenant.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <Label htmlFor="workspace_name" className="text-xs font-semibold">
                  Workspace Name
                </Label>
                <Input
                  id="workspace_name"
                  name="workspace_name"
                  value={formData.workspace_name}
                  onChange={handleChange}
                  placeholder="Acme Corp"
                  className="bg-background/80 focus:bg-background transition-colors"
                />
                <p className="text-2xs text-muted-foreground">Human-readable name displayed across navigation and reports.</p>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-xs font-semibold">Tenant Identifier</Label>
                  <button
                    type="button"
                    onClick={handleCopyId}
                    className="inline-flex items-center gap-1 text-2xs text-primary hover:underline focus:outline-none"
                  >
                    {copiedId ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                    <span>{copiedId ? 'Copied' : 'Copy ID'}</span>
                  </button>
                </div>
                <Input
                  value={workspaceId || 'Not Assigned'}
                  readOnly
                  className="bg-muted/40 cursor-not-allowed font-mono text-xs border-dashed"
                />
                <p className="text-2xs text-muted-foreground">Cryptographic tenant UUID enforcing isolation across databases.</p>
              </div>
            </div>
          </Card>
        </motion.div>

        {/* Data Management & Retention Card */}
        <motion.div
          initial={shouldReduceMotion ? false : { opacity: 0, y: 12 }}
          animate={shouldReduceMotion ? false : { opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: 0.05 }}
        >
          <Card className="p-6 border border-border/80 shadow-xs hover:border-border transition-colors">
            <div className="flex items-center gap-3 border-b border-border/60 pb-4 mb-5">
              <div className="p-2.5 bg-primary/10 rounded-lg text-primary">
                <Database className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-semibold text-foreground text-base">Data Retention & Governance</h3>
                <p className="text-xs text-muted-foreground">Compliance policies, document lifecycle, and telemetry retention.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pb-6 border-b border-border/60">
              <div className="space-y-2">
                <Label htmlFor="retention_policy" className="text-xs font-semibold">
                  Log Retention Policy
                </Label>
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
                <p className="text-2xs text-muted-foreground">Audit logs and query telemetry will be archived after this duration.</p>
              </div>

              {settingsData && (
                <div className="space-y-2">
                  <Label className="text-xs font-semibold">Canonical Document State</Label>
                  <div className="h-10 px-3 py-2 rounded-md bg-muted/40 border border-border/60 flex items-center justify-between text-xs font-mono text-muted-foreground">
                    <span className="flex items-center gap-2">
                      <FileText className="h-3.5 w-3.5 text-primary" />
                      Schema v{settingsData.schema_version} / Doc v{settingsData.version}
                    </span>
                    <span className="truncate max-w-[120px] font-mono text-2xs bg-muted px-1.5 py-0.5 rounded">
                      {settingsData.settings_hash.slice(0, 10)}…
                    </span>
                  </div>
                  <p className="text-2xs text-muted-foreground">Backed by optimistic concurrency lock with SHA-256 state hashing.</p>
                </div>
              )}
            </div>

            {/* Chat Export Sub-section */}
            <div className="space-y-4 pt-5">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
                <div>
                  <h4 className="text-sm font-semibold text-foreground">Chat History & Telemetry Export</h4>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Download workspace interaction transcripts and citations for external auditing.
                  </p>
                </div>
                {!canExport && (
                  <span className="inline-flex items-center gap-1 text-2xs text-amber-500 font-mono">
                    <AlertCircle className="h-3 w-3" />
                    Admin / Owner access required
                  </span>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 items-end pt-1">
                <div className="space-y-1.5">
                  <Label htmlFor="export_format" className="text-2xs font-semibold text-muted-foreground">
                    Format
                  </Label>
                  <select
                    id="export_format"
                    value={exportFormat}
                    onChange={e => setExportFormat(e.target.value)}
                    className="w-full flex h-9 items-center justify-between rounded-md border border-input bg-background px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    <option value="json">JSON (Structured)</option>
                    <option value="csv">CSV (Tabular)</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="export_start" className="text-2xs font-semibold text-muted-foreground">
                    Start Date (Optional)
                  </Label>
                  <div className="relative">
                    <Calendar className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                    <Input
                      id="export_start"
                      type="date"
                      className="pl-8 h-9 text-xs"
                      value={exportStartDate}
                      onChange={e => setExportStartDate(e.target.value)}
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="export_end" className="text-2xs font-semibold text-muted-foreground">
                    End Date (Optional)
                  </Label>
                  <div className="relative">
                    <Calendar className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                    <Input
                      id="export_end"
                      type="date"
                      className="pl-8 h-9 text-xs"
                      value={exportEndDate}
                      onChange={e => setExportEndDate(e.target.value)}
                    />
                  </div>
                </div>

                <div>
                  <Button
                    onClick={handleExport}
                    disabled={exporting || !canExport}
                    variant="outline"
                    className="w-full h-9 text-xs flex items-center justify-center gap-2"
                  >
                    {exporting ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Download className="w-3.5 h-3.5" />
                    )}
                    <span>{exporting ? 'Exporting...' : 'Export Chat Data'}</span>
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        </motion.div>

        {/* Team Members Navigation Card */}
        <motion.div
          initial={shouldReduceMotion ? false : { opacity: 0, y: 12 }}
          animate={shouldReduceMotion ? false : { opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: 0.1 }}
        >
          <Card className="p-6 border border-border/80 shadow-xs hover:border-border transition-colors">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border/60 pb-4 mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-primary/10 rounded-lg text-primary">
                  <Users className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground text-base">Team Members & Access</h3>
                  <p className="text-xs text-muted-foreground">Manage authorized users, invitations, and role boundaries.</p>
                </div>
              </div>
              <Button variant="outline" size="sm" onClick={() => navigate('/admin/members')} className="flex items-center gap-2">
                <span>Manage Team</span>
              </Button>
            </div>

            <div className="rounded-lg p-4 bg-muted/20 border border-border/50 text-xs text-muted-foreground leading-relaxed">
              Active workspace permissions, invitations, and role assignments are administered in the dedicated Members portal.
            </div>
          </Card>
        </motion.div>
      </div>

      <div className="flex justify-end pt-2">
        <Button onClick={handleSave} isLoading={saving} className="shadow-xs px-6">
          Save Workspace Settings
        </Button>
      </div>
    </div>
  )
}
