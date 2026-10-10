import { describe, it, expect } from 'vitest'
import { ApiError } from '@/types'

describe('WP-1: ApiError and HTTP Status Classification', () => {
  it('correctly classifies HTTP 502 Bad Gateway as gateway error', () => {
    const err = new ApiError('Bad Gateway', 'GATEWAY_ERROR', 502, 'req-502')
    expect(err.status).toBe(502)
    expect(err.code).toBe('GATEWAY_ERROR')
    expect(err.isGatewayError()).toBe(true)
    expect(err.isNetworkError()).toBe(true)
    expect(err.isAuthError()).toBe(false)
  })

  it('correctly classifies HTTP 503 and 504 as gateway errors', () => {
    const err503 = new ApiError('Service Unavailable', 'SERVICE_UNAVAILABLE', 503, 'req-503')
    expect(err503.status).toBe(503)
    expect(err503.isGatewayError()).toBe(true)
    expect(err503.isNetworkError()).toBe(true)

    const err504 = new ApiError('Gateway Timeout', 'GATEWAY_TIMEOUT', 504, 'req-504')
    expect(err504.status).toBe(504)
    expect(err504.isGatewayError()).toBe(true)
    expect(err504.isNetworkError()).toBe(true)
  })

  it('correctly classifies HTTP 401 as auth error', () => {
    const err401 = new ApiError('Authentication required', 'UNAUTHORIZED', 401, 'req-401')
    expect(err401.status).toBe(401)
    expect(err401.isAuthError()).toBe(true)
    expect(err401.isGatewayError()).toBe(false)
  })

  it('correctly classifies transport connection failure with status 0', () => {
    const err0 = new ApiError('Network Error', 'NETWORK_ERROR', 0, 'req-0')
    expect(err0.status).toBe(0)
    expect(err0.isNetworkError()).toBe(true)
    expect(err0.isGatewayError()).toBe(false)
    expect(err0.isAuthError()).toBe(false)
  })
})
