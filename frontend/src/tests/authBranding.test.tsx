import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AuthBranding, AIAssistant } from '@/components/auth'

describe('AuthBranding Component', () => {
  it('renders primary logo and dark lockup by default (variant="logo")', () => {
    const { container } = render(<AuthBranding />)

    const branding = screen.getByTestId('auth-branding')
    expect(branding).toBeInTheDocument()

    // Light logo
    const lightImg = container.querySelector('img[src="/veritas-rag-logo.png"]')
    expect(lightImg).toBeInTheDocument()
    expect(lightImg).toHaveAttribute('alt', 'Veritas RAG')
    expect(lightImg?.className).toContain('dark:hidden')

    // Dark icon & typography
    const darkImg = container.querySelector('img[src="/veritas-rag-icon-dark.png"]')
    expect(darkImg).toBeInTheDocument()
    expect(darkImg).toHaveAttribute('alt', 'Veritas RAG')

    const darkWordmark = screen.getByText('Veritas RAG', { selector: 'span' })
    expect(darkWordmark).toBeInTheDocument()
  })

  it('renders compact app icons when variant="icon"', () => {
    const { container } = render(<AuthBranding variant="icon" />)

    // Light compact icon
    const lightIcon = container.querySelector('img[src="/veritas-rag-icon-light.png"]')
    expect(lightIcon).toBeInTheDocument()
    expect(lightIcon).toHaveAttribute('alt', 'Veritas RAG')
    expect(lightIcon?.className).toContain('dark:hidden')

    // Dark compact icon
    const darkIcon = container.querySelector('img[src="/veritas-rag-icon-dark.png"]')
    expect(darkIcon).toBeInTheDocument()
    expect(darkIcon).toHaveAttribute('alt', 'Veritas RAG')
    expect(darkIcon?.className).toContain('hidden dark:block')
  })

  it('preserves backward compatibility when imported as AIAssistant', () => {
    const { container } = render(<AIAssistant state="email_focus" />)

    const branding = screen.getByTestId('auth-branding')
    expect(branding).toBeInTheDocument()

    const lightImg = container.querySelector('img[src="/veritas-rag-logo.png"]')
    expect(lightImg).toBeInTheDocument()
  })

  it('reflects state modifiers (loading, error, success) gracefully', () => {
    const { rerender } = render(<AuthBranding state="loading" />)
    let branding = screen.getByTestId('auth-branding')
    expect(branding.className).toContain('animate-pulse')

    rerender(<AuthBranding state="error" />)
    branding = screen.getByTestId('auth-branding')
    expect(branding.className).toContain('ring-danger')

    rerender(<AuthBranding state="success" />)
    branding = screen.getByTestId('auth-branding')
    expect(branding.className).toContain('ring-success')

    rerender(<AuthBranding state="idle" />)
    branding = screen.getByTestId('auth-branding')
    expect(branding.className).not.toContain('animate-pulse')
  })
})
