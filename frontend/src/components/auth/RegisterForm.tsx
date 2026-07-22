import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useAuth } from '@/hooks/useAuth'
import { useToast } from '@/hooks/useToast'
import { registerSchema, type RegisterFormData, getPasswordStrength } from '@/utils/validators'
import { Button } from '../common/Button'
import { Input } from '../common/Input'
import { Label } from '../common/Label'
import { Mail, Lock, User, Eye, EyeOff, CheckCircle2, XCircle, Building2, KeyRound } from 'lucide-react'
import { cn } from '@/utils/cn'

interface RegisterFormProps {
  role: 'admin' | 'user'
}

export function RegisterForm({ role }: RegisterFormProps) {
  const { register: registerUser } = useAuth()
  const { toast } = useToast()
  const [isLoading, setIsLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
  })

  const passwordValue = watch('password') || ''
  const confirmPasswordValue = watch('confirmPassword') || ''
  const strength = getPasswordStrength(passwordValue)

  const onSubmit = async (data: RegisterFormData) => {
    setIsLoading(true)
    try {
      await registerUser({ ...data, role })
      toast({
        title: 'Account created',
        message: 'Please check your email to verify your account.',
        type: 'success',
      })
    } catch (error: any) {
      toast({
        title: 'Registration Failed',
        message: error.message || 'Could not create account',
        type: 'error',
      })
      setIsLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      {role === 'admin' && (
        <>
          <div className="space-y-2">
            <Label htmlFor="workspaceName">Workspace Name</Label>
            <Input
              id="workspaceName"
              type="text"
              placeholder="My Company Workspace"
              leftIcon={<Building2 className="h-4 w-4" />}
              error={errors.workspaceName?.message}
              {...register('workspaceName')}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="organizationName">Organization Name</Label>
            <Input
              id="organizationName"
              type="text"
              placeholder="Acme Corp"
              leftIcon={<Building2 className="h-4 w-4" />}
              error={errors.organizationName?.message}
              {...register('organizationName')}
            />
          </div>
        </>
      )}

      {role === 'user' && (
        <div className="space-y-2">
          <Label htmlFor="invitationCode">Invitation Code / Workspace ID</Label>
          <Input
            id="invitationCode"
            type="text"
            placeholder="INV-XXXXX"
            leftIcon={<KeyRound className="h-4 w-4" />}
            error={errors.invitationCode?.message}
            {...register('invitationCode')}
          />
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="fullName">Full Name</Label>
        <Input
          id="fullName"
          type="text"
          placeholder="Jane Doe"
          autoComplete="name"
          leftIcon={<User className="h-4 w-4" />}
          error={errors.fullName?.message}
          {...register('fullName')}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          placeholder="name@example.com"
          autoComplete="email"
          leftIcon={<Mail className="h-4 w-4" />}
          error={errors.email?.message}
          {...register('email')}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type={showPassword ? "text" : "password"}
          autoComplete="new-password"
          leftIcon={<Lock className="h-4 w-4" />}
          rightIcon={
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="text-muted-foreground hover:text-foreground focus:outline-none transition-colors"
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          }
          error={errors.password?.message}
          {...register('password')}
        />
        {passwordValue && (
          <div className="mt-2 space-y-1">
            <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className={cn('h-full transition-all duration-300', strength.color)}
                style={{ width: `${Math.max((strength.score / 4) * 100, 5)}%` }}
              />
            </div>
            <p className={cn('text-[10px] font-medium text-right', strength.color.replace('bg-', 'text-'))}>
              {strength.label}
            </p>
          </div>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="confirmPassword">Confirm Password</Label>
        <Input
          id="confirmPassword"
          type={showConfirmPassword ? "text" : "password"}
          autoComplete="new-password"
          leftIcon={<Lock className="h-4 w-4" />}
          rightIcon={
            <button
              type="button"
              onClick={() => setShowConfirmPassword(!showConfirmPassword)}
              className="text-muted-foreground hover:text-foreground focus:outline-none transition-colors"
            >
              {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          }
          error={errors.confirmPassword?.message}
          {...register('confirmPassword')}
        />
        {confirmPasswordValue && passwordValue && (
          <div className="mt-2 flex items-center gap-1.5">
            {passwordValue === confirmPasswordValue ? (
              <>
                <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                <span className="text-[11px] font-medium text-success">Passwords match</span>
              </>
            ) : (
              <>
                <XCircle className="h-3.5 w-3.5 text-danger" />
                <span className="text-[11px] font-medium text-danger">Passwords do not match</span>
              </>
            )}
          </div>
        )}
      </div>

      <Button type="submit" className="w-full mt-6" isLoading={isLoading}>
        Create Account
      </Button>
    </form>
  )
}
