import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { UserMenu } from '@/components/navigation/UserMenu'
import { useAuthStore } from '@/stores/authStore'

describe('Workstream 1: UserMenu Navigation Deduping', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.setState({
      user: {
        id: 'usr-nav-1',
        email: 'testuser@veritas.rag',
        full_name: 'Test Navigator',
        role: 'MEMBER' as any,
      } as any,
      token: 'mock-jwt-token',
      status: 'AUTHENTICATED',
    })
  })

  it('renders Dashboard, Settings (to /settings/profile), and Log out, without duplicate Profile item', async () => {
    render(
      <MemoryRouter>
        <UserMenu />
      </MemoryRouter>
    )

    // Open Radix dropdown menu via pointerDown and ArrowDown
    const trigger = screen.getByRole('button')
    fireEvent.pointerDown(trigger, { pointerId: 1 })
    fireEvent.keyDown(trigger, { key: 'ArrowDown', code: 'ArrowDown' })

    await waitFor(() => {
      expect(screen.getByText('Dashboard')).toBeInTheDocument()
    })

    // 1. Dashboard exists and links to /dashboard
    const dashboardItem = screen.getByRole('menuitem', { name: /Dashboard/i })
    expect(dashboardItem).toBeInTheDocument()
    expect(dashboardItem).toHaveAttribute('href', '/dashboard')

    // 2. Settings exists and links to /settings/profile
    const settingsItem = screen.getByRole('menuitem', { name: /Settings/i })
    expect(settingsItem).toBeInTheDocument()
    expect(settingsItem).toHaveAttribute('href', '/settings/profile')

    // 3. Log out exists
    expect(screen.getByText(/Log out/i)).toBeInTheDocument()

    // 4. Duplicate "Profile" menu item must NOT exist
    const profileItem = screen.queryByRole('menuitem', { name: /^Profile$/i })
    expect(profileItem).not.toBeInTheDocument()
  })

  it('renders saved profile name over generic name or role in navbar dropdown', async () => {
    useAuthStore.setState({
      user: {
        id: 'usr-nav-2',
        email: 'alice@veritas.rag',
        username: 'alice_researcher',
        role: 'ADMIN' as any,
      } as any,
      token: 'mock-jwt-token',
      status: 'AUTHENTICATED',
    })

    render(
      <MemoryRouter>
        <UserMenu />
      </MemoryRouter>
    )

    const trigger = screen.getByRole('button')
    fireEvent.pointerDown(trigger, { pointerId: 1 })
    fireEvent.keyDown(trigger, { key: 'ArrowDown', code: 'ArrowDown' })

    await waitFor(() => {
      expect(screen.getByText('alice_researcher')).toBeInTheDocument()
    })
  })

  it('falls back to "Admin" when profile name is missing or whitespace-only and role is admin', async () => {
    useAuthStore.setState({
      user: {
        id: 'usr-nav-3',
        email: 'admin@veritas.rag',
        username: '   ',
        full_name: null,
        role: 'admin' as any,
      } as any,
      token: 'mock-jwt-token',
      status: 'AUTHENTICATED',
    })

    render(
      <MemoryRouter>
        <UserMenu />
      </MemoryRouter>
    )

    const trigger = screen.getByRole('button')
    fireEvent.pointerDown(trigger, { pointerId: 1 })
    fireEvent.keyDown(trigger, { key: 'ArrowDown', code: 'ArrowDown' })

    await waitFor(() => {
      expect(screen.getByText('Admin')).toBeInTheDocument()
    })
  })

  it('falls back to "User" when profile name is missing and role is non-admin', async () => {
    useAuthStore.setState({
      user: {
        id: 'usr-nav-4',
        email: 'viewer@veritas.rag',
        username: '',
        full_name: '',
        role: 'viewer' as any,
      } as any,
      token: 'mock-jwt-token',
      status: 'AUTHENTICATED',
    })

    render(
      <MemoryRouter>
        <UserMenu />
      </MemoryRouter>
    )

    const trigger = screen.getByRole('button')
    fireEvent.pointerDown(trigger, { pointerId: 1 })
    fireEvent.keyDown(trigger, { key: 'ArrowDown', code: 'ArrowDown' })

    await waitFor(() => {
      expect(screen.getByText('User')).toBeInTheDocument()
    })
  })

  it('renders uploaded avatar picture and falls back gracefully on image error', async () => {
    useAuthStore.setState({
      user: {
        id: 'usr-nav-5',
        email: 'carol@veritas.rag',
        username: 'carol_sec',
        avatar_url: '/api/v1/storage/avatars/usr-nav-5/photo.jpeg',
        role: 'member' as any,
      } as any,
      token: 'mock-jwt-token',
      status: 'AUTHENTICATED',
    })

    render(
      <MemoryRouter>
        <UserMenu />
      </MemoryRouter>
    )

    // Avatar image should be rendered
    const img = screen.getByRole('img', { name: /avatar/i })
    expect(img).toBeInTheDocument()
    expect(img).toHaveAttribute('src', expect.stringContaining('/api/v1/storage/avatars/usr-nav-5/photo.jpeg'))

    // Trigger onError on image
    fireEvent.error(img)

    // Image should be removed and fallback initials displayed without crashing
    await waitFor(() => {
      expect(screen.queryByRole('img', { name: /avatar/i })).not.toBeInTheDocument()
      expect(screen.getByText('C')).toBeInTheDocument()
    })
  })
})
