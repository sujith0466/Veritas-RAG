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
      config.headers.set('Authorization', `Bearer ${token}`)
    }

    // Inject X-Correlation-ID for distributed tracing
    config.headers.set('X-Correlation-ID', crypto.randomUUID())

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

      if (error.response.status === 401 && originalRequest.url?.includes('/auth/refresh')) {
        processRefreshQueue(null)
        useAuthStore.getState().clearAuth()
        return Promise.reject(apiError)
      }

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
          return Promise.reject(apiError)
        } finally {
          isRefreshing = false
        }
      }

      return Promise.reject(apiError)
    }

    // Response returned without structured JSON error envelope (e.g. Nginx 502/503/504 HTML, 401 basic, timeout)
    const status = error.response ? error.response.status : 0
    let code = 'NETWORK_ERROR'
    let message = error.message || 'Network error'

    if (status === 502) {
      code = 'GATEWAY_ERROR'
      message = 'Bad Gateway: Backend server is starting up or temporarily unreachable'
    } else if (status === 503) {
      code = 'SERVICE_UNAVAILABLE'
      message = 'Service Unavailable: Backend is temporarily overloaded'
    } else if (status === 504) {
      code = 'GATEWAY_TIMEOUT'
      message = 'Gateway Timeout: Upstream server took too long to respond'
    } else if (status === 401) {
      code = 'UNAUTHORIZED'
      message = 'Authentication required'
    }

    const networkError = new ApiError(
      message,
      code,
      status,
      'unknown',
    )
    return Promise.reject(networkError)
  },
)
