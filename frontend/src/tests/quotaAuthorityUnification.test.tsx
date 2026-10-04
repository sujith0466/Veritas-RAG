import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QuotaBillingPage } from '@/pages/admin/QuotaBillingPage'
import { adminService } from '@/services/adminService'
import { workspaceSettingsService } from '@/services/workspaceSettingsService'

// Mock toast
vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}))

// Mock authStore
vi.mock('@/stores/authStore', () => ({
  useAuthStore: vi.fn((selector) =>
    selector({
      user: {
        id: 'usr-123',
        email: 'owner@example.com',
        role: 'owner',
        workspace_id: 'ws-999',
      },
      currentWorkspace: { id: 'ws-999', name: 'Test Org' },
      token: 'jwt-mock-token',
    })
  ),
}))

describe('ADMIN-04: Quota Authority Unification (QuotaBillingPage)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const mockUsage = {
    workspace_id: 'ws-999',
    billing_period_start: '2026-10-01T00:00:00Z',
    used_tokens: 2000000,
    used_queries: 450,
    monthly_token_limit: 8000000,
    monthly_budget_usd: 120.0,
    warning_threshold_pct: 0.80,
    is_hard_enforced: true,
    remaining_tokens: 6000000,
    remaining_budget_usd: 90.0,
    is_warning: false,
    is_exceeded: false,
  }

  const mockQuota = {
    tenant_id: 'ws-999',
    monthly_token_limit: 8000000,
    monthly_budget_usd: 120.0,
    warning_threshold_pct: 0.80,
    is_hard_enforced: true,
    remaining_tokens: 6000000,
    remaining_budget_usd: 90.0,
  }

  const mockSettings = {
    success: true,
    data: {
      id: 'ws-999',
      workspace_id: 'ws-999',
      settings: {
        limits: {
          monthly_token_budget: 8000000,
          monthly_query_budget: 50000,
          max_storage_gb: 100,
          max_members: 50,
        },
      },
      schema_version: 1,
      version: 2,
      settings_hash: 'hash-abc',
      updated_at: '2026-10-04T06:00:00Z',
    },
  }

  it('renders authoritative runtime quota metrics', async () => {
    vi.spyOn(adminService, 'getWorkspaceUsage').mockResolvedValue(mockUsage)
    vi.spyOn(adminService, 'getQuota').mockResolvedValue(mockQuota)
    vi.spyOn(workspaceSettingsService, 'getSettings').mockResolvedValue(mockSettings as any)

    render(
      <MemoryRouter>
        <QuotaBillingPage />
      </MemoryRouter>
    )

    expect(await screen.findByText(/Resource & Token Governance/i)).toBeInTheDocument()
    expect(screen.getByText(/2.00M/)).toBeInTheDocument() // 2.00M tokens consumed
    expect(screen.getByText(/Ceiling: 8.0M/)).toBeInTheDocument()
    expect(screen.getByText(/450/)).toBeInTheDocument() // 450 queries
    expect(screen.getByText(/Hard Enforcement/i)).toBeInTheDocument()
  })

  it('submits authoritative quota mutation to adminService.updateQuota when Owner saves', async () => {
    vi.spyOn(adminService, 'getWorkspaceUsage').mockResolvedValue(mockUsage)
    vi.spyOn(adminService, 'getQuota').mockResolvedValue(mockQuota)
    vi.spyOn(workspaceSettingsService, 'getSettings').mockResolvedValue(mockSettings as any)

    const updateQuotaSpy = vi.spyOn(adminService, 'updateQuota').mockResolvedValue({
      ...mockQuota,
      monthly_token_limit: 12000000,
      monthly_budget_usd: 180.0,
    })

    const patchSettingsSpy = vi.spyOn(workspaceSettingsService, 'patchSettings').mockResolvedValue({
      success: true,
      data: {
        ...mockSettings.data,
        version: 3,
        updated_at: '2026-10-04T06:30:00Z',
      },
    } as any)

    render(
      <MemoryRouter>
        <QuotaBillingPage />
      </MemoryRouter>
    )

    const adjustBtn = await screen.findByRole('button', { name: /Adjust Quotas/i })
    fireEvent.click(adjustBtn)

    expect(screen.getByText(/Configure Workspace Quotas & Governance/i)).toBeInTheDocument()

    const tokenInput = screen.getByLabelText(/Monthly Token Ceiling/i)
    fireEvent.change(tokenInput, { target: { value: '12000000' } })

    const saveBtn = screen.getByRole('button', { name: /Save Quota Allocation/i })
    fireEvent.click(saveBtn)

    await waitFor(() => {
      expect(updateQuotaSpy).toHaveBeenCalledWith(
        'ws-999',
        expect.objectContaining({
          monthly_token_limit: 12000000,
        })
      )
      expect(patchSettingsSpy).toHaveBeenCalledWith(
        'ws-999',
        '2026-10-04T06:00:00Z',
        expect.objectContaining({
          limits: expect.objectContaining({
            monthly_token_budget: 12000000,
          }),
        })
      )
    })
  })
})
