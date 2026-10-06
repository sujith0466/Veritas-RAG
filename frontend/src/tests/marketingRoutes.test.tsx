import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Navbar } from '@/components/landing/Navbar'
import { Footer } from '@/components/landing/Footer'

beforeAll(() => {
  global.IntersectionObserver = class IntersectionObserver {
    readonly root: Element | Document | null = null
    readonly rootMargin: string = ''
    readonly thresholds: ReadonlyArray<number> = []
    observe = vi.fn()
    unobserve = vi.fn()
    disconnect = vi.fn()
    takeRecords = vi.fn().mockReturnValue([])
  } as any
})

// Mock stores
vi.mock('@/stores/authStore', () => ({
  useAuthStore: (selector: any) =>
    selector({
      status: 'ANONYMOUS',
      clearAuth: vi.fn(),
    }),
}))

describe('Marketing Navigation & Shell Verification', () => {
  describe('Navbar Header', () => {
    it('renders Launch Workspace CTA and DOES NOT render redundant Sign In', () => {
      render(
        <MemoryRouter>
          <Navbar />
        </MemoryRouter>
      )

      // 1. Confirm "Launch Workspace" is present
      const launchButtons = screen.getAllByRole('button', { name: /Launch Workspace/i })
      expect(launchButtons.length).toBeGreaterThan(0)

      // 2. Confirm "Sign In" is completely removed
      const signInBtn = screen.queryByRole('button', { name: /Sign In/i })
      expect(signInBtn).toBeNull()

      // 3. Confirm navigation links
      expect(screen.getByRole('link', { name: 'Platform' })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Security' })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Features' })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: 'Architecture' })).toBeInTheDocument()
    })
  })

  describe('Footer Links', () => {
    it('contains all 4 enterprise categories and zero dead hash links', () => {
      render(
        <MemoryRouter>
          <Footer />
        </MemoryRouter>
      )

      // Categories
      expect(screen.getByText('Platform')).toBeInTheDocument()
      expect(screen.getByText('Solutions')).toBeInTheDocument()
      expect(screen.getByText('Resources')).toBeInTheDocument()
      expect(screen.getByText('Company')).toBeInTheDocument()

      // Verify key links exist with valid routing paths
      const kiLink = screen.getByRole('link', { name: 'Knowledge Intelligence' })
      expect(kiLink).toHaveAttribute('href', '/platform/knowledge-intelligence')

      const hrLink = screen.getByRole('link', { name: 'Hybrid Retrieval' })
      expect(hrLink).toHaveAttribute('href', '/platform/hybrid-retrieval')

      const reLink = screen.getByRole('link', { name: 'Reliability Engine' })
      expect(reLink).toHaveAttribute('href', '/platform/reliability-engine')

      const secLink = screen.getByRole('link', { name: 'Enterprise Security' })
      expect(secLink).toHaveAttribute('href', '/platform/security')

      const finLink = screen.getByRole('link', { name: 'Financial Services' })
      expect(finLink).toHaveAttribute('href', '/solutions/financial-services')

      const docLink = screen.getByRole('link', { name: 'Documentation' })
      expect(docLink).toHaveAttribute('href', '/resources/documentation')

      const aboutLink = screen.getByRole('link', { name: 'About Us' })
      expect(aboutLink).toHaveAttribute('href', '/about')

      const privacyLink = screen.getByRole('link', { name: 'Privacy Policy' })
      expect(privacyLink).toHaveAttribute('href', '/privacy')

      // Verify bottom bar links
      expect(screen.getByRole('link', { name: 'Terms' })).toHaveAttribute('href', '/terms')
      expect(screen.getByRole('link', { name: 'Privacy' })).toHaveAttribute('href', '/privacy')
      expect(screen.getByRole('link', { name: 'Security' })).toHaveAttribute('href', '/security')

      // Verify NO link in the footer has href="#"
      const allLinks = screen.getAllByRole('link')
      allLinks.forEach((link) => {
        expect(link.getAttribute('href')).not.toBe('#')
      })
    })
  })
})
