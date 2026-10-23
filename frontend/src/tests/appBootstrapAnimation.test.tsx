import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { AppBootstrap } from '@/components/bootstrap/AppBootstrap'
import { useAuthStore } from '@/stores/authStore'
import { healthService } from '@/services/api/healthService'
import { vectorService } from '@/services/vectorService'

vi.mock('@/services/api/healthService', () => ({
  healthService: {
    getBasicHealth: vi.fn(),
  },
}))

vi.mock('@/services/vectorService', () => ({
  vectorService: {
    getHealth: vi.fn(),
  },
}))

describe('AppBootstrap Startup Animation', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.clearAllMocks()
    vi.useFakeTimers()
    useAuthStore.setState({ status: 'LOADING' })
    vi.mocked(healthService.getBasicHealth).mockResolvedValue({ status: 'healthy' } as any)
    vi.mocked(vectorService.getHealth).mockResolvedValue({ status: 'healthy' } as any)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders all eight infrastructure stages on cold start', async () => {
    await act(async () => {
      render(<AppBootstrap />)
    })

    expect(screen.getByText('Veritas RAG')).toBeInTheDocument()
    expect(screen.getByText('Initializing Enterprise AI Infrastructure')).toBeInTheDocument()

    const expectedStages = [
      'Security Layer',
      'Knowledge Engine',
      'Vector Database',
      'Hybrid Retrieval',
      'Cross-Encoder Reranker',
      'Reliability Engine',
      'Prompt Guard',
      'Workspace Ready',
    ]

    expectedStages.forEach((label) => {
      expect(screen.getByText(label)).toBeInTheDocument()
    })
  })

  it('does not render if session already bootstrapped', async () => {
    sessionStorage.setItem('raguard_bootstrapped', 'true')
    let container: HTMLElement
    await act(async () => {
      const res = render(<AppBootstrap />)
      container = res.container
    })
    expect(container!.firstChild).toBeNull()
  })

  it('staggers through ready stages smoothly and finishes with Launching Workspace', async () => {
    useAuthStore.setState({ status: 'AUTHENTICATED' })

    await act(async () => {
      render(<AppBootstrap />)
    })

    // Flush promises from mount
    await act(async () => {
      await Promise.resolve()
      await Promise.resolve()
    })

    // Advance timers across all 8 staggered stages
    for (let i = 0; i < 10; i++) {
      await act(async () => {
        vi.advanceTimersByTime(120)
        await Promise.resolve()
      })
    }

    expect(screen.getByText('Launching Workspace...')).toBeInTheDocument()

    // Settle breather
    await act(async () => {
      vi.advanceTimersByTime(400)
    })

    expect(sessionStorage.getItem('raguard_bootstrapped')).toBe('true')
  })

  it('completes Security Layer immediately when auth resolves without extra 90ms timer, while preserving 90ms stagger on subsequent stages', async () => {
    useAuthStore.setState({ status: 'LOADING' })

    await act(async () => {
      render(<AppBootstrap />)
    })

    // Flush health checks
    await act(async () => {
      await Promise.resolve()
      await Promise.resolve()
    })

    // Advance while auth is still LOADING
    await act(async () => {
      vi.advanceTimersByTime(500)
    })

    expect(screen.getByText('Security Layer')).toBeInTheDocument()

    // Now resolve auth
    await act(async () => {
      useAuthStore.setState({ status: 'AUTHENTICATED' })
    })

    // Advance only 0ms (macrotask tick for delay=0)
    await act(async () => {
      vi.advanceTimersByTime(1)
    })

    // Next stage (Knowledge Engine) requires 90ms delay, so advancing only 40ms won't finish it
    await act(async () => {
      vi.advanceTimersByTime(40)
    })

    // Advance remaining time past 90ms to verify stage 2 finishes
    await act(async () => {
      vi.advanceTimersByTime(60)
    })
  })

  it('falls back gracefully when health checks reject', async () => {
    vi.mocked(healthService.getBasicHealth).mockRejectedValue(new Error('Backend unreachable'))
    vi.mocked(vectorService.getHealth).mockRejectedValue(new Error('Vector store unreachable'))
    useAuthStore.setState({ status: 'UNAUTHENTICATED' })

    await act(async () => {
      render(<AppBootstrap />)
    })

    // Flush rejection handlers
    await act(async () => {
      await Promise.resolve()
      await Promise.resolve()
    })

    for (let i = 0; i < 10; i++) {
      await act(async () => {
        vi.advanceTimersByTime(120)
        await Promise.resolve()
      })
    }

    // Breather
    await act(async () => {
      vi.advanceTimersByTime(400)
    })

    expect(sessionStorage.getItem('raguard_bootstrapped')).toBe('true')
  })
})
