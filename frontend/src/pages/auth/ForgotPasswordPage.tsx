import React, { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft,
  CheckCircle2,
  KeyRound,
  Lock,
  Mail,
  ShieldCheck,
  Eye,
  EyeOff,
  AlertCircle,
  RefreshCw,
} from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'

import { authService } from '@/services/auth/authService'
import { PasswordStrength } from '@/components/auth/PasswordStrength'
import { Button, Input, Label } from '@/components/common'

function maskEmail(email: string): string {
  if (!email || !email.includes('@')) return email
  const [local, domain] = email.split('@')
  if (local.length <= 1) return `${local}***@${domain}`
  return `${local[0]}***@${domain}`
}

export function ForgotPasswordPage() {
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1)
  const [email, setEmail] = useState('')
  const [otpDigits, setOtpDigits] = useState<string[]>(['', '', '', '', '', ''])
  const [resetToken, setResetToken] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [resendCooldown, setResendCooldown] = useState(60)

  const otpInputRefs = useRef<(HTMLInputElement | null)[]>([])

  // Resend countdown timer for step 2
  useEffect(() => {
    if (step !== 2 || resendCooldown <= 0) return
    const timer = setInterval(() => {
      setResendCooldown((prev) => Math.max(0, prev - 1))
    }, 1000)
    return () => clearInterval(timer)
  }, [step, resendCooldown])

  // Step 1: Request Recovery Code
  const handleRequestCode = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim()) return

    setError(null)
    setIsSubmitting(true)

    try {
      await authService.requestRecoveryCode(email.trim())
      setResendCooldown(60)
      setOtpDigits(['', '', '', '', '', ''])
      setStep(2)
    } catch (err: any) {
      setError(err?.message || 'Failed to dispatch verification code. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  // Handle segmented OTP input changes
  const handleOtpChange = (index: number, value: string) => {
    const cleanValue = value.replace(/[^0-9]/g, '')
    if (!cleanValue) {
      const updated = [...otpDigits]
      updated[index] = ''
      setOtpDigits(updated)
      return
    }

    const updated = [...otpDigits]
    if (cleanValue.length > 1) {
      // Pasted multiple digits
      const digits = cleanValue.slice(0, 6).split('')
      digits.forEach((d, i) => {
        if (i < 6) updated[i] = d
      })
      setOtpDigits(updated)
      const nextIndex = Math.min(5, digits.length)
      otpInputRefs.current[nextIndex]?.focus()
      return
    }

    updated[index] = cleanValue
    setOtpDigits(updated)

    if (index < 5 && cleanValue) {
      otpInputRefs.current[index + 1]?.focus()
    }
  }

  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !otpDigits[index] && index > 0) {
      otpInputRefs.current[index - 1]?.focus()
    }
  }

  const handleOtpPaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault()
    const pastedData = e.clipboardData.getData('text').replace(/[^0-9]/g, '').slice(0, 6)
    if (pastedData) {
      const updated = [...otpDigits]
      pastedData.split('').forEach((char, idx) => {
        if (idx < 6) updated[idx] = char
      })
      setOtpDigits(updated)
      const focusTarget = Math.min(5, pastedData.length)
      otpInputRefs.current[focusTarget]?.focus()
    }
  }

  // Step 2: Verify Recovery Code
  const handleVerifyCode = async (e: React.FormEvent) => {
    e.preventDefault()
    const otp = otpDigits.join('')
    if (otp.length !== 6) {
      setError('Please enter all 6 digits of your verification code.')
      return
    }

    setError(null)
    setIsSubmitting(true)

    try {
      const result = await authService.verifyRecoveryCode(email.trim(), otp)
      setResetToken(result.reset_token)
      setStep(3)
    } catch (err: any) {
      setError(err?.message || 'Invalid or expired verification code.')
    } finally {
      setIsSubmitting(false)
    }
  }

  // Resend code handler
  const handleResendCode = async () => {
    if (resendCooldown > 0 || isSubmitting) return
    setError(null)
    setIsSubmitting(true)
    try {
      await authService.requestRecoveryCode(email.trim())
      setResendCooldown(60)
      setOtpDigits(['', '', '', '', '', ''])
      otpInputRefs.current[0]?.focus()
    } catch (err: any) {
      setError(err?.message || 'Failed to resend verification code.')
    } finally {
      setIsSubmitting(false)
    }
  }

  // Step 3: Complete Password Reset
  const handleCompleteReset = async (e: React.FormEvent) => {
    e.preventDefault()
    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters long.')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    setError(null)
    setIsSubmitting(true)

    try {
      await authService.completePasswordReset(email.trim(), resetToken, newPassword)
      setStep(4)
    } catch (err: any) {
      setError(err?.message || 'Failed to reset password. The reset link may have expired.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="w-full max-w-md mx-auto space-y-6">
      <AnimatePresence mode="wait">
        {step === 1 && (
          <motion.div
            key="step1"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.2 }}
            className="space-y-6"
          >
            <div className="text-center space-y-2">
              <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary mb-1">
                <ShieldCheck className="h-6 w-6" />
              </div>
              <h1 className="text-2xl font-bold tracking-tight text-foreground">
                Reset your password
              </h1>
              <p className="text-sm text-muted-foreground">
                Enter your verified email address to receive a 6-digit recovery code.
              </p>
            </div>

            {error && (
              <div className="flex items-start gap-2 p-3 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg">
                <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleRequestCode} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="recovery-email">Email address</Label>
                <Input
                  id="recovery-email"
                  type="email"
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  leftIcon={<Mail className="h-4 w-4" />}
                  required
                  autoFocus
                />
              </div>

              <Button
                type="submit"
                className="w-full"
                isLoading={isSubmitting}
                disabled={isSubmitting || !email.trim()}
              >
                Send Recovery Code
              </Button>
            </form>

            <div className="text-center">
              <Link
                to="/auth/login"
                className="inline-flex items-center text-sm font-medium text-muted-foreground hover:text-foreground transition-colors group"
              >
                <ArrowLeft className="h-4 w-4 mr-1.5 transition-transform group-hover:-translate-x-1" />
                Back to login
              </Link>
            </div>
          </motion.div>
        )}

        {step === 2 && (
          <motion.div
            key="step2"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.2 }}
            className="space-y-6"
          >
            <div className="text-center space-y-2">
              <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary mb-1">
                <KeyRound className="h-6 w-6" />
              </div>
              <h1 className="text-2xl font-bold tracking-tight text-foreground">
                Enter verification code
              </h1>
              <p className="text-sm text-muted-foreground">
                We sent a 6-digit code to{' '}
                <span className="font-semibold text-foreground">{maskEmail(email)}</span>.
              </p>
            </div>

            {error && (
              <div className="flex items-start gap-2 p-3 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg">
                <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleVerifyCode} className="space-y-5">
              <div className="space-y-2">
                <Label className="text-center block text-xs uppercase tracking-wider text-muted-foreground">
                  6-Digit Verification Code
                </Label>
                <div className="flex justify-center gap-2" onPaste={handleOtpPaste}>
                  {otpDigits.map((digit, idx) => (
                    <input
                      key={idx}
                      ref={(el) => (otpInputRefs.current[idx] = el)}
                      type="text"
                      inputMode="numeric"
                      pattern="[0-9]*"
                      maxLength={1}
                      value={digit}
                      onChange={(e) => handleOtpChange(idx, e.target.value)}
                      onKeyDown={(e) => handleOtpKeyDown(idx, e)}
                      aria-label={`Digit ${idx + 1}`}
                      className="h-12 w-11 text-center font-mono text-xl font-bold rounded-lg border border-border bg-background text-foreground shadow-xs focus:border-primary focus:ring-2 focus:ring-primary/20 focus:outline-hidden transition-all"
                      autoFocus={idx === 0}
                    />
                  ))}
                </div>
              </div>

              <div className="flex items-center justify-between text-xs text-muted-foreground pt-1">
                <button
                  type="button"
                  onClick={() => {
                    setError(null)
                    setStep(1)
                  }}
                  className="hover:text-foreground transition-colors"
                >
                  Change email
                </button>
                {resendCooldown > 0 ? (
                  <span>Resend code in {resendCooldown}s</span>
                ) : (
                  <button
                    type="button"
                    onClick={handleResendCode}
                    disabled={isSubmitting}
                    className="font-medium text-primary hover:underline inline-flex items-center gap-1"
                  >
                    <RefreshCw className="h-3 w-3" />
                    Resend code
                  </button>
                )}
              </div>

              <Button
                type="submit"
                className="w-full"
                isLoading={isSubmitting}
                disabled={isSubmitting || otpDigits.join('').length !== 6}
              >
                Verify Code
              </Button>
            </form>
          </motion.div>
        )}

        {step === 3 && (
          <motion.div
            key="step3"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.2 }}
            className="space-y-6"
          >
            <div className="text-center space-y-2">
              <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary mb-1">
                <Lock className="h-6 w-6" />
              </div>
              <h1 className="text-2xl font-bold tracking-tight text-foreground">
                Set new password
              </h1>
              <p className="text-sm text-muted-foreground">
                Choose a strong password to protect your account.
              </p>
            </div>

            {error && (
              <div className="flex items-start gap-2 p-3 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg">
                <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleCompleteReset} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="new-password">New password</Label>
                <Input
                  id="new-password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  leftIcon={<Lock className="h-4 w-4" />}
                  rightIcon={
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="text-muted-foreground hover:text-foreground focus:outline-hidden"
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  }
                  required
                  autoFocus
                />
                <PasswordStrength password={newPassword} />
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirm-password">Confirm password</Label>
                <Input
                  id="confirm-password"
                  type={showConfirmPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  leftIcon={<Lock className="h-4 w-4" />}
                  rightIcon={
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      className="text-muted-foreground hover:text-foreground focus:outline-hidden"
                      aria-label={showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
                    >
                      {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  }
                  required
                />
              </div>

              <Button
                type="submit"
                className="w-full"
                isLoading={isSubmitting}
                disabled={isSubmitting || newPassword.length < 8 || newPassword !== confirmPassword}
              >
                Reset Password
              </Button>
            </form>
          </motion.div>
        )}

        {step === 4 && (
          <motion.div
            key="step4"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3 }}
            className="text-center space-y-6"
          >
            <div className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-500 mb-1">
              <CheckCircle2 className="h-10 w-10" />
            </div>

            <div className="space-y-2">
              <h1 className="text-2xl font-bold tracking-tight text-foreground">
                Password Reset Complete
              </h1>
              <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                Your password has been successfully updated. All previous active sessions have been revoked for your security.
              </p>
            </div>

            <div className="pt-2">
              <Link to="/auth/login" className="block w-full">
                <Button className="w-full">
                  Proceed to Login
                </Button>
              </Link>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
