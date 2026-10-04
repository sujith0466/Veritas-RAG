import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AuditLogsPage } from '@/pages/admin/AuditLogsPage'
import { QuotaBillingPage } from '@/pages/admin/QuotaBillingPage'
import { adminService } from '@/services/adminService'
import { workspaceSettingsService } from '@/services/workspaceSettingsService'
import { useAuthStore } from '@/stores/authStore'

describe('Audit Ledger & Quota Modernization (ADMIN-03)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.setState({
      user: {
        id: 'u-admin',
        email: 'owner@test.com',
        role: 'OWNER' as any,
        workspace_id: 'ws-777',
        tenant_id: 'ws-777',
        workspace_name: 'Veritas Corp',
      } as any,
      status: 'AUTHENTICATED',
      token: 'jwt-token-777',
      error: undefined,
    })
  })

  describe('AuditLogsPage', () => {
    const mockAuditResponse = {
      items: [
        {
          id: 'log-1',
          tenant_id: 'ws-777',
          user_id: 'u-admin',
          action: 'WORKSPACE_SETTINGS_UPDATED',
          resource_type: 'WORKSPACE_SETTINGS',
          resource_id: 'ws-777',
          details: { category: 'limits' },
          created_at: '2026-10-04T05:00:00Z',
        },
      ],
      pagination: {
        page: 1,
        size: 50,
        total_elements: 75,
        total_pages: 2,
      },
    }

    it('renders audit events with server-side pagination and filters', async () => {
      const getLogsSpy = vi.spyOn(adminService, 'getAuditLogs').mockResolvedValue(mockAuditResponse as any)

      render(
        <MemoryRouter>
          <AuditLogsPage />
        </MemoryRouter>
      )

      await waitFor(() => {
        expect(getLogsSpy).toHaveBeenCalled()
      })

      expect(await screen.findByText('WORKSPACE_SETTINGS_UPDATED')).toBeInTheDocument()
      expect(screen.getByText(/Showing/)).toHaveTextContent('Showing 1 of 75 total audit events')
      expect(screen.getByText(/Page/)).toHaveTextContent('Page 1 of 2')

      // Next button should be enabled since total_pages is 2
      const nextBtn = screen.getByRole('button', { name: /Next/i })
      expect(nextBtn).toBeEnabled()

      // Previous button should be disabled on page 1
      const prevBtn = screen.getByRole('button', { name: /Previous/i })
      expect(prevBtn).toBeDisabled()
    })

    it('submits search filter query to backend service', async () => {
      const getLogsSpy = vi.spyOn(adminService, 'getAuditLogs').mockResolvedValue(mockAuditResponse as any)

      render(
        <MemoryRouter>
          <AuditLogsPage />
        </MemoryRouter>
      )

      const searchInput = screen.getByPlaceholderText(/Search by action/i)
      fireEvent.change(searchInput, { target: { value: 'limits' } })

      const searchBtn = screen.getByRole('button', { name: /Search/i })
      fireEvent.click(searchBtn)

      await waitFor(() => {
        expect(getLogsSpy).toHaveBeenCalledWith(1, 50, expect.objectContaining({ query: 'limits' }))
      })
    })
  })

  describe('QuotaBillingPage', () => {
    const mockUsage = {
      workspace_id: 'ws-777',
      billing_period_start: '2026-10-01T00:00:00Z',
      used_tokens: 1500000,
      used_queries: 250,
      monthly_token_limit: 6000000,
      monthly_budget_usd: 0,
      warning_threshold_pct: 0.8,
      is_hard_enforced: false,
      remaining_tokens: 3500000,
      remaining_budget_usd: 0,
      is_warning: false,
      is_exceeded: false,
    }

    const mockSettings = {
      success: true,
      data: {
        workspace_id: 'ws-777',
        settings: {
          limits: {
            monthly_token_budget: 6000000,
            monthly_query_budget: 60000,
            max_storage_gb: 150,
            max_members: 75,
          },
        },
        schema_version: 1,
        version: 3,
        settings_hash: 'hash-xyz',
        updated_at: '2026-10-04T05:30:00Z',
      },
    }

    it('renders token and query governance metrics using strictly resolved workspace ID', async () => {
      vi.spyOn(adminService, 'getWorkspaceUsage').mockResolvedValue(mockUsage)
      vi.spyOn(workspaceSettingsService, 'getSettings').mockResolvedValue(mockSettings as any)

      render(
        <MemoryRouter>
          <QuotaBillingPage />
        </MemoryRouter>
      )

      expect(await screen.findByText(/Resource & Token Governance/i)).toBeInTheDocument()
      expect(screen.getByText(/1.50M/)).toBeInTheDocument() // 1.50M tokens used
      expect(screen.getByText(/250/)).toBeInTheDocument() // 250 queries
      expect(screen.getByText(/150 GB/)).toBeInTheDocument()
      expect(screen.getByText(/75 Members/)).toBeInTheDocument()
    })

    it('allows Owner to adjust quotas and persists to canonical settings', async () => {
      vi.spyOn(adminService, 'getWorkspaceUsage').mockResolvedValue(mockUsage)
      const updateQuotaSpy = vi.spyOn(adminService, 'updateQuota').mockResolvedValue({
        tenant_id: 'ws-777',
        monthly_token_limit: 6000000,
        monthly_budget_usd: 150,
        warning_threshold_pct: 0.8,
        is_hard_enforced: true,
        remaining_tokens: 4500000,
        remaining_budget_usd: 112.5,
      })
      vi.spyOn(workspaceSettingsService, 'getSettings').mockResolvedValue(mockSettings as any)
      const patchSpy = vi.spyOn(workspaceSettingsService, 'patchSettings').mockResolvedValue({
        success: true,
        data: {
          ...mockSettings.data,
          version: 4,
          updated_at: '2026-10-04T05:35:00Z',
        },
      } as any)

      render(
        <MemoryRouter>
          <QuotaBillingPage />
        </MemoryRouter>
      )

      const adjustBtn = await screen.findByRole('button', { name: /Adjust Quotas/i })
      fireEvent.click(adjustBtn)

      expect(screen.getByText(/Configure Workspace/i)).toBeInTheDocument()

      const saveBtn = screen.getByRole('button', { name: /Save Quota Allocation/i })
      fireEvent.click(saveBtn)

      await waitFor(() => {
        expect(updateQuotaSpy).toHaveBeenCalledWith(
          'ws-777',
          expect.objectContaining({
            monthly_token_limit: 6000000,
          })
        )
        expect(patchSpy).toHaveBeenCalledWith(
          'ws-777',
          '2026-10-04T05:30:00Z',
          {
            limits: {
              monthly_token_budget: 6000000,
              monthly_query_budget: 60000,
              max_storage_gb: 150,
              max_members: 75,
            },
          }
        )
      })
    })
  })
})
