/* eslint-disable react-refresh/only-export-components */
import { createBrowserRouter, Navigate, Outlet, useLocation, useSearchParams } from 'react-router-dom'
import { Suspense } from 'react'
import { lazyRetry } from '@/utils/lazyRetry'
import { AppProvider } from '@/providers/AppProvider'
import { AuthLayout, DashboardLayout, LandingLayout, AdminLayout } from '@/components/layouts'
const LandingPage = lazyRetry(() => import('@/pages/landing/LandingPage').then(m => ({ default: m.LandingPage })), 'LandingPage')

// Marketing Pages
const KnowledgeIntelligencePage = lazyRetry(() => import('@/pages/marketing').then(m => ({ default: m.KnowledgeIntelligencePage })), 'KnowledgeIntelligencePage')
const HybridRetrievalPage = lazyRetry(() => import('@/pages/marketing').then(m => ({ default: m.HybridRetrievalPage })), 'HybridRetrievalPage')
const ReliabilityEnginePage = lazyRetry(() => import('@/pages/marketing').then(m => ({ default: m.ReliabilityEnginePage })), 'ReliabilityEnginePage')
const EnterpriseSecurityPage = lazyRetry(() => import('@/pages/marketing').then(m => ({ default: m.EnterpriseSecurityPage })), 'EnterpriseSecurityPage')

const FinancialServicesPage = lazyRetry(() => import('@/pages/marketing').then(m => ({ default: m.FinancialServicesPage })), 'FinancialServicesPage')
const HealthcarePage = lazyRetry(() => import('@/pages/marketing').then(m => ({ default: m.HealthcarePage })), 'HealthcarePage')
const LegalTechPage = lazyRetry(() => import('@/pages/marketing').then(m => ({ default: m.LegalTechPage })), 'LegalTechPage')
const CustomerSupportPage = lazyRetry(() => import('@/pages/marketing').then(m => ({ default: m.CustomerSupportPage })), 'CustomerSupportPage')

const DocumentationPage = lazyRetry(() => import('@/pages/marketing').then(m => ({ default: m.DocumentationPage })), 'DocumentationPage')
const ApiReferencePage = lazyRetry(() => import('@/pages/marketing').then(m => ({ default: m.ApiReferencePage })), 'ApiReferencePage')
const BlogPage = lazyRetry(() => import('@/pages/marketing').then(m => ({ default: m.BlogPage })), 'BlogPage')
const CaseStudiesPage = lazyRetry(() => import('@/pages/marketing').then(m => ({ default: m.CaseStudiesPage })), 'CaseStudiesPage')

const AboutUsPage = lazyRetry(() => import('@/pages/marketing').then(m => ({ default: m.AboutUsPage })), 'AboutUsPage')
const CareersPage = lazyRetry(() => import('@/pages/marketing').then(m => ({ default: m.CareersPage })), 'CareersPage')
const ContactPage = lazyRetry(() => import('@/pages/marketing').then(m => ({ default: m.ContactPage })), 'ContactPage')
const PrivacyPolicyPage = lazyRetry(() => import('@/pages/marketing').then(m => ({ default: m.PrivacyPolicyPage })), 'PrivacyPolicyPage')
const TermsPage = lazyRetry(() => import('@/pages/marketing').then(m => ({ default: m.TermsPage })), 'TermsPage')

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
const JoinWorkspacePage = lazyRetry(() => import('@/pages/workspace/JoinWorkspacePage').then(m => ({ default: m.JoinWorkspacePage })), 'JoinWorkspacePage')
const EditWorkspace = lazyRetry(() => import('@/pages/workspace/EditWorkspace').then(m => ({ default: m.EditWorkspace })), 'EditWorkspace')
const AcceptInvitationPage = lazyRetry(() => import('@/pages/workspace/AcceptInvitationPage').then(m => ({ default: m.AcceptInvitationPage })), 'AcceptInvitationPage')
const WorkspaceMembersPage = lazyRetry(() => import('@/pages/workspace/WorkspaceMembersPage').then(m => ({ default: m.WorkspaceMembersPage })), 'WorkspaceMembersPage')
const WorkspaceOnboardingPage = lazyRetry(() => import('@/pages/onboarding/WorkspaceOnboardingPage').then(m => ({ default: m.WorkspaceOnboardingPage })), 'WorkspaceOnboardingPage')

const AuditLogsPage = lazyRetry(() => import('@/pages/admin').then(m => ({ default: m.AuditLogsPage })), 'AuditLogsPage')
const QuotaBillingPage = lazyRetry(() => import('@/pages/admin').then(m => ({ default: m.QuotaBillingPage })), 'QuotaBillingPage')
const PlatformAdminPage = lazyRetry(() => import('@/pages/admin').then(m => ({ default: m.PlatformAdminPage })), 'PlatformAdminPage')

import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { getSafeRedirectUrl } from '@/utils/redirect'
import { AnimatePresence } from 'framer-motion'
import { MarketingThemeProvider } from '@/providers/MarketingThemeProvider'

import { PostAuthenticationRouteResolver } from '@/components/auth/PostAuthenticationRouteResolver'
import { BackendUnavailableBanner } from '@/components/auth'
// Outlet & useLocation already imported at the top

// ─── Route Guards ─────────────────────────────────────────────────────────────

