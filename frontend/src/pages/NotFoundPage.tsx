import { Link } from 'react-router-dom'
import { PageTransition } from '@/components/layouts'
import { Button } from '@/components/common/Button'
import { BackgroundProvider } from '@/components/backgrounds'
import { FileQuestion, ArrowLeft, Home } from 'lucide-react'

export function NotFoundPage() {
  return (
    <div className="relative min-h-screen w-full flex items-center justify-center p-4 overflow-hidden">
      <BackgroundProvider type="aurora" />
      
      <PageTransition className="relative z-10 w-full max-w-md">
        <div className="flex flex-col items-center text-center">
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-surface-elevated border border-border shadow-sm mb-8 text-muted-foreground">
            <FileQuestion className="h-10 w-10" />
          </div>
          
          <h1 className="text-4xl font-bold tracking-tight text-foreground mb-2">404</h1>
          <h2 className="text-xl font-semibold text-foreground mb-4">Page not found</h2>
          
          <p className="text-muted-foreground mb-8 max-w-sm">
            The page you are looking for doesn't exist or has been moved to a different URL.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-3 w-full sm:justify-center">
            <Button variant="outline" asChild>
              <button onClick={() => window.history.back()}>
                <ArrowLeft className="mr-2 h-4 w-4" />
                Go Back
              </button>
            </Button>
            <Button asChild>
              <Link to="/dashboard">
                <Home className="mr-2 h-4 w-4" />
                Back to Home
              </Link>
            </Button>
          </div>
        </div>
      </PageTransition>
    </div>
  )
}
