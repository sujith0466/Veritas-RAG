import type { AxiosRequestConfig } from 'axios'
import { apiClient } from './client'
import { ApiError } from '@/types'

/**
 * Type-safe request wrapper that enforces SuccessResponse<T> envelope handling.
 */
export async function request<T>(
  config: AxiosRequestConfig,
  signal?: AbortSignal,
): Promise<T> {
  let url = config.url
  if (url && url.startsWith('/api/v1')) {
    url = url.substring('/api/v1'.length)
  }
  const response = await apiClient.request<any>({
    ...config,
    url,
    signal,
  })

  if (response.data && response.data.success === false) {
    throw new ApiError(
      response.data.error?.message || 'Request failed',
      response.data.error?.code || 'ERROR',
      response.status,
      response.data.metadata?.request_id || 'unknown',
    )
  }

  if (response.data && typeof response.data === 'object' && 'data' in response.data && response.data.data !== undefined) {
    return response.data.data as T
  }

  return response.data as T
}

export async function get<T>(url: string, params?: Record<string, unknown>, signal?: AbortSignal): Promise<T> {
  return request<T>({ method: 'GET', url, params }, signal)
}

export async function post<T>(url: string, data?: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>({ method: 'POST', url, data }, signal)
}

export async function put<T>(url: string, data?: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>({ method: 'PUT', url, data }, signal)
}

export async function patch<T>(url: string, data?: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>({ method: 'PATCH', url, data }, signal)
}

export async function del<T>(url: string, data?: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>({ method: 'DELETE', url, data }, signal)
}
