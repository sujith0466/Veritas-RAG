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
    changePassword: vi.fn(),
    requestChangePasswordCode: vi.fn(),
    verifyChangePasswordCode: vi.fn(),
    completeChangePassword: vi.fn(),
    logout: vi.fn(),
  },
}))

describe('Security Settings: Dual-Path In-Place Password Change (Phase 4)', () => {
  let localStorageSpy: any
  let sessionStorageSpy: any
  let consoleLogSpy: any
  let consoleInfoSpy: any

  beforeEach(() => {
    vi.clearAllMocks()

    localStorageSpy = vi.spyOn(Storage.prototype, 'setItem')
    sessionStorageSpy = vi.spyOn(sessionStorage, 'setItem')
    consoleLogSpy = vi.spyOn(console, 'log')
    consoleInfoSpy = vi.spyOn(console, 'info')

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

  // ═══════════════════════════════════════════════════════════════════════════
  // PATH A TESTS
  // ═══════════════════════════════════════════════════════════════════════════
  describe('Path A — User Knows Current Password', () => {
    it('1. Default state renders Current Password + New Password + Confirm Password', () => {
      render(
        <MemoryRouter>
          <SecuritySettings />
        </MemoryRouter>
      )

      expect(screen.getByRole('heading', { name: /^Change Password$/i })).toBeInTheDocument()
      expect(screen.getByLabelText(/^Current Password$/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/^New Password$/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/^Confirm New Password$/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /^Forgot Current Password\?$/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /^Change Password$/i })).toBeInTheDocument()
    })

    it('2, 3, 4. Successful Path A submission stays on Security Settings, does NOT navigate to login, and resets the form', async () => {
      vi.mocked(authService.changePassword).mockResolvedValueOnce({
        message: 'Password changed successfully.',
        access_token: 'new-rotated-jwt-token',
      })

      render(
        <MemoryRouter>
          <SecuritySettings />
        </MemoryRouter>
      )

      const currentInput = screen.getByLabelText(/^Current Password$/i)
      const newInput = screen.getByLabelText(/^New Password$/i)
      const confirmInput = screen.getByLabelText(/^Confirm New Password$/i)

      fireEvent.change(currentInput, { target: { value: 'OldPassword123!' } })
      fireEvent.change(newInput, { target: { value: 'NewSuperPassword456!' } })
      fireEvent.change(confirmInput, { target: { value: 'NewSuperPassword456!' } })

      const submitBtn = screen.getByRole('button', { name: /^Change Password$/i })
      expect(submitBtn).toBeEnabled()
      fireEvent.click(submitBtn)

      await waitFor(() => {
        expect(authService.changePassword).toHaveBeenCalledWith(
          'OldPassword123!',
          'NewSuperPassword456!'
        )
      })

      // In-place success alert rendered
      await waitFor(() => {
        expect(screen.getByText(/Password changed successfully/i)).toBeInTheDocument()
      })

      // Preserves session and updates rotated token in store
      expect(useAuthStore.getState().token).toBe('new-rotated-jwt-token')
      expect(useAuthStore.getState().status).toBe('AUTHENTICATED')

      // Form reset
      expect((currentInput as HTMLInputElement).value).toBe('')
      expect((newInput as HTMLInputElement).value).toBe('')
      expect((confirmInput as HTMLInputElement).value).toBe('')

      // ZERO navigation to login
      expect(mockNavigate).not.toHaveBeenCalled()
    })

    it('5. Invalid current password displays appropriate error', async () => {
      vi.mocked(authService.changePassword).mockRejectedValueOnce({
        response: {
          data: {
            detail: 'Incorrect current password.',
          },
        },
      })

      render(
        <MemoryRouter>
          <SecuritySettings />
        </MemoryRouter>
      )

      fireEvent.change(screen.getByLabelText(/^Current Password$/i), { target: { value: 'WrongCurrentPassword!' } })
      fireEvent.change(screen.getByLabelText(/^New Password$/i), { target: { value: 'ValidNewPassword123!' } })
      fireEvent.change(screen.getByLabelText(/^Confirm New Password$/i), { target: { value: 'ValidNewPassword123!' } })

      fireEvent.click(screen.getByRole('button', { name: /^Change Password$/i }))

      await waitFor(() => {
        expect(screen.getByText('Incorrect current password.')).toBeInTheDocument()
      })

      // Zero navigation to login
      expect(mockNavigate).not.toHaveBeenCalled()
    })

    it('6. Password validation errors (mismatch, too short, password reuse) are handled', () => {
      render(
        <MemoryRouter>
          <SecuritySettings />
        </MemoryRouter>
      )

      const currentInput = screen.getByLabelText(/^Current Password$/i)
      const newInput = screen.getByLabelText(/^New Password$/i)
      const confirmInput = screen.getByLabelText(/^Confirm New Password$/i)
      const submitBtn = screen.getByRole('button', { name: /^Change Password$/i })

      // Empty fields: button disabled
      expect(submitBtn).toBeDisabled()

      // Short password (< 8 chars): button disabled
      fireEvent.change(currentInput, { target: { value: 'CurrentPass123!' } })
      fireEvent.change(newInput, { target: { value: 'short' } })
      fireEvent.change(confirmInput, { target: { value: 'short' } })
      expect(submitBtn).toBeDisabled()

      // Mismatched passwords: button disabled
      fireEvent.change(newInput, { target: { value: 'ValidPassword123!' } })
      fireEvent.change(confirmInput, { target: { value: 'DifferentPassword456!' } })
      expect(submitBtn).toBeDisabled()

      // Password reuse (new === current): button disabled
      fireEvent.change(newInput, { target: { value: 'CurrentPass123!' } })
      fireEvent.change(confirmInput, { target: { value: 'CurrentPass123!' } })
      expect(submitBtn).toBeDisabled()
    })

    it('7. Duplicate submissions are prevented while loading', async () => {
      let resolvePromise: any
      const pendingPromise = new Promise<{ message: string; access_token: string }>((resolve) => {
        resolvePromise = resolve
      })
      vi.mocked(authService.changePassword).mockReturnValueOnce(pendingPromise)

      render(
        <MemoryRouter>
          <SecuritySettings />
        </MemoryRouter>
      )

      fireEvent.change(screen.getByLabelText(/^Current Password$/i), { target: { value: 'CurrentPass123!' } })
      fireEvent.change(screen.getByLabelText(/^New Password$/i), { target: { value: 'NewSuperPass456!' } })
      fireEvent.change(screen.getByLabelText(/^Confirm New Password$/i), { target: { value: 'NewSuperPass456!' } })

      const submitBtn = screen.getByRole('button', { name: /^Change Password$/i })
      fireEvent.click(submitBtn)

      // In-flight: button is disabled
      expect(submitBtn).toBeDisabled()
      expect(authService.changePassword).toHaveBeenCalledTimes(1)

      // Multiple clicks do not trigger additional calls
      fireEvent.click(submitBtn)
      expect(authService.changePassword).toHaveBeenCalledTimes(1)

      resolvePromise({ message: 'Password changed successfully.', access_token: 'new-token' })
      await waitFor(() => {
        expect(screen.getByText(/Password changed successfully/i)).toBeInTheDocument()
      })
    })
  })

  // ═══════════════════════════════════════════════════════════════════════════
  // PATH B TESTS
  // ═══════════════════════════════════════════════════════════════════════════
  describe('Path B — User Does Not Know Current Password', () => {
    it('8, 9. "Forgot Current Password?" switches to Path B and Current Password field is absent', () => {
      render(
        <MemoryRouter>
          <SecuritySettings />
        </MemoryRouter>
      )

      const forgotBtn = screen.getByRole('button', { name: /^Forgot Current Password\?$/i })
      fireEvent.click(forgotBtn)

      // Switches to Path B Step 1 in place
      expect(screen.getByText(/Authorize password change via a single-use email security code/i)).toBeInTheDocument()
      expect(screen.getByText(/Email Verification Required/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Send Verification Code/i })).toBeInTheDocument()

      // Current Password field must be ABSOLUTELY ABSENT
      expect(screen.queryByLabelText(/Current Password/i)).not.toBeInTheDocument()
      expect(screen.queryByPlaceholderText(/enter current password/i)).not.toBeInTheDocument()
    })

    it('Can switch back from Path B to Path A in place', () => {
      render(
        <MemoryRouter>
          <SecuritySettings />
        </MemoryRouter>
      )

      fireEvent.click(screen.getByRole('button', { name: /^Forgot Current Password\?$/i }))
      expect(screen.queryByLabelText(/Current Password/i)).not.toBeInTheDocument()

      const backBtn = screen.getByRole('button', { name: /Use Current Password/i })
      fireEvent.click(backBtn)

      // Restores Path A
      expect(screen.getByLabelText(/^Current Password$/i)).toBeInTheDocument()
    })

    it('10, 11, 12, 13, 14, 15. Executes complete Path B flow without login redirect', async () => {
      vi.mocked(authService.requestChangePasswordCode).mockResolvedValueOnce({
        message: 'Security code dispatched.',
      })
      vi.mocked(authService.verifyChangePasswordCode).mockResolvedValueOnce({
        change_token: 'ephemeral-change-token-xyz-987',
        expires_in_seconds: 900,
      })
      vi.mocked(authService.completeChangePassword).mockResolvedValueOnce({
        message: 'Password changed successfully.',
        access_token: 'new-path-b-access-token',
      })

      render(
        <MemoryRouter>
          <SecuritySettings />
        </MemoryRouter>
      )

      // 1. Switch to Path B
      fireEvent.click(screen.getByRole('button', { name: /^Forgot Current Password\?$/i }))

      // 2. Step 1: Send Security Code
      const sendCodeBtn = screen.getByRole('button', { name: /Send Verification Code/i })
      fireEvent.click(sendCodeBtn)

      await waitFor(() => {
        expect(authService.requestChangePasswordCode).toHaveBeenCalledTimes(1)
      })

      // 3. Step 2: 6-Digit Code entry appears (New password fields NOT visible yet)
      await waitFor(() => {
        expect(screen.getByText(/6-Digit Verification Code/i)).toBeInTheDocument()
      })
      expect(screen.queryByLabelText(/^New Password$/i)).not.toBeInTheDocument()

      const digitInputs = screen.getAllByRole('textbox')
      expect(digitInputs).toHaveLength(6)

      digitInputs.forEach((input, idx) => {
        fireEvent.change(input, { target: { value: String(idx + 1) } })
      })

      const verifyBtn = screen.getByRole('button', { name: /Verify Code/i })
      fireEvent.click(verifyBtn)

      await waitFor(() => {
        expect(authService.verifyChangePasswordCode).toHaveBeenCalledWith('123456')
      })

      // 4. Step 3: New Password fields appear (NO Current Password field!)
      await waitFor(() => {
        expect(screen.getByLabelText(/^New Password$/i)).toBeInTheDocument()
        expect(screen.getByLabelText(/^Confirm New Password$/i)).toBeInTheDocument()
      })
      expect(screen.queryByLabelText(/Current Password/i)).not.toBeInTheDocument()

      fireEvent.change(screen.getByLabelText(/^New Password$/i), { target: { value: 'NewPathBPassword999!' } })
      fireEvent.change(screen.getByLabelText(/^Confirm New Password$/i), { target: { value: 'NewPathBPassword999!' } })

      const changePwdBtn = screen.getByRole('button', { name: /^Change Password$/i })
      fireEvent.click(changePwdBtn)

      await waitFor(() => {
        expect(authService.completeChangePassword).toHaveBeenCalledWith(
          'ephemeral-change-token-xyz-987',
          'NewPathBPassword999!'
        )
      })

      // 5. Success in place: stays on Security Settings, updates token, does NOT redirect to login
      await waitFor(() => {
        expect(screen.getByText(/Password changed successfully/i)).toBeInTheDocument()
      })

      expect(useAuthStore.getState().token).toBe('new-path-b-access-token')
      expect(useAuthStore.getState().status).toBe('AUTHENTICATED')
      expect(mockNavigate).not.toHaveBeenCalled()

      // Resets back to default Path A view
      expect(screen.getByLabelText(/^Current Password$/i)).toBeInTheDocument()
    })

    it('16. Invalid or expired OTP is handled with error message', async () => {
      vi.mocked(authService.requestChangePasswordCode).mockResolvedValueOnce({ message: 'Code sent' })
      vi.mocked(authService.verifyChangePasswordCode).mockRejectedValueOnce({
        response: {
          data: {
            detail: 'Invalid or expired security code.',
          },
        },
      })

      render(
        <MemoryRouter>
          <SecuritySettings />
        </MemoryRouter>
      )

      fireEvent.click(screen.getByRole('button', { name: /^Forgot Current Password\?$/i }))
      fireEvent.click(screen.getByRole('button', { name: /Send Verification Code/i }))

      await waitFor(() => expect(screen.getAllByRole('textbox')).toHaveLength(6))

      screen.getAllByRole('textbox').forEach((input) => {
        fireEvent.change(input, { target: { value: '9' } })
      })

      fireEvent.click(screen.getByRole('button', { name: /Verify Code/i }))

      await waitFor(() => {
        expect(screen.getByText('Invalid or expired security code.')).toBeInTheDocument()
      })
      expect(mockNavigate).not.toHaveBeenCalled()
    })

    it('17. Expired or invalid change token is handled with error message', async () => {
      vi.mocked(authService.requestChangePasswordCode).mockResolvedValueOnce({ message: 'Code sent' })
      vi.mocked(authService.verifyChangePasswordCode).mockResolvedValueOnce({
        change_token: 'expired-token',
        expires_in_seconds: 900,
      })
      vi.mocked(authService.completeChangePassword).mockRejectedValueOnce({
        response: {
          data: {
            detail: 'Invalid, expired, or previously consumed credential',
          },
        },
      })

      render(
        <MemoryRouter>
          <SecuritySettings />
        </MemoryRouter>
      )

      fireEvent.click(screen.getByRole('button', { name: /^Forgot Current Password\?$/i }))
      fireEvent.click(screen.getByRole('button', { name: /Send Verification Code/i }))

      await waitFor(() => expect(screen.getAllByRole('textbox')).toHaveLength(6))
      screen.getAllByRole('textbox').forEach((input, i) => {
        fireEvent.change(input, { target: { value: String(i + 1) } })
      })
      fireEvent.click(screen.getByRole('button', { name: /Verify Code/i }))

      await waitFor(() => expect(screen.getByLabelText(/^New Password$/i)).toBeInTheDocument())

      fireEvent.change(screen.getByLabelText(/^New Password$/i), { target: { value: 'ValidPassword123!' } })
      fireEvent.change(screen.getByLabelText(/^Confirm New Password$/i), { target: { value: 'ValidPassword123!' } })
      fireEvent.click(screen.getByRole('button', { name: /^Change Password$/i }))

      await waitFor(() => {
        expect(screen.getByText('Invalid, expired, or previously consumed credential')).toBeInTheDocument()
      })
      expect(mockNavigate).not.toHaveBeenCalled()
    })

    it('18. Duplicate Path B submission is prevented while loading', async () => {
      vi.mocked(authService.requestChangePasswordCode).mockResolvedValueOnce({ message: 'Code sent' })
      vi.mocked(authService.verifyChangePasswordCode).mockResolvedValueOnce({
        change_token: 'token-xyz',
        expires_in_seconds: 900,
      })

      let resolvePromise: any
      const pendingPromise = new Promise<{ message: string; access_token: string }>((resolve) => {
        resolvePromise = resolve
      })
      vi.mocked(authService.completeChangePassword).mockReturnValueOnce(pendingPromise)

      render(
        <MemoryRouter>
          <SecuritySettings />
        </MemoryRouter>
      )

      fireEvent.click(screen.getByRole('button', { name: /^Forgot Current Password\?$/i }))
      fireEvent.click(screen.getByRole('button', { name: /Send Verification Code/i }))

      await waitFor(() => expect(screen.getAllByRole('textbox')).toHaveLength(6))
      screen.getAllByRole('textbox').forEach((input, i) => {
        fireEvent.change(input, { target: { value: String(i + 1) } })
      })
      fireEvent.click(screen.getByRole('button', { name: /Verify Code/i }))

      await waitFor(() => expect(screen.getByLabelText(/^New Password$/i)).toBeInTheDocument())
      fireEvent.change(screen.getByLabelText(/^New Password$/i), { target: { value: 'ValidPassword123!' } })
      fireEvent.change(screen.getByLabelText(/^Confirm New Password$/i), { target: { value: 'ValidPassword123!' } })

      const submitBtn = screen.getByRole('button', { name: /^Change Password$/i })
      fireEvent.click(submitBtn)

      expect(submitBtn).toBeDisabled()
      expect(authService.completeChangePassword).toHaveBeenCalledTimes(1)

      fireEvent.click(submitBtn)
      expect(authService.completeChangePassword).toHaveBeenCalledTimes(1)

      resolvePromise({ message: 'Password changed successfully.' })
      await waitFor(() => expect(screen.getByText(/Password changed successfully/i)).toBeInTheDocument())
    })
  })

  // ═══════════════════════════════════════════════════════════════════════════
  // SECURITY & PERSISTENCE INVARIANTS
  // ═══════════════════════════════════════════════════════════════════════════
  describe('Security & Zero-Secret Persistence Invariants', () => {
    it('19, 20. OTP and change token are never written to localStorage or sessionStorage', async () => {
      vi.mocked(authService.requestChangePasswordCode).mockResolvedValueOnce({ message: 'Code sent' })
      vi.mocked(authService.verifyChangePasswordCode).mockResolvedValueOnce({
        change_token: 'secret-change-token-never-persist',
        expires_in_seconds: 900,
      })
      vi.mocked(authService.completeChangePassword).mockResolvedValueOnce({
        message: 'Password changed successfully.',
        access_token: 'new-token',
      })

      render(
        <MemoryRouter>
          <SecuritySettings />
        </MemoryRouter>
      )

      fireEvent.click(screen.getByRole('button', { name: /^Forgot Current Password\?$/i }))
      fireEvent.click(screen.getByRole('button', { name: /Send Verification Code/i }))

      await waitFor(() => expect(screen.getAllByRole('textbox')).toHaveLength(6))
      screen.getAllByRole('textbox').forEach((input, i) => {
        fireEvent.change(input, { target: { value: String(i + 1) } })
      })
      fireEvent.click(screen.getByRole('button', { name: /Verify Code/i }))

      await waitFor(() => expect(screen.getByLabelText(/^New Password$/i)).toBeInTheDocument())
      fireEvent.change(screen.getByLabelText(/^New Password$/i), { target: { value: 'NewPassword123!' } })
      fireEvent.change(screen.getByLabelText(/^Confirm New Password$/i), { target: { value: 'NewPassword123!' } })
      fireEvent.click(screen.getByRole('button', { name: /^Change Password$/i }))

      await waitFor(() => expect(screen.getByText(/Password changed successfully/i)).toBeInTheDocument())

      // Verify localStorage was never called with OTP or change token
      const localCalls = localStorageSpy.mock.calls
      for (const [key, value] of localCalls) {
        expect(key).not.toMatch(/otp|change_token|changeToken|security_code/i)
        expect(value).not.toContain('secret-change-token-never-persist')
        expect(value).not.toContain('123456')
      }

      // Verify sessionStorage was never called
      const sessionCalls = sessionStorageSpy.mock.calls
      for (const [key, value] of sessionCalls) {
        expect(key).not.toMatch(/otp|change_token|changeToken|security_code/i)
        expect(value).not.toContain('secret-change-token-never-persist')
        expect(value).not.toContain('123456')
      }
    })

    it('21. OTP and change token are never placed in URL or navigation history', async () => {
      render(
        <MemoryRouter initialEntries={['/settings/security']}>
          <SecuritySettings />
        </MemoryRouter>
      )

      fireEvent.click(screen.getByRole('button', { name: /^Forgot Current Password\?$/i }))
      expect(mockNavigate).not.toHaveBeenCalled()
    })

    it('22, 23, 24. Passwords, OTP, and change tokens are never logged to console', async () => {
      vi.mocked(authService.changePassword).mockResolvedValueOnce({
        message: 'Password changed successfully.',
        access_token: 'new-token',
      })

      render(
        <MemoryRouter>
          <SecuritySettings />
        </MemoryRouter>
      )

      fireEvent.change(screen.getByLabelText(/^Current Password$/i), { target: { value: 'SecretOldPassword!' } })
      fireEvent.change(screen.getByLabelText(/^New Password$/i), { target: { value: 'SecretNewPassword!' } })
      fireEvent.change(screen.getByLabelText(/^Confirm New Password$/i), { target: { value: 'SecretNewPassword!' } })
      fireEvent.click(screen.getByRole('button', { name: /^Change Password$/i }))

      await waitFor(() => expect(screen.getByText(/Password changed successfully/i)).toBeInTheDocument())

      const logCalls = [...consoleLogSpy.mock.calls, ...consoleInfoSpy.mock.calls]
      for (const args of logCalls) {
        const text = args.map(String).join(' ')
        expect(text).not.toContain('SecretOldPassword!')
        expect(text).not.toContain('SecretNewPassword!')
      }
    })
  })
})
