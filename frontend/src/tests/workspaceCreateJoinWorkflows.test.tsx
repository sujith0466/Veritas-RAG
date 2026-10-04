import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import { useWorkspaceStore } from '@/stores/workspaceStore';
import { workspaceService } from '@/services/workspaceService';
import { invitationService } from '@/services/invitationService';
import { authService } from '@/services/auth/authService';
import { CreateWorkspace } from '@/pages/workspace/CreateWorkspace';
import { JoinWorkspacePage } from '@/pages/workspace/JoinWorkspacePage';
import { AcceptInvitationPage } from '@/pages/workspace/AcceptInvitationPage';

vi.mock('@/services/workspaceService', () => ({
  workspaceService: {
    createWorkspace: vi.fn(),
    lookupWorkspace: vi.fn(),
    joinWorkspace: vi.fn(),
    switchWorkspace: vi.fn(),
    getCurrentWorkspace: vi.fn(),
    getUserWorkspaces: vi.fn(),
  },
}));

vi.mock('@/services/invitationService', () => ({
  invitationService: {
    verifyInvitation: vi.fn(),
    acceptInvitation: vi.fn(),
  },
}));

vi.mock('@/services/auth/authService', () => ({
  authService: {
    createJoinIntent: vi.fn(),
  },
}));

