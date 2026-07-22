import { Link, useLocation } from 'react-router-dom'
import { ChevronRight, Home } from 'lucide-react'

const ROUTE_LABELS: Record<string, string> = {
  dashboard: 'Executive Overview',
  'knowledge-intelligence': 'Knowledge Intelligence',
  analytics: 'AI Reliability',
  investigation: 'Investigation Console',
  documents: 'Documents',
  chunks: 'Knowledge Chunks',
  embeddings: 'Vector Embeddings',
  vectors: 'Vector Storage',
  admin: 'Administration',
  health: 'System Health',
  users: 'Access Control',
  settings: 'Preferences',
}

export function Breadcrumbs() {
  const location = useLocation()
  const paths = location.pathname.split('/').filter(Boolean)

  if (paths.length === 0 || paths[0] === 'dashboard') return null

  return (
    <nav aria-label="Breadcrumb" className="flex items-center text-sm text-muted-foreground">
      <ol className="flex items-center space-x-2">
        <li>
          <Link
            to="/dashboard"
            className="flex items-center hover:text-foreground transition-colors outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-sm"
          >
            <Home className="h-4 w-4" />
            <span className="sr-only">Home</span>
          </Link>
        </li>
        {paths.map((path, index) => {
          const isLast = index === paths.length - 1
          const href = `/${paths.slice(0, index + 1).join('/')}`
          
          let label = ROUTE_LABELS[path]
          if (!label) {
            label = path.charAt(0).toUpperCase() + path.slice(1).replace(/-/g, ' ')
          }

          return (
            <li key={path} className="flex items-center space-x-2">
              <ChevronRight className="h-4 w-4 shrink-0 opacity-50" />
              {isLast ? (
                <span className="font-medium text-foreground" aria-current="page">
                  {label}
                </span>
              ) : (
                <Link
                  to={href}
                  className="hover:text-foreground transition-colors outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-sm"
                >
                  {label}
                </Link>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
