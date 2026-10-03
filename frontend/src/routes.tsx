/* eslint-disable react-refresh/only-export-components */
import { createBrowserRouter, Navigate, Outlet, useLocation, useSearchParams } from 'react-router-dom'
import { Suspense } from 'react'
import { lazyRetry } from '@/utils/lazyRetry'
import { AppProvider } from '@/providers/AppProvider'
import { AuthLayout, DashboardLayout, LandingLayout, AdminLayout } from '@/components/layouts'
const LandingPage = lazyRetry(() => import('@/pages/landing/LandingPage').then(m => ({ default: m.LandingPage })), 'LandingPage')
const LoginPage = lazyRetry(() => import('@/pages/auth').then(m => ({ default: m.LoginPage })), 'LoginPage')
const RegisterPage = lazyRetry(() => import('@/pages/auth').then(m => ({ default: m.RegisterPage })), 'RegisterPage')
const VerifyPage = lazyRetry(() => import('@/pages/auth').then(m => ({ default: m.VerifyPage })), 'VerifyPage')
const ResendVerificationPage = lazyRetry(() => import('@/pages/auth').then(m => ({ default: m.ResendVerificationPage })), 'ResendVerificationPage')
const ForgotPasswordPage = lazyRetry(() => import('@/pages/auth').then(m => ({ default: m.ForgotPasswordPage })), 'ForgotPasswordPage')
const ResetPasswordPage = lazyRetry(() => import('@/pages/auth').then(m => ({ default: m.ResetPasswordPage })), 'ResetPasswordPage')
const OAuthCallbackPage = lazyRetry(() => import('@/pages/auth').then(m => ({ default: m.OAuthCallbackPage })), 'OAuthCallbackPage')

const DashboardPage = lazyRetry(() => import('@/pages/dashboard').then(m => ({ default: m.DashboardPage })), 'DashboardPage')
const KnowledgeIntelligenceDashboardPage = lazyRetry(() => import('@/pages/dashboard').then(m => ({ default: m.KnowledgeIntelligenceDashboardPage })), 'KnowledgeIntelligenceDashboardPage')
const DocumentsPage = lazyRetry(() => import('@/pages/documents').then(m => ({ default: m.DocumentsPage })), 'DocumentsPage')
const KnowledgeProcessingPage = lazyRetry(() => import('@/pages/knowledge-processing').then(m => ({ default: m.KnowledgeProcessingPage })), 'KnowledgeProcessingPage')
const KnowledgeHealthPage = lazyRetry(() => import('@/pages/knowledge_health').then(m => ({ default: m.KnowledgeHealthPage })), 'KnowledgeHealthPage')
const ReliabilityDashboardPage = lazyRetry(() => import('@/pages/analytics').then(m => ({ default: m.ReliabilityDashboardPage })), 'ReliabilityDashboardPage')
const WorkspaceAnalyticsPage = lazyRetry(() => import('@/pages/analytics/WorkspaceAnalyticsPage').then(m => ({ default: m.WorkspaceAnalyticsPage })), 'WorkspaceAnalyticsPage')


const SettingsLayout = lazyRetry(() => import('@/pages/settings').then(m => ({ default: m.SettingsLayout })), 'SettingsLayout')
const ProfileSettings = lazyRetry(() => import('@/pages/settings').then(m => ({ default: m.ProfileSettings })), 'ProfileSettings')
const AppearanceSettings = lazyRetry(() => import('@/pages/settings').then(m => ({ default: m.AppearanceSettings })), 'AppearanceSettings')
const SecuritySettings = lazyRetry(() => import('@/pages/settings').then(m => ({ default: m.SecuritySettings })), 'SecuritySettings')
const NotificationSettings = lazyRetry(() => import('@/pages/settings').then(m => ({ default: m.NotificationSettings })), 'NotificationSettings')
const AIPrefSettings = lazyRetry(() => import('@/pages/settings').then(m => ({ default: m.AIPrefSettings })), 'AIPrefSettings')
const WorkspaceSettings = lazyRetry(() => import('@/pages/settings').then(m => ({ default: m.WorkspaceSettings })), 'WorkspaceSettings')
const WebhookSettings = lazyRetry(() => import('@/pages/settings').then(m => ({ default: m.WebhookSettings })), 'WebhookSettings')
const DeveloperSettings = lazyRetry(() => import('@/pages/settings').then(m => ({ default: m.DeveloperSettings })), 'DeveloperSettings')
const PrivacySettings = lazyRetry(() => import('@/pages/settings').then(m => ({ default: m.PrivacySettings })), 'PrivacySettings')
const ActivitySettings = lazyRetry(() => import('@/pages/settings').then(m => ({ default: m.ActivitySettings })), 'ActivitySettings')