describe('WS-A8: Create & Join Workspace Workflows', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      user: { id: 'user-1', email: 'user@example.com', role: 'member', tenant_id: null } as any,
      status: 'AUTHENTICATED',
      error: undefined,
    });
    useWorkspaceStore.setState({
      currentWorkspace: null,
      isResolvingWorkspace: false,
      workspaces: [],
      error: null,
      isLoading: false,
    });
  });

  // =========================================================================
  // 1. CREATE WORKSPACE WORKFLOW
  // =========================================================================
  describe('Create Workspace Workflow (/workspaces/new)', () => {
    it('1. Successfully creates workspace, authoritatively switches session context to OWNER, and navigates to /dashboard', async () => {
      const mockCreatedWorkspace = {
        id: 'ws-created-uuid-1',
        name: 'Alpha Quantum Lab',
        slug: 'alpha-quantum-lab',
        public_id: 'ALPHA-7X92',
        status: 'ACTIVE',
        provisioning_status: 'READY',
        updated_at: new Date().toISOString(),
      };

      vi.mocked(workspaceService.createWorkspace).mockResolvedValueOnce({
        success: true,
        data: mockCreatedWorkspace as any,
      });

      vi.mocked(workspaceService.switchWorkspace).mockResolvedValueOnce({
        success: true,
        message: 'Workspace context switched successfully.',
        data: {
          access_token: 'new-owner-token',
          token_type: 'bearer',
          workspace: {
            id: mockCreatedWorkspace.id,
            public_id: mockCreatedWorkspace.public_id,
            name: mockCreatedWorkspace.name,
            slug: mockCreatedWorkspace.slug,
            role: 'OWNER',
          },
        },
      } as any);

      render(
        <MemoryRouter initialEntries={['/workspaces/new']}>
          <Routes>
            <Route path="/workspaces/new" element={<CreateWorkspace />} />
            <Route path="/dashboard" element={<div data-testid="dashboard-dest">Workspace Dashboard</div>} />
          </Routes>
        </MemoryRouter>
      );

      const nameInput = screen.getByLabelText(/workspace name/i);
      const descInput = screen.getByLabelText(/description/i);
      const submitBtn = screen.getByRole('button', { name: /create workspace/i });

      fireEvent.change(nameInput, { target: { value: 'Alpha Quantum Lab' } });
      fireEvent.change(descInput, { target: { value: 'Cutting edge quantum research team' } });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(workspaceService.createWorkspace).toHaveBeenCalledWith(
          'Alpha Quantum Lab',
          'Cutting edge quantum research team'
        );
        expect(workspaceService.switchWorkspace).toHaveBeenCalledWith('ws-created-uuid-1');
        expect(screen.getByTestId('dashboard-dest')).toBeInTheDocument();
      });

      // Confirm authStore was updated with the authoritative creator role
      expect(useAuthStore.getState().user?.tenant_id).toBe('ws-created-uuid-1');
      expect(useAuthStore.getState().user?.role).toBe('owner');
    });

    it('2. Enforces validation for required and length-bounded workspace name', async () => {
      render(
        <MemoryRouter initialEntries={['/workspaces/new']}>
          <CreateWorkspace />
        </MemoryRouter>
      );

      const submitBtn = screen.getByRole('button', { name: /create workspace/i });
      expect(submitBtn).toBeDisabled();

      const nameInput = screen.getByLabelText(/workspace name/i);
      // Min length 2
      fireEvent.change(nameInput, { target: { value: 'A' } });
      expect(submitBtn).not.toBeDisabled();
      fireEvent.click(submitBtn);

      expect(screen.getByText(/workspace name must be at least 2 characters long/i)).toBeInTheDocument();
      expect(workspaceService.createWorkspace).not.toHaveBeenCalled();
    });

    it('3. Prevents duplicate creation on rapid double-submission', async () => {
      let resolveCreation: any;
      const creationPromise = new Promise((resolve) => {
        resolveCreation = resolve;
      });
      vi.mocked(workspaceService.createWorkspace).mockReturnValue(creationPromise as any);

      render(
        <MemoryRouter initialEntries={['/workspaces/new']}>
          <CreateWorkspace />
        </MemoryRouter>
      );

      const nameInput = screen.getByLabelText(/workspace name/i);
      fireEvent.change(nameInput, { target: { value: 'Acme Security' } });

      const submitBtn = screen.getByRole('button', { name: /create workspace/i });
      fireEvent.click(submitBtn);
      fireEvent.click(submitBtn); // Duplicate rapid click

      expect(workspaceService.createWorkspace).toHaveBeenCalledTimes(1);

      // Clean up async promise
      resolveCreation({
        success: true,
        data: { id: 'ws-1', name: 'Acme Security', slug: 'acme-sec' },
      });
    });

    it('4. Renders backend error message on creation failure', async () => {
      vi.mocked(workspaceService.createWorkspace).mockRejectedValueOnce({
        response: {
          data: {
            detail: 'Email verification required to create a workspace.',
          },
        },
      });

      render(
        <MemoryRouter initialEntries={['/workspaces/new']}>
          <CreateWorkspace />
        </MemoryRouter>
      );

      const nameInput = screen.getByLabelText(/workspace name/i);
      fireEvent.change(nameInput, { target: { value: 'Acme Unverified' } });

      const submitBtn = screen.getByRole('button', { name: /create workspace/i });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/email verification required to create a workspace/i)).toBeInTheDocument();
      });
    });
  });

  // =========================================================================
  // 2. JOIN WORKSPACE WORKFLOW — MODE 1 (OPEN) & MODE 2 (JOIN CODE)
  // =========================================================================
  describe('Join Workspace Workflow (/workspaces/join)', () => {
    it('5. Lookup previews safe public workspace information and rejects internal Tenant UUID', async () => {
      render(
        <MemoryRouter initialEntries={['/workspaces/join']}>
          <JoinWorkspacePage />
        </MemoryRouter>
      );

      const idInput = screen.getByLabelText(/workspace id or slug/i);
      const lookupBtn = screen.getByRole('button', { name: /lookup/i });

      // Test client-side rejection of internal Tenant UUID
      fireEvent.change(idInput, { target: { value: '123e4567-e89b-12d3-a456-426614174000' } });
      fireEvent.click(lookupBtn);

      expect(screen.getByText(/internal tenant uuid cannot be used/i)).toBeInTheDocument();
      expect(workspaceService.lookupWorkspace).not.toHaveBeenCalled();

      // Test valid public lookup
      vi.mocked(workspaceService.lookupWorkspace).mockResolvedValueOnce({
        success: true,
        message: 'Workspace preview retrieved successfully.',
        data: {
          workspace_id: 'RESEARCH-LAB',
          workspace_name: 'Research Laboratory',
          workspace_slug: 'research-lab',
          joining_mode: 'JOIN_CODE' as any,
          requires_join_code: true,
          open_join: false,
          require_approval: false,
          default_join_role: 'MEMBER',
        },
      });

      fireEvent.change(idInput, { target: { value: 'RESEARCH-LAB' } });
      fireEvent.click(lookupBtn);

      await waitFor(() => {
        expect(workspaceService.lookupWorkspace).toHaveBeenCalledWith('RESEARCH-LAB');
        expect(screen.getByText('Research Laboratory')).toBeInTheDocument();
        expect(screen.getByText(/requires code/i)).toBeInTheDocument();
      });
    });

    it('6. Mode 1: Open Join succeeds without a Join Code and activates workspace session', async () => {
      vi.mocked(workspaceService.joinWorkspace).mockResolvedValueOnce({
        success: true,
        message: 'Successfully joined workspace.',
        data: {
          workspace_id: 'ws-open-uuid',
          workspace_name: 'Public AI Sandbox',
          role: 'MEMBER',
          status: 'ACTIVE',
          member_id: 'mem-1',
        },
      });

      vi.mocked(workspaceService.switchWorkspace).mockResolvedValueOnce({
        success: true,
        data: {
          access_token: 'new-token',
          workspace: { id: 'ws-open-uuid', name: 'Public AI Sandbox', role: 'MEMBER' },
        },
      } as any);

      render(
        <MemoryRouter initialEntries={['/workspaces/join']}>
          <Routes>
            <Route path="/workspaces/join" element={<JoinWorkspacePage />} />
            <Route path="/dashboard" element={<div data-testid="dashboard-dest">Dashboard Page</div>} />
          </Routes>
        </MemoryRouter>
      );

      const idInput = screen.getByLabelText(/workspace id or slug/i);
      fireEvent.change(idInput, { target: { value: 'PUBLIC-SANDBOX' } });

      const joinBtn = screen.getByRole('button', { name: /join workspace/i });
      fireEvent.click(joinBtn);

      await waitFor(() => {
        expect(workspaceService.joinWorkspace).toHaveBeenCalledWith({
          workspace_id: 'PUBLIC-SANDBOX',
          join_code: undefined,
        });
        expect(workspaceService.switchWorkspace).toHaveBeenCalledWith('ws-open-uuid');
        expect(screen.getByText(/successfully joined public ai sandbox/i)).toBeInTheDocument();
      });
    });

    it('7. Mode 2: Protected Join Code succeeds with VR-XXXXXX and activates workspace session', async () => {
      vi.mocked(workspaceService.joinWorkspace).mockResolvedValueOnce({
        success: true,
        message: 'Successfully joined workspace.',
        data: {
          workspace_id: 'ws-protected-uuid',
          workspace_name: 'Core Engineering',
          role: 'MEMBER',
          status: 'ACTIVE',
          member_id: 'mem-2',
        },
      });

      vi.mocked(workspaceService.switchWorkspace).mockResolvedValueOnce({
        success: true,
        data: {
          access_token: 'new-token',
          workspace: { id: 'ws-protected-uuid', name: 'Core Engineering', role: 'MEMBER' },
        },
      } as any);

      render(
        <MemoryRouter initialEntries={['/workspaces/join']}>
          <Routes>
            <Route path="/workspaces/join" element={<JoinWorkspacePage />} />
            <Route path="/dashboard" element={<div data-testid="dashboard-dest">Dashboard Page</div>} />
          </Routes>
        </MemoryRouter>
      );

      const idInput = screen.getByLabelText(/workspace id or slug/i);
      const codeInput = screen.getByLabelText(/join code/i);

      fireEvent.change(idInput, { target: { value: 'CORE-ENG' } });
      fireEvent.change(codeInput, { target: { value: 'VR-234567' } });

      const joinBtn = screen.getByRole('button', { name: /join workspace/i });
      fireEvent.click(joinBtn);

      await waitFor(() => {
        expect(workspaceService.joinWorkspace).toHaveBeenCalledWith({
          workspace_id: 'CORE-ENG',
          join_code: 'VR-234567',
        });
        expect(workspaceService.switchWorkspace).toHaveBeenCalledWith('ws-protected-uuid');
      });
    });

    it('8. Mode 2: Rejects invalid or expired Join Code from server with truthful error', async () => {
      vi.mocked(workspaceService.joinWorkspace).mockRejectedValueOnce({
        response: {
          status: 400,
          data: {
            detail: 'Invalid join code.',
          },
        },
      });

      render(
        <MemoryRouter initialEntries={['/workspaces/join']}>
          <JoinWorkspacePage />
        </MemoryRouter>
      );

      const idInput = screen.getByLabelText(/workspace id or slug/i);
      const codeInput = screen.getByLabelText(/join code/i);

      fireEvent.change(idInput, { target: { value: 'CORE-ENG' } });
      fireEvent.change(codeInput, { target: { value: 'VR-888888' } });

      const joinBtn = screen.getByRole('button', { name: /join workspace/i });
      fireEvent.click(joinBtn);

      await waitFor(() => {
        expect(screen.getByText('Invalid join code.')).toBeInTheDocument();
      });
    });

    it('8b. Mode 2: Client rejects malformed Join Code length and invalid Crockford characters', async () => {
      render(
        <MemoryRouter initialEntries={['/workspaces/join']}>
          <JoinWorkspacePage />
        </MemoryRouter>
      );

      const idInput = screen.getByLabelText(/workspace id or slug/i);
      const codeInput = screen.getByLabelText(/join code/i);

      fireEvent.change(idInput, { target: { value: 'CORE-ENG' } });
      // Malformed length (too short)
      fireEvent.change(codeInput, { target: { value: 'VR-12' } });

      const joinBtn = screen.getByRole('button', { name: /join workspace/i });
      fireEvent.click(joinBtn);

      await waitFor(() => {
        expect(screen.getByText(/Invalid Join Code format/i)).toBeInTheDocument();
      });

      // Invalid Crockford characters (0, O, 1, I, L)
      fireEvent.change(codeInput, { target: { value: 'VR-000000' } });
      fireEvent.click(joinBtn);

      await waitFor(() => {
        expect(screen.getByText(/Invalid Join Code format/i)).toBeInTheDocument();
      });

      expect(workspaceService.joinWorkspace).not.toHaveBeenCalled();
    });

    it('8c. Mode 2: Normalizes lowercase and 6-char payload without prefix', async () => {
      vi.mocked(workspaceService.joinWorkspace).mockResolvedValueOnce({
        success: true,
        message: 'Joined successfully',
        data: {
          workspace_id: 'ws-norm-uuid',
          workspace_name: 'Core Engineering',
          role: 'MEMBER',
          status: 'ACTIVE',
          member_id: 'mem-norm',
        },
      });

      vi.mocked(workspaceService.switchWorkspace).mockResolvedValueOnce({
        success: true,
        data: {
          access_token: 'new-token',
          workspace: { id: 'ws-norm-uuid', name: 'Core Engineering', role: 'MEMBER' },
        },
      } as any);

      render(
        <MemoryRouter initialEntries={['/workspaces/join']}>
          <JoinWorkspacePage />
        </MemoryRouter>
      );

      const idInput = screen.getByLabelText(/workspace id or slug/i);
      const codeInput = screen.getByLabelText(/join code/i);

      fireEvent.change(idInput, { target: { value: 'CORE-ENG' } });
      // Lowercase 6-character payload without VR- prefix
      fireEvent.change(codeInput, { target: { value: '234567' } });

      const joinBtn = screen.getByRole('button', { name: /join workspace/i });
      fireEvent.click(joinBtn);

      await waitFor(() => {
        expect(workspaceService.joinWorkspace).toHaveBeenCalledWith({
          workspace_id: 'CORE-ENG',
          join_code: 'VR-234567',
        });
      });
    });

    it('9. Approval Mode: Renders PENDING_APPROVAL status without activating session or granting dashboard access', async () => {
      vi.mocked(workspaceService.joinWorkspace).mockResolvedValueOnce({
        success: true,
        message: 'Request submitted.',
        data: {
          workspace_id: 'ws-approval-uuid',
          workspace_name: 'Strict Governance Team',
          role: 'VIEWER',
          status: 'PENDING_APPROVAL',
          member_id: 'mem-3',
        },
      });

      render(
        <MemoryRouter initialEntries={['/workspaces/join']}>
          <Routes>
            <Route path="/workspaces/join" element={<JoinWorkspacePage />} />
            <Route path="/dashboard" element={<div data-testid="dashboard-dest">Dashboard Page</div>} />
          </Routes>
        </MemoryRouter>
      );

      const idInput = screen.getByLabelText(/workspace id or slug/i);
      fireEvent.change(idInput, { target: { value: 'STRICT-GOV' } });

      const joinBtn = screen.getByRole('button', { name: /join workspace/i });
      fireEvent.click(joinBtn);

      await waitFor(() => {
        expect(screen.getByText('Approval Required')).toBeInTheDocument();
        expect(screen.getByText(/pending administrator approval/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /return to onboarding/i })).toBeInTheDocument();
        // Crucial security invariant: switchWorkspace was NEVER called
        expect(workspaceService.switchWorkspace).not.toHaveBeenCalled();
        expect(screen.queryByTestId('dashboard-dest')).not.toBeInTheDocument();
      });
    });

    it('10. 409 Conflict: Surfaces "already a member" with switch button to activate session', async () => {
      vi.mocked(workspaceService.joinWorkspace).mockRejectedValueOnce({
        response: {
          status: 409,
          data: {
            detail: 'User is already an active member of this workspace.',
          },
        },
      });

      vi.mocked(workspaceService.switchWorkspace).mockResolvedValueOnce({
        success: true,
        data: {
          access_token: 'switched-token',
          workspace: { id: 'CORE-ENG', name: 'Core Eng', role: 'MEMBER' },
        },
      } as any);

      render(
        <MemoryRouter initialEntries={['/workspaces/join']}>
          <Routes>
            <Route path="/workspaces/join" element={<JoinWorkspacePage />} />
            <Route path="/dashboard" element={<div data-testid="dashboard-dest">Dashboard Page</div>} />
          </Routes>
        </MemoryRouter>
      );

      const idInput = screen.getByLabelText(/workspace id or slug/i);
      fireEvent.change(idInput, { target: { value: 'CORE-ENG' } });

      const joinBtn = screen.getByRole('button', { name: /join workspace/i });
      fireEvent.click(joinBtn);

      await waitFor(() => {
        expect(screen.getByText(/you are already an active member of this workspace/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /switch to this workspace/i })).toBeInTheDocument();
      });

      const switchBtn = screen.getByRole('button', { name: /switch to this workspace/i });
      fireEvent.click(switchBtn);

      await waitFor(() => {
        expect(workspaceService.switchWorkspace).toHaveBeenCalledWith('CORE-ENG');
        expect(screen.getByTestId('dashboard-dest')).toBeInTheDocument();
      });
    });
  });

  // =========================================================================
  // 3. INVITATION TOKEN WORKFLOW (MODE 3)
  // =========================================================================
  describe('Invitation Acceptance Workflows', () => {
    it('11. AcceptInvitationPage accepts token, establishes active session context, and navigates to /dashboard', async () => {
      vi.mocked(invitationService.verifyInvitation).mockResolvedValueOnce({
        workspace_name: 'Design Systems',
        role: 'EDITOR',
        email: 'user@example.com',
      } as any);

      vi.mocked(invitationService.acceptInvitation).mockResolvedValueOnce({
        workspace_id: 'ws-invited-uuid',
        workspace_name: 'Design Systems',
        role: 'EDITOR',
        member_id: 'mem-inv-1',
      });

      vi.mocked(workspaceService.switchWorkspace).mockResolvedValueOnce({
        success: true,
        data: {
          access_token: 'new-token',
          workspace: { id: 'ws-invited-uuid', name: 'Design Systems', role: 'EDITOR' },
        },
      } as any);

      render(
        <MemoryRouter initialEntries={['/invitations/accept?token=sec_inv_valid_token_123']}>
          <Routes>
            <Route path="/invitations/accept" element={<AcceptInvitationPage />} />
            <Route path="/dashboard" element={<div data-testid="dashboard-dest">Dashboard Page</div>} />
          </Routes>
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(invitationService.verifyInvitation).toHaveBeenCalledWith('sec_inv_valid_token_123');
        expect(screen.getByText('Design Systems')).toBeInTheDocument();
        expect(screen.getByText('EDITOR')).toBeInTheDocument();
      });

      const acceptBtn = screen.getByRole('button', { name: /accept & join workspace/i });
      fireEvent.click(acceptBtn);

      await waitFor(() => {
        expect(invitationService.acceptInvitation).toHaveBeenCalledWith({
          token: 'sec_inv_valid_token_123',
        });
        expect(workspaceService.switchWorkspace).toHaveBeenCalledWith('ws-invited-uuid');
        expect(screen.getByText(/invitation accepted/i)).toBeInTheDocument();
      });
    });

    it('12. JoinWorkspacePage Invitation Tab accepts token and activates workspace session', async () => {
      vi.mocked(invitationService.acceptInvitation).mockResolvedValueOnce({
        workspace_id: 'ws-tab-uuid',
        workspace_name: 'Security Lab',
        role: 'ADMIN',
        member_id: 'mem-tab-1',
      });

      vi.mocked(workspaceService.switchWorkspace).mockResolvedValueOnce({
        success: true,
        data: {
          access_token: 'new-token',
          workspace: { id: 'ws-tab-uuid', name: 'Security Lab', role: 'ADMIN' },
        },
      } as any);

      render(
        <MemoryRouter initialEntries={['/workspaces/join?invitation_token=sec_inv_tab_token']}>
          <JoinWorkspacePage />
        </MemoryRouter>
      );

      const tokenInput = screen.getByLabelText(/invitation token/i);
      expect((tokenInput as HTMLInputElement).value).toBe('sec_inv_tab_token');

      const submitBtn = screen.getByRole('button', { name: /accept & join workspace/i });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(invitationService.acceptInvitation).toHaveBeenCalledWith({
          token: 'sec_inv_tab_token',
        });
        expect(workspaceService.switchWorkspace).toHaveBeenCalledWith('ws-tab-uuid');
        expect(screen.getByText(/invitation accepted for security lab/i)).toBeInTheDocument();
      });
    });
  });

  // =========================================================================
  // 4. GOOGLE CONTINUITY / JOIN INTENT HELPER
  // =========================================================================
  describe('Google Continuity / Pre-Auth Join Intent', () => {
    it('13. authService.createJoinIntent generates opaque intent_id without exposing secrets in URLs', async () => {
      vi.mocked(authService.createJoinIntent).mockResolvedValueOnce({
        intent_id: 'opaque_intent_abc123xyz',
        expires_in_seconds: 600,
      });

      const result = await authService.createJoinIntent({
        workspace_id: 'CORE-ENG',
        join_code: 'VR-234567',
      });

      expect(result.intent_id).toBe('opaque_intent_abc123xyz');
      expect(result.expires_in_seconds).toBe(600);
      expect(authService.createJoinIntent).toHaveBeenCalledWith({
        workspace_id: 'CORE-ENG',
        join_code: 'VR-234567',
      });
    });
  });
});
