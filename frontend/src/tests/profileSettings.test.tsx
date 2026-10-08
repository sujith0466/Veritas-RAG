import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ProfileSettings } from '@/pages/settings/ProfileSettings'
import { useAuthStore } from '@/stores/authStore'
import { userService } from '@/services/userService'

const mockToast = vi.fn()
vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({ toast: mockToast }),
}))

vi.mock('@/services/userService', () => ({
  userService: {
    getProfile: vi.fn(),
    updateProfile: vi.fn(),
    uploadAvatar: vi.fn(),
  },
}))

describe('Workstream 2: Profile Settings Hardening & Validation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.setState({
      user: {
        id: 'usr-prof-1',
        email: 'engineer@veritas.rag',
        full_name: 'Lead Engineer',
        role: 'MEMBER' as any,
      } as any,
      token: 'jwt-token-123',
      status: 'AUTHENTICATED',
    })
  })

  it('renders Profile Settings title and Job Title / Designation label', async () => {
    vi.mocked(userService.getProfile).mockResolvedValueOnce({
      data: {
        username: 'lead_dev',
        avatar_url: null,
        version: 1,
        profile_data: {
          bio: 'Building reliable RAG systems',
          designation: 'Staff Reliability Engineer',
          website: 'https://veritas-rag.example.com',
        },
      },
    } as any)

    render(
      <MemoryRouter>
        <ProfileSettings />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Profile Settings')).toBeInTheDocument()
      expect(screen.getByText('Job Title / Designation')).toBeInTheDocument()
    })

    // Confirm old misleading text is not present
    expect(screen.queryByText('Public Profile')).not.toBeInTheDocument()
  })

  it('rejects invalid website scheme on client-side submit without calling API', async () => {
    vi.mocked(userService.getProfile).mockResolvedValueOnce({
      data: {
        username: 'lead_dev',
        avatar_url: null,
        version: 1,
        profile_data: { website: '' },
      },
    } as any)

    render(
      <MemoryRouter>
        <ProfileSettings />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Profile Settings')).toBeInTheDocument()
    })

    const websiteInput = screen.getByLabelText(/website/i)
    fireEvent.change(websiteInput, { target: { value: 'javascript:alert(1)' } })

    const saveButton = screen.getByRole('button', { name: /save changes/i })
    fireEvent.click(saveButton)

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Validation Error',
          message: expect.stringContaining('http:// or https://'),
          type: 'error',
        })
      )
    })

    expect(userService.updateProfile).not.toHaveBeenCalled()
  })

  it('rejects invalid username on client-side submit without calling API', async () => {
    vi.mocked(userService.getProfile).mockResolvedValueOnce({
      data: {
        username: 'lead_dev',
        avatar_url: null,
        version: 1,
        profile_data: {},
      },
    } as any)

    render(
      <MemoryRouter>
        <ProfileSettings />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Profile Settings')).toBeInTheDocument()
    })

    const usernameInput = screen.getByLabelText(/username/i)
    fireEvent.change(usernameInput, { target: { value: 'invalid user!' } })

    const saveButton = screen.getByRole('button', { name: /save changes/i })
    fireEvent.click(saveButton)

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Validation Error',
          message: expect.stringContaining('letters, numbers, underscores'),
          type: 'error',
        })
      )
    })

    expect(userService.updateProfile).not.toHaveBeenCalled()
  })

  it('calls updateProfile with version and handles 409 conflict gracefully', async () => {
    vi.mocked(userService.getProfile).mockResolvedValueOnce({
      data: {
        username: 'lead_dev',
        avatar_url: null,
        version: 1,
        profile_data: { designation: 'Dev' },
      },
    } as any)

    vi.mocked(userService.updateProfile).mockRejectedValueOnce({
      response: {
        status: 409,
        data: { detail: 'Profile update conflict due to concurrent modification.' },
      },
    })

    render(
      <MemoryRouter>
        <ProfileSettings />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Profile Settings')).toBeInTheDocument()
    })

    const saveButton = screen.getByRole('button', { name: /save changes/i })
    fireEvent.click(saveButton)

    await waitFor(() => {
      expect(userService.updateProfile).toHaveBeenCalledWith(
        expect.anything(),
        1
      )
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Conflict',
          type: 'error',
        })
      )
    })
  })
})
