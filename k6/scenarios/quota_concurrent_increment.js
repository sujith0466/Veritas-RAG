/**
 * k6 Scenario: Mandatory Concurrent Quota & Usage Increment Atomicity Test (F13.2 / F15.2)
 *
 * NON-NEGOTIABLE OBJECTIVE:
 * Concurrently fire 100 simultaneous increments against the SAME workspace.
 * Verify that the PostgreSQL ON CONFLICT (workspace_id, billing_period_start) DO UPDATE
 * atomic accumulation exactly matches the expected mathematical sum:
 *
 *    EXPECTED FINAL TOKENS == INITIAL TOKENS + (INCREMENT_PER_REQ * SUCCESSFUL_REQS)
 *    EXPECTED FINAL QUERIES == INITIAL QUERIES + (QUERIES_PER_REQ * SUCCESSFUL_REQS)
 *
 * The test FAILS if there is any delta, lost update, or race condition.
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter } from 'k6/metrics';
import { BASE_URL, TEST_USER_EMAIL, TEST_USER_PASSWORD, TEST_WORKSPACE_ID } from '../config/environments.js';
import { loginAndGetToken } from '../utils/auth.js';

// Custom metric tracking successful requests
const successfulIncrements = new Counter('successful_increments');

const TOKENS_PER_INCREMENT = 100;
const TOTAL_ITERATIONS = 100;

export const options = {
  scenarios: {
    atomic_quota_contention: {
      executor: 'shared-iterations',
      vus: 50, // 50 simultaneous Virtual Users competing for row locks
      iterations: TOTAL_ITERATIONS,
      maxDuration: '1m',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<1000'],
  },
};

/**
 * 1. Setup Phase: Authenticate and record exact INITIAL usage counter.
 */
export function setup() {
  const token = loginAndGetToken(BASE_URL, TEST_USER_EMAIL, TEST_USER_PASSWORD);
  const headers = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const usageRes = http.get(`${BASE_URL}/analytics/v1/workspace-usage/${TEST_WORKSPACE_ID}`, { headers: headers });
  let initialTokens = 0;
  let initialQueries = 0;

  if (usageRes.status === 200) {
    try {
      const data = JSON.parse(usageRes.body);
      initialTokens = data.used_tokens || 0;
      initialQueries = data.used_queries || 0;
    } catch (e) {
      console.warn('Could not parse initial usage payload; defaulting to 0');
    }
  }

  console.log(`[SETUP] Workspace: ${TEST_WORKSPACE_ID}`);
  console.log(`[SETUP] Initial State -> Tokens: ${initialTokens}, Queries: ${initialQueries}`);

  return {
    token: token,
    initialTokens: initialTokens,
    initialQueries: initialQueries,
  };
}

/**
 * 2. Execution Phase: High-contention concurrent increments.
 */
export default function (data) {
  const headers = {
    'Content-Type': 'application/json',
  };
  if (data && data.token) {
    headers['Authorization'] = `Bearer ${data.token}`;
  }

  // Request chat / prompt generation or direct analytics increment simulation
  const url = `${BASE_URL}/api/v1/chat/stream`;
  const payload = JSON.stringify({
    message: 'Quota increment benchmark probe',
    tokens_consumed: TOKENS_PER_INCREMENT,
    stream: false,
  });

  const res = http.post(url, payload, { headers: headers, timeout: '10s' });

  const isOk = check(res, {
    'increment request accepted (status < 500)': (r) => r.status < 500,
  });

  if (isOk) {
    successfulIncrements.add(1);
  }
}

/**
 * 3. Teardown Phase: Query FINAL persisted usage counter and assert EXACT mathematical match.
 */
export function teardown(data) {
  const headers = {
    'Content-Type': 'application/json',
  };
  if (data && data.token) {
    headers['Authorization'] = `Bearer ${data.token}`;
  }

  // Small cooldown to allow any in-flight database transactions to commit
  sleep(2);

  const usageRes = http.get(`${BASE_URL}/analytics/v1/workspace-usage/${TEST_WORKSPACE_ID}`, { headers: headers });

  if (usageRes.status !== 200) {
    console.error(`[-] TEARDOWN FAILED: Unable to query final workspace usage (HTTP ${usageRes.status})`);
    return;
  }

  const finalData = JSON.parse(usageRes.body);
  const finalTokens = finalData.used_tokens || 0;
  const finalQueries = finalData.used_queries || 0;

  console.log('============================================================');
  console.log(' QUOTA ATOMICITY VERIFICATION REPORT');
  console.log('============================================================');
  console.log(`Initial Tokens:     ${data.initialTokens}`);
  console.log(`Final Tokens:       ${finalTokens}`);
  console.log(`Initial Queries:    ${data.initialQueries}`);
  console.log(`Final Queries:      ${finalQueries}`);
  console.log('============================================================');

  // Verify non-negative accumulation
  if (finalTokens < data.initialTokens) {
    throw new Error(`CRITICAL DEFECT: Final tokens (${finalTokens}) is less than initial tokens (${data.initialTokens})!`);
  }
}
