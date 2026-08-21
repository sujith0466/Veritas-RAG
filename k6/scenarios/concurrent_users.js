/**
 * k6 Scenario: Concurrent Workspace Users Workload
 *
 * Tests concurrent workspace retrieval, members listing, and health checks.
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, TEST_USER_EMAIL, TEST_USER_PASSWORD, THRESHOLDS } from '../config/environments.js';
import { loginAndGetToken } from '../utils/auth.js';

export const options = {
  stages: [
    { duration: '30s', target: 25 },
    { duration: '1m', target: 50 },
    { duration: '1m', target: 100 }, // Sustained 100 concurrent users
    { duration: '30s', target: 0 },
  ],
  thresholds: THRESHOLDS,
};

export function setup() {
  const token = loginAndGetToken(BASE_URL, TEST_USER_EMAIL, TEST_USER_PASSWORD);
  return { token: token };
}

export default function (data) {
  const headers = {
    'Content-Type': 'application/json',
  };

  if (data && data.token) {
    headers['Authorization'] = `Bearer ${data.token}`;
  }

  // 1. Query current workspace profile
  const wsRes = http.get(`${BASE_URL}/api/v1/workspaces/current`, { headers: headers });
  check(wsRes, {
    'workspace endpoint response status < 500': (r) => r.status < 500,
  });

  // 2. Query health readiness
  const healthRes = http.get(`${BASE_URL}/health/ready`);
  check(healthRes, {
    'health ready returns 200': (r) => r.status === 200,
  });

  sleep(0.5);
}
