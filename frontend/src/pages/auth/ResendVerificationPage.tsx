import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { authService } from '@/services/auth/authService'
import { Mail, ArrowLeft, Loader2, CheckCircle2 } from 'lucide-react'
import { motion } from 'framer-motion'
import { Button, Input, Label } from '@/components/common'
import { z } from 'zod'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'

const schema = z.object({
  email: z.string().email('Please enter a valid email address'),
})
type FormData = z.infer<typeof schema>

export function ResendVerificationPage() {
  const [searchParams] = useSearchParams()
  const initialEmail = searchParams.get('email') || ''
  
  const [isLoading, setIsLoading] = useState(false)
  const [isSuccess, setIsSuccess] = useState(false)

  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      email: initialEmail
    }
  })

  const onSubmit = async (data: FormData) => {
    setIsLoading(true)
    try {
      await authService.resendVerification(data.email)
      setIsSuccess(true)
    } catch (error) {
      // For F2.2 we absorb errors mostly to prevent enumeration,
      // but if the API fails entirely we handle it gracefully here.
      setIsSuccess(true) // Treat as success for anti-enumeration
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex flex-col items-center w-full">
      <div className="w-full relative min-h-[400px] flex justify-center items-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-md"
        >
          {isSuccess ? (
            <div className="flex flex-col items-center justify-center p-8 text-center space-y-4 border border-border bg-card shadow-sm rounded-xl">
              <div className="h-16 w-16 bg-primary/10 rounded-full flex items-center justify-center mb-4">
                <CheckCircle2 className="h-8 w-8 text-primary" />
              </div>
              <h2 className="text-2xl font-semibold tracking-tight text-foreground">Link Sent</h2>
              <p className="text-muted-foreground max-w-sm">
                If an account exists with that email, a new verification link has been sent. Please check your inbox.
              </p>
              <Link
                to="/auth/login"
                className="mt-8 px-6 py-2 bg-primary text-primary-foreground hover:bg-primary/90 rounded-md font-medium transition-colors"
              >
                Return to Login
              </Link>
            </div>
          ) : (
            <div className="p-8 border border-border bg-card shadow-sm rounded-xl">
              <Link
                to="/auth/login"
                className="flex items-center text-sm text-muted-foreground hover:text-foreground transition-colors mb-6"
              >
                <ArrowLeft className="h-4 w-4 mr-1" />
                Back to login
              </Link>
              
              <div className="space-y-2 mb-8">
                <h2 className="text-2xl font-semibold tracking-tight text-foreground">
                  Resend Verification Email
                </h2>
                <p className="text-sm text-muted-foreground">
                  Enter your email address and we'll send you a new link to verify your account.
                </p>
              </div>

              <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="name@example.com"
                    leftIcon={<Mail className="h-4 w-4" />}
                    error={errors.email?.message}
                    {...register('email')}
                  />
                </div>

                <Button type="submit" className="w-full mt-4" disabled={isLoading}>
                  {isLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  Send Verification Link
                </Button>
              </form>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  )
}