export function ProtectedRoute({
  children,
  adminOnly = false,
  requireWorkspace = true,
}: {
  children: React.ReactNode
  adminOnly?: boolean
  requireWorkspace?: boolean
}) {
  const location = useLocation()
  const status = useAuthStore((s) => s.status)
  const isAuthenticated = useAuthStore((s) => s.status === 'AUTHENTICATED')
  const user = useAuthStore((s) => s.user)
  const error = useAuthStore((s) => s.error)
  const currentWorkspace = useWorkspaceStore((s) => s.currentWorkspace)
  const isResolvingWorkspace = useWorkspaceStore((s) => s.isResolvingWorkspace)

  if (status === 'ERROR') {
    if (error?.code === 'BACKEND_UNAVAILABLE') {
      return <BackendUnavailableBanner />
    }
    // For other generic/fatal errors where the user should log in again:
    return <Navigate to="/auth/login" replace />
  }

  // 1. Session / authentication / workspace still resolving -> render loading state
  if (status === 'LOADING' || isResolvingWorkspace) {
    return <SuspenseFallback />
  }

  // 2. Unauthenticated -> redirect to login preserving safe redirect destination
  if (!isAuthenticated) {
    const rawRedirect = location.pathname + location.search
    const safeRedirect = getSafeRedirectUrl(rawRedirect, '/dashboard')
    const query = safeRedirect && safeRedirect !== '/dashboard' ? `?redirect=${encodeURIComponent(safeRedirect)}` : ''
    return <Navigate to={`/auth/login${query}`} replace />
  }

  // 3. Authenticated but NO active workspace context -> route to onboarding bridge
  const hasActiveWorkspace = !!(currentWorkspace?.id || user?.tenant_id)
  if (requireWorkspace && !hasActiveWorkspace) {
    return <Navigate to="/onboarding" replace />
  }

  // 4. Role check for adminOnly routes
  const userRole = String(user?.role || '').trim().toLowerCase()
  if (adminOnly && !['admin', 'owner', 'platform_admin'].includes(userRole)) {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}

export function PublicOnlyRoute({ children }: { children: React.ReactNode }) {
  const [searchParams] = useSearchParams()
  const status = useAuthStore((s) => s.status)
  const isAuthenticated = useAuthStore((s) => s.status === 'AUTHENTICATED')
  const user = useAuthStore((s) => s.user)
  const currentWorkspace = useWorkspaceStore((s) => s.currentWorkspace)
  const isResolvingWorkspace = useWorkspaceStore((s) => s.isResolvingWorkspace)

  if (status === 'LOADING' || isResolvingWorkspace) {
    return <SuspenseFallback />
  }

  if (isAuthenticated) {
    const hasActiveWorkspace = !!(currentWorkspace?.id || user?.tenant_id)
    if (!hasActiveWorkspace) {
      return <Navigate to="/onboarding" replace />
    }
    const safeRedirect = getSafeRedirectUrl(searchParams.get('redirect'), '/dashboard')
    return <Navigate to={safeRedirect} replace />
  }

  return <>{children}</>
}

export function OnboardingRoute({ children }: { children: React.ReactNode }) {
  const status = useAuthStore((s) => s.status)
  const isAuthenticated = useAuthStore((s) => s.status === 'AUTHENTICATED')
  const user = useAuthStore((s) => s.user)
  const currentWorkspace = useWorkspaceStore((s) => s.currentWorkspace)
  const isResolvingWorkspace = useWorkspaceStore((s) => s.isResolvingWorkspace)

  if (status === 'LOADING' || isResolvingWorkspace) {
    return <SuspenseFallback />
  }

  if (!isAuthenticated) {
    return <Navigate to="/auth/login?redirect=/onboarding" replace />
  }

  // If user already has an active workspace established, bridge to dashboard
  const hasActiveWorkspace = !!(currentWorkspace?.id || user?.tenant_id)
  if (hasActiveWorkspace) {
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
          { index: true, element: <LandingPage /> },
          // Platform
          { path: 'platform/knowledge-intelligence', element: <KnowledgeIntelligencePage /> },
          { path: 'platform/hybrid-retrieval', element: <HybridRetrievalPage /> },
          { path: 'platform/reliability-engine', element: <ReliabilityEnginePage /> },
          { path: 'platform/security', element: <EnterpriseSecurityPage /> },
          // Solutions
          { path: 'solutions/financial-services', element: <FinancialServicesPage /> },
          { path: 'solutions/healthcare', element: <HealthcarePage /> },
          { path: 'solutions/legal-tech', element: <LegalTechPage /> },
          { path: 'solutions/customer-support', element: <CustomerSupportPage /> },
          // Resources
          { path: 'resources/documentation', element: <DocumentationPage /> },
          { path: 'resources/api-reference', element: <ApiReferencePage /> },
          { path: 'resources/blog', element: <BlogPage /> },
          { path: 'resources/case-studies', element: <CaseStudiesPage /> },
          // Company
          { path: 'about', element: <AboutUsPage /> },
          { path: 'careers', element: <CareersPage /> },
          { path: 'contact', element: <ContactPage /> },
          { path: 'privacy', element: <PrivacyPolicyPage /> },
          // Direct legal aliases
          { path: 'terms', element: <TermsPage /> },
          { path: 'security', element: <EnterpriseSecurityPage /> },
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
        path: '/onboarding',
        element: (
          <OnboardingRoute>
            <WorkspaceOnboardingPage />
          </OnboardingRoute>
        ),
      },
      {
        path: '/workspaces/new',
        element: (
          <ProtectedRoute requireWorkspace={false}>
            <CreateWorkspace />
          </ProtectedRoute>
        ),
      },
      {
        path: '/workspaces/join',
        element: (
          <ProtectedRoute requireWorkspace={false}>
            <JoinWorkspacePage />
          </ProtectedRoute>
        ),
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
                  { path: 'appearance', element: <Navigate to="profile" replace /> },
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
