import { useState } from 'react'
import { Link } from 'react-router-dom'
import { PageTransition } from '@/components/layouts'
import { LoginForm } from '@/components/auth'
import { ShieldAlert, User as UserIcon, ArrowLeft } from 'lucide-react'
import { Button } from '@/components/common/Button'

export function LoginPage() {
  const [selectedRole, setSelectedRole] = useState<'admin' | 'user' | null>(null)

  if (!selectedRole) {
    return (
      <PageTransition>
        <div className="space-y-6">
          <div className="space-y-2 text-center">
            <h2 className="text-2xl font-semibold tracking-tight text-foreground">Welcome to RAGuard AI</h2>
            <p className="text-sm text-muted-foreground">
              Please select your role to continue
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4">
            <Button 
              variant="outline" 
              className="h-24 flex flex-col items-center justify-center space-y-2 border-2 hover:border-primary hover:bg-primary/5 transition-all"
              onClick={() => setSelectedRole('admin')}
            >
              <ShieldAlert className="h-6 w-6 text-primary" />
              <div className="font-semibold text-lg">Login as Admin</div>
            </Button>
            
            <Button 
              variant="outline" 
              className="h-24 flex flex-col items-center justify-center space-y-2 border-2 hover:border-primary hover:bg-primary/5 transition-all"
              onClick={() => setSelectedRole('user')}
            >
              <UserIcon className="h-6 w-6 text-primary" />
              <div className="font-semibold text-lg">Login as User</div>
            </Button>
          </div>

          <div className="text-center text-sm mt-6">
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

  return (
    <PageTransition>
      <div className="space-y-6">
        <button 
          onClick={() => setSelectedRole(null)}
          className="flex items-center text-sm text-muted-foreground hover:text-foreground transition-colors mb-2"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to roles
        </button>
        
        <div className="space-y-2 text-center">
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">
            {selectedRole === 'admin' ? 'Admin Login' : 'User Login'}
          </h2>
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
