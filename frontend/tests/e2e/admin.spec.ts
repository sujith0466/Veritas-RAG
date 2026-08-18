import { test, expect } from '@playwright/test';

// Configuration
const BASE_URL = 'http://127.0.0.1:5173';
const PASSWORD = 'Password123!';

// Test Users from seed
const USERS = {
  ADMIN: 'e2e_admin@raguard.ai',
  MEMBER: 'e2e_member@raguard.ai',
  PLATFORM_ADMIN: 'e2e_platform@raguard.ai',
};

async function login(page: any, email: string, roleCardText: string) {
  await page.goto('/auth/login');
  await page.getByText(roleCardText, { exact: true }).click();
  await page.getByLabel(/Email/i).fill(email);
  await page.getByLabel(/Password/i).first().fill(PASSWORD);
  await page.getByRole('button', { name: /^Login$/i }).click();
  await page.waitForURL('**/dashboard', { timeout: 15000 });
}

test.describe('Epic 12 Admin Portal E2E Tests', () => {

  test('F12.1 - Workspace Admin Dashboard', async ({ page }) => {
    await login(page, USERS.ADMIN, 'Admin Workspace');

    // Navigate to Admin Settings area
    await page.goto('/admin/workspace');

    // We expect it to redirect to /admin/workspace or show the admin layout
    await expect(page).toHaveURL(/.*\/admin.*/);

    // Should see Settings heading
    await expect(page.getByText('General Info').first()).toBeVisible();

    // Ensure Platform Admin section is NOT accessible
    await page.goto('/admin/platform');
    // Should be redirected or denied
    await expect(page.getByText('Access Denied')).toBeVisible();
  });

  test('F12.2 - Platform Admin Dashboard', async ({ page }) => {
    await login(page, USERS.PLATFORM_ADMIN, 'Admin Workspace');

    await page.goto('/admin/platform');
    await expect(page).toHaveURL(/.*\/admin\/platform/);

    // Verify platform content
    await expect(page.getByRole('heading', { name: /Platform/i })).toBeVisible();
    await expect(page.getByText(/Workspaces/i).first()).toBeVisible();
  });

  test('F12.3 - Workspace Settings UI', async ({ page }) => {
    await login(page, USERS.ADMIN, 'Admin Workspace');

    await page.goto('/admin/workspace');
    await expect(page).toHaveURL(/.*\/admin\/workspace/);

    const nameInput = page.getByLabel(/Workspace Name/i);
    await expect(nameInput).toBeVisible();

    await nameInput.fill('E2E Workspace Updated');
    await page.getByRole('button', { name: /Save Workspace Settings/i }).click();

    await expect(page.getByText(/success/i).first()).toBeVisible();

    await nameInput.fill('E2E Workspace');
    await page.getByRole('button', { name: /Save Workspace Settings/i }).click();
  });

  test('F12.4 - Member Management UI', async ({ page }) => {
    await login(page, USERS.ADMIN, 'Admin Workspace');

    await page.goto('/admin/members');
    await expect(page).toHaveURL(/.*\/admin\/members/);

    await expect(page.getByText('e2e_member@raguard.ai')).toBeVisible();
  });

  test('F12.5 - Quota Management UI', async ({ page }) => {
    await login(page, USERS.ADMIN, 'Admin Workspace');

    await page.goto('/admin/quota');
    await expect(page).toHaveURL(/.*\/admin\/quota/);

    // The quota text is e.g. "Limit: 10.0M" or "Limit: 1.0M" or "100.00"
    await expect(page.getByText(/Limit:\s*\d+(\.\d+)?[MKG]?|100\.00/i).first()).toBeVisible();
  });

  test('F12.6 - Audit Log Viewer', async ({ page }) => {
    await login(page, USERS.ADMIN, 'Admin Workspace');

    await page.goto('/admin/audit');
    await expect(page).toHaveURL(/.*\/admin\/audit/);

    await expect(page.getByRole('table').or(page.getByText(/No audit events found/i))).toBeVisible();
  });

  test('Security - MEMBER cannot access Admin Portal', async ({ page }) => {
    await login(page, USERS.MEMBER, 'Workspace Member');

    await page.goto('/admin/workspace');
    await page.waitForURL('**/dashboard', { timeout: 15000 });
    await expect(page).toHaveURL(/.*\/dashboard/);
  });
});
