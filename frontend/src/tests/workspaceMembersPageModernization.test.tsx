import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { WorkspaceMembersPage } from '@/pages/workspace/WorkspaceMembersPage'
import { useMemberStore } from '@/stores/memberStore'
import { useAuthStore } from '@/stores/authStore'
import { invitationService } from '@/services/invitationService'
import { accessRequestService } from '@/services/accessRequestService'

describe('WS-B12: Workspace Members & Role Hierarchy Modern UX', () => {
  const mockWorkspaceId = 'ws-test-b12-members'

  const mockMembers = [
    {
      id: 'm-owner-1',
      workspace_id: mockWorkspaceId,
      user_id: 'u-owner-1',
      role: 'OWNER',
      status: 'ACTIVE',
      joined_at: '2026-09-01T10:00:00Z',
      user: {
        id: 'u-owner-1',
        email: 'owner@veritas.rag',
        username: 'lead_owner',
        display_name: 'Lead Architect',
      },
    },
    {
      id: 'm-admin-2',
      workspace_id: mockWorkspaceId,
      user_id: 'u-admin-2',
      role: 'ADMIN',
      status: 'ACTIVE',
      joined_at: '2026-09-10T12:00:00Z',
      user: {
        id: 'u-admin-2',
        email: 'ops_admin@veritas.rag',
        username: 'ops_lead',
        display_name: 'Operations Admin',
      },
    },
    {
      id: 'm-member-3',
      workspace_id: mockWorkspaceId,
      user_id: 'u-member-3',
      role: 'MEMBER',
      status: 'SUSPENDED',
      joined_at: '2026-09-15T15:00:00Z',
      user: {
        id: 'u-member-3',
        email: 'analyst@veritas.rag',
        username: 'data_analyst',
        display_name: 'Data Analyst',
      },
    },
  ]

  const mockInvitations = [
    {
      id: 'inv-1',
      workspace_id: mockWorkspaceId,
      email: 'new_member@external.com',
      role: 'MEMBER',
      status: 'PENDING',
      expires_at: '2026-10-15T00:00:00Z',
      created_at: '2026-10-01T00:00:00Z',
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.setState({
      user: {
        id: 'u-owner-1',
        email: 'owner@veritas.rag',
        role: 'OWNER',
        workspace_id: mockWorkspaceId,
        workspace_name: 'Veritas Quantum',
      } as any,
      status: 'AUTHENTICATED',
    })

    useMemberStore.setState({
      members: mockMembers as any,
      total: 3,
      isLoading: false,
      error: null,
      fetchMembers: vi.fn(),
      updateRole: vi.fn(),
      suspendMember: vi.fn(),
      restoreMember: vi.fn(),
      removeMember: vi.fn(),
      bulkManage: vi.fn(),
      clearError: vi.fn(),
    })

    vi.spyOn(invitationService, 'listInvitations').mockResolvedValue({
      items: mockInvitations as any,
      pagination: { page: 1, size: 50, total_elements: 1, total_pages: 1 },
    } as any)

    vi.spyOn(accessRequestService, 'listRequests').mockResolvedValue({
      items: [],
      pagination: { page: 1, size: 50, total_elements: 0, total_pages: 0 },
    } as any)
  })

  it('does not render active seats badge beside Members & Access heading', async () => {
    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    )

    expect(screen.getByRole('heading', { level: 1, name: 'Members & Access' })).toBeInTheDocument()
    expect(screen.queryByText(/Active Seat/i)).not.toBeInTheDocument()
  })

  it('renders members list with clear distinction between Owner and other roles', async () => {
    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    )

    expect(screen.getByText('Lead Architect')).toBeInTheDocument()
    expect(screen.getByText('Operations Admin')).toBeInTheDocument()
    expect(screen.getByText('Data Analyst')).toBeInTheDocument()

    // Owner protection is visually distinguished
    expect(screen.getByText('Protected')).toBeInTheDocument()
    expect(screen.getByText('OWNER')).toBeInTheDocument()
  })

  it('prioritizes current user as first row in members table with YOU badge', async () => {
    // Set current user as analyst (3rd member in mockMembers array)
    useAuthStore.setState({
      user: {
        id: 'u-member-3',
        email: 'analyst@veritas.rag',
        role: 'MEMBER',
        workspace_id: mockWorkspaceId,
      } as any,
      status: 'AUTHENTICATED',
    })

    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    )

    const rows = screen.getAllByRole('row')
    // row 0 is header row, row 1 must be the current user (Data Analyst)
    expect(rows[1]).toHaveTextContent('Data Analyst')
    expect(rows[1]).toHaveTextContent('YOU')
    expect(rows[2]).toHaveTextContent('Lead Architect')
    expect(rows[3]).toHaveTextContent('Operations Admin')
  })

  it('toggles canonical role hierarchy guide panel', async () => {
    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    )

    const guideBtn = screen.getByRole('button', { name: /Role Permissions/i })
    expect(guideBtn).toBeInTheDocument()

    // Initially closed
    expect(screen.queryByText('Canonical Role Hierarchy & Permissions')).not.toBeInTheDocument()

    // Click to open
    fireEvent.click(guideBtn)
    expect(screen.getByText('Canonical Role Hierarchy & Permissions')).toBeInTheDocument()
    expect(screen.getByText('Workspace Owner')).toBeInTheDocument()
    expect(screen.getByText('Administrator')).toBeInTheDocument()
    expect(screen.getByText('Team Member')).toBeInTheDocument()
    expect(screen.getByText('Read-Only Viewer')).toBeInTheDocument()
  })

  it('opens in-app confirmation modal for member action and executes service action', async () => {
    const removeMemberSpy = vi.fn().mockResolvedValue(undefined)
    useMemberStore.setState({
      ...useMemberStore.getState(),
      removeMember: removeMemberSpy,
    })

    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    )

    // Click remove button on non-owner member (Operations Admin)
    const removeBtns = screen.getAllByTitle('Remove Member')
    expect(removeBtns.length).toBeGreaterThanOrEqual(1)
    fireEvent.click(removeBtns[0])

    // In-app modal should appear
    expect(await screen.findByText('Confirm Member Removal')).toBeInTheDocument()
    expect(screen.getByText('Target Member:')).toBeInTheDocument()

    // Click confirm button
    const confirmBtn = screen.getByRole('button', { name: 'Confirm' })
    fireEvent.click(confirmBtn)

    await waitFor(() => {
      expect(removeMemberSpy).toHaveBeenCalledWith(mockWorkspaceId, 'm-admin-2')
    })
  })

  it('switches to pending invitations tab and displays invitations list', async () => {
    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    )

    const invitationsTab = screen.getByRole('button', { name: /Pending Invitations/i })
    fireEvent.click(invitationsTab)

    expect(await screen.findByText('new_member@external.com')).toBeInTheDocument()
    expect(screen.getByText('PENDING')).toBeInTheDocument()
  })
})
