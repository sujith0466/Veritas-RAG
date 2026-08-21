/**
 * k6 Scenario: Mixed Enterprise Realistic Workload
 *
 * Simulates a blended enterprise load profile:
 * - 50% Chat SSE streaming
 * - 25% Workspace & member browsing
 * - 15% Authentication & token lifecycle
 * - 10% Document ingestion uploads
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, TEST_USER_EMAIL, TEST_USER_PASSWORD, THRESHOLDS } from '../config/environments.js';
import { getRandomPrompt, generateDummyDocument } from '../config/payloads.js';
import { loginAndGetToken } from '../utils/auth.js';

export const options = {
  scenarios: {
    chat_users: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 25 },
        { duration: '2m', target: 50 },
        { duration: '30s', target: 0 },
      ],
      exec: 'chatWorkload',
    },
    browsing_users: {
      executor: 'constant-vus',
      vus: 25,
      duration: '3m',
      exec: 'browsingWorkload',
    },
    upload_users: {
      executor: 'constant-vus',
      vus: 10,
      duration: '3m',
      exec: 'uploadWorkload',
    },
  },
  thresholds: THRESHOLDS,
};

export function setup() {
  const token = loginAndGetToken(BASE_URL, TEST_USER_EMAIL, TEST_USER_PASSWORD);
  return { token: token };
}

export function chatWorkload(data) {
  const headers = {
    'Content-Type': 'application/json',
    'Accept': 'text/event-stream',
  };
  if (data && data.token) {
    headers['Authorization'] = `Bearer ${data.token}`;
  }

  const res = http.post(`${BASE_URL}/api/v1/chat/stream`, JSON.stringify({
    message: getRandomPrompt(),
    stream: true,
  }), { headers: headers, timeout: '30s' });

  check(res, { 'chat success': (r) => r.status < 500 });
  sleep(1);
}

export function browsingWorkload(data) {
  const headers = { 'Content-Type': 'application/json' };
  if (data && data.token) {
    headers['Authorization'] = `Bearer ${data.token}`;
  }

  const res = http.get(`${BASE_URL}/api/v1/workspaces/current`, { headers: headers });
  check(res, { 'browse success': (r) => r.status < 500 });
  sleep(0.5);
}

export function uploadWorkload(data) {
  const doc = generateDummyDocument(10);
  const headers = {};
  if (data && data.token) {
    headers['Authorization'] = `Bearer ${data.token}`;
  }

  const res = http.post(`${BASE_URL}/api/v1/documents/upload`, {
    file: http.file(doc.content, doc.filename, doc.mimeType),
  }, { headers: headers, timeout: '30s' });

  check(res, { 'upload success': (r) => r.status < 500 });
  sleep(3);
}
