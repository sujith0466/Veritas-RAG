import React, { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Building2,
  PlusCircle,
  KeyRound,
  LogOut,
  Shield,
  ArrowRight,
  AlertCircle,
  Loader2,
  CheckCircle2,
} from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { workspaceService } from '@/services/workspaceService'
import { useAuth } from '@/hooks/useAuth'
import type { UserWorkspaceMembership } from '@/types'

export function WorkspaceOnboardingPage(): React.JSX.Element {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { logout } = useAuth()
  const user = useAuthStore((s) => s.user)
  const currentWorkspace = useWorkspaceStore((s) => s.currentWorkspace)
  const switchWorkspace = useWorkspaceStore((s) => s.switchWorkspace)

  const [isLoading, setIsLoading] = useState(true)
  const [isSwitching, setIsSwitching] = useState<string | null>(null)
  const [existingMemberships, setExistingMemberships] = useState<UserWorkspaceMembership[]>([])
  const [error, setError] = useState<string | null>(null)

  // Transient capture of onboarding query parameters (never logged or persisted to localStorage)
  const joinCodeParam = searchParams.get('join_code')
  const invitationTokenParam = searchParams.get('invitation_token')
  const intentIdParam = searchParams.get('intent_id')

  useEffect(() => {
    // If the user already has an active workspace established, bridge directly into dashboard
    if (currentWorkspace?.id || user?.tenant_id) {
      navigate('/dashboard', { replace: true })
      return
    }

    let isMounted = true

    async function loadMemberships() {
      setIsLoading(true)
      setError(null)
      try {
        const response = await workspaceService.getUserWorkspaces()
        if (isMounted && response?.items) {
          setExistingMemberships(response.items)
        }
      } catch (err: any) {
        // If 401 or network error, let the route guard or user retry
        if (isMounted) {
          setError(err?.response?.data?.detail || 'Unable to query workspace memberships.')
        }
      } finally {
        if (isMounted) {
          setIsLoading(false)
        }
      }
    }

    loadMemberships()

    return () => {
      isMounted = false
    }
  }, [currentWorkspace, user?.tenant_id, navigate])

  const handleSwitch = async (workspaceId: string) => {
    setIsSwitching(workspaceId)
    setError(null)
    try {
      await switchWorkspace(workspaceId)
      navigate('/dashboard', { replace: true })
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to activate selected workspace.')
    } finally {
      setIsSwitching(null)
    }
  }

  const handleLogout = async () => {
    await logout()
    navigate('/auth/login', { replace: true })
  }

  if (isLoading) {
    return (
      <div className="flex h-screen w-full flex-col items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3 text-muted-foreground animate-pulse-subtle">
          <Shield className="h-8 w-8 text-primary/60" />
          <p className="text-sm font-medium tracking-wide">Loading workspace onboarding...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-between p-4 sm:p-6 text-slate-100 selection:bg-indigo-500/30">
      {/* Top Navigation Bar */}
      <header className="w-full max-w-5xl mx-auto flex items-center justify-between py-4 border-b border-slate-800/80">
        <div className="flex items-center space-x-3">
          <div className="h-9 w-9 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <Shield className="h-5 w-5" />
          </div>
          <div>
            <span className="font-semibold text-white tracking-tight">Veritas RAG</span>
            <span className="ml-2 text-xs font-mono uppercase bg-indigo-950/60 text-indigo-400 px-2 py-0.5 rounded border border-indigo-800/40">
              Onboarding
            </span>
          </div>
        </div>

        <div className="flex items-center space-x-4 text-xs text-slate-400">
          <span className="hidden sm:inline-block">Signed in as <strong className="text-slate-200">{user?.email}</strong></span>
          <button
            onClick={handleLogout}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:text-white hover:bg-slate-800/80 transition-colors"
          >
            <LogOut className="h-3.5 w-3.5" />
            <span>Sign Out</span>
          </button>
        </div>
      </header>

      {/* Main Bridge Container */}
      <main className="w-full max-w-3xl mx-auto my-auto py-8">
        <div className="text-center mb-8 space-y-2">
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-white">
            Workspace Onboarding
          </h1>
          <p className="text-sm sm:text-base text-slate-400 max-w-lg mx-auto">
            You do not currently have an active workspace session. Choose an option below to enter Veritas RAG.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-xl bg-red-950/40 border border-red-800/50 flex items-start space-x-3 text-red-200">
            <AlertCircle className="h-5 w-5 text-red-400 shrink-0 mt-0.5" />
            <div className="text-sm">{error}</div>
          </div>
        )}

        {/* Transient parameter indicators */}
        {(joinCodeParam || invitationTokenParam || intentIdParam) && (
          <div className="mb-6 p-4 rounded-xl bg-indigo-950/40 border border-indigo-800/50 flex items-start space-x-3 text-indigo-200">
            <CheckCircle2 className="h-5 w-5 text-indigo-400 shrink-0 mt-0.5" />
            <div className="text-xs leading-relaxed">
              <strong>Pending Join Context Detected:</strong> We detected an invitation or join context for your session. Proceed to join to complete enrollment.
            </div>
          </div>
        )}

        {/* Existing Inactive Memberships */}
        {existingMemberships.length > 0 && (
          <div className="mb-8 p-6 rounded-2xl bg-slate-900/80 border border-slate-800 backdrop-blur shadow-xl">
            <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4 flex items-center gap-2">
              <Building2 className="h-4 w-4 text-indigo-400" />
              Existing Workspace Memberships
            </h2>
            <div className="space-y-3">
              {existingMemberships.map((membership) => (
                <div
                  key={membership.workspace_id}
                  className="flex items-center justify-between p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/70 hover:border-indigo-500/40 transition-colors"
                >
                  <div>
                    <div className="font-medium text-white flex items-center gap-2">
                      {membership.name}
                      {membership.public_id && (
                        <span className="text-xs font-mono text-slate-400 bg-slate-800/60 px-1.5 py-0.5 rounded">
                          {membership.public_id}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5">
                      Role: <span className="capitalize font-medium text-slate-300">{membership.role}</span> &bull; Status: {membership.status}
                    </div>
                  </div>

                  <button
                    onClick={() => handleSwitch(membership.workspace_id)}
                    disabled={isSwitching === membership.workspace_id}
                    className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition-colors disabled:opacity-50"
                  >
                    {isSwitching === membership.workspace_id ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span>Activating...</span>
                      </>
                    ) : (
                      <>
                        <span>Activate Session</span>
                        <ArrowRight className="h-3.5 w-3.5" />
                      </>
                    )}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Pathway Selection Grid (Bridge to WS-A8) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {/* Pathway 1: Create Workspace */}
          <div
            onClick={() => navigate('/workspaces/new')}
            className="group cursor-pointer p-6 rounded-2xl bg-slate-900/60 hover:bg-slate-900/90 border border-slate-800 hover:border-indigo-500/50 transition-all duration-200 shadow-lg flex flex-col justify-between"
          >
            <div>
              <div className="h-12 w-12 rounded-xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-4 group-hover:scale-105 transition-transform">
                <PlusCircle className="h-6 w-6" />
              </div>
              <h3 className="text-lg font-semibold text-white group-hover:text-indigo-300 transition-colors">
                Create a Workspace
              </h3>
              <p className="text-xs sm:text-sm text-slate-400 mt-2 leading-relaxed">
                Set up a new isolated organization or team workspace to ingest proprietary knowledge, manage members, and query AI assistants.
              </p>
            </div>
            <div className="mt-6 flex items-center text-xs font-medium text-indigo-400 group-hover:translate-x-1 transition-transform">
              <span>Create new workspace</span>
              <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
            </div>
          </div>

          {/* Pathway 2: Join Existing Workspace */}
          <div
            onClick={() => {
              if (invitationTokenParam) {
                navigate(`/invitations/accept?token=${encodeURIComponent(invitationTokenParam)}`)
              } else {
                // In WS-A8, opens join modal. For now, bridges to invitation accept or join endpoint
                navigate('/invitations/accept')
              }
            }}
            className="group cursor-pointer p-6 rounded-2xl bg-slate-900/60 hover:bg-slate-900/90 border border-slate-800 hover:border-indigo-500/50 transition-all duration-200 shadow-lg flex flex-col justify-between"
          >
            <div>
              <div className="h-12 w-12 rounded-xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-4 group-hover:scale-105 transition-transform">
                <KeyRound className="h-6 w-6" />
              </div>
              <h3 className="text-lg font-semibold text-white group-hover:text-indigo-300 transition-colors">
                Join with Code or Invite
              </h3>
              <p className="text-xs sm:text-sm text-slate-400 mt-2 leading-relaxed">
                Connect to an existing workspace using a 6-character Join Code (VR-XXXXXX) or a direct cryptographic invitation token.
              </p>
            </div>
            <div className="mt-6 flex items-center text-xs font-medium text-indigo-400 group-hover:translate-x-1 transition-transform">
              <span>Join existing workspace</span>
              <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="w-full max-w-5xl mx-auto text-center py-4 border-t border-slate-800/60 text-xs text-slate-500">
        Veritas RAG &bull; Enterprise Multi-Tenant AI Infrastructure &bull; Zero Trust Identity
      </footer>
    </div>
  )
}
export default WorkspaceOnboardingPage
