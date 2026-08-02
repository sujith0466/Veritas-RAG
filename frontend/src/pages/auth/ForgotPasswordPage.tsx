import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { ShieldAlert, ArrowLeft, Mail, CheckCircle2, KeyRound, Lock } from 'lucide-react'
import { authService } from '@/services/auth/authService'
import { PasswordStrength } from '@/components/auth/PasswordStrength'

export function ForgotPasswordPage() {
  // Step 1: Email
  const [email, setEmail] = useState('')
  const [recoveryMethod, setRecoveryMethod] = useState<'LINK' | 'OTP' | null>(null)
  
  // Step 2: OTP
  const [otp, setOtp] = useState('')
  
  // Step 3: Reset
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const [step, setStep] = useState<1 | 2 | 3 | 4>(1) // 1: Email, 2: OTP Entry, 3: New Password, 4: Success
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleRequestLink = async (e: React.MouseEvent) => {
    e.preventDefault()
    if (!email) return
    setError(null)
    setIsSubmitting(true)
    setRecoveryMethod('LINK')

    try {
      await authService.forgotPassword(email)
      setStep(4) // Link success
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to request password reset')
      setRecoveryMethod(null)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleRequestOTP = async (e: React.MouseEvent) => {
    e.preventDefault()
    if (!email) return
    setError(null)
    setIsSubmitting(true)
    setRecoveryMethod('OTP')

    try {
      await authService.requestOTP(email)
      setStep(2) // Move to OTP entry
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to request OTP')
      setRecoveryMethod(null)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleVerifyOTP = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      await authService.verifyOTP(email, otp)
      setStep(3) // Move to New Password
    } catch (err: any) {
      setError(err.response?.data?.message || 'Invalid or expired OTP')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleResetPasswordOTP = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (newPassword !== confirmPassword) {
      setError("Passwords don't match")
      return
    }
    
    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters")
      return
    }

    setError(null)
    setIsSubmitting(true)

    try {
      await authService.resetPasswordOTP(email, otp, newPassword)
      setStep(4) // OTP Reset success
    } catch (err: any) {
      setError(err.response?.data?.message || 'Failed to reset password')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (step === 4) {
    if (recoveryMethod === 'LINK') {
      return (
        <div className="flex flex-col space-y-6 text-center">
          <div className="flex justify-center">
            <div className="h-16 w-16 bg-brand-50 rounded-full flex items-center justify-center">
              <CheckCircle2 className="h-8 w-8 text-brand-600" />
            </div>
          </div>
          
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">Check your email</h1>
            <p className="text-sm text-neutral-500 max-w-sm mx-auto">
              If an account exists for <span className="font-medium text-neutral-900">{email}</span>, you will receive a password reset link shortly.
            </p>
          </div>

          <div className="pt-4">
            <Link to="/auth/login" className="text-sm font-medium text-brand-600 hover:text-brand-500">
              Return to login
            </Link>
          </div>
        </div>
      )
    } else {
      return (
        <div className="flex flex-col space-y-6 text-center">
          <div className="flex justify-center">
            <div className="h-16 w-16 bg-brand-50 rounded-full flex items-center justify-center">
              <CheckCircle2 className="h-8 w-8 text-brand-600" />
            </div>
          </div>
          
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">Password Reset Complete</h1>
            <p className="text-sm text-neutral-500 max-w-sm mx-auto">
              Your password has been successfully updated. You can now log in with your new password.
            </p>
          </div>

          <div className="pt-4">
            <Link to="/auth/login" className="w-full flex justify-center items-center py-2 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-primary hover:bg-primary/90">
              Return to login
            </Link>
          </div>
        </div>
      )
    }
  }

  return (
    <div className="flex flex-col space-y-6">
      <div className="flex flex-col space-y-2 text-center">
        <div className="flex justify-center mb-2">
          <div className="h-12 w-12 bg-brand-50 rounded-xl flex items-center justify-center ring-1 ring-brand-100/50 shadow-inner">
            <ShieldAlert className="h-6 w-6 text-brand-600" />
          </div>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">Reset password</h1>
        <p className="text-sm text-neutral-500">
          {step === 1 && "Enter your email address to recover your account."}
          {step === 2 && `Enter the 6-digit code sent to ${email}`}
          {step === 3 && "Create a new secure password."}
        </p>
      </div>

      <div className="space-y-4">
        {error && (
          <div className="p-3 bg-red-50 text-red-600 text-sm rounded-lg border border-red-100">
            {error}
          </div>
        )}

        {step === 1 && (
          <form className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-medium text-neutral-700">
                Email address
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-2.5 h-5 w-5 text-neutral-400" />
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-10 pr-3 py-2 border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-shadow sm:text-sm"
                  placeholder="name@example.com"
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 pt-2">
              <button
                type="button"
                onClick={handleRequestLink}
                disabled={isSubmitting || !email}
                className="w-full flex justify-center items-center py-2 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-primary hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSubmitting && recoveryMethod === 'LINK' ? 'Sending link...' : 'Send reset link'}
              </button>
              <button
                type="button"
                onClick={handleRequestOTP}
                disabled={isSubmitting || !email}
                className="w-full flex justify-center items-center py-2 px-4 border border-neutral-300 rounded-lg shadow-sm text-sm font-medium text-neutral-700 bg-white hover:bg-neutral-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSubmitting && recoveryMethod === 'OTP' ? 'Sending code...' : 'Recover using Email OTP'}
              </button>
            </div>
          </form>
        )}

        {step === 2 && (
          <form onSubmit={handleVerifyOTP} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="otp" className="text-sm font-medium text-neutral-700">
                6-Digit Verification Code
              </label>
              <div className="relative">
                <KeyRound className="absolute left-3 top-2.5 h-5 w-5 text-neutral-400" />
                <input
                  id="otp"
                  type="text"
                  maxLength={6}
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/[^0-9]/g, ''))}
                  className="w-full pl-10 pr-3 py-2 border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-shadow sm:text-sm tracking-[0.5em] text-center font-mono text-lg"
                  placeholder="000000"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting || otp.length !== 6}
              className="w-full flex justify-center items-center py-2 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-primary hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? 'Verifying...' : 'Verify Code'}
            </button>
          </form>
        )}

        {step === 3 && (
          <form onSubmit={handleResetPasswordOTP} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="newPassword" className="text-sm font-medium text-neutral-700">
                New Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-2.5 h-5 w-5 text-neutral-400" />
                <input
                  id="newPassword"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full pl-10 pr-3 py-2 border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-shadow sm:text-sm"
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="confirmPassword" className="text-sm font-medium text-neutral-700">
                Confirm Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-2.5 h-5 w-5 text-neutral-400" />
                <input
                  id="confirmPassword"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full pl-10 pr-3 py-2 border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-shadow sm:text-sm"
                  required
                />
              </div>
            </div>

            <PasswordStrength password={newPassword} />

            <button
              type="submit"
              disabled={isSubmitting || !newPassword || !confirmPassword}
              className="w-full flex justify-center items-center py-2 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-primary hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? 'Updating...' : 'Set new password'}
            </button>
          </form>
        )}
      </div>

      <div className="text-center">
        <Link 
          to="/auth/login" 
          className="text-sm font-medium text-neutral-600 hover:text-neutral-900 inline-flex items-center group"
        >
          <ArrowLeft className="h-4 w-4 mr-2 text-neutral-400 group-hover:text-neutral-600 transition-colors" />
          Back to login
        </Link>
      </div>
    </div>
  )
}
