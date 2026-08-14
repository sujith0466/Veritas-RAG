import { test, expect } from "@playwright/test";
import { login, setupConsoleListener, setupNetworkListener } from "./utils/helpers";

test.describe("Manual Validation Automation", () => {
  test.setTimeout(180000);

  test("execute all 5 manual scenarios successfully", async ({ page }) => {
    const consoleErrors = setupConsoleListener(page);
    const networkErrors = setupNetworkListener(page);

    // SCENARIO 1: New chat
    console.log("=== SCENARIO 1: New Chat ===");
    await login(page, "viewer");
    await page.goto("/chat");
    await expect(page).toHaveURL(/.*\/chat$/);

    const question1 = "What is the purpose of this workspace?";
    await page.fill("textarea", question1);

    // Set up the listener before clicking
    const streamPromise1 = page.waitForResponse(resp => resp.url().includes("/stream") && resp.status() < 500, { timeout: 60000 });
    await page.click("button[type=\"submit\"]");

    // wait for url change
    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}/, { timeout: 15000 });
    const session1Url = page.url();
    console.log("New session created:", session1Url);

    await streamPromise1;

    // Use expect.toPass to poll dynamically for the expected state instead of a massive arbitrary wait
    await expect(async () => {
      const proseNodes = page.locator("div.prose");
      const proseCount = await proseNodes.count();
      expect(proseCount).toBeGreaterThanOrEqual(2);

      const allText = await proseNodes.allTextContents();
      for (const text of allText) {
        expect(text).not.toContain("Failed to generate response");
      }
    }).toPass({ timeout: 30000 });

    console.log("Scenario 1 passed. Prose count: >= 2 and no error text");

    // SCENARIO 3 & 4 (Wait, 4 first: Follow-up question)
    console.log("=== SCENARIO 4: Follow-up question ===");
    const question2 = "Can you explain that more simply?";
    await page.fill("textarea", question2);

    const streamPromise2 = page.waitForResponse(resp => resp.url().includes("/stream") && resp.status() < 500, { timeout: 60000 });
    await page.click("button[type=\"submit\"]");

    await streamPromise2;

    await expect(async () => {
      const proseNodes = page.locator("div.prose");
      const proseCount = await proseNodes.count();
      expect(proseCount).toBeGreaterThanOrEqual(4);

      const allText = await proseNodes.allTextContents();
      for (const text of allText) {
        expect(text).not.toContain("Failed to generate response");
      }
    }).toPass({ timeout: 30000 });

    console.log("Scenario 4 passed. Prose count: >= 4 and no error text");

    // SCENARIO 3: Refresh
    console.log("=== SCENARIO 3: Refresh ===");
    // Allow backend to finish saving messages to DB before we reload and fetch them
    await page.waitForTimeout(2000);
    await page.reload();
    await expect(page).toHaveURL(session1Url);

    await expect(async () => {
      const proseNodes = page.locator("div.prose");
      const proseCount = await proseNodes.count();
      expect(proseCount).toBeGreaterThanOrEqual(4);
    }).toPass({ timeout: 30000 });

    console.log("Scenario 3 passed. Prose count restored after refresh: >= 4");

    // SCENARIO 5: Session navigation
    console.log("=== SCENARIO 5: Session navigation ===");
    // Go to New Chat to ensure we are not on the current session
    await page.goto("/chat");
    await expect(page).toHaveURL(/\/chat$/);

    // Click on the first session in the sidebar
    const urlObj = new URL(session1Url);
    const pathname = urlObj.pathname;
    await page.locator(`a[href="${pathname}"]`).first().click();
    await expect(page).toHaveURL(session1Url);

    await expect(async () => {
      const newProseCount = await page.locator("div.prose").count();
      expect(newProseCount).toBeGreaterThan(0);
    }).toPass({ timeout: 30000 });

    console.log("Scenario 5 passed. Navigated to another session. Prose count > 0");

    // SCENARIO 2: Existing session (via direct navigation)
    console.log("=== SCENARIO 2: Existing session (direct nav) ===");
    await page.goto(session1Url);

    await expect(async () => {
      const proseCount = await page.locator("div.prose").count();
      expect(proseCount).toBeGreaterThanOrEqual(4);
    }).toPass({ timeout: 30000 });

    console.log("Scenario 2 passed. Prose count restored via direct navigation: >= 4");

    // FINAL ASSERTIONS: ensure no unexpected network or console errors
    expect(consoleErrors).toEqual([]);
    expect(networkErrors).toEqual([]);

    console.log("ALL MANUAL SCENARIOS AUTOMATED SUCCESSFULLY.");
  });
});
