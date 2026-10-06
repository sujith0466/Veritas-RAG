import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { LoginForm, AdminRegisterForm, UserRegisterForm } from '@/components/auth/AuthForms'

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

describe('Password Visibility Controls (UI Polish)', () => {
  describe('LoginForm', () => {
    it('initializes password field as hidden with closed eye control', () => {
      render(<LoginForm role="admin" onSuccess={vi.fn()} />)
      const passwordInput = screen.getByLabelText(/^Password/i) as HTMLInputElement
      expect(passwordInput.type).toBe('password')

      const toggleBtn = screen.getByRole('button', { name: /Show password/i })
      expect(toggleBtn).toBeInTheDocument()
    })

    it('toggles password visibility between text and password on click', () => {
      render(<LoginForm role="admin" onSuccess={vi.fn()} />)
      const passwordInput = screen.getByLabelText(/^Password/i) as HTMLInputElement
      const toggleBtn = screen.getByRole('button', { name: /Show password/i })

      // Click to reveal password
      fireEvent.click(toggleBtn)
      expect(passwordInput.type).toBe('text')
      expect(screen.getByRole('button', { name: /Hide password/i })).toBeInTheDocument()

      // Click to hide password again
      const hideBtn = screen.getByRole('button', { name: /Hide password/i })
      fireEvent.click(hideBtn)
      expect(passwordInput.type).toBe('password')
      expect(screen.getByRole('button', { name: /Show password/i })).toBeInTheDocument()
    })
  })

  describe('AdminRegisterForm', () => {
    it('has independent visibility toggles for password and confirmPassword', () => {
      render(<AdminRegisterForm onSuccess={vi.fn()} />)

      const passwordInput = screen.getByLabelText(/^Password/i) as HTMLInputElement
      const confirmPasswordInput = screen.getByLabelText(/^Confirm Password/i) as HTMLInputElement

      expect(passwordInput.type).toBe('password')
      expect(confirmPasswordInput.type).toBe('password')

      const passwordToggle = screen.getByRole('button', { name: 'Show password' })
      const confirmToggle = screen.getByRole('button', { name: 'Show confirm password' })

      // 1. Toggle Password only
      fireEvent.click(passwordToggle)
      expect(passwordInput.type).toBe('text')
      expect(confirmPasswordInput.type).toBe('password') // MUST REMAIN HIDDEN

      // 2. Toggle Confirm Password only
      fireEvent.click(confirmToggle)
      expect(passwordInput.type).toBe('text')
      expect(confirmPasswordInput.type).toBe('text') // BOTH VISIBLE

      // 3. Toggle Password back to hidden
      const passwordHideToggle = screen.getByRole('button', { name: 'Hide password' })
      fireEvent.click(passwordHideToggle)
      expect(passwordInput.type).toBe('password') // HIDDEN
      expect(confirmPasswordInput.type).toBe('text') // STILL VISIBLE

      // 4. Toggle Confirm Password back to hidden
      const confirmHideToggle = screen.getByRole('button', { name: 'Hide confirm password' })
      fireEvent.click(confirmHideToggle)
      expect(passwordInput.type).toBe('password')
      expect(confirmPasswordInput.type).toBe('password')
    })
  })

  describe('UserRegisterForm', () => {
    it('has independent visibility toggles for password and confirmPassword', () => {
      render(<UserRegisterForm onSuccess={vi.fn()} />)

      const passwordInput = screen.getByLabelText(/^Password/i) as HTMLInputElement
      const confirmPasswordInput = screen.getByLabelText(/^Confirm Password/i) as HTMLInputElement

      expect(passwordInput.type).toBe('password')
      expect(confirmPasswordInput.type).toBe('password')

      const passwordToggle = screen.getByRole('button', { name: 'Show password' })
      const confirmToggle = screen.getByRole('button', { name: 'Show confirm password' })

      // Toggle Confirm Password first
      fireEvent.click(confirmToggle)
      expect(passwordInput.type).toBe('password')
      expect(confirmPasswordInput.type).toBe('text')

      // Toggle Password
      fireEvent.click(passwordToggle)
      expect(passwordInput.type).toBe('text')
      expect(confirmPasswordInput.type).toBe('text')
    })
  })
})
