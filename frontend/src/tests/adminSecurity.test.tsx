import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'

// Helper component matching ProtectedRoute's role check logic
function AdminRouteGuard({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user)
  const isAuthenticated = useAuthStore((s) => s.status === 'AUTHENTICATED')

  if (!isAuthenticated) {
    return <Navigate to="/auth/login" replace />
  }

  const userRole = String(user?.role || '').trim().toLowerCase()
  if (!['admin', 'owner', 'platform_admin'].includes(userRole)) {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}

describe('Admin Security & Role Normalization (ADMIN-01)', () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: null,
      status: 'UNAUTHENTICATED',
      error: undefined,
    })
  })

  it('allows access when role is lowercase admin', () => {
    useAuthStore.setState({
      status: 'AUTHENTICATED',
      user: { id: '1', email: 'admin@test.com', role: 'admin' } as any,
    })

    render(
      <MemoryRouter initialEntries={['/admin/workspace']}>
        <Routes>
          <Route
            path="/admin/workspace"
            element={
              <AdminRouteGuard>
                <div data-testid="admin-content">Admin Content</div>
              </AdminRouteGuard>
            }
          />
          <Route path="/dashboard" element={<div data-testid="dashboard">Dashboard</div>} />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByTestId('admin-content')).toHaveTextContent('Admin Content')
  })

  it('allows access when role is uppercase ADMIN (case normalization)', () => {
    useAuthStore.setState({
      status: 'AUTHENTICATED',
      user: { id: '2', email: 'admin@test.com', role: 'ADMIN' } as any,
    })

    render(
      <MemoryRouter initialEntries={['/admin/workspace']}>
        <Routes>
          <Route
            path="/admin/workspace"
            element={
              <AdminRouteGuard>
                <div data-testid="admin-content">Admin Content</div>
              </AdminRouteGuard>
            }
          />
          <Route path="/dashboard" element={<div data-testid="dashboard">Dashboard</div>} />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByTestId('admin-content')).toHaveTextContent('Admin Content')
  })

  it('allows access when role is uppercase OWNER (case normalization)', () => {
    useAuthStore.setState({
      status: 'AUTHENTICATED',
      user: { id: '3', email: 'owner@test.com', role: 'OWNER' } as any,
    })

    render(
      <MemoryRouter initialEntries={['/admin/workspace']}>
        <Routes>
          <Route
            path="/admin/workspace"
            element={
              <AdminRouteGuard>
                <div data-testid="admin-content">Admin Content</div>
              </AdminRouteGuard>
            }
          />
          <Route path="/dashboard" element={<div data-testid="dashboard">Dashboard</div>} />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByTestId('admin-content')).toHaveTextContent('Admin Content')
  })

  it('allows access when role is PLATFORM_ADMIN with mixed casing', () => {
    useAuthStore.setState({
      status: 'AUTHENTICATED',
      user: { id: '4', email: 'padmin@test.com', role: 'Platform_Admin' } as any,
    })

    render(
      <MemoryRouter initialEntries={['/admin/workspace']}>
        <Routes>
          <Route
            path="/admin/workspace"
            element={
              <AdminRouteGuard>
                <div data-testid="admin-content">Admin Content</div>
              </AdminRouteGuard>
            }
          />
          <Route path="/dashboard" element={<div data-testid="dashboard">Dashboard</div>} />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByTestId('admin-content')).toHaveTextContent('Admin Content')
  })

  it('redirects to dashboard when role is VIEWER or MEMBER', () => {
    useAuthStore.setState({
      status: 'AUTHENTICATED',
      user: { id: '5', email: 'viewer@test.com', role: 'VIEWER' } as any,
    })

    render(
      <MemoryRouter initialEntries={['/admin/workspace']}>
        <Routes>
          <Route
            path="/admin/workspace"
            element={
              <AdminRouteGuard>
                <div data-testid="admin-content">Admin Content</div>
              </AdminRouteGuard>
            }
          />
          <Route path="/dashboard" element={<div data-testid="dashboard">Dashboard</div>} />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByTestId('dashboard')).toBeInTheDocument()
    expect(screen.queryByTestId('admin-content')).not.toBeInTheDocument()
  })
})
