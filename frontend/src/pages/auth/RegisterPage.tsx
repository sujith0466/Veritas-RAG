import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { RoleSelector, AIAssistant, AdminRegisterForm, UserRegisterForm, WorkspaceLoader, type AIAssistantState } from '@/components/auth'
import { ArrowLeft } from 'lucide-react'

export function RegisterPage() {
  const [searchParams] = useSearchParams()
  const initialRole = (searchParams.get('role') as 'admin' | 'user' | null) || null
  const [selectedRole, setSelectedRole] = useState<'admin' | 'user' | null>(initialRole)
  const [aiState, setAiState] = useState<AIAssistantState>('idle')
  const [isSuccess, setIsSuccess] = useState(false)
  const navigate = useNavigate()

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
    navigate('/dashboard')
  }

  return (
    <div className="flex flex-col items-center w-full">
      <div className="mb-8 w-full flex justify-center">
        <AIAssistant state={aiState} />
      </div>

      <div className="w-full relative min-h-[550px]">
        <AnimatePresence mode="wait">
          {isSuccess ? (
            <motion.div
              key="loader"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0"
            >
              <WorkspaceLoader onComplete={handleLoaderComplete} />
            </motion.div>
          ) : !selectedRole ? (
            <motion.div
              key="selector"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="absolute inset-0"
            >
              <RoleSelector mode="register" onSelect={setSelectedRole} />
              
              <div className="text-center text-sm mt-8">
                <span className="text-muted-foreground">Already have an account? </span>
                <Link
                  to="/auth/login"
                  className="font-medium text-primary hover:underline outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-sm"
                >
                  Sign in
                </Link>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="form"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="absolute inset-0"
            >
              <button 
                onClick={() => setSelectedRole(null)}
                className="flex items-center text-sm text-muted-foreground hover:text-foreground transition-colors mb-4"
              >
                <ArrowLeft className="h-4 w-4 mr-1" />
                Back to roles
              </button>
              
              <div className="space-y-2 mb-6">
                <h2 className="text-2xl font-semibold tracking-tight text-foreground">
                  {selectedRole === 'admin' ? 'Admin Registration' : 'User Registration'}
                </h2>
                <p className="text-sm text-muted-foreground">
                  {selectedRole === 'admin' 
                    ? 'Enter your details to create a new workspace'
                    : 'Enter your details and invitation code to join'}
                </p>
              </div>

              {selectedRole === 'admin' ? (
                <AdminRegisterForm 
                  onFocusChange={handleFocusChange}
                  onSuccess={handleSuccess}
                  onError={handleError}
                />
              ) : (
                <UserRegisterForm 
                  onFocusChange={handleFocusChange}
                  onSuccess={handleSuccess}
                  onError={handleError}
                />
              )}

              <div className="text-center text-sm mt-6">
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
