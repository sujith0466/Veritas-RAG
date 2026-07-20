/**
 * API type definitions — mirror backend response envelope exactly.
 */

export interface ResponseMetadata {
  request_id: string
  timestamp: string
  version: string
  correlation_id?: string
}

export interface SuccessResponse<T> {
  success: true
  data: T
  metadata: ResponseMetadata
}

export interface ErrorDetail {
  code: string
  message: string
  detail?: Record<string, unknown>
  request_id: string
}

export interface ErrorResponse {
  success: false
  error: ErrorDetail
}

export type ApiResponse<T> = SuccessResponse<T> | ErrorResponse

export class ApiError extends Error {
  public readonly code: string
  public readonly status: number
  public readonly request_id: string
  public readonly detail?: Record<string, unknown>

  constructor(
    message: string,
    code: string,
    status: number,
    request_id: string,
    detail?: Record<string, unknown>,
  ) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.request_id = request_id
    this.detail = detail
  }

  isAuthError(): boolean {
    return this.status === 401 || this.status === 403
  }

  isNetworkError(): boolean {
    return this.status === 0 || this.status >= 500
  }

  isValidationError(): boolean {
    return this.status === 400 || this.status === 422
  }
}

export interface PaginationMeta {
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface PaginatedResponse<T> {
  items: T[]
  pagination: PaginationMeta
}
