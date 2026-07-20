import { Link } from 'react-router-dom'
import { PageTransition } from '@/components/layouts'
import { LoginForm } from '@/components/auth'

export function LoginPage() {
  return (
    <PageTransition>
      <div className="space-y-6">
        <div className="space-y-2 text-center">
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">Welcome back</h2>
          <p className="text-sm text-muted-foreground">
            Enter your credentials to access your account
          </p>
        </div>

        <LoginForm />

        <div className="text-center text-sm">
          <span className="text-muted-foreground">Don't have an account? </span>
          <Link
            to="/auth/register"
            className="font-medium text-primary hover:underline outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-sm"
          >
            Sign up
          </Link>
        </div>
      </div>
    </PageTransition>
  )
}
