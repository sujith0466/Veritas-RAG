import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Navbar } from '@/components/landing/Navbar'
import { Sidebar } from '@/components/navigation/Sidebar'
import { WhyRaguard } from '@/pages/landing/sections/WhyRaguard'

// Mock intersection observer for framer-motion whileInView
beforeEach(() => {
  window.IntersectionObserver = vi.fn().mockImplementation(() => ({
    observe: () => null,
    unobserve: () => null,
    disconnect: () => null,
  }))
})

describe('Brand Identity Integration & Navigation', () => {
  it('Navbar renders authentic Veritas RAG brand icon assets and accessible home link', () => {
    const { container } = render(
      <MemoryRouter>
        <Navbar />
      </MemoryRouter>
    )

    const homeLink = screen.getByRole('link', { name: /Veritas RAG Home/i })
    expect(homeLink).toBeInTheDocument()

    // Light icon (hidden in dark mode)
    const lightIcon = container.querySelector('img[src="/veritas-rag-icon-light.png"]')
    expect(lightIcon).toBeInTheDocument()
    expect(lightIcon?.className).toContain('dark:hidden')

    // Dark icon (visible only in dark mode)
    const darkIcon = container.querySelector('img[src="/veritas-rag-icon-dark.png"]')
    expect(darkIcon).toBeInTheDocument()
    expect(darkIcon?.className).toContain('hidden dark:block')

    // Brand text
    expect(screen.getByText('Veritas')).toBeInTheDocument()
    expect(screen.getByText('RAG')).toBeInTheDocument()
  })

  it('Sidebar renders authentic brand assets and links to public landing page (/)', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Sidebar />
      </MemoryRouter>
    )

    const brandLink = screen.getByRole('link', { name: /Veritas RAG Home/i })
    expect(brandLink).toBeInTheDocument()
    expect(brandLink).toHaveAttribute('href', '/')

    // Light and Dark brand icons
    const lightIcon = container.querySelector('img[src="/veritas-rag-icon-light.png"]')
    expect(lightIcon).toBeInTheDocument()
    expect(lightIcon?.className).toContain('dark:hidden')

    const darkIcon = container.querySelector('img[src="/veritas-rag-icon-dark.png"]')
    expect(darkIcon).toBeInTheDocument()
    expect(darkIcon?.className).toContain('hidden dark:block')

    // Brand wordmark
    expect(screen.getByText('Veritas RAG')).toBeInTheDocument()
  })
})

describe('Why Veritas RAG? Flagship Comparison Section', () => {
  it('renders kicker, headings, and both comparative surfaces with all 6 capabilities', () => {
    render(<WhyRaguard />)

    // Category Kicker & Headings
    expect(screen.getByText('The Reliability Advantage')).toBeInTheDocument()
    expect(screen.getByText('Why Veritas RAG?')).toBeInTheDocument()
    expect(
      screen.getByText('Differentiate your infrastructure with enterprise-grade reliability.')
    ).toBeInTheDocument()

    // Column Headings & Badges
    expect(screen.getByText('Legacy Architecture')).toBeInTheDocument()
    expect(screen.getByText('Traditional RAG')).toBeInTheDocument()
    expect(screen.getByText('Enterprise Reliability Standard')).toBeInTheDocument()
    expect(screen.getByText('Veritas RAG')).toBeInTheDocument()

    // 6 Semantic Comparison Rows
    const comparisons = [
      { trad: 'Basic Retrieval', veritas: 'Hybrid Retrieval', highlight: 'Dense + BM25 Fusion' },
      { trad: 'Generic Responses', veritas: 'Grounded Responses', highlight: 'Zero-Hallucination Guard' },
      { trad: 'Limited Explainability', veritas: 'Source Attribution', highlight: 'Cryptographic Lineage' },
      { trad: 'Static Pipelines', veritas: 'Reflection Engine', highlight: 'Self-Correcting Loops' },
      { trad: 'Minimal Monitoring', veritas: 'Reliability Dashboard', highlight: 'Live Telemetry & SLOs' },
      { trad: 'Basic Security', veritas: 'Enterprise RBAC & Audit Logs', highlight: 'Strict Multi-Tenancy' },
    ]

    for (const comp of comparisons) {
      expect(screen.getByText(comp.trad)).toBeInTheDocument()
      expect(screen.getByText(comp.veritas)).toBeInTheDocument()
      expect(screen.getByText(comp.highlight)).toBeInTheDocument()
    }

    // Architectural badges
    expect(screen.getByText('Self-Correcting Architecture')).toBeInTheDocument()
    expect(screen.getByText('100% Provenance & Attribution')).toBeInTheDocument()
  })
})
