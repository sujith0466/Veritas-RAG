import React, { useState, useEffect } from 'react'
import { KeyRound, Copy, Check, Loader2, AlertCircle, Clock, ShieldAlert, UserX, AlertTriangle, Info } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/common/Dialog'
import { workspaceService, buildWorkspaceJoinLink } from '@/services/workspaceService'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useAuthStore } from '@/stores/authStore'
import { formatDateDDMMYYYY } from '@/utils/formatters'
import type { WorkspaceJoinAccessResponse } from '@/types'

interface JoinAccessDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function JoinAccessDialog({ open, onOpenChange }: JoinAccessDialogProps) {
  const { currentWorkspace } = useWorkspaceStore()
  const { user } = useAuthStore()

  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<WorkspaceJoinAccessResponse | null>(null)
  const [copiedCode, setCopiedCode] = useState(false)
  const [copiedLink, setCopiedLink] = useState(false)

  const workspaceId = user?.workspace_id || user?.tenant_id || currentWorkspace?.id || ''

  useEffect(() => {
    if (!open || !workspaceId) return

    let isMounted = true
    setIsLoading(true)
    setError(null)
    setCopiedCode(false)
    setCopiedLink(false)

    workspaceService
      .getJoinAccess(workspaceId)
      .then((res) => {
        if (!isMounted) return
        setData(res)
      })
      .catch((err) => {
        if (!isMounted) return
        const msg = err.response?.data?.detail || err.message || 'Unable to retrieve workspace join access.'
        setError(msg)
      })
      .finally(() => {
        if (isMounted) setIsLoading(false)
      })

    return () => {
      isMounted = false
    }
  }, [open, workspaceId])

  const canonicalJoinLink = React.useMemo(() => {
    if (!data?.join_code) return ''
    const identifier = data.public_id || currentWorkspace?.public_id || currentWorkspace?.slug || workspaceId
    return buildWorkspaceJoinLink(identifier, data.join_code)
  }, [data, currentWorkspace, workspaceId])

  const handleCopyCode = async () => {
    if (!data?.join_code) return
    try {
      await navigator.clipboard.writeText(data.join_code)
      setCopiedCode(true)
      setTimeout(() => setCopiedCode(false), 2000)
    } catch {
      // fallback
    }
  }

