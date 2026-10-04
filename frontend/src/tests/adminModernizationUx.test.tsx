import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AdminLayout } from '@/components/layouts/AdminLayout'
import { AdminPageHeader } from '@/components/admin/AdminPageHeader'
import { PlatformAdminPage } from '@/pages/admin/PlatformAdminPage'
import { adminService } from '@/services/adminService'
import { useAuthStore } from '@/stores/authStore'

describe('Admin Portal UI/UX Modernization (ADMIN-05)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.setState({
      user: {
        id: 'u-admin-1',
        email: 'admin@veritas.internal',
        role: 'owner',
        workspace_id: 'ws-test-101',
        tenant_id: 'ws-test-101',
        workspace_name: 'Veritas AI Labs',
      } as any,
      status: 'AUTHENTICATED',
      token: 'jwt-mock-token',
      error: undefined,
    })
  })

  describe('AdminPageHeader Component', () => {
    it('renders category eyebrow, title, description, and badge', () => {
      render(
        <AdminPageHeader
          eyebrow="SYSTEM / TESTING"
          title="Telemetry Console"
          description="Real-time evaluation of infrastructure metrics."
          badge={<span data-testid="status-badge">LIVE</span>}
          actions={<button>Export</button>}
        />
      )

      expect(screen.getByText('SYSTEM / TESTING')).toBeInTheDocument()
      expect(screen.getByText('Telemetry Console')).toBeInTheDocument()
      expect(screen.getByText('Real-time evaluation of infrastructure metrics.')).toBeInTheDocument()
      expect(screen.getByTestId('status-badge')).toHaveTextContent('LIVE')
      expect(screen.getByRole('button', { name: /Export/i })).toBeInTheDocument()
    })

    it('renders breadcrumbs navigation when provided', () => {
      render(
        <AdminPageHeader
          title="Audit Ledger"
          breadcrumbs={[
            { label: 'Admin', href: '/admin' },
            { label: 'Security' },
          ]}
        />
      )

      expect(screen.getByRole('navigation', { name: /Breadcrumb/i })).toBeInTheDocument()
      expect(screen.getByText('Admin')).toBeInTheDocument()
      expect(screen.getByText('Security')).toBeInTheDocument()
    })
  })

  describe('AdminLayout Modern Shell & Responsive Navigation', () => {
    it('renders workspace identity card and persistent sidebar navigation links', () => {
      render(
        <MemoryRouter initialEntries={['/admin/workspace']}>
          <Routes>
            <Route path="/admin" element={<AdminLayout />}>
              <Route path="workspace" element={<div data-testid="child-page">Workspace Content</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      )

      // Workspace card in sidebar
      expect(screen.getByText('Veritas AI Labs')).toBeInTheDocument()
      expect(screen.getByText('OWNER')).toBeInTheDocument()

      // Primary navigation links in desktop sidebar
      expect(screen.getByRole('link', { name: /Workspace Settings/i })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /Members & Access/i })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /Resource & Governance/i })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /Audit Ledger/i })).toBeInTheDocument()

      // Active child route
      expect(screen.getByTestId('child-page')).toBeInTheDocument()
    })

    it('toggles mobile navigation drawer sheet with accessible attributes', () => {
      render(
        <MemoryRouter initialEntries={['/admin/workspace']}>
          <Routes>
            <Route path="/admin" element={<AdminLayout />}>
              <Route path="workspace" element={<div>Workspace Page</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      )

      const menuToggle = screen.getByLabelText(/Open navigation drawer/i)
      expect(menuToggle).toHaveAttribute('aria-expanded', 'false')

      fireEvent.click(menuToggle)
      expect(menuToggle).toHaveAttribute('aria-expanded', 'true')

      // Exit button inside mobile drawer
      expect(screen.getByText(/Exit to Main Dashboard/i)).toBeInTheDocument()
    })

    it('exposes Platform Admin nav item when user possesses platform_admin role', () => {
      useAuthStore.setState({
        user: {
          id: 'u-sys-admin',
          email: 'root@veritas.internal',
          role: 'platform_admin',
          workspace_id: 'ws-root',
          workspace_name: 'Global Ops',
        } as any,
        status: 'AUTHENTICATED',
      })

      render(
        <MemoryRouter initialEntries={['/admin/workspace']}>
          <Routes>
            <Route path="/admin" element={<AdminLayout />}>
              <Route path="workspace" element={<div>Workspace Page</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      )

      expect(screen.getByRole('link', { name: /Platform Admin/i })).toBeInTheDocument()
    })
  })

  describe('PlatformAdminPage', () => {
    it('renders global infrastructure metrics and filters fleet table', async () => {
      useAuthStore.setState({
        user: {
          id: 'u-sys-admin',
          email: 'root@veritas.internal',
          role: 'platform_admin',
          workspace_id: 'ws-root',
        } as any,
        status: 'AUTHENTICATED',
      })

      const mockWorkspaces = [
        { id: 'ws-alpha', name: 'Alpha Analytics', member_count: 12, total_queries: 45000 },
        { id: 'ws-beta', name: 'Beta Health', member_count: 8, total_queries: 32000 },
      ]

      vi.spyOn(adminService, 'getGlobalWorkspaces').mockResolvedValue({
        data: mockWorkspaces,
        total: 2,
        page: 1,
        page_size: 50,
      } as any)

      render(
        <MemoryRouter>
          <PlatformAdminPage />
        </MemoryRouter>
      )

      expect(await screen.findByText('Platform Administration')).toBeInTheDocument()
      expect(screen.getByText('GLOBAL SCOPE')).toBeInTheDocument()

      // Fleet table rows
      expect(await screen.findByText('Alpha Analytics')).toBeInTheDocument()
      expect(screen.getByText('Beta Health')).toBeInTheDocument()

      // Filter input
      const filterInput = screen.getByPlaceholderText(/Filter workspaces/i)
      fireEvent.change(filterInput, { target: { value: 'Alpha' } })

      expect(screen.getByText('Alpha Analytics')).toBeInTheDocument()
      expect(screen.queryByText('Beta Health')).not.toBeInTheDocument()
    })

    it('denies access to regular workspace owners or members', () => {
      useAuthStore.setState({
        user: {
          id: 'u-user',
          email: 'owner@tenant.com',
          role: 'owner',
          workspace_id: 'ws-tenant',
        } as any,
        status: 'AUTHENTICATED',
      })

      render(
        <MemoryRouter>
          <PlatformAdminPage />
        </MemoryRouter>
      )

      expect(screen.getByText('Access Denied')).toBeInTheDocument()
      expect(screen.getByText(/You must possess the/i)).toBeInTheDocument()
    })
  })
})
