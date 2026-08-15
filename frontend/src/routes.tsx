/* eslint-disable react-refresh/only-export-components */
import { createBrowserRouter, Navigate, Outlet, useLocation } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { AppProvider } from '@/providers/AppProvider'
import { AuthLayout, DashboardLayout, LandingLayout, AdminLayout } from '@/components/layouts'
const LandingPage = lazy(() => import('@/pages/landing/LandingPage').then(m => ({ default: m.LandingPage })))
const LoginPage = lazy(() => import('@/pages/auth').then(m => ({ default: m.LoginPage })))
const RegisterPage = lazy(() => import('@/pages/auth').then(m => ({ default: m.RegisterPage })))
const VerifyPage = lazy(() => import('@/pages/auth').then(m => ({ default: m.VerifyPage })))
const ResendVerificationPage = lazy(() => import('@/pages/auth').then(m => ({ default: m.ResendVerificationPage })))
const ForgotPasswordPage = lazy(() => import('@/pages/auth').then(m => ({ default: m.ForgotPasswordPage })))
const ResetPasswordPage = lazy(() => import('@/pages/auth').then(m => ({ default: m.ResetPasswordPage })))

const DashboardPage = lazy(() => import('@/pages/dashboard').then(m => ({ default: m.DashboardPage })))
const KnowledgeIntelligenceDashboardPage = lazy(() => import('@/pages/dashboard').then(m => ({ default: m.KnowledgeIntelligenceDashboardPage })))
const DocumentsPage = lazy(() => import('@/pages/documents').then(m => ({ default: m.DocumentsPage })))
const ChunksPage = lazy(() => import('@/pages/chunks').then(m => ({ default: m.ChunksPage })))
const EmbeddingsPage = lazy(() => import('@/pages/embeddings').then(m => ({ default: m.EmbeddingsPage })))
const VectorsPage = lazy(() => import('@/pages/vectors').then(m => ({ default: m.VectorsPage })))
const KnowledgeHealthPage = lazy(() => import('@/pages/knowledge_health').then(m => ({ default: m.KnowledgeHealthPage })))
const ReliabilityDashboardPage = lazy(() => import('@/pages/analytics').then(m => ({ default: m.ReliabilityDashboardPage })))
const WorkspaceAnalyticsPage = lazy(() => import('@/pages/analytics/WorkspaceAnalyticsPage').then(m => ({ default: m.WorkspaceAnalyticsPage })))
const DeveloperInvestigationPage = lazy(() => import('@/pages/investigation').then(m => ({ default: m.DeveloperInvestigationPage })))

const SettingsLayout = lazy(() => import('@/pages/settings').then(m => ({ default: m.SettingsLayout })))
const ProfileSettings = lazy(() => import('@/pages/settings').then(m => ({ default: m.ProfileSettings })))
const AppearanceSettings = lazy(() => import('@/pages/settings').then(m => ({ default: m.AppearanceSettings })))
const SecuritySettings = lazy(() => import('@/pages/settings').then(m => ({ default: m.SecuritySettings })))
const NotificationSettings = lazy(() => import('@/pages/settings').then(m => ({ default: m.NotificationSettings })))
const AIPrefSettings = lazy(() => import('@/pages/settings').then(m => ({ default: m.AIPrefSettings })))
const WorkspaceSettings = lazy(() => import('@/pages/settings').then(m => ({ default: m.WorkspaceSettings })))
const WebhookSettings = lazy(() => import('@/pages/settings').then(m => ({ default: m.WebhookSettings })))
const DeveloperSettings = lazy(() => import('@/pages/settings').then(m => ({ default: m.DeveloperSettings })))
const PrivacySettings = lazy(() => import('@/pages/settings').then(m => ({ default: m.PrivacySettings })))
const ActivitySettings = lazy(() => import('@/pages/settings').then(m => ({ default: m.ActivitySettings })))

