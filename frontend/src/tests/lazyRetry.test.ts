import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { isDynamicImportError, lazyRetry } from '../utils/lazyRetry'

describe('lazyRetry and isDynamicImportError', () => {
  const originalLocation = window.location

  beforeEach(() => {
    sessionStorage.clear()
    // Mock window.location.reload
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        ...originalLocation,
        reload: vi.fn(),
      },
    })
  })

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: originalLocation,
    })
  })

  it('correctly identifies dynamic import failure error messages', () => {
    expect(
      isDynamicImportError(
        new TypeError('Failed to fetch dynamically imported module: http://localhost:5173/assets/index-123.js')
      )
    ).toBe(true)

    expect(
      isDynamicImportError(new Error('error loading dynamically imported module'))
    ).toBe(true)

    expect(
      isDynamicImportError(new Error('Importing a module script failed.'))
    ).toBe(true)

    expect(
      isDynamicImportError(new Error('Loading chunk 42 failed.'))
    ).toBe(true)

    // Regular errors should not be classified as chunk load errors
    expect(isDynamicImportError(new Error('Cannot read properties of undefined'))).toBe(false)
    expect(isDynamicImportError(new Error('Network error on API /documents'))).toBe(false)
    expect(isDynamicImportError(null)).toBe(false)
  })

  it('triggers a controlled reload on chunk import failure when not previously reloaded', async () => {
    const failingImport = vi.fn().mockRejectedValue(
      new TypeError('Failed to fetch dynamically imported module: http://localhost:5173/assets/stale-chunk.js')
    )

    const LazyComp = lazyRetry(failingImport, 'TestComponent')
    
    // Invoke React.lazy loader function
    // @ts-expect-error React.lazy internals for testing
    const ctor = LazyComp._payload?._result || LazyComp._payload?._ctor
    if (typeof ctor === 'function') {
      ctor()
    } else {
      // @ts-expect-error React.lazy internals for testing
      LazyComp._init(LazyComp._payload)
    }

    // Allow microtasks/promises to resolve
    await new Promise((resolve) => setTimeout(resolve, 50))

    // Expect window.location.reload to be called
    expect(window.location.reload).toHaveBeenCalledTimes(1)
    expect(sessionStorage.getItem('raguard_chunk_reload_attempt')).toBeTruthy()
  })

  it('prevents infinite reload loops if chunk load fails again after a recent reload', async () => {
    // Simulate a recent reload 2 seconds ago
    sessionStorage.setItem('raguard_chunk_reload_attempt', String(Date.now() - 2000))

    const failingImport = vi.fn().mockRejectedValue(
      new TypeError('Failed to fetch dynamically imported module: http://localhost:5173/assets/stale-chunk.js')
    )

    const LazyComp = lazyRetry(failingImport, 'TestComponent')

    // @ts-expect-error React.lazy internals for testing
    const ctor = LazyComp._payload?._result || LazyComp._payload?._ctor
    let caughtError: unknown = null
    try {
      if (typeof ctor === 'function') {
        await ctor()
      } else {
        // @ts-expect-error React.lazy internals for testing
        await LazyComp._init(LazyComp._payload)
      }
    } catch (err) {
      caughtError = err
    }

    // Expect error to be thrown to ErrorBoundary without triggering another reload
    expect(caughtError).toBeInstanceOf(TypeError)
    expect(window.location.reload).not.toHaveBeenCalled()
  })
})
