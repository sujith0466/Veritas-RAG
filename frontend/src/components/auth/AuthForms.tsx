import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useAuth } from '@/hooks/useAuth'
import { useToast } from '@/hooks/useToast'
import { Button, Input, Label } from '../common'
import { Mail, Lock, Eye, EyeOff, Building, User, Hash } from 'lucide-react'
import { PasswordStrength } from './PasswordStrength'
import { motion } from 'framer-motion'

// Add focus callback props for AI Assistant integration
interface BaseFormProps {
  onSuccess: () => void
  onFocusChange?: (field: 'email' | 'password' | 'password_visible' | 'idle') => void
  onError?: () => void
}

// ---------------------------------------------------------
// LOGIN FORMS
// ---------------------------------------------------------

const loginSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
})
type LoginFormData = z.infer<typeof loginSchema>

export function LoginForm({ role, onSuccess, onFocusChange, onError }: BaseFormProps & { role: 'admin' | 'viewer' }) {
  const { login } = useAuth()
  const { toast } = useToast()
  const [isLoading, setIsLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  const { register, handleSubmit, formState: { errors } } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  })

  const onSubmit = async (data: LoginFormData) => {
    setIsLoading(true)
    try {
      await login(data)
      onSuccess()
    } catch (error: unknown) {
      if (onError) onError()
      toast({
        title: 'Authentication Failed',
        message: (error as Error).message || 'Invalid email or password',
        type: 'error',
      })
      setIsLoading(false)
    }
  }

  return (
    <motion.form
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      onSubmit={handleSubmit(onSubmit)}
      className="space-y-4"
    >
      <div className="space-y-2">
        <Label htmlFor="email">{role === 'admin' ? 'Business Email' : 'Email'}</Label>
        <Input
          id="email"
          type="email"
          placeholder={role === 'admin' ? 'admin@company.com' : 'name@example.com'}
          autoComplete="email"
          autoFocus
          onFocus={() => onFocusChange?.('email')}

          leftIcon={<Mail className="h-4 w-4" />}
          error={errors.email?.message}
          {...register('email')}
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="password">Password</Label>
          <button
            type="button"
            className="text-xs font-medium text-primary hover:underline outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-sm"
          >
            Forgot Password?
          </button>
        </div>
        <Input
          id="password"
          type={showPassword ? "text" : "password"}
          autoComplete="current-password"
          onFocus={() => onFocusChange?.(showPassword ? 'password_visible' : 'password')}

          leftIcon={<Lock className="h-4 w-4" />}
          rightIcon={
            <button
              type="button"
              onClick={() => { setShowPassword(!showPassword); onFocusChange?.(!showPassword ? 'password_visible' : 'password'); }}
              className="text-muted-foreground hover:text-foreground focus:outline-none transition-colors"
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          }
          error={errors.password?.message}
          {...register('password')}
        />
      </div>

      <div className="flex items-center space-x-2 pt-1 pb-2">
        <input type="checkbox" id="remember" className="rounded border-border bg-surface text-primary focus:ring-primary" />
        <label htmlFor="remember" className="text-sm text-muted-foreground cursor-pointer">
          Remember Me
        </label>
      </div>

      <Button type="submit" className="w-full" isLoading={isLoading}>
        Login
      </Button>

      <div className="relative my-4">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-border" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-background px-2 text-muted-foreground">Or continue with</span>
        </div>
      </div>

      <Button
        type="button"
        variant="outline"
        className="w-full"
        onClick={() => {
          window.location.href = `${import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'}/api/v1/auth/sso/login/google`
        }}
      >
        <svg className="mr-2 h-4 w-4" aria-hidden="true" focusable="false" data-prefix="fab" data-icon="google" role="img" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 488 512">
          <path fill="currentColor" d="M488 261.8C488 403.3 391.1 504 248 504 110.8 504 0 393.2 0 256S110.8 8 248 8c66.8 0 123 24.5 166.3 64.9l-67.5 64.9C258.5 52.6 94.3 116.6 94.3 256c0 86.5 69.1 156.6 153.7 156.6 98.2 0 135-70.4 140.8-106.9H248v-85.3h236.1c2.3 12.7 3.9 24.9 3.9 41.4z"></path>
        </svg>
        Google
      </Button>
    </motion.form>
  )
}

