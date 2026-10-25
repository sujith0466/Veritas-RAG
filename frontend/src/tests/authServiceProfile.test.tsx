import { describe, it, expect, vi, beforeEach } from 'vitest'
import { authService } from '@/services/auth/authService'
import { apiClient } from '@/api/client'
import * as wrapper from '@/api/wrapper'

describe('authService.fetchBackendProfile Concurrent Hydration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('concurrently fetches /auth/me and /users/me and merges profile data correctly', async () => {
    const mockAuthContext = {
      id: 'usr-1',
      email: 'alex@veritasrag.com',
      role: 'admin',
      tenant_id: 'ten-1',
      demo_role_switcher_enabled: true,
      demo_simulated: false,
    }

    const mockExtendedUser = {
      full_name: 'Alex Rivera',
      avatar_url: 'https://cdn.veritasrag.com/avatars/alex.jpg',
      workspace_settings: { onboarding_completed: true },
    }

    vi.spyOn(wrapper, 'get').mockResolvedValue(mockAuthContext)
    vi.spyOn(apiClient, 'get').mockResolvedValue({ data: mockExtendedUser } as any)

    const profile = await authService.fetchBackendProfile()

    expect(wrapper.get).toHaveBeenCalledWith('/auth/me')
    expect(apiClient.get).toHaveBeenCalledWith('/users/me')

    expect(profile.email).toBe('alex@veritasrag.com')
    expect(profile.role).toBe('admin') // Authoritative role preserved
    expect((profile as any).full_name).toBe('Alex Rivera')
    expect((profile as any).workspace_settings?.onboarding_completed).toBe(true)
  })

  it('gracefully falls back to core authContext when /users/me fails or rejects', async () => {
    const mockAuthContext = {
      id: 'usr-2',
      email: 'viewer@veritasrag.com',
      role: 'viewer',
      tenant_id: 'ten-2',
      demo_role_switcher_enabled: false,
      demo_simulated: false,
    }

    vi.spyOn(wrapper, 'get').mockResolvedValue(mockAuthContext)
    vi.spyOn(apiClient, 'get').mockRejectedValue(new Error('Users service 503 unavailable'))

    const profile = await authService.fetchBackendProfile()

    expect(profile.id).toBe('usr-2')
    expect(profile.role).toBe('viewer')
    expect(profile.email).toBe('viewer@veritasrag.com')
  })

  it('throws authoritative error if /auth/me fails after retry budget, preventing invalid session state', async () => {
    vi.spyOn(wrapper, 'get').mockRejectedValue(new Error('Auth token invalid'))
    vi.spyOn(apiClient, 'get').mockResolvedValue({ data: {} } as any)

    await expect(authService.fetchBackendProfile()).rejects.toThrow('Auth token invalid')
  })
})
