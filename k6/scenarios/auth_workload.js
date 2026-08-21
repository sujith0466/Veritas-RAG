/**
 * k6 Scenario: Authentication & Session Workload
 *
 * Tests concurrent login and session token generation.
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, TEST_USER_EMAIL, TEST_USER_PASSWORD, AUTH_THRESHOLDS } from '../config/environments.js';

export const options = {
  stages: [
    { duration: '30s', target: 20 },  // Ramp-up to 20 users
    { duration: '1m', target: 50 },   // Ramp-up to 50 concurrent logins
    { duration: '30s', target: 100 },  // Peak 100 concurrent logins
    { duration: '30s', target: 0 },    // Ramp-down
  ],
  thresholds: AUTH_THRESHOLDS,
};

export default function () {
  const loginUrl = `${BASE_URL}/api/v1/auth/login`;
  const payload = JSON.stringify({
    email: TEST_USER_EMAIL,
    password: TEST_USER_PASSWORD,
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
  };

  const res = http.post(loginUrl, payload, params);

  check(res, {
    'login returns 200': (r) => r.status === 200,
    'jwt token returned': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body && body.data && !!body.data.access_token;
      } catch (e) {
        return false;
      }
    },
  });

  sleep(1);
}
