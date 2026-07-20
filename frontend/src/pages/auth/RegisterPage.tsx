import { Link } from 'react-router-dom'
import { PageTransition } from '@/components/layouts'
import { RegisterForm } from '@/components/auth'

export function RegisterPage() {
  return (
    <PageTransition>
      <div className="space-y-6">
        <div className="space-y-2 text-center">
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">Create an account</h2>
          <p className="text-sm text-muted-foreground">
            Enter your details to get started with RAGuard AI
          </p>
        </div>

        <RegisterForm />

        <div className="text-center text-sm">
          <span className="text-muted-foreground">Already have an account? </span>
          <Link
            to="/auth/login"
            className="font-medium text-primary hover:underline outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-sm"
          >
            Sign in
          </Link>
        </div>
      </div>
    </PageTransition>
  )
}