const AIChatPage = lazy(() => import('@/pages/chat').then(m => ({ default: m.AIChatPage })))
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage').then(m => ({ default: m.NotFoundPage })))
const CreateWorkspace = lazy(() => import('@/pages/workspace/CreateWorkspace').then(m => ({ default: m.CreateWorkspace })))
const EditWorkspace = lazy(() => import('@/pages/workspace/EditWorkspace').then(m => ({ default: m.EditWorkspace })))
const AcceptInvitationPage = lazy(() => import('@/pages/workspace/AcceptInvitationPage').then(m => ({ default: m.AcceptInvitationPage })))
const WorkspaceMembersPage = lazy(() => import('@/pages/workspace/WorkspaceMembersPage').then(m => ({ default: m.WorkspaceMembersPage })))

const AuditLogsPage = lazy(() => import('@/pages/admin').then(m => ({ default: m.AuditLogsPage })))
const QuotaBillingPage = lazy(() => import('@/pages/admin').then(m => ({ default: m.QuotaBillingPage })))
const PlatformAdminPage = lazy(() => import('@/pages/admin').then(m => ({ default: m.PlatformAdminPage })))

import { useAuthStore } from '@/stores/authStore'
import { AnimatePresence } from 'framer-motion'
import { MarketingThemeProvider } from '@/providers/MarketingThemeProvider'

import { PostAuthenticationRouteResolver } from '@/components/auth/PostAuthenticationRouteResolver'
import { BackendUnavailableBanner } from '@/components/auth'
// Outlet & useLocation already imported at the top

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

  if (adminOnly && !['admin', 'owner', 'platform_admin'].includes(user?.role || '')) {
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
              { path: 'workspace-analytics', element: <ProtectedRoute adminOnly><WorkspaceAnalyticsPage /></ProtectedRoute> },
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
                  { path: 'webhooks', element: <WebhookSettings /> },
                  { path: 'developer', element: <DeveloperSettings /> },
                  { path: 'privacy', element: <PrivacySettings /> },
                  { path: 'activity', element: <ActivitySettings /> },
                ]
              },
              
              // Workspace Management
              { path: 'workspaces/new', element: <CreateWorkspace /> },
              { path: 'w/:slug/edit', element: <EditWorkspace /> },
              { path: 'workspaces/:workspaceId/members', element: <WorkspaceMembersPage /> },
              { path: 'w/:workspaceId/members', element: <WorkspaceMembersPage /> },
              
              // Admin Portal (Epic 12)
              {
                path: 'admin',
                element: <ProtectedRoute adminOnly><AdminLayout /></ProtectedRoute>,
                children: [
                  { index: true, element: <Navigate to="workspace" replace /> },
                  { path: 'workspace', element: <WorkspaceSettings /> },
                  { path: 'members', element: <WorkspaceMembersPage /> },
                  { path: 'quota', element: <QuotaBillingPage /> },
                  { path: 'audit', element: <AuditLogsPage /> },
                  { path: 'platform', element: <PlatformAdminPage /> },
                ]
              },
            ],
          }
        ],
      },
      {
        path: '/invitations/accept',
        element: <AcceptInvitationPage />,
      },
      {
        path: '*',
        element: <MarketingThemeProvider><NotFoundPage /></MarketingThemeProvider>,
      },
    ],
  },
])

function SuspenseFallback() {
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-background pointer-events-none">
      <div className="w-8 h-8 border-[3px] border-primary border-t-transparent rounded-full animate-spin"></div>
    </div>
  )
}

// Helper component for AnimatePresence support across layout boundaries
function OutletWithAnimation() {
  const location = useLocation()

  // Group chat routes under a single key to prevent unmounting during chat session navigation
  // This prevents the chat streaming state from being destroyed when navigating from /chat to /chat/:id
  const animationKey = location.pathname.startsWith('/chat') ? '/chat' : location.pathname

  return (
    <AnimatePresence mode="wait">
      <Suspense fallback={<SuspenseFallback />}>
        <Outlet key={animationKey} />
      </Suspense>
    </AnimatePresence>
  )
}
