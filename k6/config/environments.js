/**
 * RAGuard V2 k6 Load Testing Configuration
 *
 * All parameters are environment-driven via __ENV or fallback defaults.
 * Zero hardcoded secrets.
 */

export const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
export const TEST_USER_EMAIL = __ENV.TEST_USER_EMAIL || 'loadtest@example.com';
export const TEST_USER_PASSWORD = __ENV.TEST_USER_PASSWORD || 'LoadTestPassword123!';
export const TEST_WORKSPACE_ID = __ENV.TEST_WORKSPACE_ID || '00000000-0000-0000-0000-000000000001';

/**
 * Standard Performance SLO Thresholds (from Approved Architecture Plan)
 */
export const THRESHOLDS = {
  // HTTP status code success rate
  http_req_failed: ['rate<0.01'], // < 1% error rate
  // P95 / P99 Latency targets
  http_req_duration: ['p(95)<3000', 'p(99)<5000'], // P95 < 3s, P99 < 5s
};

export const AUTH_THRESHOLDS = {
  http_req_failed: ['rate<0.005'], // < 0.5% failure
  http_req_duration: ['p(95)<400', 'p(99)<800'], // Fast auth
};

export const CHAT_THRESHOLDS = {
  http_req_failed: ['rate<0.01'],
  http_req_duration: ['p(95)<3000', 'p(99)<5000'],
};
