import { Page, expect } from '@playwright/test';

export async function login(page: Page, role: 'admin' | 'viewer' = 'admin') {
  await page.goto('/auth/login');
  // Click the role card based on role
  await page.locator(`text="${role === 'admin' ? 'Admin Workspace' : 'Workspace Member'}"`).click();

  // Use the correct credentials for each role:
  //   admin  → demoadmin@gmail.com / ChangeMe123!  (role='admin' in DB)
  //   user   → demo@gmail.com / ChangeMe123!       (role='viewer' in DB)
  const email = role === 'admin' ? 'demoadmin@gmail.com' : 'demo@gmail.com';
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', 'ChangeMe123!');

  await Promise.all([
    page.waitForResponse(resp => resp.url().includes('/auth') && resp.status() === 200, { timeout: 15000 }),
    page.locator('button[type="submit"]').click()
  ]);
  await page.waitForFunction(
    () => window.location.pathname.includes('/dashboard') || window.location.pathname.includes('/chat'),
    { timeout: 30000 }
  );

  // CRITICAL: AuthProvider calls authService.fetchBackendProfile() which makes two API calls:
  //   1. GET /api/v1/auth/me  → populates UserContext (including user.role)
  //   2. GET /api/v1/users/me → merges extended profile
  // Only after BOTH complete does setAuth(userContext, token) fire, populating authStore.user.role.
  //
  // The sidebar filters adminOnly links by user?.role === 'admin', and ProtectedRoute adminOnly
  // redirects if user?.role !== 'admin'. We MUST wait for /users/me to return before proceeding.
  //
  // We wait for /users/me (the last call in fetchBackendProfile) to return 200 OR 404/any status,
  // which confirms user.role is now set in authStore. Then we fall back to networkidle.
  await page.waitForResponse(
    resp => resp.url().includes('/api/v1/users/me') && resp.status() < 500,
    { timeout: 15000 }
  ).catch(async () => {
    // Fallback: if /users/me didn't fire (e.g. auth/me already had full profile),
    // wait for auth/me instead.
    await page.waitForResponse(
      resp => resp.url().includes('/api/v1/auth/me') && resp.status() < 500,
      { timeout: 10000 }
    ).catch(() => {
      // Last resort: give the app time to settle
    });
  });

  // Wait for any remaining initial API burst to complete.
  await page.waitForLoadState('networkidle', { timeout: 20000 }).catch(() => {
    // Ignore networkidle timeout — Supabase realtime connections never become truly idle.
  });
}

export function setupConsoleListener(page: Page) {
  const errors: string[] = [];
  page.on('console', msg => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      const text = msg.text();
      // Ignore extension errors, known dev warnings, and expected auth-related errors
      if (
        !text.includes('favicon.ico') &&
        !text.includes('chrome-extension') &&
        !text.includes('react-refresh') &&
        // 401 is expected during Supabase session hydration on initial page load
        !text.includes('401') &&
        !text.includes('Unauthorized') &&
        // Supabase realtime connection warnings are expected in test environment
        !text.includes('realtime') &&
        !text.includes('WebSocket')
      ) {
        errors.push(`[${msg.type()}] ${text}`);
      }
    }
  });
  page.on('pageerror', exception => {
    errors.push(`[Exception] ${exception.message}`);
  });
  return errors;
}

export function setupNetworkListener(page: Page) {
  const failedRequests: string[] = [];
  page.on('response', response => {
    // Only check API requests, ignore static assets and auth-related requests
    if (response.url().includes('/api/') && response.status() >= 500) {
      failedRequests.push(`${response.request().method()} ${response.url()} failed with ${response.status()}`);
    }
  });
  return failedRequests;
}
