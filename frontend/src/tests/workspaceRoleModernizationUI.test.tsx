import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { BrowserRouter, MemoryRouter } from 'react-router-dom'
import { WorkspaceMembersPage, matchMemberIdentity } from '@/pages/workspace/WorkspaceMembersPage'
import { WorkspaceSettings } from '@/pages/settings/WorkspaceSettings'
import { useMemberStore } from '@/stores/memberStore'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { invitationService } from '@/services/invitationService'
import { accessRequestService } from '@/services/accessRequestService'
import { workspaceService } from '@/services/workspaceService'
import { workspaceSettingsService } from '@/services/workspaceSettingsService'
import { memberService } from '@/services/memberService'

describe('WP-9: Workspace Role & UI Dropdown Modernization', () => {
  const mockWorkspaceId = 'ws-test-wp9-modern'
  const originalFetchMembers = useMemberStore.getState().fetchMembers

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
        email: 'owner@example.com',
        username: 'lead_owner',
        display_name: 'Lead Owner',
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
        email: 'ops_admin@example.com',
        username: 'ops_admin',
        display_name: 'Ops Admin',
      },
    },
    {
      id: 'm-admin-peer',
      workspace_id: mockWorkspaceId,
      user_id: 'u-admin-peer',
      role: 'ADMIN',
      status: 'ACTIVE',
      joined_at: '2026-09-12T12:00:00Z',
      user: {
        id: 'u-admin-peer',
        email: 'peer_admin@example.com',
        username: 'peer_admin',
        display_name: 'Peer Admin',
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
        email: 'member@example.com',
        username: 'dev_member',
        display_name: 'Dev Member',
      },
    },
    {
      id: 'm-viewer-legacy',
      workspace_id: mockWorkspaceId,
      user_id: 'u-viewer-legacy',
      role: 'VIEWER',
      status: 'ACTIVE',
      joined_at: '2026-08-01T10:00:00Z',
      user: {
        id: 'u-viewer-legacy',
        email: 'legacy_viewer@example.com',
        username: 'old_viewer',
        display_name: 'Legacy Viewer',
      },
    },
  ]

  const mockInvitations = [
    {
      id: 'inv-member',
      workspace_id: mockWorkspaceId,
      email: 'invitee_member@example.com',
      role: 'MEMBER',
      status: 'PENDING',
      expires_at: '2026-11-15T00:00:00Z',
      created_at: '2026-10-01T00:00:00Z',
    },
    {
      id: 'inv-admin',
      workspace_id: mockWorkspaceId,
      email: 'invitee_admin@example.com',
      role: 'ADMIN',
      status: 'PENDING',
      expires_at: '2026-11-15T00:00:00Z',
      created_at: '2026-10-01T00:00:00Z',
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()

    useWorkspaceStore.setState({
      currentWorkspace: {
        id: mockWorkspaceId,
        public_id: 'wrk_pub999',
        name: 'WP9 Modern Workspace',
        slug: 'wp9-modern',
        status: 'ACTIVE',
        role: 'OWNER',
      } as any,
    })

    useAuthStore.setState({
      user: {
        id: 'u-owner-1',
        email: 'owner@example.com',
        role: 'OWNER',
        workspace_id: mockWorkspaceId,
        workspace_name: 'WP9 Modern Workspace',
      } as any,
      status: 'AUTHENTICATED',
    })

    useMemberStore.setState({
      members: mockMembers as any,
      total: 5,
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
      pagination: { page: 1, size: 50, total_elements: 2, total_pages: 1 },
    } as any)

    vi.spyOn(invitationService, 'sendInvitation').mockResolvedValue({} as any)
    vi.spyOn(invitationService, 'revokeInvitation').mockResolvedValue({} as any)
    vi.spyOn(invitationService, 'resendInvitation').mockResolvedValue({} as any)

    vi.spyOn(accessRequestService, 'listRequests').mockResolvedValue({
      items: [],
      pagination: { page: 1, size: 50, total_elements: 0, total_pages: 0 },
    } as any)

    vi.spyOn(memberService, 'listMembers').mockResolvedValue({
      items: mockMembers as any,
      total: mockMembers.length,
      page: 1,
      page_size: 50,
    } as any)
  })

  // ── 1. INVITATION MODAL ROLE CHOICES ───────────────────────────────────────

  it('OWNER invitation modal offers ADMIN and MEMBER options, but NOT VIEWER', async () => {
    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    )

    // Open invite modal
    const inviteBtn = screen.getByRole('button', { name: /Invite Team Member/i })
    fireEvent.click(inviteBtn)

    const roleSelect = screen.getByLabelText(/Assigned Workspace Role/i) as HTMLSelectElement
    const options = Array.from(roleSelect.options).map(o => o.value)

    expect(options).toContain('ADMIN')
    expect(options).toContain('MEMBER')
    expect(options).not.toContain('VIEWER')
    expect(roleSelect.value).toBe('MEMBER')
  })

  it('ADMIN invitation modal offers ONLY MEMBER, prohibiting ADMIN and VIEWER', async () => {
    useAuthStore.setState({
      user: {
        id: 'u-admin-2',
        email: 'ops_admin@example.com',
        role: 'ADMIN',
        workspace_id: mockWorkspaceId,
      } as any,
    })
    useWorkspaceStore.setState({
      currentWorkspace: {
        id: mockWorkspaceId,
        role: 'ADMIN',
      } as any,
    })

    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    )

    const inviteBtn = screen.getByRole('button', { name: /Invite Team Member/i })
    fireEvent.click(inviteBtn)

    const roleSelect = screen.getByLabelText(/Assigned Workspace Role/i) as HTMLSelectElement
    const options = Array.from(roleSelect.options).map(o => o.value)

    expect(options).toContain('MEMBER')
    expect(options).not.toContain('ADMIN')
    expect(options).not.toContain('VIEWER')
    expect(roleSelect.value).toBe('MEMBER')
  })

  // ── 2. PEER ADMIN PROTECTION (ADMIN ACTOR) ─────────────────────────────────

  it('ADMIN cannot demote, suspend, or remove a peer ADMIN', async () => {
    useAuthStore.setState({
      user: {
        id: 'u-admin-2',
        email: 'ops_admin@example.com',
        role: 'ADMIN',
        workspace_id: mockWorkspaceId,
      } as any,
    })
    useWorkspaceStore.setState({
      currentWorkspace: {
        id: mockWorkspaceId,
        role: 'ADMIN',
      } as any,
    })

    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    )

    // Find the row for Peer Admin
    const peerRow = screen.getByText('Peer Admin').closest('tr')!
    expect(peerRow).toBeInTheDocument()

    // Role should NOT be a select dropdown, but rendered as the ADMIN badge
    expect(within(peerRow).queryByRole('combobox')).not.toBeInTheDocument()
    expect(within(peerRow).getByText('ADMIN')).toBeInTheDocument()

    // Action buttons (Suspend, Remove) should NOT be present; row shows Protected
    expect(within(peerRow).queryByTitle('Suspend Member')).not.toBeInTheDocument()
    expect(within(peerRow).queryByTitle('Remove Member')).not.toBeInTheDocument()
    expect(within(peerRow).getByText('Protected')).toBeInTheDocument()

    // Checkbox for bulk management should NOT be an input, but a disabled/protected icon
    expect(within(peerRow).queryByRole('checkbox')).not.toBeInTheDocument()
  })

  // ── 3. ADMIN PROMOTING ACTIVE MEMBER ───────────────────────────────────────

  it('ADMIN can promote an active MEMBER to ADMIN, but cannot assign VIEWER', async () => {
    useAuthStore.setState({
      user: {
        id: 'u-admin-2',
        email: 'ops_admin@example.com',
        role: 'ADMIN',
        workspace_id: mockWorkspaceId,
      } as any,
    })
    useWorkspaceStore.setState({
      currentWorkspace: {
        id: mockWorkspaceId,
        role: 'ADMIN',
      } as any,
    })

    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    )

    const memberRow = screen.getByText('Dev Member').closest('tr')!
    expect(memberRow).toBeInTheDocument()

    // Role SHOULD be an editable select for the Member
    const roleSelect = within(memberRow).getByRole('combobox') as HTMLSelectElement
    const options = Array.from(roleSelect.options).map(o => o.value)

    expect(options).toContain('MEMBER')
    expect(options).toContain('ADMIN')
    expect(options).not.toContain('VIEWER')

    // ADMIN can trigger promotion to ADMIN
    fireEvent.change(roleSelect, { target: { value: 'ADMIN' } })
    expect(useMemberStore.getState().updateRole).toHaveBeenCalledWith(mockWorkspaceId, 'm-member-3', 'ADMIN')
  })

  // ── 4. OWNER ROLE MUTATION & ACTIONS ON ADMIN ──────────────────────────────

  it('OWNER can demote an ADMIN to MEMBER and remove an ADMIN', async () => {
    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    )

    const adminRow = screen.getByText('Ops Admin').closest('tr')!
    expect(adminRow).toBeInTheDocument()

    // Role select is editable for OWNER
    const roleSelect = within(adminRow).getByRole('combobox') as HTMLSelectElement
    const options = Array.from(roleSelect.options).map(o => o.value)

    expect(options).toContain('ADMIN')
    expect(options).toContain('MEMBER')
    expect(options).not.toContain('VIEWER')

    // OWNER can demote ADMIN to MEMBER
    fireEvent.change(roleSelect, { target: { value: 'MEMBER' } })
    expect(useMemberStore.getState().updateRole).toHaveBeenCalledWith(mockWorkspaceId, 'm-admin-2', 'MEMBER')

    // OWNER can remove ADMIN
    const removeBtn = within(adminRow).getByTitle('Remove Member')
    expect(removeBtn).toBeInTheDocument()
  })

  // ── 5. LEGACY VIEWER PRESERVATION ──────────────────────────────────────────

  it('preserves and cleanly renders legacy VIEWER records with badge', async () => {
    useAuthStore.setState({
      user: {
        id: 'u-viewer-legacy',
        email: 'legacy_viewer@example.com',
        role: 'VIEWER',
      } as any,
    })

    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    )

    const viewerRow = screen.getByText('Legacy Viewer').closest('tr')!
    expect(viewerRow).toBeInTheDocument()

    // Renders the VIEWER badge
    const roleCell = viewerRow.querySelectorAll('td')[2]
    const badge = within(roleCell).getByText(/VIEWER/i)
    expect(badge).toBeInTheDocument()

    // T-66: Verify tooltip / deprecation text and accessible attributes
    expect(badge.getAttribute('title')).toBe(
      'Legacy read-only access. New VIEWER assignments are deprecated.'
    )
    expect(badge.getAttribute('aria-label')).toBe(
      'VIEWER: Legacy read-only access. New VIEWER assignments are deprecated.'
    )
  })

  // ── 6. PENDING INVITATIONS TAB PEER PROTECTION ─────────────────────────────

  it('OWNER can resend and revoke ADMIN invitations', async () => {
    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    )

    // Switch to invitations tab
    const invTab = screen.getByRole('button', { name: /Pending Invitations/i })
    fireEvent.click(invTab)

    expect(await screen.findByText('invitee_admin@example.com')).toBeInTheDocument()
    const adminInvRow = screen.getByText('invitee_admin@example.com').closest('tr')!

    // Both Resend and Revoke are available for OWNER
    expect(within(adminInvRow).getByTitle(/Resend Invitation/i)).toBeInTheDocument()
    expect(within(adminInvRow).getByTitle(/Revoke Invitation/i)).toBeInTheDocument()
  })

  it('ADMIN cannot resend or revoke peer ADMIN invitations', async () => {
    useAuthStore.setState({
      user: {
        id: 'u-admin-2',
        email: 'ops_admin@example.com',
        role: 'ADMIN',
        workspace_id: mockWorkspaceId,
      } as any,
    })
    useWorkspaceStore.setState({
      currentWorkspace: {
        id: mockWorkspaceId,
        role: 'ADMIN',
      } as any,
    })

    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    )

    const invTab = screen.getByRole('button', { name: /Pending Invitations/i })
    fireEvent.click(invTab)

    expect(await screen.findByText('invitee_admin@example.com')).toBeInTheDocument()
    const adminInvRow = screen.getByText('invitee_admin@example.com').closest('tr')!

    // ADMIN cannot resend or revoke peer ADMIN invitation -> shows Protected
    expect(within(adminInvRow).queryByTitle(/Resend Invitation/i)).not.toBeInTheDocument()
    expect(within(adminInvRow).queryByTitle(/Revoke Invitation/i)).not.toBeInTheDocument()
    expect(within(adminInvRow).getByText('Protected')).toBeInTheDocument()

    // But ADMIN CAN manage MEMBER invitations
    const memberInvRow = screen.getByText('invitee_member@example.com').closest('tr')!
    expect(within(memberInvRow).getByTitle(/Resend Invitation/i)).toBeInTheDocument()
    expect(within(memberInvRow).getByTitle(/Revoke Invitation/i)).toBeInTheDocument()
  })

  // ── 7. JOIN CODE SETTINGS DEFAULT ROLE MODERNIZATION ───────────────────────

  it('Join Code Settings default role selector offers only MEMBER, prohibiting VIEWER as a new option', async () => {
    const mockJoinCodeSettings = {
      enabled: true,
      has_code: true,
      default_role: 'MEMBER' as const,
      require_approval: false,
      max_uses: 25,
      current_uses: 3,
      expires_at: '2026-12-01T00:00:00Z',
    }

    vi.spyOn(workspaceService, 'getJoinCodeSettings').mockResolvedValue(mockJoinCodeSettings as any)
    vi.spyOn(workspaceService, 'getJoinAccess').mockResolvedValue({
      join_code: 'VR-TEST99',
      has_active_code: true,
    } as any)
    vi.spyOn(workspaceSettingsService, 'getSettings').mockResolvedValue({
      settings: { general: { retention_days: 90, default_language: 'en' } },
      schema_version: 1,
      version: 1,
      settings_hash: 'abc123',
    } as any)

    render(
      <MemoryRouter>
        <WorkspaceSettings />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Active Join Code')).toBeInTheDocument()
    })

    const roleSelect = screen.getByLabelText(/Default Role/i) as HTMLSelectElement
    const options = Array.from(roleSelect.options).map(o => o.value)

    expect(options).toContain('MEMBER')
    expect(options).not.toContain('VIEWER')
  })

  // ── 8. WP-9.1 WORKSPACE-SPECIFIC ROLE RESOLUTION & SUSPENDED GUARDS ──────

  it('Non-member with global user.role === "ADMIN" sees no workspace administration controls', async () => {
    useAuthStore.setState({
      user: {
        id: 'u-foreign-admin',
        email: 'foreign_admin@other.com',
        role: 'ADMIN',
        workspace_id: 'ws-foreign',
      } as any,
    })
    useWorkspaceStore.setState({
      currentWorkspace: {
        id: mockWorkspaceId,
      } as any,
    })

    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    )

    // Should NOT see administrative action buttons
    expect(screen.queryByRole('button', { name: /Invite Team Member/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Access Requests/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Request to Admin/i })).not.toBeInTheDocument()

    // Member table rows should NOT have role select dropdowns or bulk checkboxes
    expect(screen.queryByTitle(/Update member role/i)).not.toBeInTheDocument()
    expect(screen.queryByTitle(/Select all actionable members/i)).not.toBeInTheDocument()
  })

  it('Global platform administrator without active workspace membership does not acquire workspace OWNER/ADMIN affordances', async () => {
    useAuthStore.setState({
      user: {
        id: 'u-platform-admin',
        email: 'padmin@platform.com',
        role: 'PLATFORM_ADMIN',
      } as any,
    })
    useWorkspaceStore.setState({
      currentWorkspace: {
        id: mockWorkspaceId,
      } as any,
    })

    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    )

    expect(screen.queryByRole('button', { name: /Invite Team Member/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Access Requests/i })).not.toBeInTheDocument()
    expect(screen.queryByTitle(/Update member role/i)).not.toBeInTheDocument()
  })

  it('Legitimate workspace ADMIN retains correct role when searching or filtering removes their own row from the visible list', async () => {
    useAuthStore.setState({
      user: {
        id: 'u-admin-2',
        email: 'ops_admin@example.com',
        role: 'MEMBER', // global role is deliberately MEMBER to verify workspace membership primacy
        workspace_id: mockWorkspaceId,
      } as any,
    })
    useWorkspaceStore.setState({
      currentWorkspace: {
        id: mockWorkspaceId,
      } as any,
    })

    const { rerender } = render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    )

    // Initially caller is in mockMembers as ADMIN -> Invite button is visible
    expect(screen.getByRole('button', { name: /Invite Team Member/i })).toBeInTheDocument()

    // Simulate search: list is filtered to only include Dev Member (caller u-admin-2 is filtered out)
    useMemberStore.setState({
      members: [mockMembers[3]] as any, // only Dev Member (MEMBER)
    })

    rerender(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    )

    // Cached caller membership ensures ADMIN affordances persist across search/filtering
    expect(screen.getByRole('button', { name: /Invite Team Member/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Access Requests/i })).toBeInTheDocument()

    // Can still manage the visible member's role
    const devMemberRow = screen.getByText('Dev Member').closest('tr')!
    expect(within(devMemberRow).getByRole('combobox')).toBeInTheDocument()
  })

  it('Suspended ADMIN does not see actionable workspace administration controls', async () => {
    const suspendedAdminMember = {
      id: 'm-admin-suspended',
      workspace_id: mockWorkspaceId,
      user_id: 'u-admin-suspended',
      role: 'ADMIN',
      status: 'SUSPENDED',
      joined_at: '2026-09-01T10:00:00Z',
      user: {
        id: 'u-admin-suspended',
        email: 'suspended_admin@example.com',
        username: 'suspended_admin',
        display_name: 'Suspended Admin',
      },
    }

    useAuthStore.setState({
      user: {
        id: 'u-admin-suspended',
        email: 'suspended_admin@example.com',
        role: 'ADMIN',
        workspace_id: mockWorkspaceId,
      } as any,
    })
    useWorkspaceStore.setState({
      currentWorkspace: {
        id: mockWorkspaceId,
      } as any,
    })
    useMemberStore.setState({
      members: [suspendedAdminMember, mockMembers[3]] as any,
    })

    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    )

    // Must show suspended warning banner
    expect(screen.getByText(/Workspace Access Suspended:/i)).toBeInTheDocument()

    // Must NOT show administrative buttons
    expect(screen.queryByRole('button', { name: /Invite Team Member/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Access Requests/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Request to Admin/i })).not.toBeInTheDocument()

    // Must NOT render role select dropdowns or action buttons on other members
    expect(screen.queryByTitle(/Update member role/i)).not.toBeInTheDocument()
    expect(screen.queryByTitle(/Select all actionable members/i)).not.toBeInTheDocument()
  })

  it('Switching workspaces cannot reuse the previous workspace role (fails closed)', async () => {
    // 1. Initial render as ADMIN in workspace A
    useAuthStore.setState({
      user: {
        id: 'u-admin-2',
        email: 'ops_admin@example.com',
        role: 'ADMIN',
        workspace_id: mockWorkspaceId,
      } as any,
    })
    useWorkspaceStore.setState({
      currentWorkspace: {
        id: mockWorkspaceId,
      } as any,
    })

    const { rerender } = render(
      <MemoryRouter initialEntries={[`/workspaces/${mockWorkspaceId}/members`]}>
        <WorkspaceMembersPage />
      </MemoryRouter>
    )

    expect(screen.getByRole('button', { name: /Invite Team Member/i })).toBeInTheDocument()

    // 2. Switch workspace to workspace B where caller has no membership
    const foreignWorkspaceId = 'ws-foreign-workspace-999'
    useWorkspaceStore.setState({
      currentWorkspace: {
        id: foreignWorkspaceId,
      } as any,
    })
    useMemberStore.setState({
      members: [
        {
          id: 'm-other-user',
          workspace_id: foreignWorkspaceId,
          user_id: 'u-different-user',
          role: 'OWNER',
          status: 'ACTIVE',
          joined_at: '2026-09-01T10:00:00Z',
          user: {
            id: 'u-different-user',
            email: 'other@example.com',
          },
        },
      ] as any,
    })

    rerender(
      <MemoryRouter initialEntries={[`/workspaces/${foreignWorkspaceId}/members`]}>
        <WorkspaceMembersPage />
      </MemoryRouter>
    )

    // Previous workspace ADMIN role must NOT leak into the new workspace
    expect(screen.queryByRole('button', { name: /Invite Team Member/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Access Requests/i })).not.toBeInTheDocument()
  })

  it('Loading and unconfirmed membership states fail closed', async () => {
    useAuthStore.setState({
      user: {
        id: 'u-admin-2',
        email: 'ops_admin@example.com',
        role: 'ADMIN',
        workspace_id: mockWorkspaceId,
      } as any,
    })
    useMemberStore.setState({
      members: [],
      isLoading: true,
    })

    render(
      <BrowserRouter>
        <WorkspaceMembersPage />
      </BrowserRouter>
    )

    // While loading without confirmed membership, fail closed
    expect(screen.queryByRole('button', { name: /Invite Team Member/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Access Requests/i })).not.toBeInTheDocument()
  })

  it('matchMemberIdentity enforces foreign key preference and prohibits contradictory email collision or member PK confusion', () => {
    // 1. Foreign key user_id matches target user
    expect(
      matchMemberIdentity(
        { id: 'm-1', user_id: 'u-1', user: { id: 'u-1', email: 'u1@example.com' } } as any,
        { id: 'u-1', email: 'u1@example.com' }
      )
    ).toBe(true)

    // 2. Member row PK (m.id) must NEVER match user.id when user_ids differ
    expect(
      matchMemberIdentity(
        { id: 'u-target-id', user_id: 'u-different-id', user: { id: 'u-different-id' } } as any,
        { id: 'u-target-id' }
      )
    ).toBe(false)

    // 3. Contradictory user_id rejects email match (prevents cross-user email collision)
    expect(
      matchMemberIdentity(
        { id: 'm-2', user_id: 'u-2', user: { id: 'u-2', email: 'common@example.com' } } as any,
        { id: 'u-1', email: 'common@example.com' }
      )
    ).toBe(false)

    // 4. Stable user ID match succeeds even if email differs (e.g. email update in progress)
    expect(
      matchMemberIdentity(
        { id: 'm-3', user_id: 'u-1', user: { id: 'u-1', email: 'old@example.com' } } as any,
        { id: 'u-1', email: 'new@example.com' }
      )
    ).toBe(true)

    // 5. Case-insensitive email matches when member has no contradictory user_id
    expect(
      matchMemberIdentity(
        { id: 'm-4', user: { email: 'USER@example.COM' } } as any,
        { email: 'user@example.com' }
      )
    ).toBe(true)
  })

  // ── 9. WP-9.3 WORKSPACE SCOPING, CACHE REVALIDATION & CONCURRENCY TESTS ────

  it('Workspace A OWNER navigating to Workspace B cannot adopt OWNER privileges from stale store members', async () => {
    const workspaceA = 'ws-workspace-aaa'
    const workspaceB = 'ws-workspace-bbb'

    useAuthStore.setState({
      user: {
        id: 'u-owner-1',
        email: 'owner@example.com',
        role: 'MEMBER',
      } as any,
    })

    // Store intentionally still holds Workspace A members with caller as OWNER
    useMemberStore.setState({
      currentWorkspaceId: workspaceA,
      members: [
        {
          id: 'm-owner-1',
          workspace_id: workspaceA,
          user_id: 'u-owner-1',
          role: 'OWNER',
          status: 'ACTIVE',
          user: { id: 'u-owner-1', email: 'owner@example.com' },
        },
      ] as any,
      total: 1,
      isLoading: false,
    })

    useWorkspaceStore.setState({
      currentWorkspace: { id: workspaceB } as any,
    })

    render(
      <MemoryRouter initialEntries={[`/workspaces/${workspaceB}/members`]}>
        <WorkspaceMembersPage />
      </MemoryRouter>
    )

    // Stale Workspace A OWNER record must NOT grant OWNER in Workspace B
    expect(screen.queryByRole('button', { name: /Invite Team Member/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Access Requests/i })).not.toBeInTheDocument()
  })

  it('Workspace switching followed by an HTTP 403 fails closed and cannot acquire administrative controls', async () => {
    const workspaceB = 'ws-workspace-403'

    useAuthStore.setState({
      user: {
        id: 'u-user-unauth',
        email: 'unauth@example.com',
        role: 'MEMBER',
      } as any,
    })

    vi.spyOn(memberService, 'listMembers').mockRejectedValue({
      response: { status: 403, data: { detail: 'Forbidden' } },
    })

    useMemberStore.setState({
      members: [],
      total: 0,
      isLoading: false,
    })

    render(
      <MemoryRouter initialEntries={[`/workspaces/${workspaceB}/members`]}>
        <WorkspaceMembersPage />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Invite Team Member/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Access Requests/i })).not.toBeInTheDocument()
    })
  })

  it('Caller removal after initial render invalidates cached role and clears administrative affordances', async () => {
    useAuthStore.setState({
      user: {
        id: 'u-admin-2',
        email: 'ops_admin@example.com',
        role: 'MEMBER',
      } as any,
    })
    useWorkspaceStore.setState({
      currentWorkspace: { id: mockWorkspaceId } as any,
    })

    // Initial render with caller as active ADMIN in list
    const { rerender } = render(
      <MemoryRouter initialEntries={[`/workspaces/${mockWorkspaceId}/members`]}>
        <WorkspaceMembersPage />
      </MemoryRouter>
    )

    expect(screen.getByRole('button', { name: /Invite Team Member/i })).toBeInTheDocument()

    // Simulate backend removal: member list refreshes with only other member (caller removed)
    useMemberStore.setState({
      members: [mockMembers[0]] as any, // only lead_owner
      total: 1,
      isLoading: false,
    })

    rerender(
      <MemoryRouter initialEntries={[`/workspaces/${mockWorkspaceId}/members`]}>
        <WorkspaceMembersPage />
      </MemoryRouter>
    )

    // Stale cached admin role MUST be invalidated; affordances must disappear
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Invite Team Member/i })).not.toBeInTheDocument()
    })
  })

  it('Filtered or paginated results that legitimately omit caller preserve cached admin affordances', async () => {
    useAuthStore.setState({
      user: {
        id: 'u-admin-2',
        email: 'ops_admin@example.com',
        role: 'MEMBER',
      } as any,
    })
    useWorkspaceStore.setState({
      currentWorkspace: { id: mockWorkspaceId } as any,
    })

    const { rerender } = render(
      <MemoryRouter initialEntries={[`/workspaces/${mockWorkspaceId}/members`]}>
        <WorkspaceMembersPage />
      </MemoryRouter>
    )

    expect(screen.getByRole('button', { name: /Invite Team Member/i })).toBeInTheDocument()

    // Simulate filter search where caller row is omitted but total indicates partial/filtered
    const searchInput = screen.getByPlaceholderText(/Search members/i)
    fireEvent.change(searchInput, { target: { value: 'alice' } })

    useMemberStore.setState({
      members: [mockMembers[3]] as any, // only dev member
      total: 5, // total is 5, visible is 1 (partial)
    })

    rerender(
      <MemoryRouter initialEntries={[`/workspaces/${mockWorkspaceId}/members`]}>
        <WorkspaceMembersPage />
      </MemoryRouter>
    )

    // Admin affordance must be preserved while searching/filtering
    expect(screen.getByRole('button', { name: /Invite Team Member/i })).toBeInTheDocument()
  })

  it('Fallback lookup rejecting records with mismatched workspace ID fails closed', async () => {
    const workspaceId = 'ws-workspace-target'

    useAuthStore.setState({
      user: {
        id: 'u-attacker',
        email: 'attacker@example.com',
      } as any,
    })

    // Fallback query returns item with mismatched workspace_id
    vi.spyOn(memberService, 'listMembers').mockResolvedValue({
      items: [
        {
          id: 'm-foreign',
          workspace_id: 'ws-different-workspace',
          user_id: 'u-attacker',
          role: 'OWNER',
          status: 'ACTIVE',
          user: { id: 'u-attacker', email: 'attacker@example.com' },
        },
      ] as any,
      total: 1,
      page: 1,
      page_size: 50,
    })

    useMemberStore.setState({
      members: [mockMembers[0]] as any,
      total: 2, // partial, triggers fallback
      isLoading: false,
    })

    render(
      <MemoryRouter initialEntries={[`/workspaces/${workspaceId}/members`]}>
        <WorkspaceMembersPage />
      </MemoryRouter>
    )

    // Foreign workspace record must be rejected; no admin affordances
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Invite Team Member/i })).not.toBeInTheDocument()
    })
  })

  it('useMemberStore discards out-of-order search responses', async () => {
    useMemberStore.setState({ fetchMembers: originalFetchMembers })

    let resolveFirst: (value: any) => void
    let resolveSecond: (value: any) => void

    const p1 = new Promise(r => { resolveFirst = r })
    const p2 = new Promise(r => { resolveSecond = r })

    vi.spyOn(memberService, 'listMembers')
      .mockReturnValueOnce(p1 as any)
      .mockReturnValueOnce(p2 as any)

    const store = useMemberStore.getState()

    // Request 1: search = 'slow'
    const req1 = store.fetchMembers('ws-test', { search: 'slow' })
    // Request 2: search = 'fast'
    const req2 = store.fetchMembers('ws-test', { search: 'fast' })

    // Resolve Request 2 first with fast result
    resolveSecond!({
      items: [{ id: 'm-fast', workspace_id: 'ws-test', role: 'MEMBER', user: { id: 'u-fast' } }],
      total: 1,
    })
    await req2

    expect(useMemberStore.getState().members[0].id).toBe('m-fast')

    // Resolve Request 1 later with slow result (stale)
    resolveFirst!({
      items: [{ id: 'm-slow', workspace_id: 'ws-test', role: 'MEMBER', user: { id: 'u-slow' } }],
      total: 1,
    })
    await req1

    // Stale p1 result must NOT overwrite newer p2 result
    expect(useMemberStore.getState().members[0].id).toBe('m-fast')
  })

  it('Dynamically reflects role demotion and suspension without page reload', async () => {
    useAuthStore.setState({
      user: {
        id: 'u-admin-2',
        email: 'ops_admin@example.com',
      } as any,
    })
    useWorkspaceStore.setState({
      currentWorkspace: { id: mockWorkspaceId } as any,
    })

    const { rerender } = render(
      <MemoryRouter initialEntries={[`/workspaces/${mockWorkspaceId}/members`]}>
        <WorkspaceMembersPage />
      </MemoryRouter>
    )

    expect(screen.getByRole('button', { name: /Invite Team Member/i })).toBeInTheDocument()

    // 1. Demote to MEMBER
    const demotedMember = { ...mockMembers[1], role: 'MEMBER' }
    useMemberStore.setState({
      members: [mockMembers[0], demotedMember, mockMembers[2], mockMembers[3], mockMembers[4]] as any,
    })

    rerender(
      <MemoryRouter initialEntries={[`/workspaces/${mockWorkspaceId}/members`]}>
        <WorkspaceMembersPage />
      </MemoryRouter>
    )

    // Admin controls should be gone
    expect(screen.queryByRole('button', { name: /Invite Team Member/i })).not.toBeInTheDocument()

    // 2. Suspend member
    const suspendedMember = { ...demotedMember, status: 'SUSPENDED' }
    useMemberStore.setState({
      members: [mockMembers[0], suspendedMember, mockMembers[2], mockMembers[3], mockMembers[4]] as any,
    })

    rerender(
      <MemoryRouter initialEntries={[`/workspaces/${mockWorkspaceId}/members`]}>
        <WorkspaceMembersPage />
      </MemoryRouter>
    )

    // Warning banner should be rendered
    expect(screen.getByText(/Workspace Access Suspended:/i)).toBeInTheDocument()
  })

  it('matchMemberIdentity verifies workspace ID boundary when expectedWorkspaceId is provided', () => {
    const member = {
      id: 'm-1',
      workspace_id: 'ws-100',
      user_id: 'u-1',
      user: { id: 'u-1', email: 'u1@example.com' },
    } as any

    // Matches when workspace_id matches expectedWorkspaceId
    expect(matchMemberIdentity(member, { id: 'u-1' }, 'ws-100')).toBe(true)

    // Rejects when workspace_id differs from expectedWorkspaceId
    expect(matchMemberIdentity(member, { id: 'u-1' }, 'ws-200')).toBe(false)

    // Continues to work if expectedWorkspaceId is omitted (backward compatibility)
    expect(matchMemberIdentity(member, { id: 'u-1' })).toBe(true)
  })

  // ── 10. WP-9.3.2 STRICT WORKSPACE-ID VALIDATION & BOUNDARY ENFORCEMENT ─────

  it('WP-9.3.2 (1-3): matchMemberIdentity strictly rejects missing, null, empty, or mismatched workspace_id', () => {
    const validMember = {
      id: 'm-1',
      workspace_id: 'ws-100',
      user_id: 'u-1',
      user: { id: 'u-1', email: 'u1@example.com' },
    } as any

    // 1. Matches valid matching workspace ID
    expect(matchMemberIdentity(validMember, { id: 'u-1' }, 'ws-100')).toBe(true)

    // 2. Rejects mismatched workspace ID
    expect(matchMemberIdentity(validMember, { id: 'u-1' }, 'ws-200')).toBe(false)

    // 3. Rejects missing (undefined) workspace_id when expectedWorkspaceId is provided
    const missingWsMember = { id: 'm-2', user_id: 'u-1', user: { id: 'u-1', email: 'u1@example.com' } } as any
    expect(matchMemberIdentity(missingWsMember, { id: 'u-1' }, 'ws-100')).toBe(false)

    // 4. Rejects null workspace_id
    const nullWsMember = { id: 'm-3', workspace_id: null, user_id: 'u-1', user: { id: 'u-1', email: 'u1@example.com' } } as any
    expect(matchMemberIdentity(nullWsMember, { id: 'u-1' }, 'ws-100')).toBe(false)

    // 5. Rejects empty string workspace_id
    const emptyWsMember = { id: 'm-4', workspace_id: '', user_id: 'u-1', user: { id: 'u-1', email: 'u1@example.com' } } as any
    expect(matchMemberIdentity(emptyWsMember, { id: 'u-1' }, 'ws-100')).toBe(false)

    // 6. Rejects whitespace-only workspace_id
    const whitespaceWsMember = { id: 'm-5', workspace_id: '   ', user_id: 'u-1', user: { id: 'u-1', email: 'u1@example.com' } } as any
    expect(matchMemberIdentity(whitespaceWsMember, { id: 'u-1' }, 'ws-100')).toBe(false)

    // 7. Email fallback cannot bypass missing or mismatched workspace_id
    const emailOnlyMissingWs = { id: 'm-6', user: { email: 'u1@example.com' } } as any
    expect(matchMemberIdentity(emailOnlyMissingWs, { email: 'u1@example.com' }, 'ws-100')).toBe(false)
    const emailOnlyMismatchedWs = { id: 'm-7', workspace_id: 'ws-wrong', user: { email: 'u1@example.com' } } as any
    expect(matchMemberIdentity(emailOnlyMismatchedWs, { email: 'u1@example.com' }, 'ws-100')).toBe(false)

    // 8. Backward compatibility when expectedWorkspaceId is omitted
    expect(matchMemberIdentity(validMember, { id: 'u-1' })).toBe(true)
  })

  it('WP-9.3.2 (4): Malformed membership record without workspace_id cannot grant OWNER/ADMIN affordances through memberInList', () => {
    const targetWs = 'ws-strict-target'
    useAuthStore.setState({
      user: {
        id: 'u-caller-admin',
        email: 'caller@example.com',
        role: 'MEMBER',
      } as any,
    })
    useWorkspaceStore.setState({
      currentWorkspace: { id: targetWs } as any,
    })

    // Member in list has user_id matching caller and role ADMIN, but workspace_id is missing or undefined
    useMemberStore.setState({
      currentWorkspaceId: targetWs,
      members: [
        {
          id: 'm-malformed-1',
          // workspace_id intentionally omitted
          user_id: 'u-caller-admin',
          role: 'ADMIN',
          status: 'ACTIVE',
          user: { id: 'u-caller-admin', email: 'caller@example.com' },
        },
      ] as any,
      total: 1,
      isLoading: false,
    })

    render(
      <MemoryRouter initialEntries={[`/workspaces/${targetWs}/members`]}>
        <WorkspaceMembersPage />
      </MemoryRouter>
    )

    // Because workspace_id is missing, currentMember must fail closed: no administrative affordances
    expect(screen.queryByRole('button', { name: /Invite Team Member/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Access Requests/i })).not.toBeInTheDocument()
  })

  it('WP-9.3.2 (5): Malformed fallback response without matching workspace_id cannot grant OWNER/ADMIN affordances', async () => {
    const targetWs = 'ws-strict-fallback'
    useAuthStore.setState({
      user: {
        id: 'u-caller-admin',
        email: 'caller@example.com',
        role: 'MEMBER',
      } as any,
    })
    useWorkspaceStore.setState({
      currentWorkspace: { id: targetWs } as any,
    })

    // List in store is empty, triggering fallback query
    useMemberStore.setState({
      currentWorkspaceId: targetWs,
      members: [],
      total: 0,
      isLoading: false,
    })

    // Fallback search returns a member whose workspace_id is empty or null
    vi.spyOn(memberService, 'listMembers').mockResolvedValue({
      items: [
        {
          id: 'm-fallback-malformed',
          workspace_id: '',
          user_id: 'u-caller-admin',
          role: 'ADMIN',
          status: 'ACTIVE',
          user: { id: 'u-caller-admin', email: 'caller@example.com' },
        },
      ] as any,
      total: 1,
      page: 1,
      page_size: 5,
    })

    render(
      <MemoryRouter initialEntries={[`/workspaces/${targetWs}/members`]}>
        <WorkspaceMembersPage />
      </MemoryRouter>
    )

    // Fallback response with empty workspace_id must be rejected; affordances remain fail-closed
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Invite Team Member/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Access Requests/i })).not.toBeInTheDocument()
    })
  })

  it('WP-9.3.2 (6): Valid matching-workspace OWNER/ADMIN membership correctly grants affordances', () => {
    const targetWs = 'ws-valid-owner'
    useAuthStore.setState({
      user: {
        id: 'u-valid-owner',
        email: 'owner@example.com',
        role: 'MEMBER',
      } as any,
    })
    useWorkspaceStore.setState({
      currentWorkspace: { id: targetWs } as any,
    })

    useMemberStore.setState({
      currentWorkspaceId: targetWs,
      members: [
        {
          id: 'm-valid-1',
          workspace_id: targetWs,
          user_id: 'u-valid-owner',
          role: 'OWNER',
          status: 'ACTIVE',
          user: { id: 'u-valid-owner', email: 'owner@example.com' },
        },
      ] as any,
      total: 1,
      isLoading: false,
    })

    render(
      <MemoryRouter initialEntries={[`/workspaces/${targetWs}/members`]}>
        <WorkspaceMembersPage />
      </MemoryRouter>
    )

    // Valid OWNER in matching workspace receives admin affordances
    expect(screen.getByRole('button', { name: /Invite Team Member/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Access Requests/i })).toBeInTheDocument()
  })
})
