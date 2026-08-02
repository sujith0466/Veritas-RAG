import { useEffect, useState, useRef } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { authService } from '@/services/auth/authService'
import { CheckCircle2, XCircle, Loader2, ArrowRight, Mail } from 'lucide-react'
import { motion } from 'framer-motion'

type VerificationState = 'loading' | 'success' | 'invalid' | 'expired' | 'error'

export function VerifyPage() {
  const [searchParams] = useSearchParams()
  const email = searchParams.get('email')
  const token = searchParams.get('token')
  
  const [status, setStatus] = useState<VerificationState>('loading')
  const initialized = useRef(false)

  useEffect(() => {
    if (!email || !token) {
      setStatus('invalid')
      return
    }

    if (initialized.current) return
    initialized.current = true

    const verify = async () => {
      try {
        await authService.verifyEmail(email, token)
        setStatus('success')
      } catch (error: any) {
        const msg = error?.response?.data?.message || error?.message || ""
        if (msg.toLowerCase().includes('expired')) {
          setStatus('expired')
        } else if (msg.toLowerCase().includes('invalid')) {
          setStatus('invalid')
        } else {
          setStatus('error')
        }
      }
    }

    verify()
  }, [email, token])

  const renderContent = () => {
    switch (status) {
      case 'loading':
        return (
          <>
            <Loader2 className="h-12 w-12 text-primary animate-spin mb-4" />
            <h2 className="text-2xl font-semibold tracking-tight">Verifying your email</h2>
            <p className="text-muted-foreground mt-2">Please wait while we confirm your email address...</p>
          </>
        )
      case 'success':
        return (
          <>
            <div className="h-16 w-16 bg-green-500/10 rounded-full flex items-center justify-center mb-4">
              <CheckCircle2 className="h-8 w-8 text-green-500" />
            </div>
            <h2 className="text-2xl font-semibold tracking-tight">Email Verified</h2>
            <p className="text-muted-foreground mt-2 mb-6 text-center max-w-sm">
              Your email address has been successfully verified. You can now log in to your account.
            </p>
            <Link
              to="/auth/login"
              className="px-6 py-2 bg-primary text-primary-foreground hover:bg-primary/90 rounded-md font-medium transition-colors flex items-center"
            >
              Go to Login <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </>
        )
      case 'expired':
        return (
          <>
            <div className="h-16 w-16 bg-amber-500/10 rounded-full flex items-center justify-center mb-4">
              <XCircle className="h-8 w-8 text-amber-500" />
            </div>
            <h2 className="text-2xl font-semibold tracking-tight">Link Expired</h2>
            <p className="text-muted-foreground mt-2 mb-6 text-center max-w-sm">
              This verification link has expired. Please request a new verification email.
            </p>
            <Link
              to={`/auth/resend-verification?email=${encodeURIComponent(email || '')}`}
              className="px-6 py-2 bg-primary text-primary-foreground hover:bg-primary/90 rounded-md font-medium transition-colors flex items-center"
            >
              <Mail className="ml-2 mr-2 h-4 w-4" /> Resend Email
            </Link>
          </>
        )
      default:
        return (
          <>
            <div className="h-16 w-16 bg-destructive/10 rounded-full flex items-center justify-center mb-4">
              <XCircle className="h-8 w-8 text-destructive" />
            </div>
            <h2 className="text-2xl font-semibold tracking-tight">Verification Failed</h2>
            <p className="text-muted-foreground mt-2 mb-6 text-center max-w-sm">
              The verification link is invalid or has already been used.
            </p>
            <Link
              to="/auth/login"
              className="px-6 py-2 border border-input hover:bg-accent hover:text-accent-foreground rounded-md font-medium transition-colors"
            >
              Return to Login
            </Link>
          </>
        )
    }
  }

  return (
    <div className="flex flex-col items-center justify-center w-full min-h-[400px]">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col items-center max-w-md w-full p-8 rounded-xl border border-border bg-card shadow-sm"
      >
        {renderContent()}
      </motion.div>
    </div>
  )
}
