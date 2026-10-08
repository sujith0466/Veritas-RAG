import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { SecuritySettings } from '@/pages/settings/SecuritySettings'
import { useAuthStore } from '@/stores/authStore'
import { authService } from '@/services/auth/authService'

const mockToast = vi.fn()
vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({ toast: mockToast }),
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('@/services/auth/authService', () => ({
  authService: {
    requestChangePasswordCode: vi.fn(),
    verifyChangePasswordCode: vi.fn(),
    completeChangePassword: vi.fn(),
    logout: vi.fn(),
  },
}))

describe('Workstream 3: Security Change Password 4-Step Wizard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.setState({
      user: {
        id: 'usr-sec-1',
        email: 'developer@veritas.rag',
        full_name: 'Security Engineer',
        role: 'MEMBER' as any,
      } as any,
      token: 'mock-jwt-token',
      status: 'AUTHENTICATED',
    })
  })

  it('never displays a Current Password field', () => {
    render(
      <MemoryRouter>
        <SecuritySettings />
      </MemoryRouter>
    )

    expect(screen.queryByLabelText(/Current Password/i)).not.toBeInTheDocument()
    expect(screen.queryByPlaceholderText(/current password/i)).not.toBeInTheDocument()
  })

  it('executes full 4-step wizard: request code -> enter 6-digit OTP -> set new password -> success and relogin', async () => {
    vi.mocked(authService.requestChangePasswordCode).mockResolvedValueOnce({
      message: 'Code sent',
    })
    vi.mocked(authService.verifyChangePasswordCode).mockResolvedValueOnce({
      change_token: 'ephemeral-change-token-xyz',
      expires_in_seconds: 900,
    })
    vi.mocked(authService.completeChangePassword).mockResolvedValueOnce({
      message: 'Password updated',
    })

    render(
      <MemoryRouter>
        <SecuritySettings />
      </MemoryRouter>
    )

    // Step 1: Request Security Code
    expect(screen.getByText('Change Password')).toBeInTheDocument()
    expect(screen.getByText(/Email Verification Required/i)).toBeInTheDocument()
    expect(screen.getByText(/d\*\*\*@veritas.rag/i)).toBeInTheDocument()

    const sendCodeBtn = screen.getByRole('button', { name: /Send Verification Code/i })
    fireEvent.click(sendCodeBtn)

    await waitFor(() => {
      expect(authService.requestChangePasswordCode).toHaveBeenCalledTimes(1)
    })

    // Step 2: Enter 6-digit OTP
    await waitFor(() => {
      expect(screen.getByText(/6-Digit Verification Code/i)).toBeInTheDocument()
    })

    const digitInputs = screen.getAllByRole('textbox')
    expect(digitInputs).toHaveLength(6)

    // Fill 6 digits: 1, 2, 3, 4, 5, 6
    digitInputs.forEach((input, idx) => {
      fireEvent.change(input, { target: { value: String(idx + 1) } })
    })

    const verifyBtn = screen.getByRole('button', { name: /Verify Code/i })
    fireEvent.click(verifyBtn)

    await waitFor(() => {
      expect(authService.verifyChangePasswordCode).toHaveBeenCalledWith('123456')
    })

    // Step 3: Set New Password
    await waitFor(() => {
      expect(screen.getByLabelText(/^New Password$/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/^Confirm New Password$/i)).toBeInTheDocument()
    })

    const newPwdInput = screen.getByLabelText(/^New Password$/i)
    const confirmPwdInput = screen.getByLabelText(/^Confirm New Password$/i)

    fireEvent.change(newPwdInput, { target: { value: 'CorrectHorseBatteryStaple123!' } })
    fireEvent.change(confirmPwdInput, { target: { value: 'CorrectHorseBatteryStaple123!' } })

    const updatePwdBtn = screen.getByRole('button', { name: /Update Password/i })
    fireEvent.click(updatePwdBtn)

    await waitFor(() => {
      expect(authService.completeChangePassword).toHaveBeenCalledWith(
        'ephemeral-change-token-xyz',
        'CorrectHorseBatteryStaple123!'
      )
    })

    // Step 4: Success card and Relogin redirect
    await waitFor(() => {
      expect(screen.getByText(/Password Changed Successfully/i)).toBeInTheDocument()
    })

    const reloginBtn = screen.getByRole('button', { name: /Log In With New Password/i })
    fireEvent.click(reloginBtn)

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/login')
    })
  })

  it('validates password mismatch and min length at Step 3', async () => {
    vi.mocked(authService.requestChangePasswordCode).mockResolvedValueOnce({
      message: 'Code sent',
    })
    vi.mocked(authService.verifyChangePasswordCode).mockResolvedValueOnce({
      change_token: 'token-abc',
      expires_in_seconds: 900,
    })

    render(
      <MemoryRouter>
        <SecuritySettings />
      </MemoryRouter>
    )

    // Advance to Step 2
    fireEvent.click(screen.getByRole('button', { name: /Send Verification Code/i }))
    await waitFor(() => expect(screen.getAllByRole('textbox')).toHaveLength(6))

    // Advance to Step 3
    screen.getAllByRole('textbox').forEach((input, idx) => {
      fireEvent.change(input, { target: { value: String(idx + 1) } })
    })
    fireEvent.click(screen.getByRole('button', { name: /Verify Code/i }))

    await waitFor(() => {
      expect(screen.getByLabelText(/^New Password$/i)).toBeInTheDocument()
    })

    const newPwdInput = screen.getByLabelText(/^New Password$/i)
    const confirmPwdInput = screen.getByLabelText(/^Confirm New Password$/i)

    // 1. Password mismatch
    fireEvent.change(newPwdInput, { target: { value: 'Password123!' } })
    fireEvent.change(confirmPwdInput, { target: { value: 'DifferentPassword123!' } })

    const updateBtn = screen.getByRole('button', { name: /Update Password/i })
    expect(updateBtn).toBeDisabled()

    // 2. Short password (< 8 chars)
    fireEvent.change(newPwdInput, { target: { value: 'short' } })
    fireEvent.change(confirmPwdInput, { target: { value: 'short' } })
    expect(updateBtn).toBeDisabled()
  })
})