  const handleCopyLink = async () => {
    if (!canonicalJoinLink) return
    try {
      await navigator.clipboard.writeText(canonicalJoinLink)
      setCopiedLink(true)
      setTimeout(() => setCopiedLink(false), 2000)
    } catch {
      // fallback
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md bg-surface-elevated border border-border shadow-2xl p-6">
        <DialogHeader className="text-left space-y-1.5 pb-2">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <KeyRound className="h-4 w-4" />
            </div>
            <DialogTitle className="text-lg font-bold text-foreground">
              Workspace Joining
            </DialogTitle>
          </div>
          <DialogDescription className="text-xs text-muted-foreground">
            Current active Join Code and invitation link for {data?.workspace_name || currentWorkspace?.name || 'this workspace'}.
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="py-12 flex flex-col items-center justify-center space-y-3">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
            <span className="text-xs text-muted-foreground font-mono">Loading active credentials...</span>
          </div>
        ) : error ? (
          <div className="p-4 rounded-xl bg-destructive/10 border border-destructive/20 flex items-start space-x-3 text-destructive text-xs">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        ) : data?.status === 'EXPIRED' ? (
          <div className="p-5 rounded-xl bg-amber-500/10 dark:bg-amber-950/20 border border-amber-500/30 text-center space-y-2">
            <Clock className="h-6 w-6 text-amber-500 mx-auto" />
            <h4 className="text-sm font-semibold text-foreground">Join Code Expired</h4>
            <p className="text-xs text-muted-foreground leading-relaxed">
              The join code created by <strong className="text-foreground">{data.creator_name || 'your administrator'}</strong> expired on{' '}
              <span className="font-mono font-medium text-foreground">{data.expires_at ? formatDateDDMMYYYY(data.expires_at) : 'recently'}</span>.
              Please contact <strong className="text-foreground">{data.creator_name || 'your administrator'}</strong> to request an updated code.
            </p>
          </div>
        ) : data?.status === 'REVOKED' ? (
          <div className="p-5 rounded-xl bg-slate-500/10 dark:bg-slate-900/30 border border-slate-500/30 text-center space-y-2">
            <AlertTriangle className="h-6 w-6 text-slate-500 mx-auto" />
            <h4 className="text-sm font-semibold text-foreground">Join Code Deactivated</h4>
            <p className="text-xs text-muted-foreground leading-relaxed">
              The join code created by <strong className="text-foreground">{data.creator_name || 'your administrator'}</strong> has been deactivated.
              Please contact <strong className="text-foreground">{data.creator_name || 'your administrator'}</strong> for an updated code.
            </p>
          </div>
        ) : data?.status === 'CREATOR_INELIGIBLE' ? (
          <div className="p-5 rounded-xl bg-rose-500/10 dark:bg-rose-950/20 border border-rose-500/30 text-center space-y-2">
            <UserX className="h-6 w-6 text-rose-500 mx-auto" />
            <h4 className="text-sm font-semibold text-foreground">Administrator Ineligible</h4>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Your originating administrator (<strong className="text-foreground">{data.creator_name || 'Administrator'}</strong>) is no longer eligible to manage workspace join credentials.
              Please contact the workspace owner.
            </p>
          </div>
        ) : data?.status === 'ATTRIBUTION_CONFLICT' ? (
          <div className="p-5 rounded-xl bg-rose-500/10 dark:bg-rose-950/20 border border-rose-500/30 text-center space-y-2">
            <ShieldAlert className="h-6 w-6 text-rose-500 mx-auto" />
            <h4 className="text-sm font-semibold text-foreground">Credential Sharing Suspended</h4>
            <p className="text-xs text-muted-foreground leading-relaxed">
              An attribution integrity conflict has been detected on your workspace membership. To safeguard workspace security, join credentials cannot be displayed.
              Please contact your workspace owner.
            </p>
          </div>
        ) : data?.status === 'ADMIN_MANAGEMENT_REQUIRED' ? (
          <div className="p-5 rounded-xl bg-primary/10 border border-primary/20 text-center space-y-2">
            <KeyRound className="h-6 w-6 text-primary mx-auto" />
            <h4 className="text-sm font-semibold text-foreground">Administrator Access</h4>
            <p className="text-xs text-muted-foreground leading-relaxed">
              {data.message || 'Administrators manage and rotate join codes directly in Workspace Settings. Plaintext recovery is disabled under single-reveal policy.'}
            </p>
            {data.code_display && (
              <div className="pt-2">
                <span className="font-mono text-xs font-semibold px-2.5 py-1 bg-surface rounded border border-border">
                  Current code: {data.code_display}
                </span>
              </div>
            )}
          </div>
        ) : data?.status === 'NO_ATTRIBUTION' ? (
          <div className="p-5 rounded-xl bg-muted/40 dark:bg-background/90 border border-border text-center space-y-2">
            <Info className="h-6 w-6 text-muted-foreground mx-auto" />
            <h4 className="text-sm font-semibold text-foreground">No Attribution Recorded</h4>
            <p className="text-xs text-muted-foreground leading-relaxed">
              No originating administrator attribution is recorded for your membership. Please contact your workspace administrator.
            </p>
          </div>
        ) : data?.status === 'NO_CODE_CONFIGURED' ? (
          <div className="p-5 rounded-xl bg-muted/40 dark:bg-background/90 border border-border text-center space-y-2">
            <Info className="h-6 w-6 text-muted-foreground mx-auto" />
            <h4 className="text-sm font-semibold text-foreground">No Code Configured</h4>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Your originating administrator (<strong className="text-foreground">{data.creator_name || 'Administrator'}</strong>) does not currently have an active join code configured.
            </p>
          </div>
        ) : !data?.join_code ? (
          <div className="p-5 rounded-xl bg-muted/40 dark:bg-background/90 border border-border text-center space-y-2">
            <AlertCircle className="h-6 w-6 text-muted-foreground mx-auto" />
            <h4 className="text-sm font-semibold text-foreground">No Active Join Code</h4>
            <p className="text-xs text-muted-foreground">
              There is currently no active Join Code configured for this workspace. A workspace administrator can generate one in Workspace Settings.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Current Join Code Box */}
            <div className="p-4 rounded-xl bg-muted/40 dark:bg-background/90 border border-primary/30 dark:border-border flex flex-col items-center justify-center space-y-2.5 shadow-inner">
              <span className="text-2xs font-semibold uppercase tracking-wider text-muted-foreground font-mono">
                Current Join Code
              </span>
              <div className="flex items-center gap-3">
                <span className="text-3xl font-extrabold tracking-widest text-primary dark:text-teal-400 font-mono select-all">
                  {data.join_code}
                </span>
                <button
                  type="button"
                  onClick={handleCopyCode}
                  aria-label="Copy join code"
                  title="Copy join code"
                  className="p-2 rounded-lg bg-background hover:bg-muted border border-border dark:bg-surface dark:hover:bg-muted dark:border-border text-foreground hover:text-primary dark:hover:text-teal-400 transition-colors focus:outline-none focus:ring-1 focus:ring-primary shadow-2xs"
                >
                  {copiedCode ? (
                    <Check className="h-4 w-4 text-emerald-500 dark:text-emerald-400" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>

            {/* Join Link Box */}
            <div className="p-4 rounded-xl bg-muted/40 dark:bg-background/90 border border-primary/30 dark:border-border space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-2xs font-semibold uppercase tracking-wider text-muted-foreground font-mono">
                  Join Link
                </span>
                <button
                  type="button"
                  onClick={handleCopyLink}
                  aria-label="Copy join link"
                  title="Copy join link"
                  className="p-1.5 rounded-lg bg-background hover:bg-muted border border-border dark:bg-surface dark:hover:bg-muted dark:border-border text-foreground hover:text-primary dark:hover:text-teal-400 transition-colors focus:outline-none focus:ring-1 focus:ring-primary shadow-2xs"
                >
                  {copiedLink ? (
                    <Check className="h-3.5 w-3.5 text-emerald-500 dark:text-emerald-400" />
                  ) : (
                    <Copy className="h-3.5 w-3.5" />
                  )}
                </button>
              </div>
              <p className="text-xs font-mono text-foreground break-all select-all leading-relaxed bg-background/50 dark:bg-surface/50 p-2 rounded-md border border-border/50">
                {canonicalJoinLink}
              </p>
            </div>

            {/* Expiration and Entrant Role Metadata */}
            <div className="flex items-center justify-between text-2xs text-muted-foreground px-1 pt-1">
              <span>
                Entrant Role:{' '}
                <span className="font-semibold text-foreground font-mono">
                  {data.default_role || 'MEMBER'}
                </span>
              </span>
              <span>
                {data.expires_at ? (
                  <>
                    Expires:{' '}
                    <span className="font-semibold text-foreground font-mono">
                      {formatDateDDMMYYYY(data.expires_at)}
                    </span>
                  </>
                ) : (
                  <span className="font-medium text-emerald-600 dark:text-emerald-400 font-mono">
                    Never expires
                  </span>
                )}
              </span>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
