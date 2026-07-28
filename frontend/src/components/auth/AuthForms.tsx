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

export function LoginForm({ role, onSuccess, onFocusChange, onError }: BaseFormProps & { role: 'admin' | 'user' }) {
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
    </motion.form>
  )
}

// ---------------------------------------------------------
// REGISTRATION FORMS
// ---------------------------------------------------------

const baseRegisterSchema = {
  fullName: z.string().min(2, 'Full name must be at least 2 characters'),
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
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
        role: 'user',
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