// ---------------------------------------------------------
// REGISTRATION FORMS
// ---------------------------------------------------------

const baseRegisterSchema = {
  fullName: z.string().min(2, 'Full name must be at least 2 characters'),
  email: z.string().email('Please enter a valid email address'),
  password: z
    .string()
    .min(8, 'Password must be at least 8 characters')
    .regex(/[A-Z]/, 'Password must contain at least one uppercase letter')
    .regex(/[a-z]/, 'Password must contain at least one lowercase letter')
    .regex(/\d/, 'Password must contain at least one number')
    .regex(/[^A-Za-z0-9]/, 'Password must contain at least one special character'),
  confirmPassword: z.string(),
  acceptTerms: z.literal(true, {
    errorMap: () => ({ message: "You must accept the terms" }),
  }),
}

const adminRegisterSchema = z.object({
  ...baseRegisterSchema,
  workspaceName: z.string().min(2, 'Workspace name is required'),
  companyName: z.string().optional(),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ["confirmPassword"],
})

const userRegisterSchema = z.object({
  ...baseRegisterSchema,
  inviteCode: z.string().min(1, 'Invite code is required'),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ["confirmPassword"],
})

export function AdminRegisterForm({ onSuccess, onFocusChange, onError }: BaseFormProps) {
  const { register: registerAuth } = useAuth()
  const { toast } = useToast()
  const [isLoading, setIsLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  const { register, handleSubmit, watch, formState: { errors } } = useForm<z.infer<typeof adminRegisterSchema>>({
    resolver: zodResolver(adminRegisterSchema),
  })

  const passwordVal = watch('password'); console.log('ERRORS:', errors);

  const onSubmit = async (data: z.infer<typeof adminRegisterSchema>) => {
    setIsLoading(true)
    try {
      await registerAuth({
        ...data,
        role: 'admin',
        organizationName: data.companyName,
      })
      onSuccess()
    } catch (error: unknown) {
      if (onError) onError()
      toast({ title: 'Registration Failed', message: (error as Error).message || 'Something went wrong', type: 'error' })
      setIsLoading(false)
    }
  }

  return (
    <motion.form
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      onSubmit={handleSubmit(onSubmit)}
      className="space-y-4"
    >
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="workspaceName">Workspace Name</Label>
          <Input id="workspaceName" placeholder="Acme Corp AI" onFocus={() => onFocusChange?.('idle')} leftIcon={<Building className="h-4 w-4" />} error={errors.workspaceName?.message} {...register('workspaceName')} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="companyName">Company (Optional)</Label>
          <Input id="companyName" placeholder="Acme Inc" onFocus={() => onFocusChange?.('idle')} leftIcon={<Building className="h-4 w-4" />} {...register('companyName')} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="fullName">Full Name</Label>
          <Input id="fullName" placeholder="Jane Doe" onFocus={() => onFocusChange?.('idle')} leftIcon={<User className="h-4 w-4" />} error={errors.fullName?.message} {...register('fullName')} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="email">Business Email</Label>
          <Input id="email" type="email" placeholder="jane@acme.com" onFocus={() => onFocusChange?.('email')} leftIcon={<Mail className="h-4 w-4" />} error={errors.email?.message} {...register('email')} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type={showPassword ? "text" : "password"}
            onFocus={() => onFocusChange?.(showPassword ? 'password_visible' : 'password')}

            leftIcon={<Lock className="h-4 w-4" />}
            error={errors.password?.message}
            {...register('password')}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="confirmPassword">Confirm Password</Label>
          <Input
            id="confirmPassword"
            type={showPassword ? "text" : "password"}
            onFocus={() => onFocusChange?.(showPassword ? 'password_visible' : 'password')}

            leftIcon={<Lock className="h-4 w-4" />}
            rightIcon={
              <button type="button" onClick={() => { setShowPassword(!showPassword); onFocusChange?.(!showPassword ? 'password_visible' : 'password'); }} className="text-muted-foreground hover:text-foreground">
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            }
            error={errors.confirmPassword?.message}
            {...register('confirmPassword')}
          />
        </div>
      </div>

      <PasswordStrength password={passwordVal} />

      <div className="flex items-center space-x-2 pt-2 pb-2">
        <input type="checkbox" id="acceptTermsAdmin" {...register('acceptTerms')} className="rounded border-border bg-surface text-primary focus:ring-primary" />
        <label htmlFor="acceptTermsAdmin" className="text-sm text-muted-foreground cursor-pointer">
          I accept the <span className="text-primary hover:underline">Terms of Service</span>
        </label>
      </div>

      <Button type="submit" className="w-full" isLoading={isLoading}>
        Create Enterprise Workspace
      </Button>
    </motion.form>
  )
}

export function UserRegisterForm({ onSuccess, onFocusChange, onError }: BaseFormProps) {
  const { register: registerAuth } = useAuth()
  const { toast } = useToast()
  const [isLoading, setIsLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  const { register, handleSubmit, watch, formState: { errors } } = useForm<z.infer<typeof userRegisterSchema>>({
    resolver: zodResolver(userRegisterSchema),
  })

  const passwordVal = watch('password')

  const onSubmit = async (data: z.infer<typeof userRegisterSchema>) => {
    setIsLoading(true)
    try {
      await registerAuth({
        ...data,
        role: 'viewer',
      })
      onSuccess()
    } catch (error: unknown) {
      if (onError) onError()
      toast({ title: 'Registration Failed', message: (error as Error).message || 'Something went wrong', type: 'error' })
      setIsLoading(false)
    }
  }

  return (
    <motion.form
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      onSubmit={handleSubmit(onSubmit)}
      className="space-y-4"
    >
      <div className="space-y-2">
        <Label htmlFor="inviteCode">Workspace Invitation Code</Label>
        <Input id="inviteCode" placeholder="Enter join code" onFocus={() => onFocusChange?.('idle')} leftIcon={<Hash className="h-4 w-4" />} error={errors.inviteCode?.message} {...register('inviteCode')} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="fullName">Full Name</Label>
          <Input id="fullName" placeholder="John Doe" onFocus={() => onFocusChange?.('idle')} leftIcon={<User className="h-4 w-4" />} error={errors.fullName?.message} {...register('fullName')} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" placeholder="john@example.com" onFocus={() => onFocusChange?.('email')} leftIcon={<Mail className="h-4 w-4" />} error={errors.email?.message} {...register('email')} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type={showPassword ? "text" : "password"}
            onFocus={() => onFocusChange?.(showPassword ? 'password_visible' : 'password')}

            leftIcon={<Lock className="h-4 w-4" />}
            error={errors.password?.message}
            {...register('password')}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="confirmPassword">Confirm Password</Label>
          <Input
            id="confirmPassword"
            type={showPassword ? "text" : "password"}
            onFocus={() => onFocusChange?.(showPassword ? 'password_visible' : 'password')}

            leftIcon={<Lock className="h-4 w-4" />}
            rightIcon={
              <button type="button" onClick={() => { setShowPassword(!showPassword); onFocusChange?.(!showPassword ? 'password_visible' : 'password'); }} className="text-muted-foreground hover:text-foreground">
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            }
            error={errors.confirmPassword?.message}
            {...register('confirmPassword')}
          />
        </div>
      </div>

      <PasswordStrength password={passwordVal} />

      <div className="flex items-center space-x-2 pt-2 pb-2">
        <input type="checkbox" id="acceptTermsUser" {...register('acceptTerms')} className="rounded border-border bg-surface text-primary focus:ring-primary" />
        <label htmlFor="acceptTermsUser" className="text-sm text-muted-foreground cursor-pointer">
          I accept the <span className="text-primary hover:underline">Terms of Service</span>
        </label>
      </div>

      <Button type="submit" className="w-full" isLoading={isLoading}>
        Join Existing Workspace
      </Button>
    </motion.form>
  )
}
