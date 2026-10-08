import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { LoginForm } from '@/components/auth/AuthForms'
import { ForgotPasswordPage } from '@/pages/auth/ForgotPasswordPage'
import { authService } from '@/services/auth/authService'

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({
    login: vi.fn(),
    register: vi.fn(),
  }),
}))

vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}))

vi.mock('@/components/auth/GoogleAuthButton', () => ({
  GoogleAuthButton: () => <div data-testid="google-auth-button" />,
}))

vi.mock('@/components/auth/PasswordStrength', () => ({
  PasswordStrength: () => <div data-testid="password-strength" />,
}))

vi.mock('@/services/auth/authService', () => ({
  authService: {
    requestRecoveryCode: vi.fn(),
    verifyRecoveryCode: vi.fn(),
    completePasswordReset: vi.fn(),
  },
}))

describe('Password Recovery Workflow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders Forgot Password link in LoginForm pointing to /auth/forgot-password', () => {
    render(
      <MemoryRouter>
        <LoginForm role="viewer" onSuccess={vi.fn()} />
      </MemoryRouter>
    )

    const forgotLink = screen.getByRole('link', { name: /Forgot Password\?/i })
    expect(forgotLink).toBeInTheDocument()
    expect(forgotLink.getAttribute('href')).toBe('/auth/forgot-password')
  })

  it('progresses from Step 1 (Email) through Step 4 (Success) smoothly', async () => {
    const mockRequest = vi.mocked(authService.requestRecoveryCode)
    const mockVerify = vi.mocked(authService.verifyRecoveryCode)
    const mockComplete = vi.mocked(authService.completePasswordReset)

    mockRequest.mockResolvedValueOnce({ message: 'Code dispatched' })
    mockVerify.mockResolvedValueOnce({ reset_token: 'fake_ephemeral_token_123', expires_in_seconds: 900 })
    mockComplete.mockResolvedValueOnce({ message: 'Password reset successful' })

    render(
      <MemoryRouter>
        <ForgotPasswordPage />
      </MemoryRouter>
    )

    // Step 1: Email Entry
    expect(screen.getByRole('heading', { name: /Reset your password/i })).toBeInTheDocument()
    const emailInput = screen.getByLabelText(/Email address/i)
    fireEvent.change(emailInput, { target: { value: 'user@veritas.rag' } })

    const sendCodeBtn = screen.getByRole('button', { name: /Send Recovery Code/i })
    fireEvent.click(sendCodeBtn)

    await waitFor(() => {
      expect(mockRequest).toHaveBeenCalledWith('user@veritas.rag')
    })

    // Step 2: 6-Digit OTP Entry
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Enter verification code/i })).toBeInTheDocument()
    })
    expect(screen.getByText(/u\*\*\*@veritas.rag/i)).toBeInTheDocument()

    const digitInputs = screen.getAllByRole('textbox')
    expect(digitInputs.length).toBe(6)

    // Type 6 digits: 4 8 1 9 2 0
    const testDigits = ['4', '8', '1', '9', '2', '0']
    testDigits.forEach((digit, idx) => {
      fireEvent.change(digitInputs[idx], { target: { value: digit } })
    })

    const verifyBtn = screen.getByRole('button', { name: /Verify Code/i })
    fireEvent.click(verifyBtn)

    await waitFor(() => {
      expect(mockVerify).toHaveBeenCalledWith('user@veritas.rag', '481920')
    })

    // Step 3: Set New Password
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Set new password/i })).toBeInTheDocument()
    })

    const newPasswordInput = screen.getByLabelText(/^New password/i)
    const confirmPasswordInput = screen.getByLabelText(/^Confirm password/i)

    fireEvent.change(newPasswordInput, { target: { value: 'NewSecurePassword123!' } })
    fireEvent.change(confirmPasswordInput, { target: { value: 'NewSecurePassword123!' } })

    const resetBtn = screen.getByRole('button', { name: /Reset Password/i })
    fireEvent.click(resetBtn)

    await waitFor(() => {
      expect(mockComplete).toHaveBeenCalledWith(
        'user@veritas.rag',
        'fake_ephemeral_token_123',
        'NewSecurePassword123!'
      )
    })

    // Step 4: Success confirmation
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Password Reset Complete/i })).toBeInTheDocument()
    })
    expect(screen.getByText(/All previous active sessions have been revoked/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Proceed to Login/i })).toBeInTheDocument()
  })

  it('displays error banner if verification code is invalid', async () => {
    const mockRequest = vi.mocked(authService.requestRecoveryCode)
    const mockVerify = vi.mocked(authService.verifyRecoveryCode)

    mockRequest.mockResolvedValueOnce({ message: 'Code dispatched' })
    mockVerify.mockRejectedValueOnce(new Error('Invalid or expired verification code.'))

    render(
      <MemoryRouter>
        <ForgotPasswordPage />
      </MemoryRouter>
    )

    // Enter email
    fireEvent.change(screen.getByLabelText(/Email address/i), { target: { value: 'user@veritas.rag' } })
    fireEvent.click(screen.getByRole('button', { name: /Send Recovery Code/i }))

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Enter verification code/i })).toBeInTheDocument()
    })

    // Enter wrong 6 digits
    const digitInputs = screen.getAllByRole('textbox')
    ;['0', '0', '0', '0', '0', '0'].forEach((digit, idx) => {
      fireEvent.change(digitInputs[idx], { target: { value: digit } })
    })

    fireEvent.click(screen.getByRole('button', { name: /Verify Code/i }))

    await waitFor(() => {
      expect(screen.getByText(/Invalid or expired verification code\./i)).toBeInTheDocument()
    })
  })
})
