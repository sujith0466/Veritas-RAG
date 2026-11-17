import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { WorkspaceMembersPage } from '@/pages/workspace/WorkspaceMembersPage';
import { useMemberStore } from '@/stores/memberStore';
import { useAuthStore } from '@/stores/authStore';
import { workspaceTransferService } from '@/services/workspaceTransferService';
import { invitationService } from '@/services/invitationService';
import { accessRequestService } from '@/services/accessRequestService';

describe('WS-SEC7-B1: Workspace Ownership Transfers UI', () => {
  const mockWorkspaceId = 'ws-test-transfer-123';

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
      status: 'ACTIVE',
      joined_at: '2026-09-15T15:00:00Z',
      user: {
        id: 'u-member-3',
        email: 'analyst@veritas.rag',
        username: 'data_analyst',
        display_name: 'Data Analyst',
      },
    },
    {
      id: 'm-viewer-4',
      workspace_id: mockWorkspaceId,
      user_id: 'u-viewer-4',
      role: 'VIEWER',
      status: 'ACTIVE',
      joined_at: '2026-09-20T15:00:00Z',
      user: {
        id: 'u-viewer-4',
        email: 'viewer@veritas.rag',
        username: 'viewer_user',
        display_name: 'Viewer User',
      },
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();

    useAuthStore.setState({
      user: {
        id: 'u-owner-1',
        email: 'owner@veritas.rag',
        role: 'OWNER',
        workspace_id: mockWorkspaceId,
        workspace_name: 'Veritas Security',
      } as any,
      status: 'AUTHENTICATED',
    });

    useMemberStore.setState({
      members: mockMembers as any,
      total: 4,
      isLoading: false,
      error: null,
      fetchMembers: vi.fn(),
      updateRole: vi.fn(),
      suspendMember: vi.fn(),
      restoreMember: vi.fn(),
      removeMember: vi.fn(),
      bulkManage: vi.fn(),
      clearError: vi.fn(),
    });

    vi.spyOn(invitationService, 'listInvitations').mockResolvedValue({
      items: [],
      pagination: { page: 1, size: 50, total_elements: 0, total_pages: 0 },
    } as any);

    vi.spyOn(accessRequestService, 'listRequests').mockResolvedValue({
      items: [],
      pagination: { page: 1, size: 50, total_elements: 0, total_pages: 0 },
    } as any);
    vi.spyOn(workspaceTransferService, 'getActiveTransfer').mockResolvedValue(null);
  });

  it('renders transfer ownership button for active admin/member rows when caller is owner', async () => {
    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      // Admin row has transfer button
      const adminTransferBtn = screen.getByTestId('transfer-ownership-m-admin-2');
      expect(adminTransferBtn).toBeInTheDocument();
      expect(adminTransferBtn).not.toBeDisabled();

      // Member row has transfer button
      const memberTransferBtn = screen.getByTestId('transfer-ownership-m-member-3');
      expect(memberTransferBtn).toBeInTheDocument();
      expect(memberTransferBtn).not.toBeDisabled();

      // Viewer row transfer button is disabled
      const viewerTransferBtn = screen.getByTestId('transfer-ownership-m-viewer-4');
      expect(viewerTransferBtn).toBeInTheDocument();
      expect(viewerTransferBtn).toBeDisabled();
    });
  });

  it('opens nominate modal when owner clicks transfer ownership button', async () => {
    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      const adminTransferBtn = screen.getByTestId('transfer-ownership-m-admin-2');
      fireEvent.click(adminTransferBtn);
    });

    expect(screen.getByText('Nominate New Workspace Owner')).toBeInTheDocument();
    expect(screen.getByText(/7-Day Transfer Invitation/i)).toBeInTheDocument();
    expect(screen.getByTestId('confirm-nomination-btn')).toBeInTheDocument();
  });

  it('renders nominee banner when logged in as designated nominee with pending transfer', async () => {
    useAuthStore.setState({
      user: {
        id: 'u-admin-2',
        email: 'ops_admin@veritas.rag',
        role: 'ADMIN',
        workspace_id: mockWorkspaceId,
      } as any,
      status: 'AUTHENTICATED',
    });

    vi.spyOn(workspaceTransferService, 'getActiveTransfer').mockResolvedValue({
      id: 'trans-100',
      workspace_id: mockWorkspaceId,
      nominated_by: { id: 'u-owner-1', email: 'owner@veritas.rag', full_name: 'Lead Architect' },
      nominee: { id: 'u-admin-2', email: 'ops_admin@veritas.rag', full_name: 'Operations Admin' },
      status: 'PENDING',
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 7 * 86400000).toISOString(),
      is_expired: false,
    });

    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('transfer-nominee-banner')).toBeInTheDocument();
      expect(screen.getByTestId('accept-transfer-btn')).toBeInTheDocument();
      expect(screen.getByTestId('reject-transfer-btn')).toBeInTheDocument();
    });
  });

  it('renders owner banner when active transfer is pending and allows cancellation', async () => {
    vi.spyOn(workspaceTransferService, 'getActiveTransfer').mockResolvedValue({
      id: 'trans-100',
      workspace_id: mockWorkspaceId,
      nominated_by: { id: 'u-owner-1', email: 'owner@veritas.rag', full_name: 'Lead Architect' },
      nominee: { id: 'u-admin-2', email: 'ops_admin@veritas.rag', full_name: 'Operations Admin' },
      status: 'PENDING',
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 7 * 86400000).toISOString(),
      is_expired: false,
    });

    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('transfer-owner-banner')).toBeInTheDocument();
      expect(screen.getByTestId('cancel-transfer-btn')).toBeInTheDocument();

      // When transfer is pending, nomination buttons in table are disabled
      const adminTransferBtn = screen.getByTestId('transfer-ownership-m-admin-2');
      expect(adminTransferBtn).toBeDisabled();
    });
  });

  it('renders former owner choice banner in State 5 and submits choice', async () => {
    useAuthStore.setState({
      user: {
        id: 'u-owner-1',
        email: 'owner@veritas.rag',
        role: 'MEMBER',
        workspace_id: mockWorkspaceId,
      } as any,
      status: 'AUTHENTICATED',
    });

    vi.spyOn(workspaceTransferService, 'getActiveTransfer').mockResolvedValue({
      id: 'trans-100',
      workspace_id: mockWorkspaceId,
      nominated_by: { id: 'u-owner-1', email: 'owner@veritas.rag', full_name: 'Lead Architect' },
      nominee: { id: 'u-admin-2', email: 'ops_admin@veritas.rag', full_name: 'Operations Admin' },
      status: 'ACCEPTED',
      former_owner_choice: 'PENDING',
      decision_status: 'PENDING',
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 7 * 86400000).toISOString(),
      is_expired: false,
    });

    const submitSpy = vi.spyOn(workspaceTransferService, 'submitFormerOwnerChoice').mockResolvedValue({
      id: 'trans-100',
      workspace_id: mockWorkspaceId,
      nominated_by: { id: 'u-owner-1', email: 'owner@veritas.rag', full_name: 'Lead Architect' },
      nominee: { id: 'u-admin-2', email: 'ops_admin@veritas.rag', full_name: 'Operations Admin' },
      status: 'ACCEPTED',
      former_owner_choice: 'STAY',
      decision_status: 'PENDING',
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 7 * 86400000).toISOString(),
      is_expired: false,
    } as any);

    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('former-owner-choice-banner')).toBeInTheDocument();
      expect(screen.getByTestId('former-owner-leave-btn')).toBeInTheDocument();
      expect(screen.getByTestId('former-owner-stay-btn')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('former-owner-stay-btn'));

    await waitFor(() => {
      expect(submitSpy).toHaveBeenCalledWith(mockWorkspaceId, 'trans-100', { choice: 'STAY' });
    });
  });

  it('renders new owner role decision banner in State 7 and submits role decision', async () => {
    useAuthStore.setState({
      user: {
        id: 'u-admin-2',
        email: 'ops_admin@veritas.rag',
        role: 'OWNER',
        workspace_id: mockWorkspaceId,
      } as any,
      status: 'AUTHENTICATED',
    });

    vi.spyOn(workspaceTransferService, 'getActiveTransfer').mockResolvedValue({
      id: 'trans-100',
      workspace_id: mockWorkspaceId,
      nominated_by: { id: 'u-owner-1', email: 'owner@veritas.rag', full_name: 'Lead Architect' },
      nominee: { id: 'u-admin-2', email: 'ops_admin@veritas.rag', full_name: 'Operations Admin' },
      status: 'ACCEPTED',
      former_owner_choice: 'STAY',
      decision_status: 'PENDING',
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 7 * 86400000).toISOString(),
      is_expired: false,
    });

    const decideSpy = vi.spyOn(workspaceTransferService, 'decideFormerOwnerRole').mockResolvedValue({
      id: 'trans-100',
      workspace_id: mockWorkspaceId,
      nominated_by: { id: 'u-owner-1', email: 'owner@veritas.rag', full_name: 'Lead Architect' },
      nominee: { id: 'u-admin-2', email: 'ops_admin@veritas.rag', full_name: 'Operations Admin' },
      status: 'ACCEPTED',
      former_owner_choice: 'STAY',
      decision_status: 'DECIDED_ROLE_ADMIN',
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 7 * 86400000).toISOString(),
      is_expired: false,
    } as any);

    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('new-owner-role-decision-banner')).toBeInTheDocument();
      expect(screen.getByTestId('decision-remove-btn')).toBeInTheDocument();
      expect(screen.getByTestId('decision-member-btn')).toBeInTheDocument();
      expect(screen.getByTestId('decision-admin-btn')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('decision-admin-btn'));

    await waitFor(() => {
      expect(decideSpy).toHaveBeenCalledWith(mockWorkspaceId, 'trans-100', { decision: 'ADMIN' });
    });
  });

  it('displays former owner badge for members flagged with is_former_owner', async () => {
    const membersWithFormerOwner = [
      ...mockMembers.slice(0, 2),
      {
        ...mockMembers[2],
        is_former_owner: true,
      },
    ];

    useMemberStore.setState({
      members: membersWithFormerOwner as any,
    });

    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('former-owner-badge-m-member-3')).toBeInTheDocument();
      expect(screen.getByTestId('former-owner-badge-m-member-3')).toHaveTextContent('Former Owner');
    });
  });
});
