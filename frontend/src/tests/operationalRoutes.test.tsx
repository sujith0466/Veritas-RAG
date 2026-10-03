import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import { LegacyAnalyticsRedirect, LegacyDiagnosticsRedirect, LegacyHealthRedirect } from '../routes'

function LocationDisplay() {
  const location = useLocation()
  return <div data-testid="location-display">{location.pathname}{location.search}</div>
}

describe('Operational Routes & Legacy Compatibility (UNIT-OPS-02)', () => {
  describe('LegacyAnalyticsRedirect', () => {
    it('redirects /analytics to /reliability?tab=overview when no tab is provided', () => {
      render(
        <MemoryRouter initialEntries={['/analytics']}>
          <Routes>
            <Route path="/analytics" element={<LegacyAnalyticsRedirect />} />
            <Route path="/reliability" element={<LocationDisplay />} />
          </Routes>
        </MemoryRouter>
      )

      expect(screen.getByTestId('location-display')).toHaveTextContent('/reliability?tab=overview')
    })

    it('preserves existing query parameters while adding default tab=overview', () => {
      render(
        <MemoryRouter initialEntries={['/analytics?time=7d&mode=deep']}>
          <Routes>
            <Route path="/analytics" element={<LegacyAnalyticsRedirect />} />
            <Route path="/reliability" element={<LocationDisplay />} />
          </Routes>
        </MemoryRouter>
      )

      const display = screen.getByTestId('location-display').textContent
      expect(display).toContain('/reliability?')
      expect(display).toContain('time=7d')
      expect(display).toContain('mode=deep')
      expect(display).toContain('tab=overview')
    })

    it('retains specified tab parameter if already present', () => {
      render(
        <MemoryRouter initialEntries={['/analytics?tab=performance']}>
          <Routes>
            <Route path="/analytics" element={<LegacyAnalyticsRedirect />} />
            <Route path="/reliability" element={<LocationDisplay />} />
          </Routes>
        </MemoryRouter>
      )

      expect(screen.getByTestId('location-display')).toHaveTextContent('/reliability?tab=performance')
    })
  })

  describe('LegacyDiagnosticsRedirect', () => {
    it('redirects /diagnostics to /reliability?tab=explorer by default', () => {
      render(
        <MemoryRouter initialEntries={['/diagnostics']}>
          <Routes>
            <Route path="/diagnostics" element={<LegacyDiagnosticsRedirect />} />
            <Route path="/reliability" element={<LocationDisplay />} />
          </Routes>
        </MemoryRouter>
      )

      expect(screen.getByTestId('location-display')).toHaveTextContent('/reliability?tab=explorer')
    })

    it('preserves existing query parameters such as traceId or query_id', () => {
      render(
        <MemoryRouter initialEntries={['/diagnostics?query_id=query-1234']}>
          <Routes>
            <Route path="/diagnostics" element={<LegacyDiagnosticsRedirect />} />
            <Route path="/reliability" element={<LocationDisplay />} />
          </Routes>
        </MemoryRouter>
      )

      const display = screen.getByTestId('location-display').textContent
      expect(display).toContain('/reliability?')
      expect(display).toContain('query_id=query-1234')
      expect(display).toContain('tab=explorer')
    })
  })

  describe('LegacyHealthRedirect', () => {
    it('redirects /health to /knowledge-health without query string if none present', () => {
      render(
        <MemoryRouter initialEntries={['/health']}>
          <Routes>
            <Route path="/health" element={<LegacyHealthRedirect />} />
            <Route path="/knowledge-health" element={<LocationDisplay />} />
          </Routes>
        </MemoryRouter>
      )

      expect(screen.getByTestId('location-display')).toHaveTextContent('/knowledge-health')
    })

    it('preserves query parameters during redirect to /knowledge-health', () => {
      render(
        <MemoryRouter initialEntries={['/health?refresh=true&filter=degraded']}>
          <Routes>
            <Route path="/health" element={<LegacyHealthRedirect />} />
            <Route path="/knowledge-health" element={<LocationDisplay />} />
          </Routes>
        </MemoryRouter>
      )

      expect(screen.getByTestId('location-display')).toHaveTextContent('/knowledge-health?refresh=true&filter=degraded')
    })
  })
})
