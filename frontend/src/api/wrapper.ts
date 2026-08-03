import type { AxiosRequestConfig } from 'axios'
import { apiClient } from './client'
import { ApiError } from '@/types'
import type { SuccessResponse } from '@/types'

/**
 * Type-safe request wrapper that enforces SuccessResponse<T> envelope handling.
 */
export async function request<T>(
  config: AxiosRequestConfig,
  signal?: AbortSignal,
): Promise<T> {
  const response = await apiClient.request<SuccessResponse<T>>({
    ...config,
    signal,
  })

  if (!response.data.success) {
    throw new ApiError(
      'Unexpected response format',
      'PARSE_ERROR',
      500,
      'unknown',
    )
  }

  return response.data.data
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
