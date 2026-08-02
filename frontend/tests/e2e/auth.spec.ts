import { test, expect } from '@playwright/test';
import { login, setupConsoleListener, setupNetworkListener } from './utils/helpers';

test.describe('Authentication Suite @auth', () => {
  test.beforeEach(async ({ page }) => {
    setupConsoleListener(page);
    setupNetworkListener(page);
  });

  test('Valid Login and Logout', async ({ page }) => {
    await test.step('Login', async () => {
      await login(page, 'admin');
      // Verify redirect to dashboard
      await expect(page).toHaveURL(/.*\/dashboard/);
    });

    await test.step('Logout', async () => {
      // The UserMenu is always the LAST button in the sticky header.
      const header = page.locator('header').first();
      await expect(header).toBeVisible({ timeout: 10000 });

      // The UserMenu trigger is the last button in the header (after Bell and theme toggle)
      const userMenuBtn = header.locator('button').last();
      await expect(userMenuBtn).toBeVisible({ timeout: 10000 });
      await userMenuBtn.click();

      // The dropdown portal renders in the body.
      // Use getByText with exact match to avoid picking up partial matches.
      const logoutItem = page.getByText('Log out', { exact: true });
      await expect(logoutItem).toBeVisible({ timeout: 8000 });
      await logoutItem.click();

      // handleLogout() calls navigate('/') which goes to the landing page root.
      // The full URL becomes http://127.0.0.1:5173/ — check for either landing or login page.
      // We use a loose URL check: the path should be '/' or '/auth/login'
      await expect(page).toHaveURL(/(\/auth\/login|:5173\/)$/, { timeout: 15000 });
    });
  });

  test('Session Persistence', async ({ page }) => {
    await login(page, 'admin');
    await expect(page).toHaveURL(/.*\/dashboard/);

    // Reload and check we stay logged in
    await page.reload();
    await page.waitForLoadState('networkidle', { timeout: 20000 }).catch(() => {});
    await expect(page).toHaveURL(/.*\/dashboard/);
  });

  test('Protected Routes', async ({ page }) => {
    // Navigate directly without logging in
    await page.goto('/dashboard');
    // Verify redirect to login page
    await expect(page).toHaveURL(/.*\/auth\/login/, { timeout: 15000 });
  });
});
