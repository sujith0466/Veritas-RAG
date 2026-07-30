import { test, expect } from '@playwright/test';

test.describe('Landing Page Audit', () => {
  test('Capture landing page sections', async ({ page }) => {
    // Set viewport to a standard desktop size
    await page.setViewportSize({ width: 1440, height: 900 });
    
    await page.goto('http://localhost:5173/');
    
    // Wait for initial load
    await page.waitForTimeout(2000);
    
    // Capture Hero
    await page.screenshot({ path: 'test-results/audit/hero.png' });
    
    // Scroll and capture sections
    const scrolls = 6;
    for (let i = 1; i <= scrolls; i++) {
      await page.evaluate(() => window.scrollBy(0, 800));
      await page.waitForTimeout(1000); // Wait for animations
      await page.screenshot({ path: `test-results/audit/section_${i}.png` });
    }
  });
});
