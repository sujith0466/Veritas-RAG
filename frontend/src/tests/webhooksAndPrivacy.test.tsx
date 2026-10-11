import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { WebhookSettings } from '../pages/settings/WebhookSettings'
import { PrivacySettings } from '../pages/settings/PrivacySettings'

// Mock toast and authStore
vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}))

const mockUser = {
  id: 'usr_test_123',
  email: 'test_user@veritas.internal',
  tenant_id: 'ws_tenant_456',
}

vi.mock('@/stores/authStore', () => ({
  useAuthStore: (selector: any) =>
    selector({
      user: mockUser,
      token: 'fake_jwt_token',
      logout: vi.fn(),
    }),
}))

describe('Modernized WebhookSettings Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    global.fetch = vi.fn().mockImplementation((url: string) => {
      const u = url.split('?')[0]
      if (u.endsWith('/webhooks/events')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve([
              {
                category: 'Document Intelligence',
                events: [{ id: 'document.uploaded', name: 'Document Uploaded' }],
              },
            ]),
        })
      }
      if (u.endsWith('/webhooks/logs')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              items: [
                {
                  id: 'log_1',
                  target: 'https://api.example.com/webhook',
                  status: 'SUCCESS',
                  attempt_count: 1,
                  created_at: new Date().toISOString(),
                  event_type: 'document.uploaded',
                },
              ],
              total: 1,
            }),
        })
      }
      if (u.endsWith('/webhooks')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve([
              {
                id: 'wh_1',
                endpoint_url: 'https://api.example.com/webhook',
                events: ['*'],
                is_active: true,
                created_at: new Date().toISOString(),
              },
            ]),
        })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      })
    })
  })

  it('renders Webhook Endpoints heading, endpoints list, and delivery logs table', async () => {
    render(<WebhookSettings />)

    expect(await screen.findByText('Webhook Endpoints')).toBeDefined()
    expect(await screen.findByTestId('webhook-endpoint-url')).toBeDefined()
    expect(await screen.findByText('Recent Webhook Delivery Logs')).toBeDefined()
  })
})

describe('Modernized PrivacySettings Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders Export Data card and Danger Zone with deactivation modal trigger', () => {
    render(<PrivacySettings />)

    expect(screen.getByText('Privacy & Data Governance')).toBeDefined()
    expect(screen.getByText('Export Account Archive')).toBeDefined()
    expect(screen.getByText('Download Data Archive')).toBeDefined()
    expect(screen.getByText('Danger Zone: Account Deactivation')).toBeDefined()
    expect(screen.getByText('Deactivate Account')).toBeDefined()
  })
})