const AIChatPage = lazyRetry(() => import('@/pages/chat').then(m => ({ default: m.AIChatPage })), 'AIChatPage')
const NotFoundPage = lazyRetry(() => import('@/pages/NotFoundPage').then(m => ({ default: m.NotFoundPage })), 'NotFoundPage')
const CreateWorkspace = lazyRetry(() => import('@/pages/workspace/CreateWorkspace').then(m => ({ default: m.CreateWorkspace })), 'CreateWorkspace')
const EditWorkspace = lazyRetry(() => import('@/pages/workspace/EditWorkspace').then(m => ({ default: m.EditWorkspace })), 'EditWorkspace')
const AcceptInvitationPage = lazyRetry(() => import('@/pages/workspace/AcceptInvitationPage').then(m => ({ default: m.AcceptInvitationPage })), 'AcceptInvitationPage')
const WorkspaceMembersPage = lazyRetry(() => import('@/pages/workspace/WorkspaceMembersPage').then(m => ({ default: m.WorkspaceMembersPage })), 'WorkspaceMembersPage')

const AuditLogsPage = lazyRetry(() => import('@/pages/admin').then(m => ({ default: m.AuditLogsPage })), 'AuditLogsPage')
const QuotaBillingPage = lazyRetry(() => import('@/pages/admin').then(m => ({ default: m.QuotaBillingPage })), 'QuotaBillingPage')
const PlatformAdminPage = lazyRetry(() => import('@/pages/admin').then(m => ({ default: m.PlatformAdminPage })), 'PlatformAdminPage')

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

export function LegacyAnalyticsRedirect() {
  const [searchParams] = useSearchParams()
  const params = new URLSearchParams(searchParams)
  if (!params.has('tab')) {
    params.set('tab', 'overview')
  }
  return <Navigate to={`/reliability?${params.toString()}`} replace />
}

export function LegacyDiagnosticsRedirect() {
  const [searchParams] = useSearchParams()
  const params = new URLSearchParams(searchParams)
  if (!params.has('tab')) {
    params.set('tab', 'explorer')
  }
  return <Navigate to={`/reliability?${params.toString()}`} replace />
}

export function LegacyHealthRedirect() {
  const [searchParams] = useSearchParams()
  const search = searchParams.toString()
  return <Navigate to={`/knowledge-health${search ? `?${search}` : ''}`} replace />
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
        path: '/auth/callback',
        element: <AuthLayout />,
        children: [
          { index: true, element: <OAuthCallbackPage /> }
        ],
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
              { path: 'knowledge-processing', element: <ProtectedRoute adminOnly><KnowledgeProcessingPage /></ProtectedRoute> },
              { path: 'chunks', element: <ProtectedRoute adminOnly><Navigate to="/knowledge-processing?stage=chunks" replace /></ProtectedRoute> },
              { path: 'embeddings', element: <ProtectedRoute adminOnly><Navigate to="/knowledge-processing?stage=embeddings" replace /></ProtectedRoute> },
              { path: 'vectors', element: <ProtectedRoute adminOnly><Navigate to="/knowledge-processing?stage=vectors" replace /></ProtectedRoute> },

              // Canonical Operational Consoles
              { path: 'reliability', element: <ProtectedRoute adminOnly><ReliabilityDashboardPage /></ProtectedRoute> },
              { path: 'knowledge-health', element: <ProtectedRoute adminOnly><KnowledgeHealthPage /></ProtectedRoute> },

              // Legacy Compatibility Redirects
              { path: 'analytics', element: <ProtectedRoute adminOnly><LegacyAnalyticsRedirect /></ProtectedRoute> },
              { path: 'diagnostics', element: <ProtectedRoute adminOnly><LegacyDiagnosticsRedirect /></ProtectedRoute> },
              { path: 'health', element: <ProtectedRoute adminOnly><LegacyHealthRedirect /></ProtectedRoute> },

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
