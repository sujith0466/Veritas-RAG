import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppProvider } from '@/providers/AppProvider'
import { AuthLayout, DashboardLayout } from '@/components/layouts'
import { LoginPage, RegisterPage } from '@/pages/auth'
import { DashboardPage, KnowledgeIntelligenceDashboardPage } from '@/pages/dashboard'
import { DocumentsPage } from '@/pages/documents'
import { ChunksPage } from '@/pages/chunks'
import { EmbeddingsPage } from '@/pages/embeddings'
import { VectorsPage } from '@/pages/vectors'
import { KnowledgeHealthPage } from '@/pages/knowledge_health'
import { ReliabilityDashboardPage } from '@/pages/analytics'
import { DeveloperInvestigationPage } from '@/pages/investigation'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { useAuthStore } from '@/stores/authStore'
import { GlobalLoadingOverlay } from '@/components/feedback/GlobalLoadingOverlay'
import { AnimatePresence } from 'framer-motion'

// ─── Route Guards ─────────────────────────────────────────────────────────────

function ProtectedRoute({ children, adminOnly = false }: { children: React.ReactNode, adminOnly?: boolean }) {
  const status = useAuthStore((s) => s.status)
  const isAuthenticated = useAuthStore((s) => s.status === 'AUTHENTICATED')
  const user = useAuthStore((s) => s.user)

  if (status === 'LOADING') {
    return <GlobalLoadingOverlay message="Verifying secure session..." />
  }

  if (!isAuthenticated) {
    return <Navigate to="/auth/login" replace />
  }

  if (adminOnly && user?.role !== 'admin') {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}

function PublicOnlyRoute({ children }: { children: React.ReactNode }) {
  const status = useAuthStore((s) => s.status)
  const isAuthenticated = useAuthStore((s) => s.status === 'AUTHENTICATED')

  if (status === 'LOADING') {
    return <GlobalLoadingOverlay message="Checking session..." />
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}

// ─── Router Configuration ─────────────────────────────────────────────────────

export const router = createBrowserRouter([
  {
    element: <AppProvider><OutletWithAnimation /></AppProvider>,
    children: [
      {
        path: '/',
        element: <Navigate to="/dashboard" replace />,
      },
      {
        path: '/auth',
        element: <PublicOnlyRoute><AuthLayout /></PublicOnlyRoute>,
        children: [
          { path: 'login', element: <LoginPage /> },
          { path: 'register', element: <RegisterPage /> },
          { path: '', element: <Navigate to="/auth/login" replace /> },
        ],
      },
      {
        path: '/',
        element: <ProtectedRoute><DashboardLayout /></ProtectedRoute>,
        children: [
          { path: 'dashboard', element: <DashboardPage /> },
          { path: 'knowledge-intelligence', element: <KnowledgeIntelligenceDashboardPage /> },
          { path: 'analytics', element: <ReliabilityDashboardPage /> },
          { path: 'investigation', element: <DeveloperInvestigationPage /> },
          { path: 'documents', element: <DocumentsPage /> },
          { path: 'chunks', element: <ChunksPage /> },
          { path: 'embeddings', element: <EmbeddingsPage /> },
          { path: 'vectors', element: <VectorsPage /> },
          { path: 'admin/health', element: <KnowledgeHealthPage /> },
          { path: 'admin/users', element: <DashboardPage /> },
          { path: 'settings', element: <DashboardPage /> },
        ],
      },
      {
        path: '*',
        element: <NotFoundPage />,
      },
    ],
  },
])

// Helper component for AnimatePresence support across layout boundaries
import { Outlet, useLocation } from 'react-router-dom'

function OutletWithAnimation() {
  const location = useLocation()
  return (
    <AnimatePresence mode="wait">
      <Outlet key={location.pathname} />
    </AnimatePresence>
  )
}
