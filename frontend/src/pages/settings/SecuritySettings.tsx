import React, { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
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
  ArrowRight,
} from 'lucide-react'

function maskEmail(email: string | undefined): string {
  if (!email || !email.includes('@')) return email || 'your email'
  const [local, domain] = email.split('@')
  if (local.length <= 1) return `${local}***@${domain}`
  return `${local[0]}***@${domain}`
}

export function SecuritySettings() {
  const navigate = useNavigate()
  const user = useAuthStore(s => s.user)
  const clearAuth = useAuthStore(s => s.clearAuth)
  const { toast } = useToast()

  const [step, setStep] = useState<1 | 2 | 3 | 4>(1)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Step 2 state
  const [otpDigits, setOtpDigits] = useState<string[]>(['', '', '', '', '', ''])
  const [cooldown, setCooldown] = useState(0)
  const otpInputRefs = useRef<(HTMLInputElement | null)[]>([])

  // Step 3 state
  const [changeToken, setChangeToken] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showNewPassword, setShowNewPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)

  // Cooldown timer
  useEffect(() => {
    if (cooldown <= 0) return
    const timer = setInterval(() => {
      setCooldown(prev => Math.max(0, prev - 1))
    }, 1000)
    return () => clearInterval(timer)
  }, [cooldown])

  // Step 1: Request Security Code
  const handleRequestCode = async () => {
    setError(null)
    setIsLoading(true)
    try {
      await authService.requestChangePasswordCode()
      setCooldown(60)
      setOtpDigits(['', '', '', '', '', ''])
      setStep(2)
      toast({
        title: 'Code Dispatched',
        message: 'A 6-digit verification code was sent to your registered email.',
        type: 'success',
      })
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to dispatch verification code.'
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

  // Step 2: Verify Code
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
      const { change_token } = await authService.verifyChangePasswordCode(rawOtp)
      setChangeToken(change_token)
      setStep(3)
      toast({
        title: 'Code Verified',
        message: 'Please set your new account password.',
        type: 'success',
      })
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Invalid or expired verification code.'
      setError(msg)
      toast({ title: 'Verification Failed', message: msg, type: 'error' })
    } finally {
      setIsLoading(false)
    }
  }

  // Step 3: Complete Password Change
  const handleCompleteChange = async (e: React.FormEvent) => {
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
    setIsLoading(true)
    try {
      await authService.completeChangePassword(changeToken, newPassword)
      setStep(4)
      toast({
        title: 'Password Changed',
        message: 'Password changed successfully. Active sessions revoked.',
        type: 'success',
      })
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to update password.'
      setError(msg)
      toast({ title: 'Update Failed', message: msg, type: 'error' })
    } finally {
      setIsLoading(false)
    }
  }

  // Step 4: Logout and redirect to login
  const handleRelogin = async () => {
    try {
      await authService.logout()
    } catch {
      // ignore
    }
    clearAuth()
    navigate('/login')
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <SectionHeader
        title="Security Settings"
        description="Manage your account password and security preferences."
      />

      <div className="grid gap-8">
        <Card className="p-6 space-y-6">
          <div className="flex items-center gap-3 border-b border-border pb-4 mb-4">
            <div className="p-2 bg-primary/10 rounded-lg text-primary">
              <Lock className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">Change Password</h3>
              <p className="text-sm text-muted-foreground">
                Authorize password change via a single-use email verification code.
              </p>
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 p-3 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-md">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Step 1: Request Security Code */}
          {step === 1 && (
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

              <div className="flex justify-start">
                <Button
                  onClick={handleRequestCode}
                  isLoading={isLoading}
                  disabled={isLoading || cooldown > 0}
                  className="gap-2"
                >
                  <Mail className="w-4 h-4" />
                  {cooldown > 0 ? `Wait ${cooldown}s` : 'Send Verification Code'}
                </Button>
              </div>
            </div>
          )}

          {/* Step 2: Enter 6-Digit Code */}
          {step === 2 && (
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
                    setStep(1)
                  }}
                  disabled={isLoading}
                >
                  Back
                </Button>
              </div>
            </form>
          )}

          {/* Step 3: Set New Password */}
          {step === 3 && (
            <form onSubmit={handleCompleteChange} className="space-y-6 max-w-xl">
              <div className="space-y-4">
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
                    />
                    <button
                      type="button"
                      onClick={() => setShowNewPassword(!showNewPassword)}
                      className="absolute right-3 top-3 text-muted-foreground hover:text-foreground"
                      aria-label={showNewPassword ? 'Hide password' : 'Show password'}
                    >
                      {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  <PasswordStrength password={newPassword} />
                </div>

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
                  disabled={isLoading || newPassword.length < 8 || newPassword !== confirmPassword}
                >
                  Update Password
                </Button>
              </div>
            </form>
          )}

          {/* Step 4: Success & Relogin */}
          {step === 4 && (
            <div className="space-y-6 max-w-xl py-2">
              <div className="flex items-start gap-3 rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-4">
                <CheckCircle2 className="w-6 h-6 text-emerald-500 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <h4 className="font-semibold text-foreground">Password Changed Successfully</h4>
                  <p className="text-sm text-muted-foreground">
                    Your password has been updated and all existing active sessions and access tokens have been securely revoked. Please log in with your new password.
                  </p>
                </div>
              </div>

              <div className="flex justify-start">
                <Button onClick={handleRelogin} className="gap-2">
                  <span>Log In With New Password</span>
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </div>
            </div>
          )}
        </Card>

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
