/**
 * Authentication helper for k6 scenarios.
 */

import http from 'k6/http';
import { check } from 'k6';

export function loginAndGetToken(baseUrl, email, password) {
  const loginUrl = `${baseUrl}/api/v1/auth/login`;
  const payload = JSON.stringify({
    email: email,
    password: password,
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
  };

  const res = http.post(loginUrl, payload, params);

  const isSuccess = check(res, {
    'login status is 200': (r) => r.status === 200,
    'token present in response': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body && body.data && body.data.access_token !== undefined;
      } catch (e) {
        return false;
      }
    },
  });

  if (!isSuccess) {
    return null;
  }

  const data = JSON.parse(res.body);
  return data.data.access_token;
}
