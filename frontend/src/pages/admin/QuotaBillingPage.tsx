import { useState, useEffect } from 'react'
import {
  Zap,
  Server,
  AlertTriangle,
  Activity,
  Database,
  Users,
  Settings2,
  Loader2,
  CheckCircle2,
  Gauge,
} from 'lucide-react'
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion'
import { adminService, TenantQuota, WorkspaceUsage } from '@/services/adminService'
import { workspaceSettingsService, WorkspaceSettingsData } from '@/services/workspaceSettingsService'
import { useAuthStore } from '@/stores/authStore'
import { cn } from '@/utils/cn'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'
import { Label } from '@/components/common/Label'
import { Card } from '@/components/common/Card'
import { useToast } from '@/hooks/useToast'
import { AdminPageHeader } from '@/components/admin/AdminPageHeader'

export function QuotaBillingPage() {
  const { toast } = useToast()
  const user = useAuthStore(s => s.user)
  const shouldReduceMotion = useReducedMotion()

  const [quota, setQuota] = useState<TenantQuota | null>(null)
  const [usage, setUsage] = useState<WorkspaceUsage | null>(null)
  const [settingsData, setSettingsData] = useState<WorkspaceSettingsData | null>(null)
  const [expectedUpdatedAt, setExpectedUpdatedAt] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [savingLimits, setSavingLimits] = useState(false)
  const [isEditingLimits, setIsEditingLimits] = useState(false)

  // Editable limits form state
  const [limitForm, setLimitForm] = useState({
    monthly_token_budget: 10000000,
    monthly_budget_usd: 150.0,
    warning_threshold_pct: 80,
    is_hard_enforced: true,
    monthly_query_budget: 50000,
    max_storage_gb: 100,
    max_members: 50,
  })

  // Fixed workspace ID resolution: strictly use workspace_id or tenant_id, never fallback to name
  const workspaceId = user?.workspace_id || user?.tenant_id || ''

  const userRole = String(user?.role || '').trim().toLowerCase()
  const canEditLimits = ['owner', 'platform_admin'].includes(userRole)

  const loadData = async () => {
    if (!workspaceId) {
      setLoading(false)
      return
    }

    setLoading(true)
    try {
      let currentQuota: TenantQuota | null = null

      // 1. Fetch runtime telemetry usage & quota
      try {
        const usageData = await adminService.getWorkspaceUsage(workspaceId)
        setUsage(usageData)
        currentQuota = {
          tenant_id: usageData.workspace_id,
          monthly_token_limit: usageData.monthly_token_limit,
          monthly_budget_usd: usageData.monthly_budget_usd,
          warning_threshold_pct: usageData.warning_threshold_pct,
          is_hard_enforced: usageData.is_hard_enforced,
          remaining_tokens: usageData.remaining_tokens,
          remaining_budget_usd: usageData.remaining_budget_usd,
        }
        setQuota(currentQuota)
      } catch {
        try {
          currentQuota = await adminService.getQuota(workspaceId)
          setQuota(currentQuota)
        } catch (qErr) {
          console.warn('Could not load telemetry quota', qErr)
        }
      }

      // 2. Fetch canonical workspace limits from /api/v1/workspaces/{id}/settings
      let currentSettings: WorkspaceSettingsData | null = null
      try {
        const res = await workspaceSettingsService.getSettings(workspaceId)
        if (res?.data) {
          currentSettings = res.data
          setSettingsData(res.data)
          setExpectedUpdatedAt(res.data.updated_at)
        }
      } catch (sErr) {
        console.warn('Could not load canonical settings limits', sErr)
      }

      const l = currentSettings?.settings?.limits || {}
      setLimitForm({
        monthly_token_budget: currentQuota?.monthly_token_limit ?? l.monthly_token_budget ?? 10000000,
        monthly_budget_usd: currentQuota?.monthly_budget_usd ?? 150.0,
        warning_threshold_pct: Math.round((currentQuota?.warning_threshold_pct ?? 0.8) * 100),
        is_hard_enforced: currentQuota?.is_hard_enforced ?? true,
        monthly_query_budget: l.monthly_query_budget ?? 50000,
        max_storage_gb: l.max_storage_gb ?? 100,
        max_members: l.max_members ?? 50,
      })
    } catch (e) {
      console.error('Failed to load governance data', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [workspaceId])

  const handleSaveLimits = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!workspaceId) {
      toast({ title: 'Error', message: 'Missing workspace context', type: 'error' })
      return
    }

    setSavingLimits(true)
    try {
      const tokenLimitNum = Number(limitForm.monthly_token_budget)
      if (isNaN(tokenLimitNum) || tokenLimitNum < 1) {
        toast({ title: 'Validation Error', message: 'Monthly token limit must be a positive integer', type: 'error' })
        setSavingLimits(false)
        return
      }

      // 1. Authoritative Quota Update via PUT /analytics/v1/quotas/{tenant_id}
      await adminService.updateQuota(workspaceId, {
        monthly_token_limit: tokenLimitNum,
        monthly_budget_usd: Number(limitForm.monthly_budget_usd ?? 150),
        warning_threshold_pct: Number(limitForm.warning_threshold_pct ?? 80) / 100,
        is_hard_enforced: Boolean(limitForm.is_hard_enforced),
      })

      // 2. Ancillary Workspace Settings Update
      if (expectedUpdatedAt) {
        try {
          const res = await workspaceSettingsService.patchSettings(
            workspaceId,
            expectedUpdatedAt,
            {
              limits: {
                monthly_token_budget: tokenLimitNum,
                monthly_query_budget: Number(limitForm.monthly_query_budget),
                max_storage_gb: Number(limitForm.max_storage_gb),
                max_members: Number(limitForm.max_members),
              },
            }
          )
          if (res?.data) {
            setSettingsData(res.data)
            setExpectedUpdatedAt(res.data.updated_at)
          }
        } catch (settingsErr: any) {
          if (settingsErr?.response?.status === 409 || settingsErr?.status === 409) {
            console.warn('Workspace settings concurrency conflict during ancillary save')
          }
        }
      }

      toast({ title: 'Success', message: 'Resource governance limits updated successfully', type: 'success' })
      setIsEditingLimits(false)
      await loadData()
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err.message || 'Failed to update governance limits'
      toast({ title: 'Error', message: msg, type: 'error' })
    } finally {
      setSavingLimits(false)
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col h-[400px] items-center justify-center gap-3">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        <span className="text-xs font-mono text-muted-foreground">Loading authoritative governance telemetry...</span>
      </div>
    )
  }

  const effectiveTokenLimit =
    quota?.monthly_token_limit ??
    usage?.monthly_token_limit ??
    settingsData?.settings?.limits?.monthly_token_budget ??
    10000000
  const effectiveQueryLimit = settingsData?.settings?.limits?.monthly_query_budget || 50000
  const usedTokens = usage ? usage.used_tokens : quota ? quota.monthly_token_limit - quota.remaining_tokens : 0
  const usedQueries = usage ? usage.used_queries : 0
  const usagePct = (usedTokens / Math.max(1, effectiveTokenLimit)) * 100
  const queryUsagePct = (usedQueries / Math.max(1, effectiveQueryLimit)) * 100
  const isWarning = usagePct >= (quota?.warning_threshold_pct ? quota.warning_threshold_pct * 100 : 80)
  const isCritical = usagePct >= 95

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <AdminPageHeader
        eyebrow="ADMINISTRATION / GOVERNANCE"
        title="Resource & Token Governance"
        description="Manage compute budgets, token consumption ceilings, and workspace resource allocations."
        badge={
          <span
            className={cn(
              'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-2xs font-mono font-medium border',
              quota?.is_hard_enforced
                ? 'bg-rose-500/10 text-rose-500 border-rose-500/20'
                : 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
            )}
          >
            <Gauge className="h-3 w-3" />
            {quota?.is_hard_enforced ? 'Strict Throttling' : 'Telemetry Mode'}
          </span>
        }
        actions={
          canEditLimits && (
            <Button
              variant={isEditingLimits ? 'outline' : 'default'}
              size="sm"
              onClick={() => setIsEditingLimits(!isEditingLimits)}
              className="flex items-center gap-2 shadow-xs"
            >
              <Settings2 className="h-4 w-4" />
              <span>{isEditingLimits ? 'Cancel Editing' : 'Adjust Quotas'}</span>
            </Button>
          )
        }
      />

      {/* Editable Limits Panel for Owner / Platform Admin */}
      <AnimatePresence>
        {isEditingLimits && canEditLimits && (
          <motion.form
            initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: -8 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            onSubmit={handleSaveLimits}
            className="bg-card border border-primary/30 p-6 rounded-xl space-y-4 shadow-sm"
          >
            <div className="flex items-center justify-between border-b border-border/70 pb-3">
              <div>
                <h3 className="font-semibold text-foreground text-sm">Configure Workspace Quotas & Governance</h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Authoritative runtime quotas enforced by QuotaGovernor and synchronized with workspace settings.
                </p>
              </div>
              <span className="text-2xs font-mono text-muted-foreground bg-muted px-2 py-0.5 rounded">
                v{settingsData?.version || 1} ({expectedUpdatedAt ? expectedUpdatedAt.slice(0, 19) : ''})
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 pt-2">
              <div className="space-y-1.5">
                <Label htmlFor="monthly_token_budget" className="text-xs font-semibold">
                  Monthly Token Ceiling
                </Label>
                <Input
                  id="monthly_token_budget"
                  type="number"
                  min="1"
                  step="100000"
                  value={limitForm.monthly_token_budget}
                  onChange={e =>
                    setLimitForm(prev => ({ ...prev, monthly_token_budget: parseInt(e.target.value, 10) || 0 }))
                  }
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="monthly_budget_usd" className="text-xs font-semibold">
                  Budget Ceiling ($ USD)
                </Label>
                <Input
                  id="monthly_budget_usd"
                  type="number"
                  min="0"
                  step="10"
                  value={limitForm.monthly_budget_usd}
                  onChange={e =>
                    setLimitForm(prev => ({ ...prev, monthly_budget_usd: parseFloat(e.target.value) || 0 }))
                  }
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="warning_threshold_pct" className="text-xs font-semibold">
                  Warning Threshold (%)
                </Label>
                <Input
                  id="warning_threshold_pct"
                  type="number"
                  min="1"
                  max="100"
                  value={limitForm.warning_threshold_pct}
                  onChange={e =>
                    setLimitForm(prev => ({ ...prev, warning_threshold_pct: parseInt(e.target.value, 10) || 80 }))
                  }
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="is_hard_enforced" className="text-xs font-semibold">
                  Enforcement Mode
                </Label>
                <select
                  id="is_hard_enforced"
                  className="w-full h-9 px-3 text-xs bg-background border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                  value={limitForm.is_hard_enforced ? 'true' : 'false'}
                  onChange={e => setLimitForm(prev => ({ ...prev, is_hard_enforced: e.target.value === 'true' }))}
                >
                  <option value="true">Hard Throttling (Block on Limit)</option>
                  <option value="false">Soft Warning (Telemetry Only)</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="monthly_query_budget" className="text-xs font-semibold">
                  Monthly Query Budget
                </Label>
                <Input
                  id="monthly_query_budget"
                  type="number"
                  min="0"
                  step="1000"
                  value={limitForm.monthly_query_budget}
                  onChange={e =>
                    setLimitForm(prev => ({ ...prev, monthly_query_budget: parseInt(e.target.value, 10) || 0 }))
                  }
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="max_storage_gb" className="text-xs font-semibold">
                  Storage Cap (GB)
                </Label>
                <Input
                  id="max_storage_gb"
                  type="number"
                  min="1"
                  max="10000"
                  value={limitForm.max_storage_gb}
                  onChange={e => setLimitForm(prev => ({ ...prev, max_storage_gb: parseInt(e.target.value, 10) || 1 }))}
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="max_members" className="text-xs font-semibold">
                  Team Members Limit
                </Label>
                <Input
                  id="max_members"
                  type="number"
                  min="1"
                  max="1000"
                  value={limitForm.max_members}
                  onChange={e => setLimitForm(prev => ({ ...prev, max_members: parseInt(e.target.value, 10) || 1 }))}
                  className="h-9 text-xs"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2.5 pt-3 border-t border-border/70">
              <Button type="button" variant="outline" size="sm" onClick={() => setIsEditingLimits(false)}>
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={savingLimits} onClick={handleSaveLimits}>
                {savingLimits && <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />}
                Save Quota Allocation
              </Button>
            </div>
          </motion.form>
        )}
      </AnimatePresence>

      {/* Main Resource Cards */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Token Consumption */}
        <motion.div
          initial={shouldReduceMotion ? false : { opacity: 0, y: 10 }}
          animate={shouldReduceMotion ? false : { opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
        >
          <Card className="p-6 border border-border/80 shadow-xs hover:border-border transition-colors">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2.5 bg-primary/10 rounded-lg text-primary">
                <Zap className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-semibold text-base text-foreground">Inference Token Consumption</h3>
                <p className="text-xs text-muted-foreground">Monthly LLM tokens utilized across workspace sessions</p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-end justify-between">
                <div>
                  <div className="text-3xl font-bold tracking-tight text-foreground font-mono">
                    {(usedTokens / 1000000).toFixed(2)}M
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">Tokens consumed this billing period</div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-medium font-mono">Ceiling: {(effectiveTokenLimit / 1000000).toFixed(1)}M</div>
                  <div
                    className={cn(
                      'text-xs font-semibold font-mono',
                      isCritical ? 'text-destructive' : isWarning ? 'text-amber-500' : 'text-emerald-500'
                    )}
                  >
                    {Math.max(0, effectiveTokenLimit - usedTokens).toLocaleString()} tokens remaining
                  </div>
                </div>
              </div>

              <div className="h-2.5 w-full bg-muted/60 rounded-full overflow-hidden">
                <div
                  className={cn(
                    'h-full transition-all duration-1000 ease-out',
                    isCritical ? 'bg-destructive' : isWarning ? 'bg-amber-500' : 'bg-primary'
                  )}
                  style={{ width: `${Math.min(100, Math.max(0, usagePct))}%` }}
                />
              </div>

              {isCritical && (
                <div className="p-3 bg-destructive/10 text-destructive text-xs rounded-md border border-destructive/20 flex gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                  <p>Warning: Workspace inference token consumption has exceeded 95% of allocated capacity.</p>
                </div>
              )}
            </div>
          </Card>
        </motion.div>

        {/* Query Consumption */}
        <motion.div
          initial={shouldReduceMotion ? false : { opacity: 0, y: 10 }}
          animate={shouldReduceMotion ? false : { opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: 0.05 }}
        >
          <Card className="p-6 border border-border/80 shadow-xs hover:border-border transition-colors">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2.5 bg-indigo-500/10 rounded-lg text-indigo-400">
                <Activity className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-semibold text-base text-foreground">RAG Queries Processed</h3>
                <p className="text-xs text-muted-foreground">Retrieved grounded question answering operations</p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-end justify-between">
                <div>
                  <div className="text-3xl font-bold tracking-tight text-foreground font-mono">
                    {usedQueries.toLocaleString()}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">Queries executed this period</div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-medium font-mono">Limit: {effectiveQueryLimit.toLocaleString()}</div>
                  <div className="text-xs font-semibold text-emerald-500 font-mono">
                    {Math.max(0, effectiveQueryLimit - usedQueries).toLocaleString()} queries remaining
                  </div>
                </div>
              </div>

              <div className="h-2.5 w-full bg-muted/60 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-500 transition-all duration-1000 ease-out"
                  style={{ width: `${Math.min(100, Math.max(0, queryUsagePct))}%` }}
                />
              </div>
            </div>
          </Card>
        </motion.div>
      </div>

      {/* Governance & Capacity Breakdown */}
      <div className="grid gap-6 md:grid-cols-3">
        <motion.div
          initial={shouldReduceMotion ? false : { opacity: 0, y: 10 }}
          animate={shouldReduceMotion ? false : { opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: 0.1 }}
        >
          <Card className="p-5 border border-border/80 shadow-xs hover:border-border transition-colors">
            <div className="flex items-center gap-2 mb-2">
              <Database className="h-4 w-4 text-primary" />
              <span className="text-sm font-medium text-foreground">Vector & Knowledge Storage</span>
            </div>
            <div className="text-2xl font-bold mt-1 text-foreground font-mono">
              {settingsData?.settings?.limits?.max_storage_gb ?? 100} GB
            </div>
            <p className="text-xs text-muted-foreground mt-1">Tenant document index capacity</p>
          </Card>
        </motion.div>

        <motion.div
          initial={shouldReduceMotion ? false : { opacity: 0, y: 10 }}
          animate={shouldReduceMotion ? false : { opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: 0.15 }}
        >
          <Card className="p-5 border border-border/80 shadow-xs hover:border-border transition-colors">
            <div className="flex items-center gap-2 mb-2">
              <Users className="h-4 w-4 text-primary" />
              <span className="text-sm font-medium text-foreground">Team Member Cap</span>
            </div>
            <div className="text-2xl font-bold mt-1 text-foreground font-mono">
              {settingsData?.settings?.limits?.max_members ?? 50} Members
            </div>
            <p className="text-xs text-muted-foreground mt-1">Maximum active seats allocated</p>
          </Card>
        </motion.div>

        <motion.div
          initial={shouldReduceMotion ? false : { opacity: 0, y: 10 }}
          animate={shouldReduceMotion ? false : { opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: 0.2 }}
        >
          <Card className="p-5 border border-border/80 shadow-xs hover:border-border transition-colors">
            <div className="flex items-center gap-2 mb-2">
              <Server className="h-4 w-4 text-primary" />
              <span className="text-sm font-medium text-foreground">Policy Enforcement</span>
            </div>
            <div className="flex items-center gap-1.5 mt-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              <span className="text-sm font-semibold text-foreground">
                {quota?.is_hard_enforced ? 'Hard Enforcement' : 'Soft Warning (Telemetry)'}
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">Automatic throttling on budget depletion</p>
          </Card>
        </motion.div>
      </div>
    </div>
  )
}
