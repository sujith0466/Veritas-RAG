import { request } from './wrapper'
import type { AxiosRequestConfig } from 'axios'

const MAX_RETRIES = 2
const BASE_DELAY_MS = 1000

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * Executes a GET request with automatic exponential backoff retry.
 * Only retries on network errors (status 0) or 503/504 errors.
 */
export async function fetchWithRetry<T>(
  url: string,
  params?: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<T> {
  const config: AxiosRequestConfig = { method: 'GET', url, params }

  let attempt = 0
  while (attempt <= MAX_RETRIES) {
    try {
      return await request<T>(config, signal)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } catch (error: any) {
      const isRetryable =
        error.isNetworkError?.() ||
        error.status === 503 ||
        error.status === 504 ||
        error.code === 'ECONNABORTED'

      if (!isRetryable || attempt === MAX_RETRIES) {
        throw error
      }

      attempt++
      const backoffMs = BASE_DELAY_MS * Math.pow(2, attempt - 1)
      await delay(backoffMs)
    }
  }

  throw new Error('Unreachable')
}
