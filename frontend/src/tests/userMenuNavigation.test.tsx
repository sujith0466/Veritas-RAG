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
})
