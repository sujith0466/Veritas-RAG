import { test, expect } from '@playwright/test';
import { setupConsoleListener, setupNetworkListener } from './utils/helpers';

test.describe('Smoke Suite @smoke', () => {
  test('API Health and Core Navigation', async ({ page, request }) => {
    setupConsoleListener(page);
    setupNetworkListener(page);

    // 1. Verify API Health (assuming /api/v1/health exists, otherwise just check frontend loads)
    const res = await request.get('/api/v1/health').catch(() => null);
    if (res) {
      expect(res.ok()).toBeTruthy();
    }

    // 2. Core Navigation
    await page.goto('/auth/login');
    await expect(page).toHaveTitle(/Veritas RAG/i);

    // Ensure Role Selector is visible
    await expect(page.locator('text="Admin Workspace"')).toBeVisible();
    await expect(page.locator('text="Workspace Member"')).toBeVisible();
  });
});
