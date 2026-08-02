/* eslint-disable react-refresh/only-export-components */
import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppProvider } from '@/providers/AppProvider'
import { AuthLayout, DashboardLayout, LandingLayout } from '@/components/layouts'
import { LoginPage, RegisterPage, VerifyPage, ResendVerificationPage, ForgotPasswordPage, ResetPasswordPage } from '@/pages/auth'
import { LandingPage } from '@/pages/landing/LandingPage'
import { DashboardPage, KnowledgeIntelligenceDashboardPage } from '@/pages/dashboard'
import { DocumentsPage } from '@/pages/documents'
import { ChunksPage } from '@/pages/chunks'
import { EmbeddingsPage } from '@/pages/embeddings'
import { VectorsPage } from '@/pages/vectors'
import { KnowledgeHealthPage } from '@/pages/knowledge_health'
import { ReliabilityDashboardPage } from '@/pages/analytics'
import { DeveloperInvestigationPage } from '@/pages/investigation'
import {
  SettingsLayout,
  ProfileSettings,
  AppearanceSettings,
  SecuritySettings,
  NotificationSettings,
  AIPrefSettings,
  WorkspaceSettings,
  DeveloperSettings,
  PrivacySettings,
  ActivitySettings
} from '@/pages/settings'
import { AIChatPage } from '@/pages/chat'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { CreateWorkspace } from '@/pages/workspace/CreateWorkspace'
import { EditWorkspace } from '@/pages/workspace/EditWorkspace'
import { useAuthStore } from '@/stores/authStore'
import { AnimatePresence } from 'framer-motion'
import { MarketingThemeProvider } from '@/providers/MarketingThemeProvider'

import { PostAuthenticationRouteResolver } from '@/components/auth/PostAuthenticationRouteResolver'
import { BackendUnavailableBanner } from '@/components/auth'
import { Outlet, useLocation } from 'react-router-dom'

// ─── Route Guards ─────────────────────────────────────────────────────────────

function ProtectedRoute({ children, adminOnly = false }: { children: React.ReactNode, adminOnly?: boolean }) {
  const status = useAuthStore((s) => s.status)
  const isAuthenticated = useAuthStore((s) => s.status === 'AUTHENTICATED')
  const user = useAuthStore((s) => s.user)
  const error = useAuthStore((s) => s.error)

  if (status === 'ERROR') {
    if (error?.code === 'BACKEND_UNAVAILABLE') {
      return <BackendUnavailableBanner />
    }
    // For other generic/fatal errors where the user should log in again:
    return <Navigate to="/auth/login" replace />
  }

  if (status === 'LOADING') {
    return null
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
    return null
  }

  if (isAuthenticated) {
    const lastVisited = localStorage.getItem('raguard-last-page')
    // If we have a last visited page that isn't auth, use it, else default to dashboard
    const target = (lastVisited && !lastVisited.startsWith('/auth')) ? lastVisited : '/dashboard'
    return <Navigate to={target} replace />
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
        element: <LandingLayout />,
        children: [
          { index: true, element: <LandingPage /> }
        ]
      },
      {
        path: '/auth',
        element: <PublicOnlyRoute><AuthLayout /></PublicOnlyRoute>,
        children: [
          { path: 'login', element: <LoginPage /> },
          { path: 'register', element: <RegisterPage /> },
          { path: 'verify', element: <VerifyPage /> },
          { path: 'resend-verification', element: <ResendVerificationPage /> },
          { path: 'forgot-password', element: <ForgotPasswordPage /> },
          { path: 'reset-password', element: <ResetPasswordPage /> },
          { path: '', element: <Navigate to="/auth/login" replace /> },
        ],
      },
      {
        element: (
          <ProtectedRoute>
            <PostAuthenticationRouteResolver />
          </ProtectedRoute>
        ),
        children: [
          {
            element: <DashboardLayout />,
            children: [
              // Common (User & Admin)
              { path: 'dashboard', element: <DashboardPage /> },
              { path: 'chat', element: <AIChatPage /> },
              { path: 'chat/:sessionId', element: <AIChatPage /> },

              // Admin Only
              { path: 'knowledge', element: <ProtectedRoute adminOnly><KnowledgeIntelligenceDashboardPage /></ProtectedRoute> },
              { path: 'documents', element: <ProtectedRoute adminOnly><DocumentsPage /></ProtectedRoute> },
              { path: 'analytics', element: <ProtectedRoute adminOnly><ReliabilityDashboardPage /></ProtectedRoute> },
              { path: 'chunks', element: <ProtectedRoute adminOnly><ChunksPage /></ProtectedRoute> },
              { path: 'embeddings', element: <ProtectedRoute adminOnly><EmbeddingsPage /></ProtectedRoute> },
              { path: 'vectors', element: <ProtectedRoute adminOnly><VectorsPage /></ProtectedRoute> },
              { path: 'health', element: <ProtectedRoute adminOnly><KnowledgeHealthPage /></ProtectedRoute> },
              { path: 'diagnostics', element: <ProtectedRoute adminOnly><DeveloperInvestigationPage /></ProtectedRoute> },

              // Settings
              {
                path: 'settings',
                element: <SettingsLayout />,
                children: [
                  { index: true, element: <Navigate to="profile" replace /> },
                  { path: 'profile', element: <ProfileSettings /> },
                  { path: 'security', element: <SecuritySettings /> },
                  { path: 'appearance', element: <AppearanceSettings /> },
                  { path: 'notifications', element: <NotificationSettings /> },
                  { path: 'ai', element: <AIPrefSettings /> },
                  { path: 'workspace', element: <WorkspaceSettings /> },
                  { path: 'developer', element: <DeveloperSettings /> },
                  { path: 'privacy', element: <PrivacySettings /> },
                  { path: 'activity', element: <ActivitySettings /> },
                ]
              },
              
              // Workspace Management
              { path: 'workspaces/new', element: <CreateWorkspace /> },
              { path: 'w/:slug/edit', element: <EditWorkspace /> }
            ],
          }
        ],
      },
      {
        path: '*',
        element: <MarketingThemeProvider><NotFoundPage /></MarketingThemeProvider>,
      },
    ],
  },
])

// Helper component for AnimatePresence support across layout boundaries
function OutletWithAnimation() {
  const location = useLocation()

  // Group chat routes under a single key to prevent unmounting during chat session navigation
  // This prevents the chat streaming state from being destroyed when navigating from /chat to /chat/:id
  const animationKey = location.pathname.startsWith('/chat') ? '/chat' : location.pathname

  return (
    <AnimatePresence mode="wait">
      <Outlet key={animationKey} />
    </AnimatePresence>
  )
}
