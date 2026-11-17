import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { AuthBranding, IdentityRegisterForm, type AIAssistantState } from '@/components/auth'
import { MailCheck, AlertCircle, ArrowRight, ShieldCheck } from 'lucide-react'

export function RegisterPage() {
  const [aiState, setAiState] = useState<AIAssistantState>('idle')
  const [isSuccess, setIsSuccess] = useState(false)
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const roleParam = searchParams.get('role')
  const isAdminRegistration = roleParam === 'admin'

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
    // Navigate to login after registration email dispatch
    navigate('/auth/login')
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
              className="w-full"
            >
              <div className="flex flex-col items-center justify-center py-8 text-center space-y-4">
                <div className="h-16 w-16 bg-primary/10 rounded-full flex items-center justify-center mb-4">
                  <MailCheck className="h-8 w-8 text-primary" />
                </div>
                <h2 className="text-2xl font-semibold tracking-tight text-foreground">Check your email</h2>
                <p className="text-muted-foreground max-w-sm">
                  We've sent a verification link to your email address. Please verify your account to continue.
                </p>
                <button
                  onClick={handleLoaderComplete}
                  className="mt-8 px-4 py-2 bg-primary text-primary-foreground hover:bg-primary/90 rounded-md font-medium transition-colors"
                >
                  Return to Login
                </button>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="form"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="w-full"
            >
              {isAdminRegistration ? (
                <div className="space-y-1.5 mb-5">
                  <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary mb-1">
                    <ShieldCheck className="h-3.5 w-3.5" />
                    <span>Administrator Registration</span>
                  </div>
                  <h2 className="text-2xl font-semibold tracking-tight text-foreground">
                    Create admin account
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    Register your identity to provision a new workspace as an administrator.
                  </p>
                </div>
              ) : (
                <div className="space-y-3 mb-5">
                  <div className="space-y-1.5">
                    <h2 className="text-2xl font-semibold tracking-tight text-foreground">
                      Create your account
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      Register your individual identity to access Veritas RAG.
                    </p>
                  </div>

                  {/* Explanatory Notice Banner for Regular Registration */}
                  <div
                    role="alert"
                    aria-label="workspace-creation-notice"
                    className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-3.5 text-sm text-amber-900 dark:text-amber-200"
                  >
                    <div className="flex items-start gap-2.5">
                      <AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                      <div className="space-y-2">
                        <div>
                          <p className="font-medium text-amber-800 dark:text-amber-300">
                            Workspace creation is not supported through regular user registration.
                          </p>
                          <p className="text-xs text-muted-foreground mt-1">
                            Regular registration creates an individual user identity only and cannot create or register a workspace. To provision a workspace as an administrator, proceed to Admin Registration.
                          </p>
                        </div>
                        <div className="pt-1 flex flex-wrap gap-2 items-center">
                          <Link
                            to="/auth/register?role=admin"
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
                          >
                            <span>Register as Admin to Create Workspace</span>
                            <ArrowRight className="h-3.5 w-3.5" />
                          </Link>
                          <Link
                            to="/workspaces/join"
                            className="inline-flex items-center text-xs text-muted-foreground hover:text-foreground underline transition-colors"
                          >
                            Joining an existing workspace?
                          </Link>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <IdentityRegisterForm
                onFocusChange={handleFocusChange}
                onSuccess={handleSuccess}
                onError={handleError}
              />

              {isAdminRegistration && (
                <div className="text-center text-xs text-muted-foreground mt-3">
                  Looking for regular user registration?{' '}
                  <Link
                    to="/auth/register"
                    className="font-medium text-primary hover:underline"
                  >
                    Switch to Regular Registration
                  </Link>
                </div>
              )}

              <div className="text-center text-sm mt-5">
                <span className="text-muted-foreground">Already have an account? </span>
                <Link
                  to="/auth/login"
                  className="font-medium text-primary hover:underline outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-sm"
                >
                  Sign in
                </Link>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
