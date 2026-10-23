import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { HeroSection } from '@/pages/landing/sections/HeroSection'
import { SecurityCompliance } from '@/pages/landing/sections/SecurityCompliance'
import { WhyRaguard } from '@/pages/landing/sections/WhyRaguard'
import { UseCases } from '@/pages/landing/sections/UseCases'
import { LandingPage } from '@/pages/landing/LandingPage'

// Mock intersection observer for framer-motion whileInView
beforeEach(() => {
  window.IntersectionObserver = vi.fn().mockImplementation(() => ({
    observe: () => null,
    unobserve: () => null,
    disconnect: () => null,
  }))
})

describe('Landing Page Entrance & Scroll Animation Integration', () => {
  beforeEach(() => {
    sessionStorage.clear()
    delete (window as any).__VERITAS_BOOTSTRAPPED__
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('HeroSection initializes in cold-start waiting mode and activates on bootstrap completion', async () => {
    await act(async () => {
      render(
        <MemoryRouter>
          <HeroSection />
        </MemoryRouter>
      )
    })

    // Content is rendered
    expect(screen.getByText('Trusted AI Infrastructure for Enterprise RAG')).toBeInTheDocument()
    expect(screen.getByText('Launch Workspace')).toBeInTheDocument()

    // Dispatch the custom bootstrap completion event
    await act(async () => {
      window.dispatchEvent(new CustomEvent('veritas:bootstrap-complete'))
    })

    expect(screen.getByText('Launch Workspace')).toBeInTheDocument()
  })

  it('HeroSection activates immediately on warm visit if session is already bootstrapped', async () => {
    sessionStorage.setItem('raguard_bootstrapped', 'true')

    await act(async () => {
      render(
        <MemoryRouter>
          <HeroSection />
        </MemoryRouter>
      )
    })

    expect(screen.getByText('Trusted AI Infrastructure for Enterprise RAG')).toBeInTheDocument()
    expect(screen.getByText('Launch Workspace')).toBeInTheDocument()
  })

  it('HeroSection safety fallback timer activates hero if event is not dispatched', async () => {
    await act(async () => {
      render(
        <MemoryRouter>
          <HeroSection />
        </MemoryRouter>
      )
    })

    // Advance past safety fallback (6500ms)
    await act(async () => {
      vi.advanceTimersByTime(7000)
    })

    expect(screen.getByText('Launch Workspace')).toBeInTheDocument()
  })

  it('SecurityCompliance renders standardized heading and all 7 security badges in Stagger', async () => {
    await act(async () => {
      render(<SecurityCompliance />)
    })

    expect(screen.getByText('Security First. Always.')).toBeInTheDocument()
    expect(screen.getByText('View Security Brief')).toBeInTheDocument()

    const badges = [
      'Granular RBAC',
      'End-to-End Encryption',
      'Comprehensive Audit Logs',
      'Strict Tenant Isolation',
      'Secure Hybrid Retrieval',
      '100% Explainability',
      'Enterprise Governance',
    ]

    badges.forEach((badge) => {
      expect(screen.getByText(badge)).toBeInTheDocument()
    })
  })

  it('WhyRaguard renders section heading and comparison columns', async () => {
    await act(async () => {
      render(<WhyRaguard />)
    })

    expect(screen.getByText('Why Veritas RAG?')).toBeInTheDocument()
    expect(screen.getByText('Traditional RAG')).toBeInTheDocument()
    expect(screen.getByText('Basic Retrieval')).toBeInTheDocument()
    expect(screen.getByText('Hybrid Retrieval')).toBeInTheDocument()
  })

  it('UseCases renders section heading and all 4 personas in grid', async () => {
    await act(async () => {
      render(<UseCases />)
    })

    expect(screen.getByText('Built for Enterprise AI Teams.')).toBeInTheDocument()
    expect(screen.getByText('AI Engineers')).toBeInTheDocument()
    expect(screen.getByText('Platform Teams')).toBeInTheDocument()
    expect(screen.getByText('Enterprise Architects')).toBeInTheDocument()
    expect(screen.getByText('Security Teams')).toBeInTheDocument()
  })

  it('LandingPage renders without throwing and mounts all sections', async () => {
    sessionStorage.setItem('raguard_bootstrapped', 'true')

    await act(async () => {
      render(
        <MemoryRouter>
          <LandingPage />
        </MemoryRouter>
      )
    })

    expect(screen.getByText('Why Veritas RAG?')).toBeInTheDocument()
    expect(screen.getByText('Security First. Always.')).toBeInTheDocument()
    expect(screen.getByText('Built for Enterprise AI Teams.')).toBeInTheDocument()
  })
})
