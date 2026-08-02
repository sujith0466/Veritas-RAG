import React, { useState, useEffect } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Lock, CheckCircle2, AlertCircle } from 'lucide-react'
import { authService } from '@/services/auth/authService'

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const navigate = useNavigate()

  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSuccess, setIsSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) {
      setError('Invalid or missing reset token.')
    }
  }, [token])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) return
    if (password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters long.')
      return
    }

    setError(null)
    setIsSubmitting(true)

    try {
      await authService.resetPassword(token, password)
      setIsSuccess(true)
    } catch (err: any) {
      setError(err.response?.data?.error?.message || err.response?.data?.message || 'Failed to reset password. The link may have expired.')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (isSuccess) {
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
          <button 
            onClick={() => navigate('/auth/login')} 
            className="w-full flex justify-center items-center py-2 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-primary hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Proceed to Login
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col space-y-6">
      <div className="flex flex-col space-y-2 text-center">
        <div className="flex justify-center mb-2">
          <div className="h-12 w-12 bg-brand-50 rounded-xl flex items-center justify-center ring-1 ring-brand-100/50 shadow-inner">
            <Lock className="h-6 w-6 text-brand-600" />
          </div>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">Create new password</h1>
        <p className="text-sm text-neutral-500">
          Your new password must be at least 8 characters long.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="p-3 bg-red-50 text-red-600 flex gap-2 text-sm rounded-lg border border-red-100">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="space-y-2">
          <label htmlFor="new-password" className="text-sm font-medium text-neutral-700">
            New password
          </label>
          <div className="relative">
            <Lock className="absolute left-3 top-2.5 h-5 w-5 text-neutral-400" />
            <input
              id="new-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full pl-10 pr-3 py-2 border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-shadow sm:text-sm"
              required
              disabled={!token || isSubmitting}
            />
          </div>
        </div>

        <div className="space-y-2">
          <label htmlFor="confirm-password" className="text-sm font-medium text-neutral-700">
            Confirm new password
          </label>
          <div className="relative">
            <Lock className="absolute left-3 top-2.5 h-5 w-5 text-neutral-400" />
            <input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full pl-10 pr-3 py-2 border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-shadow sm:text-sm"
              required
              disabled={!token || isSubmitting}
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={!token || isSubmitting || !password || !confirmPassword}
          className="w-full flex justify-center items-center py-2 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-primary hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSubmitting ? 'Resetting...' : 'Reset password'}
        </button>
      </form>

      <div className="text-center">
        <Link 
          to="/auth/login" 
          className="text-sm font-medium text-neutral-600 hover:text-neutral-900 inline-flex items-center transition-colors"
        >
          Cancel and return to login
        </Link>
      </div>
    </div>
  )
}
