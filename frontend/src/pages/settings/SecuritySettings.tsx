import React, { useEffect, useRef, useState } from 'react'
import { Card, Input, Label, Button, SectionHeader } from '@/components/common'
import { useToast } from '@/hooks/useToast'
import { useAuthStore } from '@/stores/authStore'
import { authService } from '@/services/auth/authService'
import { PasswordStrength } from '@/components/auth/PasswordStrength'
import {
  Lock,
  Mail,
  ShieldCheck,
  CheckCircle2,
  RefreshCw,
  Eye,
  EyeOff,
  AlertCircle,
  ArrowLeft,
  KeyRound,
  X,
} from 'lucide-react'

function maskEmail(email: string | undefined): string {
  if (!email || !email.includes('@')) return email || 'your email'
  const [local, domain] = email.split('@')
  if (local.length <= 1) return `${local}***@${domain}`
  return `${local[0]}***@${domain}`
}

export function SecuritySettings() {
  const user = useAuthStore(s => s.user)
  const setToken = useAuthStore(s => s.setToken)
  const { toast } = useToast()

  // Mode: Path A (knows current password) vs Path B (security code)
  const [mode, setMode] = useState<'path_a' | 'path_b'>('path_a')
  const [pathBStep, setPathBStep] = useState<1 | 2 | 3>(1)

  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  // Path A state
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showCurrentPassword, setShowCurrentPassword] = useState(false)
  const [showNewPassword, setShowNewPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)

  // Path B Step 2 state
  const [otpDigits, setOtpDigits] = useState<string[]>(['', '', '', '', '', ''])
  const [cooldown, setCooldown] = useState(0)
  const otpInputRefs = useRef<(HTMLInputElement | null)[]>([])

  // Path B Step 3 state (ephemeral in-memory only)
  const [changeToken, setChangeToken] = useState('')

  // Cooldown timer
  useEffect(() => {
    if (cooldown <= 0) return
    const timer = setInterval(() => {
      setCooldown(prev => Math.max(0, prev - 1))
    }, 1000)
    return () => clearInterval(timer)
  }, [cooldown])

  // Reset Path A form
  const resetPathAForm = () => {
    setCurrentPassword('')
    setNewPassword('')
    setConfirmPassword('')
    setShowCurrentPassword(false)
    setShowNewPassword(false)
    setShowConfirmPassword(false)
  }

  // Reset Path B state
  const resetPathBState = () => {
    setPathBStep(1)
    setOtpDigits(['', '', '', '', '', ''])
    setChangeToken('')
    setNewPassword('')
    setConfirmPassword('')
    setShowNewPassword(false)
    setShowConfirmPassword(false)
  }

  // Switch to Path B
  const handleSwitchToPathB = () => {
    setError(null)
    setSuccessMessage(null)
    resetPathAForm()
    resetPathBState()
    setMode('path_b')
  }

  // Switch back to Path A
  const handleSwitchToPathA = () => {
    setError(null)
    setSuccessMessage(null)
    resetPathBState()
    resetPathAForm()
    setMode('path_a')
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // PATH A: Submit with Current Password
  // ═══════════════════════════════════════════════════════════════════════════
  const handleSubmitPathA = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!currentPassword || !newPassword || !confirmPassword) {
      setError('Please fill in all password fields.')
      return
    }

    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters long.')
      return
    }

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    if (newPassword === currentPassword) {
      setError('New password cannot be the same as current password.')
      return
    }

    setError(null)
    setSuccessMessage(null)
    setIsLoading(true)

    try {
      const res = await authService.changePassword(currentPassword, newPassword)

      // Maintain session continuity with rotated access token
      if (res?.access_token) {
        setToken(res.access_token)
      }

      resetPathAForm()
      const msg = res?.message || 'Password changed successfully.'
      setSuccessMessage(msg)
      toast({
        title: 'Password Changed',
        message: msg,
        type: 'success',
      })
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ||
        err?.response?.data?.error?.message ||
        err?.message ||
        'Failed to change password. Please check your current password.'
      setError(msg)
      toast({ title: 'Password Change Failed', message: msg, type: 'error' })
    } finally {
      setIsLoading(false)
    }
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // PATH B: Step 1 — Request Security Code
  // ═══════════════════════════════════════════════════════════════════════════
  const handleRequestCode = async () => {
    setError(null)
    setSuccessMessage(null)
    setIsLoading(true)
    try {
      await authService.requestChangePasswordCode()
      setCooldown(60)
      setOtpDigits(['', '', '', '', '', ''])
      setPathBStep(2)
      toast({
        title: 'Code Dispatched',
        message: 'A 6-digit verification code was sent to your registered email.',
        type: 'success',
      })
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ||
        err?.response?.data?.error?.message ||
        err?.message ||
        'Failed to dispatch verification code.'
      setError(msg)
      toast({ title: 'Error', message: msg, type: 'error' })
    } finally {
      setIsLoading(false)
    }
  }

  // Handle segmented OTP digits
  const handleOtpChange = (index: number, value: string) => {
    const clean = value.replace(/[^0-9]/g, '')
    if (!clean) {
      const updated = [...otpDigits]
      updated[index] = ''
      setOtpDigits(updated)
      return
    }

    if (clean.length > 1) {
      const digits = clean.slice(0, 6).split('')
      const updated = [...otpDigits]
      digits.forEach((d, i) => {
        if (i < 6) updated[i] = d
      })
      setOtpDigits(updated)
      const nextIndex = Math.min(5, digits.length)
      otpInputRefs.current[nextIndex]?.focus()
      return
    }

    const updated = [...otpDigits]
    updated[index] = clean
    setOtpDigits(updated)

    if (index < 5 && clean) {
      otpInputRefs.current[index + 1]?.focus()
    }
  }

  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !otpDigits[index] && index > 0) {
      otpInputRefs.current[index - 1]?.focus()
    }
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // PATH B: Step 2 — Verify Code
  // ═══════════════════════════════════════════════════════════════════════════
  const handleVerifyCode = async (e: React.FormEvent) => {
    e.preventDefault()
    const rawOtp = otpDigits.join('')
    if (rawOtp.length !== 6) {
      setError('Please enter the full 6-digit verification code.')
      return
    }

    setError(null)
    setIsLoading(true)
    try {
      const res = await authService.verifyChangePasswordCode(rawOtp)
      const token = res?.change_token || (res as any)?.data?.change_token || ''
      setChangeToken(token)
      // Clear sensitive OTP from component state immediately
      setOtpDigits(['', '', '', '', '', ''])
      setPathBStep(3)
      toast({
        title: 'Code Verified',
        message: 'Please set your new account password.',
        type: 'success',
      })
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ||
        err?.response?.data?.error?.message ||
        err?.message ||
        'Invalid or expired verification code.'
      setError(msg)
      toast({ title: 'Verification Failed', message: msg, type: 'error' })
    } finally {
      setIsLoading(false)
    }
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // PATH B: Step 3 — Complete Password Change (No Current Password)
  // ═══════════════════════════════════════════════════════════════════════════
  const handleSubmitPathB = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newPassword || !confirmPassword) {
      setError('Please fill in both password fields.')
      return
    }

    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters long.')
      return
    }

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    setError(null)
    setSuccessMessage(null)
    setIsLoading(true)

    try {
      const res = await authService.completeChangePassword(changeToken, newPassword)

      // Maintain session continuity with rotated access token
      if (res?.access_token) {
        setToken(res.access_token)
      }

      // Clear ephemeral secrets & return to default state in place
      resetPathBState()
      resetPathAForm()
      setMode('path_a')

      const msg = res?.message || 'Password changed successfully.'
      setSuccessMessage(msg)
      toast({
        title: 'Password Changed',
        message: msg,
        type: 'success',
      })
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ||
        err?.response?.data?.error?.message ||
        err?.message ||
        'Failed to update password.'
      setError(msg)
      toast({ title: 'Update Failed', message: msg, type: 'error' })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <SectionHeader
        title="Security Settings"
        description="Manage your account password and security preferences."
      />

      <div className="grid gap-8">
        <Card className="p-6 space-y-6">
          <div className="flex items-center justify-between border-b border-border pb-4 mb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary/10 rounded-lg text-primary">
                {mode === 'path_a' ? <Lock className="w-5 h-5" /> : <KeyRound className="w-5 h-5" />}
              </div>
              <div>
                <h3 className="font-semibold text-foreground">Change Password</h3>
                <p className="text-sm text-muted-foreground">
                  {mode === 'path_a'
                    ? 'Update your password using your current password.'
                    : 'Authorize password change via a single-use email security code.'}
                </p>
              </div>
            </div>

            {mode === 'path_b' && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleSwitchToPathA}
                disabled={isLoading}
                className="gap-1.5 text-muted-foreground hover:text-foreground"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Use Current Password</span>
              </Button>
            )}
          </div>

          {/* Success Alert */}
          {successMessage && (
            <div className="flex items-start justify-between gap-3 p-4 text-sm text-emerald-800 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 rounded-lg">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                <span className="font-medium">{successMessage}</span>
              </div>
              <button
                type="button"
                onClick={() => setSuccessMessage(null)}
                className="text-emerald-600 hover:text-emerald-900 dark:hover:text-emerald-100"
                aria-label="Dismiss notification"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Error Alert */}
          {error && (
            <div className="flex items-center gap-2 p-3 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-md">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* ═══════════════════════════════════════════════════════════════════════ */}
          {/* PATH A: User Knows Current Password (Default)                           */}
          {/* ═══════════════════════════════════════════════════════════════════════ */}
          {mode === 'path_a' && (
            <form onSubmit={handleSubmitPathA} className="space-y-6 max-w-xl">
              <div className="space-y-4">
                {/* Current Password Field */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="currentPassword">Current Password</Label>
                    <button
                      type="button"
                      onClick={handleSwitchToPathB}
                      disabled={isLoading}
                      className="text-xs text-primary hover:underline font-medium focus:outline-none"
                    >
                      Forgot Current Password?
                    </button>
                  </div>
                  <div className="relative">
                    <Input
                      id="currentPassword"
                      name="currentPassword"
                      type={showCurrentPassword ? 'text' : 'password'}
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                      placeholder="Enter current password"
                      className="pr-10"
                      autoComplete="current-password"
                      disabled={isLoading}
                    />
                    <button
                      type="button"
                      onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                      className="absolute right-3 top-3 text-muted-foreground hover:text-foreground"
                      aria-label={showCurrentPassword ? 'Hide current password' : 'Show current password'}
                    >
                      {showCurrentPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* New Password Field */}
                <div className="space-y-2">
                  <Label htmlFor="newPassword">New Password</Label>
                  <div className="relative">
                    <Input
                      id="newPassword"
                      name="newPassword"
                      type={showNewPassword ? 'text' : 'password'}
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="Minimum 8 characters"
                      className="pr-10"
                      autoComplete="new-password"
                      disabled={isLoading}
                    />
                    <button
                      type="button"
                      onClick={() => setShowNewPassword(!showNewPassword)}
                      className="absolute right-3 top-3 text-muted-foreground hover:text-foreground"
                      aria-label={showNewPassword ? 'Hide new password' : 'Show new password'}
                    >
                      {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  <PasswordStrength password={newPassword} />
                </div>

                {/* Confirm New Password Field */}
                <div className="space-y-2">
                  <Label htmlFor="confirmPassword">Confirm New Password</Label>
                  <div className="relative">
                    <Input
                      id="confirmPassword"
                      name="confirmPassword"
                      type={showConfirmPassword ? 'text' : 'password'}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Re-enter new password"
                      className="pr-10"
                      autoComplete="new-password"
                      disabled={isLoading}
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      className="absolute right-3 top-3 text-muted-foreground hover:text-foreground"
                      aria-label={showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
                    >
                      {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              </div>

              <div className="flex justify-end pt-2">
                <Button
                  type="submit"
                  isLoading={isLoading}
                  disabled={
                    isLoading ||
                    !currentPassword ||
                    !newPassword ||
                    !confirmPassword ||
                    newPassword.length < 8 ||
                    newPassword !== confirmPassword ||
                    newPassword === currentPassword
                  }
                >
                  Change Password
                </Button>
              </div>
            </form>
          )}

          {/* ═══════════════════════════════════════════════════════════════════════ */}
          {/* PATH B: Step 1 — Request Security Code                                   */}
          {/* ═══════════════════════════════════════════════════════════════════════ */}
          {mode === 'path_b' && pathBStep === 1 && (
            <div className="space-y-6 max-w-xl">
              <div className="rounded-lg border border-border/60 bg-muted/30 p-4 space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <Mail className="w-4 h-4 text-primary" />
                  <span>Email Verification Required</span>
                </div>
                <p className="text-sm text-muted-foreground">
                  To protect your account, password changes require a 6-digit security code sent to your registered email address ({maskEmail(user?.email)}).
                </p>
              </div>

              <div className="flex items-center gap-3">
                <Button
                  onClick={handleRequestCode}
                  isLoading={isLoading}
                  disabled={isLoading || cooldown > 0}
                  className="gap-2"
                >
                  <Mail className="w-4 h-4" />
                  {cooldown > 0 ? `Wait ${cooldown}s` : 'Send Verification Code'}
                </Button>

                <Button
                  type="button"
                  variant="outline"
                  onClick={handleSwitchToPathA}
                  disabled={isLoading}
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}

          {/* ═══════════════════════════════════════════════════════════════════════ */}
          {/* PATH B: Step 2 — Enter 6-Digit Code                                      */}
          {/* ═══════════════════════════════════════════════════════════════════════ */}
          {mode === 'path_b' && pathBStep === 2 && (
            <form onSubmit={handleVerifyCode} className="space-y-6 max-w-xl">
              <div className="space-y-2">
                <Label>6-Digit Verification Code</Label>
                <p className="text-xs text-muted-foreground">
                  Enter the code sent to {maskEmail(user?.email)}. Valid for 10 minutes.
                </p>

                <div className="flex items-center gap-2 pt-2">
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
                      className="w-12 h-14 text-center text-xl font-bold rounded-lg border border-input bg-background focus:border-primary focus:ring-2 focus:ring-primary/20 outline-none transition"
                      aria-label={`Digit ${idx + 1}`}
                      disabled={isLoading}
                    />
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-3">
                <Button
                  type="submit"
                  isLoading={isLoading}
                  disabled={isLoading || otpDigits.join('').length !== 6}
                >
                  Verify Code
                </Button>

                <Button
                  type="button"
                  variant="outline"
                  onClick={handleRequestCode}
                  disabled={isLoading || cooldown > 0}
                  className="gap-1.5"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  {cooldown > 0 ? `Resend (${cooldown}s)` : 'Resend Code'}
                </Button>

                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setError(null)
                    setPathBStep(1)
                  }}
                  disabled={isLoading}
                >
                  Back
                </Button>
              </div>
            </form>
          )}

          {/* ═══════════════════════════════════════════════════════════════════════ */}
          {/* PATH B: Step 3 — Set New Password (NO Current Password Field!)          */}
          {/* ═══════════════════════════════════════════════════════════════════════ */}
          {mode === 'path_b' && pathBStep === 3 && (
            <form onSubmit={handleSubmitPathB} className="space-y-6 max-w-xl">
              <div className="space-y-4">
                <div className="rounded-lg border border-border/60 bg-muted/20 p-3 text-xs text-muted-foreground flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                  <span>Security code verified. Set your new password below.</span>
                </div>

                {/* New Password Field */}
                <div className="space-y-2">
                  <Label htmlFor="pathBNewPassword">New Password</Label>
                  <div className="relative">
                    <Input
                      id="pathBNewPassword"
                      name="pathBNewPassword"
                      type={showNewPassword ? 'text' : 'password'}
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="Minimum 8 characters"
                      className="pr-10"
                      autoComplete="new-password"
                      disabled={isLoading}
                    />
                    <button
                      type="button"
                      onClick={() => setShowNewPassword(!showNewPassword)}
                      className="absolute right-3 top-3 text-muted-foreground hover:text-foreground"
                      aria-label={showNewPassword ? 'Hide new password' : 'Show new password'}
                    >
                      {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  <PasswordStrength password={newPassword} />
                </div>

                {/* Confirm New Password Field */}
                <div className="space-y-2">
                  <Label htmlFor="pathBConfirmPassword">Confirm New Password</Label>
                  <div className="relative">
                    <Input
                      id="pathBConfirmPassword"
                      name="pathBConfirmPassword"
                      type={showConfirmPassword ? 'text' : 'password'}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Re-enter new password"
                      className="pr-10"
                      autoComplete="new-password"
                      disabled={isLoading}
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      className="absolute right-3 top-3 text-muted-foreground hover:text-foreground"
                      aria-label={showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
                    >
                      {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3 pt-2">
                <Button
                  type="submit"
                  isLoading={isLoading}
                  disabled={
                    isLoading ||
                    !newPassword ||
                    !confirmPassword ||
                    newPassword.length < 8 ||
                    newPassword !== confirmPassword
                  }
                >
                  Change Password
                </Button>

                <Button
                  type="button"
                  variant="outline"
                  onClick={handleSwitchToPathA}
                  disabled={isLoading}
                >
                  Cancel
                </Button>
              </div>
            </form>
          )}
        </Card>

        {/* Two-Factor Authentication Card */}
        <Card className="p-6 space-y-6">
          <div className="flex items-center gap-3 border-b border-border pb-4 mb-4">
            <div className="p-2 bg-success-subtle text-success rounded-lg">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">Two-Factor Authentication</h3>
              <p className="text-sm text-muted-foreground">Add an extra layer of security to your account.</p>
            </div>
          </div>
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Two-factor authentication is enforced at the enterprise level by your identity provider (SSO).
            </p>
            <Button variant="outline" disabled>Managed by Admin</Button>
          </div>
        </Card>
      </div>
    </div>
  )
}
