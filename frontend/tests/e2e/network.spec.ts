import { test, expect } from '@playwright/test';
import { login, setupConsoleListener, setupNetworkListener } from './utils/helpers';

test.describe('Network & UI Error States Suite @network', () => {
  let errors: string[] = [];
  let failedRequests: string[] = [];

  test.beforeEach(async ({ page }) => {
    errors = setupConsoleListener(page);
    failedRequests = setupNetworkListener(page);
    await login(page, 'admin');
  });

  test('No Unhandled Exceptions or HTTP 500s During Core Flow', async ({ page }) => {
    // Navigate through core sections
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/.*\/dashboard/);

    await page.goto('/documents');
    await expect(page).toHaveURL(/.*\/documents/);

    await page.goto('/chat');
    await expect(page).toHaveURL(/.*\/chat/);

    // Wait a bit to ensure background requests settle
    await page.waitForTimeout(2000);

    // Assert no console errors (other than ignored ones)
    expect(errors.length, `Found console errors: ${errors.join(', ')}`).toBe(0);

    // Assert no API 500s
    expect(failedRequests.length, `Found failed network requests: ${failedRequests.join(', ')}`).toBe(0);
  });
});
