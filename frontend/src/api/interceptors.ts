import type { InternalAxiosRequestConfig, AxiosResponse, AxiosError } from 'axios'
import { apiClient } from './client'
import { ApiError } from '@/types'
import type { ErrorResponse, SuccessResponse } from '@/types'
import { useAuthStore } from '@/stores/authStore'
import { authService } from '@/services/auth/authService'

// ─── Request Interceptor ──────────────────────────────────────────────────────

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Inject Authorization header from Zustand auth store
    const token = useAuthStore.getState().token
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    // Inject X-Correlation-ID for distributed tracing
    config.headers['X-Correlation-ID'] = crypto.randomUUID()

    return config
  },
  (error: unknown) => Promise.reject(error),
)

// ─── Response Interceptor ─────────────────────────────────────────────────────

let isRefreshing = false
let refreshQueue: Array<(token: string | null) => void> = []

function processRefreshQueue(token: string | null): void {
  refreshQueue.forEach((cb) => cb(token))
  refreshQueue = []
}

apiClient.interceptors.response.use(
  // Success: unwrap SuccessResponse<T> envelope
  (response: AxiosResponse<SuccessResponse<unknown>>) => response,

  // Error: map to ApiError and handle 401 refresh
  async (error: AxiosError<ErrorResponse>) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retried?: boolean }

    // Map API error response to ApiError
    if (error.response?.data?.error) {
      const { code, message, detail, request_id } = error.response.data.error
      const apiError = new ApiError(
        message,
        code,
        error.response.status,
        request_id ?? 'unknown',
        detail as Record<string, unknown> | undefined,
      )

      // Handle 401 — attempt token refresh (only once)
      if (error.response.status === 401 && !originalRequest._retried) {
        if (isRefreshing) {
          return new Promise<AxiosResponse>((resolve, reject) => {
            refreshQueue.push((newToken) => {
              if (!newToken) {
                reject(apiError)
                return
              }
              originalRequest.headers.Authorization = `Bearer ${newToken}`
              resolve(apiClient(originalRequest))
            })
          })
        }

        originalRequest._retried = true
        isRefreshing = true

        try {
          const newToken = await authService.refresh()
          
          const currentUser = useAuthStore.getState().user;
          if (currentUser) {
            useAuthStore.getState().setAuth(currentUser, newToken);
          }
          processRefreshQueue(newToken)
          originalRequest.headers.Authorization = `Bearer ${newToken}`
          return apiClient(originalRequest)
        } catch {
          processRefreshQueue(null)
          useAuthStore.getState().clearAuth()
          window.location.replace('/auth/login')
          return Promise.reject(apiError)
        } finally {
          isRefreshing = false
        }
      }

      return Promise.reject(apiError)
    }

    // Network / timeout error
    const networkError = new ApiError(
      error.message || 'Network error',
      'NETWORK_ERROR',
      0,
      'unknown',
    )
    return Promise.reject(networkError)
  },
)
