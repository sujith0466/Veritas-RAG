import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { AuthBranding, LoginForm, WorkspaceLoader, type AIAssistantState } from '@/components/auth'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { getSafeRedirectUrl } from '@/utils/redirect'

export function LoginPage() {
  const [aiState, setAiState] = useState<AIAssistantState>('idle')
  const [isSuccess, setIsSuccess] = useState(false)
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const handleFocusChange = (field: 'email' | 'password' | 'password_visible' | 'idle') => {
    if (isSuccess || aiState === 'loading' || aiState === 'error') return
    if (field === 'email') setAiState('email_focus')
    else if (field === 'password') setAiState('password_focus')
    else if (field === 'password_visible') setAiState('password_visible')
    else setAiState('idle')
  }

  const handleError = () => {
    setAiState('error')
    setTimeout(() => {
      setAiState('idle')
    }, 2000)
  }

  const handleSuccess = () => {
    setAiState('success')
    setIsSuccess(true)
  }

  const handleLoaderComplete = () => {
    const user = useAuthStore.getState().user
    const currentWorkspace = useWorkspaceStore.getState().currentWorkspace
    const hasWorkspace = !!(user?.tenant_id || user?.workspace_id || currentWorkspace)

    if (!hasWorkspace) {
      navigate('/onboarding', { replace: true })
    } else {
      const redirectTarget = getSafeRedirectUrl(searchParams.get('redirect'), '/dashboard')
      navigate(redirectTarget, { replace: true })
    }
  }

  return (
    <div className="flex flex-col items-center w-full">
      <div className="mb-6 w-full flex justify-center relative z-20">
        <AuthBranding state={aiState} />
      </div>

      <div className="w-full relative">
        <AnimatePresence mode="wait">
          {isSuccess ? (
            <motion.div
              key="loader"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              className="w-full flex flex-col items-center justify-center py-8"
            >
              <WorkspaceLoader onComplete={handleLoaderComplete} />
            </motion.div>
          ) : (
            <motion.div
              key="form"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="w-full"
            >
              <div className="space-y-1.5 mb-5">
                <h2 className="text-2xl font-semibold tracking-tight text-foreground">
                  Welcome back
                </h2>
                <p className="text-sm text-muted-foreground">
                  Enter your credentials to access your workspace
                </p>
              </div>

              <LoginForm
                onFocusChange={handleFocusChange}
                onSuccess={handleSuccess}
                onError={handleError}
              />

              <div className="text-center text-sm mt-5">
                <span className="text-muted-foreground">Don&apos;t have an account? </span>
                <Link
                  to="/auth/register"
                  className="font-medium text-primary hover:underline outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-sm"
                >
                  Sign up
                </Link>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
