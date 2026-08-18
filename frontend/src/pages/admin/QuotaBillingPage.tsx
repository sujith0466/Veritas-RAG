import { useState, useEffect } from 'react'
import { Zap, Server, AlertTriangle } from 'lucide-react'
import { adminService, TenantQuota } from '@/services/adminService'
import { useAuthStore } from '@/stores/authStore'
import { cn } from '@/utils/cn'

export function QuotaBillingPage() {
  const [quota, setQuota] = useState<TenantQuota | null>(null)
  const [loading, setLoading] = useState(true)
  const user = useAuthStore(s => s.user)
  const tenantId = user?.tenant_id || user?.workspace_name || (user as any)?.workspace_id

  useEffect(() => {
    const fetchQuota = async () => {
      if (!tenantId) {
        setLoading(false)
        return
      }
      setLoading(true)
      try {
        const data = await adminService.getQuota(tenantId)
        setQuota(data)
      } catch (e) {
        console.error('Failed to load quota', e)
      } finally {
        setLoading(false)
      }
    }
    fetchQuota()
  }, [tenantId])

  if (loading) {
    return (
      <div className="flex h-[400px] items-center justify-center">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!quota) {
    return (
      <div className="p-12 flex flex-col items-center text-center bg-card border border-border rounded-lg">
        <AlertTriangle className="h-8 w-8 text-destructive mb-4" />
        <h3 className="font-medium text-lg">Unable to load quota data</h3>
        <p className="text-sm text-muted-foreground mt-1 max-w-sm">
          Please check your connection and try again later.
        </p>
      </div>
    )
  }

  const usagePct = ((quota.monthly_token_limit - quota.remaining_tokens) / quota.monthly_token_limit) * 100
  const isWarning = usagePct >= quota.warning_threshold_pct * 100
  const isCritical = usagePct >= 95

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Quota & Billing</h2>
        <p className="text-muted-foreground">
          Manage workspace token limits and billing subscriptions.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-primary/10 rounded-md text-primary">
              <Zap className="h-5 w-5" />
            </div>
            <h3 className="font-medium text-lg">Token Usage</h3>
          </div>

          <div className="space-y-4">
            <div className="flex items-end justify-between">
              <div>
                <div className="text-3xl font-bold">
                  {((quota.monthly_token_limit - quota.remaining_tokens) / 1000000).toFixed(1)}M
                </div>
                <div className="text-sm text-muted-foreground">Tokens used this month</div>
              </div>
              <div className="text-right">
                <div className="text-sm font-medium">Limit: {(quota.monthly_token_limit / 1000000).toFixed(1)}M</div>
                <div className={cn(
                  "text-xs font-medium",
                  isCritical ? "text-destructive" : isWarning ? "text-amber-500" : "text-emerald-500"
                )}>
                  {quota.remaining_tokens.toLocaleString()} remaining
                </div>
              </div>
            </div>

            <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
              <div
                className={cn(
                  "h-full transition-all duration-1000 ease-out",
                  isCritical ? "bg-destructive" : isWarning ? "bg-amber-500" : "bg-primary"
                )}
                style={{ width: `${Math.min(100, Math.max(0, usagePct))}%` }}
              />
            </div>

            {isCritical && (
              <div className="p-3 bg-destructive/10 text-destructive text-sm rounded-md border border-destructive/20 flex gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                <p>Critical limit reached. Inference may be suspended soon.</p>
              </div>
            )}
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-primary/10 rounded-md text-primary">
              <Server className="h-5 w-5" />
            </div>
            <h3 className="font-medium text-lg">Current Plan</h3>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-3xl font-bold">Enterprise</div>
                <div className="text-sm text-muted-foreground">Self-hosted license</div>
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold">${quota.monthly_budget_usd.toFixed(2)}</div>
                <div className="text-xs text-muted-foreground">/ month</div>
              </div>
            </div>

            <div className="space-y-2 text-sm pt-4 border-t border-border">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Hard enforcement</span>
                <span className="font-medium">{quota.is_hard_enforced ? 'Enabled' : 'Disabled'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Warning threshold</span>
                <span className="font-medium">{quota.warning_threshold_pct * 100}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
