import { test, expect } from '@playwright/test';

test.describe('Reg Test', () => {
  test('Admin Reg', async ({ page }) => {
    page.on('console', m => console.log('PAGE LOG:', m.text()));
    
    await page.goto('http://localhost:5173/auth/register?role=admin');
    
    await page.fill('input[name="workspaceName"]', 'Test Workspace');
    await page.fill('input[name="fullName"]', 'Test Admin');
    await page.fill('input[name="email"]', 'admin_'+Date.now()+'@example.com');
    await page.fill('input[name="password"]', 'Password123!');
    await page.fill('input[name="confirmPassword"]', 'Password123!');
    await page.check('input[name="acceptTerms"]');
    
    await page.click('button[type="submit"]');
    
    await page.waitForTimeout(5000); // Give it time to log errors or redirect
    
    console.log("Final URL:", page.url());
  });
});
