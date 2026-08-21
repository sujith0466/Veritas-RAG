/**
 * k6 Scenario: Document Upload Throughput Workload
 *
 * Tests single and multi-part document ingestion under concurrency.
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, TEST_USER_EMAIL, TEST_USER_PASSWORD, THRESHOLDS } from '../config/environments.js';
import { generateDummyDocument } from '../config/payloads.js';
import { loginAndGetToken } from '../utils/auth.js';

export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '1m', target: 25 },
    { duration: '1m', target: 50 }, // 50 concurrent uploads
    { duration: '30s', target: 0 },
  ],
  thresholds: THRESHOLDS,
};

export function setup() {
  const token = loginAndGetToken(BASE_URL, TEST_USER_EMAIL, TEST_USER_PASSWORD);
  return { token: token };
}

export default function (data) {
  const doc = generateDummyDocument(20); // 20KB test payload
  const uploadUrl = `${BASE_URL}/api/v1/documents/upload`;

  const payload = {
    file: http.file(doc.content, doc.filename, doc.mimeType),
  };

  const params = {
    headers: {},
    timeout: '30s',
  };

  if (data && data.token) {
    params.headers['Authorization'] = `Bearer ${data.token}`;
  }

  const res = http.post(uploadUrl, payload, params);

  check(res, {
    'upload status < 500': (r) => r.status < 500,
  });

  sleep(2);
}
