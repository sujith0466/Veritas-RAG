import { test, expect } from "@playwright/test";
import { login } from "./utils/helpers";

test.describe("Manual Validation Automation", () => {
  test.setTimeout(180000);

  test("execute all 5 manual scenarios successfully", async ({ page }) => {
    // SCENARIO 1: New chat
    console.log("=== SCENARIO 1: New Chat ===");
    await login(page, "user");
    await page.goto("/chat");
    await expect(page).toHaveURL(/.*\/chat$/);

    const question1 = "What is the purpose of this workspace?";
    await page.fill("textarea", question1);
    await page.click("button[type=\"submit\"]");

    // wait for url change
    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}/, { timeout: 15000 });
    const session1Url = page.url();
    console.log("New session created:", session1Url);

    // wait for stream to finish (Playwright waitForResponse only waits for headers, so we must wait for the actual stream body to complete)
    await page.waitForResponse(resp => resp.url().includes("/stream") && resp.status() < 500, { timeout: 30000 });
    
    // Check if wipe happens within 5 seconds (we wait 25s for stream to finish + 5s to check for wipe)
    await page.waitForTimeout(25000);
    let proseCount = await page.locator("div.prose").count();
    expect(proseCount).toBeGreaterThanOrEqual(2);
    console.log("Scenario 1 passed. Prose count:", proseCount);

    // SCENARIO 3 & 4 (Wait, 4 first: Follow-up question)
    console.log("=== SCENARIO 4: Follow-up question ===");
    const question2 = "Can you explain that more simply?";
    await page.fill("textarea", question2);
    await page.click("button[type=\"submit\"]");

    await page.waitForResponse(resp => resp.url().includes("/stream") && resp.status() < 500, { timeout: 30000 });
    await page.waitForTimeout(25000);
    
    proseCount = await page.locator("div.prose").count();
    expect(proseCount).toBeGreaterThanOrEqual(4); // 2 pairs of user/assistant
    console.log("Scenario 4 passed. Prose count:", proseCount);

    // SCENARIO 3: Refresh
    console.log("=== SCENARIO 3: Refresh ===");
    await page.reload();
    await expect(page).toHaveURL(session1Url);
    
    // wait for messages to load
    await page.waitForResponse(resp => resp.url().includes("/messages"), { timeout: 15000 });
    await page.waitForTimeout(2000);

    proseCount = await page.locator("div.prose").count();
    expect(proseCount).toBeGreaterThanOrEqual(4);
    console.log("Scenario 3 passed. Prose count restored after refresh:", proseCount);

    // SCENARIO 5: Session navigation
    console.log("=== SCENARIO 5: Session navigation ===");
    // Go to New Chat to ensure we are not on the current session
    await page.goto("/chat");
    await expect(page).toHaveURL(/\/chat$/);
    await page.waitForTimeout(1000);

    // Click on the first session in the sidebar
    const urlObj = new URL(session1Url);
    const pathname = urlObj.pathname;
    const sidebarLink = page.locator(`a[href="${pathname}"]`).first();
    await sidebarLink.click();
    await expect(page).toHaveURL(session1Url);
    
    await page.waitForResponse(resp => resp.url().includes("/messages"), { timeout: 15000 });
    await page.waitForTimeout(2000);

    const newProseCount = await page.locator("div.prose").count();
    expect(newProseCount).toBeGreaterThan(0);
    console.log("Scenario 5 passed. Navigated to another session. Prose count:", newProseCount);

    // SCENARIO 2: Existing session (via direct navigation)
    console.log("=== SCENARIO 2: Existing session (direct nav) ===");
    await page.goto(session1Url);
    await page.waitForResponse(resp => resp.url().includes("/messages"), { timeout: 15000 });
    await page.waitForTimeout(2000);
    
    proseCount = await page.locator("div.prose").count();
    expect(proseCount).toBeGreaterThanOrEqual(4);
    console.log("Scenario 2 passed. Prose count restored via direct navigation:", proseCount);

    console.log("ALL MANUAL SCENARIOS AUTOMATED SUCCESSFULLY.");
  });
});
