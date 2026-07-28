import * as React from 'react'
import { useState, useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import { dashboardService } from '@/services/dashboardService'
import { userService } from '@/services/userService'
import { useAuthStore } from '@/stores/authStore'
import { PageTransition } from '@/components/layouts'
import { Shield, RefreshCw } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { OnboardingWizard } from '@/pages/dashboard/OnboardingWizard'

export function PostAuthenticationRouteResolver(): React.JSX.Element | null {
  const [isResolved, setIsResolved] = useState(false)
  const [isWorkspaceEmpty, setIsWorkspaceEmpty] = useState<boolean | null>(null)
  const [error, setError] = useState<string | null>(null)
  
  const user = useAuthStore(s => s.user)
  const updateUser = useAuthStore(s => s.updateUser)

  const resolveWorkspaceState = React.useCallback(async () => {
    // If the user already completed onboarding, skip all checks
    if (user?.workspace_settings?.onboarding_completed) {
      setIsWorkspaceEmpty(false)
      setIsResolved(true)
      return
    }

    setError(null)
    try {
      // For backward compatibility: if onboarding_completed is missing/false,
      // we check if documents exist.
      const kiSummary = await dashboardService.getKnowledgeIntelligenceSummary()
      const hasDocuments = kiSummary.total_documents > 0
      
      if (hasDocuments) {
        // Lazy migration for existing workspaces
        try {
          const updatedSettings = { ...user?.workspace_settings, onboarding_completed: true }
          await userService.updateWorkspace({ workspace_settings: updatedSettings })
          updateUser({ workspace_settings: updatedSettings })
        } catch (e) {
          console.error('Failed to lazily migrate onboarding status', e)
        }
        setIsWorkspaceEmpty(false)
      } else {
        setIsWorkspaceEmpty(true)
      }
    } catch (err) {
      console.error('Failed to resolve workspace state:', err)
      setError('Unable to fetch workspace status. Please check your connection.')
    } finally {
      setIsResolved(true)
    }
  }, [user, updateUser])

  useEffect(() => {
    resolveWorkspaceState()
  }, [resolveWorkspaceState])

  if (!isResolved) {
    // Render a subtle loading state while resolving routing decisions
    return (
      <div className="flex h-screen w-full flex-col items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4 text-muted-foreground animate-pulse-subtle">
          <Shield className="h-8 w-8 text-primary/40" />
          <p className="text-sm font-medium tracking-wide">Resolving workspace environment...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-screen w-full flex-col items-center justify-center bg-background p-8 text-center space-y-4">
        <div className="h-16 w-16 rounded-full bg-danger/10 flex items-center justify-center">
          <Shield className="h-8 w-8 text-danger" />
        </div>
        <h2 className="text-xl font-bold text-foreground">Workspace Resolution Failed</h2>
        <p className="text-sm text-muted-foreground">{error}</p>
        <Button variant="outline" onClick={() => { setIsResolved(false); resolveWorkspaceState(); }}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Retry
        </Button>
      </div>
    )
  }

  if (isWorkspaceEmpty) {
    // If the workspace is empty, force the onboarding/setup experience
    if (user?.role === 'admin') {
      return (
        <PageTransition>
          <OnboardingWizard onComplete={() => resolveWorkspaceState()} />
        </PageTransition>
      )
    } else {
      return (
        <PageTransition>
          <div className="flex h-screen w-full flex-col items-center justify-center bg-background text-center p-8 space-y-4">
            <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center">
              <Shield className="h-8 w-8 text-primary" />
            </div>
            <h2 className="text-2xl font-bold text-foreground">Welcome to {user?.workspace_name || 'RAGuard AI'}</h2>
            <p className="text-muted-foreground max-w-md">
              Your workspace is currently being set up by an administrator.
              Once knowledge sources are connected and ingested, your intelligence dashboards will become active.
            </p>
            <Button variant="outline" onClick={() => { setIsResolved(false); resolveWorkspaceState(); }} className="mt-4">
              <RefreshCw className="h-4 w-4 mr-2" />
              Check Status
            </Button>
          </div>
        </PageTransition>
      )
    }
  }

  // Once all protected state checks pass, render the requested route
  return <Outlet />
}
