import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion'
import { Card, Input, Label, Button } from '@/components/common'
import { AdminPageHeader } from '@/components/admin/AdminPageHeader'
import { useToast } from '@/hooks/useToast'
import { userService } from '@/services/userService'
import { workspaceSettingsService, WorkspaceSettingsData } from '@/services/workspaceSettingsService'
import { workspaceService } from '@/services/workspaceService'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import type { JoinCodeSettings, JoinCodeGenerateResponse } from '@/types'
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
  KeyRound,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Clock,
  X,
  ExternalLink,
} from 'lucide-react'

export function WorkspaceSettings() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const user = useAuthStore(s => s.user)
  const setAuth = useAuthStore(s => s.setAuth)
  const token = useAuthStore(s => s.token)
  const currentWorkspace = useWorkspaceStore(s => s.currentWorkspace)
  const shouldReduceMotion = useReducedMotion()

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [settingsData, setSettingsData] = useState<WorkspaceSettingsData | null>(null)
  const [expectedUpdatedAt, setExpectedUpdatedAt] = useState<string>('')
  const [workspaceUpdatedAt, setWorkspaceUpdatedAt] = useState<string>('')
  const [initialWorkspaceName, setInitialWorkspaceName] = useState<string>('')

  // Workspace Identity State
  const [publicId, setPublicId] = useState<string>('')
  const [slug, setSlug] = useState<string>('')
  const [copiedTenantId, setCopiedTenantId] = useState(false)
  const [copiedPublicId, setCopiedPublicId] = useState(false)
  const [copiedSlug, setCopiedSlug] = useState(false)
  const [formData, setFormData] = useState({
    workspace_name: '',
    retention_policy: '90',
  })

  // Export State
  const [exportFormat, setExportFormat] = useState('json')
  const [exportStartDate, setExportStartDate] = useState('')
  const [exportEndDate, setExportEndDate] = useState('')
  const [exporting, setExporting] = useState(false)

  // WS-A9 Join Code State
  const [joinCodeSettings, setJoinCodeSettings] = useState<JoinCodeSettings | null>(null)
  const [loadingJoinCode, setLoadingJoinCode] = useState(false)
  const [savingJoinCode, setSavingJoinCode] = useState(false)
  const [generatingCode, setGeneratingCode] = useState(false)
  const [joinCodeForm, setJoinCodeForm] = useState({
    enabled: true,
    default_role: 'MEMBER' as 'MEMBER' | 'VIEWER',
    require_approval: false,
    max_uses: '' as string,
  })

  // One-time Plaintext Reveal Modal State (Strictly ephemeral in-memory state)
  const [revealedCode, setRevealedCode] = useState<JoinCodeGenerateResponse | null>(null)
  const [copiedRevealedCode, setCopiedRevealedCode] = useState(false)

  // Regenerate Confirmation Modal State
  const [isRegenerateModalOpen, setIsRegenerateModalOpen] = useState(false)
  const [generateOptions, setGenerateOptions] = useState({
    expires_in_days: 30,
    max_uses: '' as string,
    default_role: 'MEMBER' as 'MEMBER' | 'VIEWER',
    require_approval: false,
  })

  const workspaceId = user?.workspace_id || user?.tenant_id || currentWorkspace?.id || ''
  const role = String(user?.role || '').trim().toLowerCase()
  const isAuthorizedAdmin = ['admin', 'owner', 'platform_admin'].includes(role)
  const canExport = isAuthorizedAdmin

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

      // 2. Resolve current workspace identity (public_id, slug, name, updated_at)
      let wsUpdatedAt = currentWorkspace?.updated_at || ''
      try {
        let curWs = currentWorkspace
        if (workspaceId) {
          try {
            const wsDetail = await workspaceService.getWorkspace(workspaceId)
            if (wsDetail?.data) {
              const d = wsDetail.data
              curWs = {
                id: d.id,
                public_id: d.public_id,
                name: d.name,
                slug: d.slug,
                status: d.status,
                provisioning_status: d.provisioning_status,
                updated_at: d.updated_at,
              }
              wsUpdatedAt = d.updated_at || ''
              useWorkspaceStore.getState().setCurrentWorkspace(curWs)
            }
          } catch {
            // fallback
          }
        }
        if (!wsUpdatedAt) {
          const res = await workspaceService.getCurrentWorkspace()
          const d = (res as any)?.data || res
          if (d && (d.public_id || d.workspace_id || d.id)) {
            curWs = {
              id: d.workspace_id || d.id,
              public_id: d.public_id || undefined,
              name: d.name,
              slug: d.slug,
              status: d.status || 'ACTIVE',
              provisioning_status: 'READY',
              updated_at: d.updated_at || curWs?.updated_at || new Date().toISOString(),
            }
            wsUpdatedAt = d.updated_at || curWs.updated_at || ''
            useWorkspaceStore.getState().setCurrentWorkspace(curWs)
          }
        }
        if (curWs) {
          setPublicId(curWs.public_id || '')
          setSlug(curWs.slug || '')
          if (curWs.name) currentWsName = curWs.name
          if (curWs.updated_at && !wsUpdatedAt) wsUpdatedAt = curWs.updated_at
        }
      } catch (wsErr) {
        console.warn('Could not fetch current workspace summary', wsErr)
        if (currentWorkspace) {
          setPublicId(currentWorkspace.public_id || '')
          setSlug(currentWorkspace.slug || '')
          if (currentWorkspace.name) currentWsName = currentWorkspace.name
          if (currentWorkspace.updated_at && !wsUpdatedAt) wsUpdatedAt = currentWorkspace.updated_at
        }
      }

      setWorkspaceUpdatedAt(wsUpdatedAt)
      setInitialWorkspaceName(currentWsName)

      // 3. Fetch canonical settings from /api/v1/workspaces/{id}/settings
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
          }
        } catch (settingsErr) {
          console.warn('Could not fetch canonical settings, falling back to profile defaults', settingsErr)
          setFormData({
            workspace_name: currentWsName,
            retention_policy: '90',
          })
        }

        // 4. If authorized admin, fetch Join Code settings
        if (isAuthorizedAdmin) {
          await loadJoinCodeSettings()
        }
      } else {
        setFormData({
          workspace_name: currentWsName,
          retention_policy: '90',
        })
      }
    } catch (error) {
      toast({ title: 'Error', message: 'Failed to load workspace settings', type: 'error' })
    } finally {
      setLoading(false)
    }
  }

  const loadJoinCodeSettings = async () => {
    if (!workspaceId) return
    try {
      setLoadingJoinCode(true)
      const res = await workspaceService.getJoinCodeSettings(workspaceId)
      const data = (res as any)?.data || res
      setJoinCodeSettings(data)
      setJoinCodeForm({
        enabled: Boolean(data.enabled),
        default_role: (data.default_role as 'MEMBER' | 'VIEWER') || 'MEMBER',
        require_approval: Boolean(data.require_approval),
        max_uses: data.max_uses ? String(data.max_uses) : '',
      })
    } catch (err: any) {
      console.warn('Failed to load join code settings', err)
    } finally {
      setLoadingJoinCode(false)
    }
  }

  const handleCopyTenantId = () => {
    if (!workspaceId) return
    navigator.clipboard.writeText(workspaceId)
    setCopiedTenantId(true)
    toast({ title: 'Copied', message: 'Tenant UUID copied to clipboard', type: 'info' })
    setTimeout(() => setCopiedTenantId(false), 2000)
  }

  const handleCopyPublicId = () => {
    if (!publicId) return
    navigator.clipboard.writeText(publicId)
    setCopiedPublicId(true)
    toast({ title: 'Copied', message: 'Public Workspace ID copied to clipboard', type: 'info' })
    setTimeout(() => setCopiedPublicId(false), 2000)
  }

  const handleCopySlug = () => {
    if (!slug) return
    navigator.clipboard.writeText(slug)
    setCopiedSlug(true)
    toast({ title: 'Copied', message: 'Workspace Slug copied to clipboard', type: 'info' })
    setTimeout(() => setCopiedSlug(false), 2000)
  }

  const handleCopyRevealedCode = () => {
    if (!revealedCode?.join_code) return
    navigator.clipboard.writeText(revealedCode.join_code)
    setCopiedRevealedCode(true)
    toast({ title: 'Copied', message: 'Join Code copied to clipboard', type: 'info' })
    setTimeout(() => setCopiedRevealedCode(false), 2500)
  }

  const handleDismissRevealedCode = () => {
    setRevealedCode(null)
    setCopiedRevealedCode(false)
  }

  const handleGenerateJoinCode = async (isRegen = false) => {
    if (!workspaceId) return
    try {
      setGeneratingCode(true)
      const maxUsesVal = generateOptions.max_uses ? parseInt(generateOptions.max_uses, 10) : null
      const res = isRegen
        ? await workspaceService.regenerateJoinCode(workspaceId, {
            expires_in_days: generateOptions.expires_in_days,
            max_uses: maxUsesVal,
          })
        : await workspaceService.generateJoinCode(workspaceId, {
            expires_in_days: generateOptions.expires_in_days,
            default_role: generateOptions.default_role,
            require_approval: generateOptions.require_approval,
            max_uses: maxUsesVal,
          })

      const data = (res as any)?.data || res
      setRevealedCode(data)
      setIsRegenerateModalOpen(false)
      toast({
        title: isRegen ? 'Join Code Regenerated' : 'Join Code Generated',
        message: 'A new Join Code was generated. Store it safely now; it will only be revealed once.',
        type: 'success',
      })
      await loadJoinCodeSettings()
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to generate join code'
      toast({ title: 'Error', message: msg, type: 'error' })
    } finally {
      setGeneratingCode(false)
    }
  }

  const handleSaveJoinCodeSettings = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!workspaceId) return
    try {
      setSavingJoinCode(true)
      const maxUsesVal = joinCodeForm.max_uses ? parseInt(joinCodeForm.max_uses, 10) : null
      const res = await workspaceService.patchJoinCodeSettings(workspaceId, {
        enabled: joinCodeForm.enabled,
        default_role: joinCodeForm.default_role,
        require_approval: joinCodeForm.require_approval,
        max_uses: maxUsesVal,
      })
      const data = (res as any)?.data || res
      setJoinCodeSettings(data)
      toast({ title: 'Settings Saved', message: 'Join Code configuration updated successfully', type: 'success' })
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to update join code settings'
      toast({ title: 'Error', message: msg, type: 'error' })
    } finally {
      setSavingJoinCode(false)
    }
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

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }))
  }

  const handleSave = async () => {
    const trimmedWsName = formData.workspace_name.trim()
    if (!trimmedWsName) {
      toast({ title: 'Error', message: 'Workspace Name is required', type: 'error' })
      return
    }

    setSaving(true)
    try {
      let effectiveWsName = trimmedWsName

      // 1. If workspace name changed and workspaceId is available, persist to workspace entity
      if (workspaceId && trimmedWsName !== initialWorkspaceName) {
        let lockTimestamp = workspaceUpdatedAt || currentWorkspace?.updated_at
        if (!lockTimestamp) {
          try {
            const wsDetail = await workspaceService.getWorkspace(workspaceId)
            if (wsDetail?.data?.updated_at) {
              lockTimestamp = wsDetail.data.updated_at
            }
          } catch {
            // fallback
          }
        }
        if (lockTimestamp) {
          try {
            const updateRes = await workspaceService.updateWorkspace(
              workspaceId,
              lockTimestamp,
              trimmedWsName
            )
            if (updateRes?.data) {
              effectiveWsName = updateRes.data.name
              setWorkspaceUpdatedAt(updateRes.data.updated_at)
              setInitialWorkspaceName(updateRes.data.name)
              useWorkspaceStore.getState().setCurrentWorkspace(updateRes.data)
            }
          } catch (wsErr: any) {
            if (wsErr?.response?.status === 409 || wsErr?.status === 409) {
              toast({
                title: 'Conflict Detected',
                message: 'Workspace was modified by another user. Reloading fresh settings...',
                type: 'error',
              })
              await loadWorkspace()
              return
            }
            throw wsErr
          }
        }
      }

      const retentionDays = parseInt(formData.retention_policy, 10) || 90

      // 2. Save canonical workspace settings if workspaceId exists
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

      // 3. Synchronize workspace name across profile and auth store
      await userService.updateProfile({
        profile_data: {
          ...user?.profile_data,
          workspace_name: effectiveWsName,
        },
      })

      if (user && token) {
        setAuth(
          {
            ...user,
            workspace_name: effectiveWsName,
            profile_data: { ...user.profile_data, workspace_name: effectiveWsName },
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

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      <AdminPageHeader
        eyebrow="ADMINISTRATION / WORKSPACE"
        title="Workspace Configuration"
        description="Manage your enterprise workspace identity, public join codes, data compliance policies, and export pipelines."
        badge={
          settingsData ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-2xs font-mono font-medium bg-primary/10 text-primary border border-primary/20">
              <ShieldCheck className="h-3 w-3" />
              Version {settingsData.version}
            </span>
          ) : undefined
        }
      />

      {/* ONE-TIME REVEAL MODAL (WS-A9 Strict Invariant: Plaintext displayed once, never persisted) */}
      <AnimatePresence>
        {revealedCode && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md"
            role="dialog"
            aria-modal="true"
            aria-labelledby="one-time-reveal-title"
          >
            <motion.div
              initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.95, y: 10 }}
              animate={shouldReduceMotion ? { opacity: 1 } : { opacity: 1, scale: 1, y: 0 }}
              exit={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.95, y: 10 }}
              transition={{ duration: 0.2 }}
              className="w-full max-w-lg bg-slate-900 border border-indigo-500/40 rounded-2xl p-6 sm:p-8 shadow-2xl space-y-6 text-slate-100"
            >
              <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                <div className="flex items-center space-x-3">
                  <div className="h-10 w-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
                    <KeyRound className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 id="one-time-reveal-title" className="text-lg font-bold text-white tracking-tight">
                      Join Code Generated
                    </h3>
                    <p className="text-xs text-slate-400">One-time plaintext secret reveal</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleDismissRevealedCode}
                  className="text-slate-400 hover:text-white p-1 rounded-lg transition-colors"
                  aria-label="Close modal"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              {/* Plaintext Code Box */}
              <div className="p-5 rounded-xl bg-slate-950 border border-indigo-500/50 flex flex-col items-center justify-center space-y-3 shadow-inner">
                <span className="text-2xs font-semibold uppercase tracking-wider text-slate-400 font-mono">
                  Active Plaintext Join Code
                </span>
                <span className="text-3xl sm:text-4xl font-extrabold tracking-widest text-indigo-400 font-mono select-all">
                  {revealedCode.join_code}
                </span>
                <Button
                  onClick={handleCopyRevealedCode}
                  variant="outline"
                  size="sm"
                  className="flex items-center space-x-2 border-indigo-500/40 bg-indigo-950/40 hover:bg-indigo-900/60 text-indigo-200 mt-2"
                >
                  {copiedRevealedCode ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                  <span>{copiedRevealedCode ? 'Copied to Clipboard' : 'Copy Join Code'}</span>
                </Button>
              </div>

              {/* Strict Security Alert */}
              <div className="p-4 rounded-xl bg-amber-950/40 border border-amber-800/60 flex items-start space-x-3 text-amber-200">
                <AlertTriangle className="h-5 w-5 text-amber-400 shrink-0 mt-0.5" />
                <div className="text-xs space-y-1">
                  <span className="font-semibold text-amber-300 block">Strict One-Time Reveal</span>
                  <p className="text-amber-200/90 leading-relaxed">
                    This Join Code will only be shown once. Copy and share it with your authorized team members now.
                    Veritas-RAG stores only a salted cryptographic hash and cannot retrieve this plaintext code once dismissed.
                  </p>
                  {revealedCode.expires_at && (
                    <p className="text-2xs text-amber-300/80 font-mono pt-1">
                      Expires: {new Date(revealedCode.expires_at).toLocaleString()}
                    </p>
                  )}
                </div>
              </div>

              <div className="pt-2 flex justify-end">
                <Button
                  onClick={handleDismissRevealedCode}
                  className="w-full sm:w-auto bg-indigo-600 hover:bg-indigo-500 text-white font-medium px-6 py-2.5 rounded-xl"
                >
                  I Have Copied This Code (Dismiss)
                </Button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* REGENERATE CONFIRMATION MODAL */}
      <AnimatePresence>
        {isRegenerateModalOpen && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md"
            role="dialog"
            aria-modal="true"
            aria-labelledby="regenerate-modal-title"
          >
            <motion.div
              initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.95 }}
              animate={shouldReduceMotion ? { opacity: 1 } : { opacity: 1, scale: 1 }}
              exit={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.95 }}
              className="w-full max-w-md bg-slate-900 border border-red-500/40 rounded-2xl p-6 shadow-2xl space-y-5 text-slate-100"
            >
              <div className="flex items-center space-x-3 border-b border-slate-800 pb-3">
                <div className="h-10 w-10 rounded-xl bg-red-600/20 border border-red-500/30 flex items-center justify-center text-red-400">
                  <AlertTriangle className="h-5 w-5" />
                </div>
                <div>
                  <h3 id="regenerate-modal-title" className="text-base font-bold text-white">
                    Regenerate Join Code?
                  </h3>
                  <p className="text-xs text-slate-400">Immediate invalidation of existing code</p>
                </div>
              </div>

              <p className="text-xs text-slate-300 leading-relaxed">
                Regenerating will immediately invalidate any previous Join Code. Any team member currently attempting to
                join with the old code will be rejected. A new code will be generated and shown strictly once.
              </p>

              <div className="space-y-3 pt-1">
                <Label className="text-2xs font-semibold text-slate-300">New Code Validity (Days)</Label>
                <select
                  value={generateOptions.expires_in_days}
                  onChange={e => setGenerateOptions(prev => ({ ...prev, expires_in_days: parseInt(e.target.value, 10) }))}
                  className="w-full flex h-9 items-center justify-between rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="7">7 Days</option>
                  <option value="30">30 Days (Default)</option>
                  <option value="90">90 Days</option>
                  <option value="365">1 Year (365 Days)</option>
                  <option value="0">Never Expires</option>
                </select>
              </div>

              <div className="flex justify-end space-x-3 pt-3">
                <Button
                  variant="outline"
                  onClick={() => setIsRegenerateModalOpen(false)}
                  disabled={generatingCode}
                  className="text-xs"
                >
                  Cancel
                </Button>
                <Button
                  onClick={() => handleGenerateJoinCode(true)}
                  disabled={generatingCode}
                  className="bg-red-600 hover:bg-red-500 text-white text-xs flex items-center space-x-2"
                >
                  {generatingCode && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  <span>Confirm & Regenerate</span>
                </Button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      <div className="grid gap-6">
        {/* 1. WORKSPACE IDENTITY CARD (WS-A9.1, A9.2, A9.3) */}
        <motion.div
          initial={shouldReduceMotion ? false : { opacity: 0, y: 12 }}
          animate={shouldReduceMotion ? false : { opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
        >
          <Card className="p-6 border border-border/80 shadow-xs hover:border-border transition-colors">
            <div className="flex items-center justify-between border-b border-border/60 pb-4 mb-5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-primary/10 rounded-lg text-primary">
                  <Briefcase className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground text-base">Workspace Identity</h3>
                  <p className="text-xs text-muted-foreground">
                    Public identification and diagnostic boundary identifiers for this enterprise workspace.
                  </p>
                </div>
              </div>
              {publicId && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/25">
                  ID: {publicId}
                </span>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Workspace Display Name */}
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

              {/* Public Workspace ID */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-xs font-semibold">Public Workspace ID</Label>
                  <button
                    type="button"
                    onClick={handleCopyPublicId}
                    disabled={!publicId}
                    className="inline-flex items-center gap-1 text-2xs text-primary hover:underline focus:outline-none disabled:opacity-40"
                  >
                    {copiedPublicId ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                    <span>{copiedPublicId ? 'Copied' : 'Copy Public ID'}</span>
                  </button>
                </div>
                <Input
                  value={publicId || 'Resolving ID...'}
                  readOnly
                  className="bg-muted/30 font-mono text-xs font-medium border-border/80 tracking-wide"
                />
                <p className="text-2xs text-muted-foreground">
                  Public identifier shared with prospective team members to join via the join portal. Safe for distribution.
                </p>
              </div>

              {/* Workspace Slug */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-xs font-semibold">Workspace Slug</Label>
                  <button
                    type="button"
                    onClick={handleCopySlug}
                    disabled={!slug}
                    className="inline-flex items-center gap-1 text-2xs text-primary hover:underline focus:outline-none disabled:opacity-40"
                  >
                    {copiedSlug ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                    <span>{copiedSlug ? 'Copied' : 'Copy Slug'}</span>
                  </button>
                </div>
                <Input
                  value={slug || 'Resolving slug...'}
                  readOnly
                  className="bg-muted/30 font-mono text-xs border-border/80"
                />
                <p className="text-2xs text-muted-foreground">URL slug used for workspace web routing and deep links.</p>
              </div>

              {/* Diagnostic Internal Tenant UUID (Admin-only diagnostic) */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-xs font-semibold text-muted-foreground">
                    Tenant UUID (Admin Diagnostic Only)
                  </Label>
                  <button
                    type="button"
                    onClick={handleCopyTenantId}
                    className="inline-flex items-center gap-1 text-2xs text-muted-foreground hover:text-foreground hover:underline focus:outline-none"
                  >
                    {copiedTenantId ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                    <span>{copiedTenantId ? 'Copied' : 'Copy UUID'}</span>
                  </button>
                </div>
                <Input
                  value={workspaceId || 'Not Assigned'}
                  readOnly
                  className="bg-muted/40 cursor-not-allowed font-mono text-xs border-dashed text-muted-foreground"
                />
                <p className="text-2xs text-muted-foreground">
                  Internal database tenant key. Used exclusively for diagnostic logging. Never share as a join credential.
                </p>
              </div>
            </div>
          </Card>
        </motion.div>

        {/* 2. WORKSPACE JOINING & JOIN CODE MANAGEMENT CARD (WS-A9.1, A9.4–A9.13) */}
        <motion.div
          initial={shouldReduceMotion ? false : { opacity: 0, y: 12 }}
          animate={shouldReduceMotion ? false : { opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: 0.05 }}
        >
          <Card className="p-6 border border-border/80 shadow-xs hover:border-border transition-colors">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border/60 pb-4 mb-5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-indigo-500/10 rounded-lg text-indigo-400">
                  <KeyRound className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground text-base">Self-Service Joining & Join Code</h3>
                  <p className="text-xs text-muted-foreground">
                    Administer 6-character Crockford Base32 Join Code credentials for self-service team onboarding.
                  </p>
                </div>
              </div>

              {/* Status Badge */}
              <div className="flex items-center gap-2">
                {loadingJoinCode ? (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono text-muted-foreground bg-muted/40 border border-border/60">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    <span>Loading...</span>
                  </span>
                ) : joinCodeSettings?.has_code && joinCodeSettings?.enabled ? (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/25">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    <span>Active Join Code</span>
                  </span>
                ) : joinCodeSettings?.has_code && !joinCodeSettings?.enabled ? (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-medium bg-amber-500/10 text-amber-400 border border-amber-500/25">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    <span>Join Code Disabled</span>
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-medium bg-muted text-muted-foreground border border-border/60">
                    <Clock className="h-3.5 w-3.5" />
                    <span>Not Configured</span>
                  </span>
                )}
              </div>
            </div>

            {/* Diagnostic Details Grid */}
            {joinCodeSettings?.has_code && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 p-4 rounded-xl bg-muted/20 border border-border/50 mb-6 text-xs">
                <div>
                  <span className="text-muted-foreground text-2xs uppercase tracking-wider block font-mono">Expiration</span>
                  <span className="font-semibold text-foreground mt-0.5 block">
                    {joinCodeSettings.expires_at ? new Date(joinCodeSettings.expires_at).toLocaleDateString() : 'Never expires'}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground text-2xs uppercase tracking-wider block font-mono">Usage Count</span>
                  <span className="font-semibold text-foreground mt-0.5 block">
                    {joinCodeSettings.current_uses ?? 0}{' '}
                    <span className="text-muted-foreground font-normal">
                      {joinCodeSettings.max_uses ? `/ ${joinCodeSettings.max_uses} limit` : '(unlimited)'}
                    </span>
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground text-2xs uppercase tracking-wider block font-mono">Default Entrant Role</span>
                  <span className="font-semibold text-foreground mt-0.5 block">
                    {joinCodeSettings.default_role || 'MEMBER'}
                  </span>
                </div>
              </div>
            )}

            {/* Admin Management Section */}
            {isAuthorizedAdmin ? (
              <div className="space-y-6">
                {/* Generation / Regeneration Trigger */}
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 rounded-xl bg-slate-950/40 border border-border/60">
                  <div>
                    <h4 className="text-xs font-semibold text-foreground">
                      {joinCodeSettings?.has_code ? 'Regenerate Join Code' : 'Generate Initial Join Code'}
                    </h4>
                    <p className="text-2xs text-muted-foreground mt-0.5 leading-relaxed">
                      {joinCodeSettings?.has_code
                        ? 'Generate a fresh Join Code. Immediately invalidates the previous code across all sessions.'
                        : 'Create a secure Crockford Base32 join code to allow team members to self-join this workspace.'}
                    </p>
                  </div>

                  <div>
                    {joinCodeSettings?.has_code ? (
                      <Button
                        type="button"
                        onClick={() => setIsRegenerateModalOpen(true)}
                        variant="outline"
                        size="sm"
                        disabled={generatingCode}
                        className="flex items-center space-x-1.5 border-border/80 hover:bg-muted/40 text-xs shrink-0"
                      >
                        <RefreshCw className="h-3.5 w-3.5" />
                        <span>Regenerate Code</span>
                      </Button>
                    ) : (
                      <Button
                        type="button"
                        onClick={() => handleGenerateJoinCode(false)}
                        size="sm"
                        disabled={generatingCode}
                        className="flex items-center space-x-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs shrink-0"
                      >
                        {generatingCode ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <KeyRound className="h-3.5 w-3.5" />}
                        <span>Generate Join Code</span>
                      </Button>
                    )}
                  </div>
                </div>

                {/* Join Code Settings Mutation Form (WS-A9.13) */}
                {joinCodeSettings?.has_code && (
                  <form onSubmit={handleSaveJoinCodeSettings} className="space-y-4 pt-2">
                    <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider font-mono">
                      Join Policy Configuration
                    </h4>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {/* Enable/Disable Toggle */}
                      <div className="p-3.5 rounded-lg border border-border/60 bg-background/50 flex items-center justify-between">
                        <div>
                          <Label htmlFor="join_enabled" className="text-xs font-medium cursor-pointer">
                            Enable Join Code
                          </Label>
                          <p className="text-2xs text-muted-foreground">Allow entrants with code</p>
                        </div>
                        <input
                          id="join_enabled"
                          type="checkbox"
                          checked={joinCodeForm.enabled}
                          onChange={e => setJoinCodeForm(prev => ({ ...prev, enabled: e.target.checked }))}
                          className="h-4 w-4 rounded border-border text-primary focus:ring-primary cursor-pointer"
                        />
                      </div>

                      {/* Default Role */}
                      <div className="space-y-1.5">
                        <Label htmlFor="default_role" className="text-2xs font-semibold text-muted-foreground">
                          Default Role
                        </Label>
                        <select
                          id="default_role"
                          value={joinCodeForm.default_role}
                          onChange={e => setJoinCodeForm(prev => ({ ...prev, default_role: e.target.value as any }))}
                          className="w-full flex h-10 items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                        >
                          <option value="MEMBER">MEMBER (Standard Access)</option>
                          <option value="VIEWER">VIEWER (Read-Only Access)</option>
                        </select>
                      </div>

                      {/* Max Uses */}
                      <div className="space-y-1.5">
                        <Label htmlFor="max_uses" className="text-2xs font-semibold text-muted-foreground">
                          Max Uses (Optional)
                        </Label>
                        <Input
                          id="max_uses"
                          type="number"
                          min="1"
                          max="10000"
                          placeholder="Unlimited"
                          value={joinCodeForm.max_uses}
                          onChange={e => setJoinCodeForm(prev => ({ ...prev, max_uses: e.target.value }))}
                          className="h-10 text-xs"
                        />
                      </div>
                    </div>

                    <div className="flex justify-end pt-2">
                      <Button
                        type="submit"
                        disabled={savingJoinCode}
                        variant="outline"
                        size="sm"
                        className="flex items-center space-x-1.5 text-xs"
                      >
                        {savingJoinCode && <Loader2 className="h-3 w-3 animate-spin" />}
                        <span>Save Join Code Settings</span>
                      </Button>
                    </div>
                  </form>
                )}
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-muted/20 border border-border/50 text-xs text-muted-foreground flex items-center space-x-2">
                <AlertCircle className="h-4 w-4 text-amber-500 shrink-0" />
                <span>Join Code generation and access policies require Workspace Owner or Admin permissions.</span>
              </div>
            )}
          </Card>
        </motion.div>

        {/* 3. DATA MANAGEMENT & RETENTION CARD */}
        <motion.div
          initial={shouldReduceMotion ? false : { opacity: 0, y: 12 }}
          animate={shouldReduceMotion ? false : { opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: 0.1 }}
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

        {/* 4. TEAM MEMBERS & ACCESS NAVIGATION CARD (WS-A9.4) */}
        <motion.div
          initial={shouldReduceMotion ? false : { opacity: 0, y: 12 }}
          animate={shouldReduceMotion ? false : { opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: 0.15 }}
        >
          <Card className="p-6 border border-border/80 shadow-xs hover:border-border transition-colors">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border/60 pb-4 mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-primary/10 rounded-lg text-primary">
                  <Users className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground text-base">Team Members & Invitations</h3>
                  <p className="text-xs text-muted-foreground">
                    Invite new colleagues, manage pending invitations, and assign granular RBAC roles.
                  </p>
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate('/admin/members')}
                className="flex items-center gap-2"
              >
                <span>Manage Team & Invitations</span>
                <ExternalLink className="h-3.5 w-3.5" />
              </Button>
            </div>

            <div className="rounded-lg p-4 bg-muted/20 border border-border/50 text-xs text-muted-foreground leading-relaxed flex items-center justify-between">
              <span>
                Active workspace memberships, email invitations, and role assignments are administered in the dedicated Members portal.
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate('/admin/members')}
                className="text-xs text-primary hover:text-primary/80 shrink-0"
              >
                Go to Members &rarr;
              </Button>
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

export default WorkspaceSettings
