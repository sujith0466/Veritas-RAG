import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { NotificationSettings } from '@/pages/settings/NotificationSettings'
import { AIPrefSettings } from '@/pages/settings/AIPrefSettings'
import { NotificationBell } from '@/components/common/NotificationBell'
import { SettingsLayout } from '@/pages/settings/SettingsLayout'
import { userService } from '@/services/userService'
import { notificationService } from '@/services/notificationService'
import { useAuthStore } from '@/stores/authStore'
import { useInAppNotificationStore } from '@/stores/inAppNotificationStore'

vi.mock('@/services/userService', () => ({
  userService: {
    getProfile: vi.fn(),
    updatePreferences: vi.fn(),
  },
}))

vi.mock('@/services/notificationService', () => ({
  notificationService: {
    listNotifications: vi.fn(),
    getUnreadCount: vi.fn(),
    markAsRead: vi.fn(),
    markAllAsRead: vi.fn(),
    dismissNotification: vi.fn(),
  },
}))

describe('Settings Modernization (WP-8 Verification)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useInAppNotificationStore.getState().reset()

    useAuthStore.setState({
      status: 'AUTHENTICATED',
      user: {
        id: '00000000-0000-0000-0000-000000000001',
        email: 'test@veritas.rag',
        tenant_id: '00000000-0000-0000-0000-000000000002',
        role: 'MEMBER',
        preferences: {},
      } as any,
      token: 'fake-jwt-token',
    })

    vi.mocked(userService.getProfile).mockResolvedValue({
      data: {
        preferences: {
          notifications: { email_alerts: true, security_alerts: true, weekly_reports: false },
          ai: { default_model: 'gemini-2.0-flash', temperature: 0.2, system_prompt: 'Strict tone.' },
        },
      },
    } as any)

    vi.mocked(notificationService.getUnreadCount).mockResolvedValue({
      data: { unread_count: 3 },
    } as any)

    vi.mocked(notificationService.listNotifications).mockResolvedValue({
      data: {
        items: [
          {
            id: 'n-1',
            tenant_id: '00000000-0000-0000-0000-000000000002',
            user_id: '00000000-0000-0000-0000-000000000001',
            category: 'SECURITY',
            severity: 'WARNING',
            title: 'Password Changed',
            message: 'Your account password was updated successfully.',
            action_url: '/settings/security',
            payload_json: {},
            is_read: false,
            read_at: null,
            created_at: new Date().toISOString(),
          },
          {
            id: 'n-2',
            tenant_id: '00000000-0000-0000-0000-000000000002',
            user_id: null,
            category: 'DOCUMENT',
            severity: 'INFO',
            title: 'Document Ready',
            message: 'File annual_report.pdf is ready for search.',
            action_url: '/documents',
            payload_json: {},
            is_read: true,
            read_at: new Date().toISOString(),
            created_at: new Date().toISOString(),
          },
        ],
        total: 2,
        page: 1,
        page_size: 50,
        unread_count: 1,
      },
    } as any)
  })

  describe('Notification Center (NotificationSettings.tsx)', () => {
    it('renders dual-tab header with Inbox & Activity and Preferences', async () => {
      render(
        <MemoryRouter>
          <NotificationSettings />
        </MemoryRouter>
      )

      expect(await screen.findByText('Notification Center')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Inbox & Activity/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Preferences/i })).toBeInTheDocument()
    })

    it('displays notifications feed and category filters in Inbox tab', async () => {
      render(
        <MemoryRouter>
          <NotificationSettings />
        </MemoryRouter>
      )

      expect(await screen.findByText('Password Changed')).toBeInTheDocument()
      expect(screen.getByText('Document Ready')).toBeInTheDocument()
      expect(screen.getByText('All Events')).toBeInTheDocument()
      expect(screen.getAllByText('SECURITY').length).toBeGreaterThanOrEqual(1)
    })

    it('switches to Preferences tab and displays toggles with saving capability', async () => {
      vi.mocked(userService.updatePreferences).mockResolvedValue({ data: {} } as any)

      render(
        <MemoryRouter>
          <NotificationSettings />
        </MemoryRouter>
      )

      const prefTabBtn = await screen.findByRole('button', { name: /Preferences/i })
      fireEvent.click(prefTabBtn)

      expect(await screen.findByText(/General Document & Pipeline Alerts/i)).toBeInTheDocument()
      expect(screen.getByText(/Security & Reliability Alerts/i)).toBeInTheDocument()
      expect(screen.getByText(/Weekly Digest & Usage Summary/i)).toBeInTheDocument()
      expect(screen.getByText(/Coming Soon/i)).toBeInTheDocument()

      const saveBtn = screen.getByRole('button', { name: /Save Preferences/i })
      fireEvent.click(saveBtn)

      await waitFor(() => {
        expect(userService.updatePreferences).toHaveBeenCalledWith({
          preferences: expect.objectContaining({
            notifications: expect.objectContaining({
              email_alerts: true,
              security_alerts: true,
              weekly_reports: false,
            }),
          }),
        })
      })
    })
  })

  describe('Navbar Notification Bell (NotificationBell.tsx)', () => {
    it('hydrates unread count and renders badge', async () => {
      render(
        <MemoryRouter>
          <NotificationBell />
        </MemoryRouter>
      )

      await waitFor(() => {
        const badge = screen.getByTestId('unread-badge')
        expect(badge).toHaveTextContent('3')
      })
    })

    it('opens popover on click and fetches recent notifications with deep link', async () => {
      render(
        <MemoryRouter>
          <NotificationBell />
        </MemoryRouter>
      )

      const bellBtn = screen.getByRole('button', { name: /Open notifications/i })
      fireEvent.click(bellBtn)

      expect(await screen.findByTestId('notification-popover')).toBeInTheDocument()
      expect(screen.getByText('View all notifications in Settings →')).toBeInTheDocument()
    })
  })

  describe('AI Preferences (AIPrefSettings.tsx)', () => {
    it('renders real model catalogue, temperature slider, and system prompt', async () => {
      render(
        <MemoryRouter>
          <AIPrefSettings />
        </MemoryRouter>
      )

      expect(await screen.findByText('Gemini 2.0 Flash')).toBeInTheDocument()
      expect(screen.getByText('Llama 3.3 70B Instruct')).toBeInTheDocument()
      expect(screen.getByText('Temperature & Creativity')).toBeInTheDocument()
      expect(screen.getByDisplayValue('Strict tone.')).toBeInTheDocument()
    })

    it('displays floating sticky save bar when modifications are made', async () => {
      render(
        <MemoryRouter>
          <AIPrefSettings />
        </MemoryRouter>
      )

      await screen.findByText('Gemini 2.0 Flash')
      expect(screen.queryByText(/You have unsaved changes in AI Preferences/i)).not.toBeInTheDocument()

      // Select another model (Llama)
      const llamaCard = screen.getByText('Llama 3.3 70B Instruct')
      fireEvent.click(llamaCard)

      expect(await screen.findByText(/You have unsaved changes in AI Preferences/i)).toBeInTheDocument()
    })
  })

  describe('Responsive Settings Layout (SettingsLayout.tsx)', () => {
    it('renders mobile navigation tabs and desktop sidebar items', async () => {
      render(
        <MemoryRouter initialEntries={['/settings/notifications']}>
          <SettingsLayout />
        </MemoryRouter>
      )

      expect(screen.getByText('Settings')).toBeInTheDocument()
      // Desktop + mobile navigation items
      const notifLinks = screen.getAllByRole('link', { name: /Notifications/i })
      expect(notifLinks.length).toBeGreaterThanOrEqual(2)
      const aiLinks = screen.getAllByRole('link', { name: /AI Preferences/i })
      expect(aiLinks.length).toBeGreaterThanOrEqual(2)
    })
  })
})
