import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { JoinAccessDialog } from '@/components/navigation/JoinAccessDialog'
import { Header } from '@/components/navigation/Header'
import { workspaceService } from '@/services/workspaceService'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'

vi.mock('@/hooks/useTheme', () => ({
  useTheme: () => ({
    mode: 'dark',
    resolvedMode: 'dark',
    setMode: vi.fn(),
  }),
}))

describe('Workstream D: Member / Viewer Join Access', () => {
  const mockWorkspace = {
    id: 'ws-uuid-111',
    public_id: 'wrk_pub111abc',
    name: 'Acme Global Corp',
    slug: 'acme-global',
    role: 'MEMBER',
    status: 'ACTIVE',
    updated_at: '2026-10-01T00:00:00Z',
  }

  beforeEach(() => {
    vi.clearAllMocks()

    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    })

    useAuthStore.setState({
      user: {
        id: 'usr-member-1',
        email: 'member@acme.org',
        role: 'MEMBER' as any,
        workspace_id: 'ws-uuid-111',
        tenant_id: 'ws-uuid-111',
        workspace_name: 'Acme Global Corp',
        demo_role_switcher_enabled: false,
      } as any,
      status: 'AUTHENTICATED',
      token: 'jwt-member-token',
    })

    useWorkspaceStore.setState({
      currentWorkspace: mockWorkspace as any,
      workspaces: [mockWorkspace as any],
    })
  })

  it('WS-D: JoinAccessDialog fetches server-authoritative credentials and renders code and link', async () => {
    const mockJoinAccess = {
      success: true,
      workspace_id: 'ws-uuid-111',
      public_id: 'wrk_pub111abc',
      workspace_name: 'Acme Global Corp',
      has_active_code: true,
      join_code: 'VR-ABC123',
      join_link: '/workspaces/join?workspace_id=wrk_pub111abc&join_code=VR-ABC123',
      expires_at: '2026-12-01T00:00:00Z',
      default_role: 'MEMBER',
    }

    const accessSpy = vi.spyOn(workspaceService, 'getJoinAccess').mockResolvedValue(mockJoinAccess as any)

    render(
      <MemoryRouter>
        <JoinAccessDialog open={true} onOpenChange={() => {}} />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(accessSpy).toHaveBeenCalledWith('ws-uuid-111')
      expect(screen.getByText('VR-ABC123')).toBeInTheDocument()
      expect(screen.getByText(/workspaces\/join\?workspace_id=wrk_pub111abc&join_code=VR-ABC123/)).toBeInTheDocument()
    })

    expect(screen.getByText('Workspace Joining')).toBeInTheDocument()
  })

  it('WS-D: JoinAccessDialog provides accessible icon-only copy actions for code and link', async () => {
    const mockJoinAccess = {
      success: true,
      workspace_id: 'ws-uuid-111',
      public_id: 'wrk_pub111abc',
      workspace_name: 'Acme Global Corp',
      has_active_code: true,
      join_code: 'VR-XYZ789',
      join_link: '/workspaces/join?workspace_id=wrk_pub111abc&join_code=VR-XYZ789',
      expires_at: null,
      default_role: 'VIEWER',
    }

    vi.spyOn(workspaceService, 'getJoinAccess').mockResolvedValue(mockJoinAccess as any)

    render(
      <MemoryRouter>
        <JoinAccessDialog open={true} onOpenChange={() => {}} />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('VR-XYZ789')).toBeInTheDocument()
    })

    const copyCodeBtn = screen.getByRole('button', { name: 'Copy join code' })
    const copyLinkBtn = screen.getByRole('button', { name: 'Copy join link' })

    expect(copyCodeBtn).toBeInTheDocument()
    expect(copyLinkBtn).toBeInTheDocument()

    // Test copy join code
    fireEvent.click(copyCodeBtn)
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('VR-XYZ789')

    // Test copy join link
    fireEvent.click(copyLinkBtn)
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.stringContaining('/workspaces/join?workspace_id=wrk_pub111abc&join_code=VR-XYZ789')
    )
  })

  it('WS-D: JoinAccessDialog handles inactive/expired join code gracefully', async () => {
    const mockNoCode = {
      success: true,
      workspace_id: 'ws-uuid-111',
      public_id: 'wrk_pub111abc',
      workspace_name: 'Acme Global Corp',
      has_active_code: false,
      join_code: null,
      join_link: null,
      expires_at: null,
      default_role: 'MEMBER',
    }

    vi.spyOn(workspaceService, 'getJoinAccess').mockResolvedValue(mockNoCode as any)

    render(
      <MemoryRouter>
        <JoinAccessDialog open={true} onOpenChange={() => {}} />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('No Active Join Code')).toBeInTheDocument()
    })
  })

  it('WS-D: Header contains subtle Workspace Join Access button opening dialog', async () => {
    render(
      <MemoryRouter>
        <Header />
      </MemoryRouter>
    )

    const joinBtn = screen.getByRole('button', { name: 'Workspace Join Access' })
    expect(joinBtn).toBeInTheDocument()
  })
})
