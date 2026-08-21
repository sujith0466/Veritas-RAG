/**
 * k6 Scenario: Chat SSE Streaming Concurrency Workload
 *
 * Tests concurrent Server-Sent Events (SSE) streaming connections and first-token latency.
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, TEST_USER_EMAIL, TEST_USER_PASSWORD, CHAT_THRESHOLDS } from '../config/environments.js';
import { getRandomPrompt } from '../config/payloads.js';
import { loginAndGetToken } from '../utils/auth.js';

export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '1m', target: 30 },
    { duration: '1m', target: 50 }, // 50 concurrent SSE streams
    { duration: '30s', target: 0 },
  ],
  thresholds: CHAT_THRESHOLDS,
};

export function setup() {
  const token = loginAndGetToken(BASE_URL, TEST_USER_EMAIL, TEST_USER_PASSWORD);
  return { token: token };
}

export default function (data) {
  const url = `${BASE_URL}/api/v1/chat/stream`;
  const prompt = getRandomPrompt();

  const payload = JSON.stringify({
    message: prompt,
    stream: true,
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    },
    timeout: '30s',
  };

  if (data && data.token) {
    params.headers['Authorization'] = `Bearer ${data.token}`;
  }

  const res = http.post(url, payload, params);

  check(res, {
    'chat stream status is 200 or accepted': (r) => r.status === 200 || r.status === 202,
    'response has stream or text body': (r) => r.body && r.body.length > 0,
  });

  sleep(1);
}
