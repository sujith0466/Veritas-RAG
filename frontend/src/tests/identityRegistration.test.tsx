import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { RegisterPage } from '@/pages/auth/RegisterPage'
import { IdentityRegisterForm } from '@/components/auth/AuthForms'

const mockRegister = vi.fn()

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({
    register: mockRegister,
    login: vi.fn(),
  }),
}))

vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}))

vi.mock('@/components/auth/GoogleAuthButton', () => ({
  GoogleAuthButton: () => <div data-testid="google-auth-button">Google Auth</div>,
}))

vi.mock('@/components/auth/PasswordStrength', () => ({
  PasswordStrength: () => <div data-testid="password-strength">Strength Meter</div>,
}))

vi.mock('@/components/auth/AuthBranding', () => ({
  AuthBranding: () => <div data-testid="auth-branding">Veritas Logo</div>,
}))

describe('T-02A: Identity-Only Registration Contract', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders registration form directly without role selector or role prompt', () => {
    render(
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    )

    // Asserts identity registration heading
    expect(screen.getByRole('heading', { name: /create your account/i })).toBeInTheDocument()

    // Asserts identity fields are rendered
    expect(screen.getByLabelText(/full name/i, { selector: 'input' })).toBeInTheDocument()
    expect(screen.getByLabelText(/email/i, { selector: 'input' })).toBeInTheDocument()
    expect(screen.getByLabelText(/^password$/i, { selector: 'input' })).toBeInTheDocument()
    expect(screen.getByLabelText(/^confirm password$/i, { selector: 'input' })).toBeInTheDocument()
    expect(screen.getByLabelText(/i accept the/i, { selector: 'input' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument()

    // Strictly verifies NO workspace name, company name, or invite code exists
    expect(screen.queryByLabelText(/workspace name/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/company/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/invitation code/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/invite code/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/choose your role/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/back to roles/i)).not.toBeInTheDocument()
  })

  it('submits identity-only payload to auth service without role, workspaceName, or inviteCode', async () => {
    mockRegister.mockResolvedValueOnce(undefined)

    render(
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    )

    fireEvent.change(screen.getByLabelText(/full name/i, { selector: 'input' }), { target: { value: 'Alice Morgan' } })
    fireEvent.change(screen.getByLabelText(/email/i, { selector: 'input' }), { target: { value: 'alice@example.com' } })
    fireEvent.change(screen.getByLabelText(/^password$/i, { selector: 'input' }), { target: { value: 'SecurePass123!' } })
    fireEvent.change(screen.getByLabelText(/^confirm password$/i, { selector: 'input' }), { target: { value: 'SecurePass123!' } })
    fireEvent.click(screen.getByLabelText(/i accept the/i, { selector: 'input' }))

    fireEvent.click(screen.getByRole('button', { name: /create account/i }))

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledTimes(1)
      expect(mockRegister).toHaveBeenCalledWith({
        email: 'alice@example.com',
        password: 'SecurePass123!',
        confirmPassword: 'SecurePass123!',
        fullName: 'Alice Morgan',
      })
    })

    // After success, displays email verification instruction
    await waitFor(() => {
      expect(screen.getByText(/check your email/i)).toBeInTheDocument()
      expect(screen.getByText(/sent a verification link to your email address/i)).toBeInTheDocument()
    })
  })

  it('rejects registration when password and confirm password do not match', async () => {
    render(
      <MemoryRouter>
        <IdentityRegisterForm onSuccess={vi.fn()} />
      </MemoryRouter>
    )

    fireEvent.change(screen.getByLabelText(/full name/i, { selector: 'input' }), { target: { value: 'Bob Smith' } })
    fireEvent.change(screen.getByLabelText(/email/i, { selector: 'input' }), { target: { value: 'bob@example.com' } })
    fireEvent.change(screen.getByLabelText(/^password$/i, { selector: 'input' }), { target: { value: 'SecurePass123!' } })
    fireEvent.change(screen.getByLabelText(/^confirm password$/i, { selector: 'input' }), { target: { value: 'MismatchPass999!' } })
    fireEvent.click(screen.getByLabelText(/i accept the/i, { selector: 'input' }))

    fireEvent.click(screen.getByRole('button', { name: /create account/i }))

    await waitFor(() => {
      expect(screen.getByText(/passwords don't match/i)).toBeInTheDocument()
    })
    expect(mockRegister).not.toHaveBeenCalled()
  })

  it('rejects registration when terms of service are not accepted', async () => {
    render(
      <MemoryRouter>
        <IdentityRegisterForm onSuccess={vi.fn()} />
      </MemoryRouter>
    )

    fireEvent.change(screen.getByLabelText(/full name/i, { selector: 'input' }), { target: { value: 'Charlie Brown' } })
    fireEvent.change(screen.getByLabelText(/email/i, { selector: 'input' }), { target: { value: 'charlie@example.com' } })
    fireEvent.change(screen.getByLabelText(/^password$/i, { selector: 'input' }), { target: { value: 'SecurePass123!' } })
    fireEvent.change(screen.getByLabelText(/^confirm password$/i, { selector: 'input' }), { target: { value: 'SecurePass123!' } })

    fireEvent.click(screen.getByRole('button', { name: /create account/i }))

    await waitFor(() => {
      expect(screen.getByText(/you must accept the terms/i)).toBeInTheDocument()
    })
    expect(mockRegister).not.toHaveBeenCalled()
  })

  it('Section 1.2: displays explanatory rejection notice banner and admin navigation button on regular registration', () => {
    render(
      <MemoryRouter initialEntries={['/auth/register']}>
        <RegisterPage />
      </MemoryRouter>
    )

    // Asserts clear explanatory notice banner is rendered
    expect(
      screen.getByText(/workspace creation is not supported through regular user registration/i)
    ).toBeInTheDocument()
    expect(
      screen.getByText(/regular registration creates an individual user identity only and cannot create or register a workspace/i)
    ).toBeInTheDocument()

    // Asserts navigation button to Admin Registration
    const adminLink = screen.getByRole('link', { name: /register as admin to create workspace/i })
    expect(adminLink).toBeInTheDocument()
    expect(adminLink).toHaveAttribute('href', '/auth/register?role=admin')

    // Asserts dedicated join workflow link
    const joinLink = screen.getByRole('link', { name: /joining an existing workspace\?/i })
    expect(joinLink).toBeInTheDocument()
    expect(joinLink).toHaveAttribute('href', '/workspaces/join')
  })

  it('Section 1.2: displays explanatory notice when accessed with role=viewer', () => {
    render(
      <MemoryRouter initialEntries={['/auth/register?role=viewer']}>
        <RegisterPage />
      </MemoryRouter>
    )

    expect(
      screen.getByText(/workspace creation is not supported through regular user registration/i)
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /register as admin to create workspace/i })
    ).toBeInTheDocument()
  })

  it('Section 1.2: renders admin registration heading and switch link when role=admin', () => {
    render(
      <MemoryRouter initialEntries={['/auth/register?role=admin']}>
        <RegisterPage />
      </MemoryRouter>
    )

    // Asserts admin registration title and badge
    expect(screen.getByRole('heading', { name: /create admin account/i })).toBeInTheDocument()
    expect(screen.getByText(/administrator registration/i)).toBeInTheDocument()
    expect(screen.getByText(/register your identity to provision a new workspace as an administrator/i)).toBeInTheDocument()

    // Rejection notice banner should NOT be rendered in admin registration mode
    expect(
      screen.queryByText(/workspace creation is not supported through regular user registration/i)
    ).not.toBeInTheDocument()

    // Asserts switch link to regular registration
    const regularLink = screen.getByRole('link', { name: /switch to regular registration/i })
    expect(regularLink).toBeInTheDocument()
    expect(regularLink).toHaveAttribute('href', '/auth/register')

    // Preserves identity-only contract (no client-supplied platform role or workspace name inputs)
    expect(screen.queryByLabelText(/workspace name/i)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument()
  })
})
