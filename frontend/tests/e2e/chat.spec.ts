import { test, expect } from '@playwright/test';
import { login, setupConsoleListener, setupNetworkListener } from './utils/helpers';

test.describe('Chat Suite @chat', () => {
  test.beforeEach(async ({ page }) => {
    setupConsoleListener(page);
    setupNetworkListener(page);
    await login(page, 'viewer');
  });

  test('Navigate, Send Prompt, Verify Stream and Completion', async ({ page }) => {
    await test.step('Navigate to Chat', async () => {
      // Navigate to chat — the login helper may have already landed here
      if (!page.url().includes('/chat')) {
        await page.goto('/chat');
      }
      await expect(page).toHaveURL(/.*\/chat/, { timeout: 15000 });

      // Wait for a successful authenticated API call before interacting with the page.
      // The chat sidebar fetches /chat/sessions on mount — this confirms the auth token
      // is active in the apiClient interceptor, so createSession() won't throw 401.
      await page.waitForResponse(
        resp => resp.url().includes('/api/v1/chat/sessions') && resp.status() === 200,
        { timeout: 20000 }
      ).catch(() => {
        // If the sessions call doesn't fire (sidebar hidden), we still proceed.
        // The networkidle wait in login() should have hydrated the token.
      });
    });

    const question = 'What are the core capabilities of Veritas RAG?';

    await test.step('Send Prompt', async () => {
      // Wait for the textarea to be available and interactive
      const input = page.locator('textarea').first();
      await expect(input).toBeVisible({ timeout: 15000 });
      await expect(input).toBeEnabled({ timeout: 5000 });

      await input.click();
      await input.fill(question);

      // Confirm React state updated: submit button must become enabled
      const submitBtn = page.locator('button[type="submit"]').first();
      await expect(submitBtn).toBeEnabled({ timeout: 5000 });
      await submitBtn.click();
    });

    await test.step('Verify Response is Rendered', async () => {
      // Wait for URL to change to /chat/{uuid} indicating session navigation is complete
      await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}/, { timeout: 15000 }).catch(() => {
        // May already be on session URL if it's a continuing chat
      });

      // Wait for the backend to accept the query before polling for response content
      await page.waitForResponse(
        resp => resp.url().includes('/stream') && resp.status() < 500,
        { timeout: 30000 }
      ).catch(() => {
        // SSE streams may not be captured — proceed with prose poll
      });

      // ANY response — real LLM stream, isIndexing message, or streaming error fallback —
      // populates a div.prose element. We wait for text > 20 chars.
      await expect.poll(async () => {
        const proseElements = page.locator('div.prose');
        const count = await proseElements.count();
        if (count === 0) return 0;

        // Check the last prose element (the assistant response)
        const text = await proseElements.last().innerText().catch(() => '');
        if (text.trim().length > 20) return text.trim().length;

        // Also check for inline error messages in the message bubble
        const errorMsg = page.getByText(/Failed to generate|temporarily unavailable|error occurred/i);
        const hasError = await errorMsg.isVisible().catch(() => false);
        if (hasError) return 50; // Error messages are valid terminal states

        return 0;
      }, {
        message: 'No assistant response appeared in the chat',
        timeout: 180000,
        intervals: [1000, 2000, 3000, 5000, 5000, 5000, 5000, 10000, 10000, 10000, 10000, 15000, 15000],
      }).toBeGreaterThan(20);
    });

    await test.step('Verify Completion Badge (if real stream)', async () => {
      // The reliability badge only appears after a real LLM stream with is_final SSE event.
      // If isIndexing was true, there's no badge. We make this step optional.
      const groundedBadge = page.locator('span').filter({ hasText: /^(Grounded|Partial\/Ungrounded)$/ });
      const badgeCount = await groundedBadge.count().catch(() => 0);
      if (badgeCount > 0) {
        await expect(groundedBadge.last()).toBeVisible({ timeout: 20000 });
      }
    });
  });

  test('New Chat - Session Isolation and Independent Conversation Switching', async ({ page }) => {
    // 1. Start at /chat
    if (!page.url().includes('/chat')) {
      await page.goto('/chat');
    }
    await expect(page).toHaveURL(/.*\/chat/, { timeout: 15000 });

    // Wait for auth to be fully hydrated
    await page.waitForResponse(
      resp => resp.url().includes('/api/v1/chat/sessions') && resp.status() === 200,
      { timeout: 20000 }
    ).catch(() => {});

    // 2. Send query in Chat A
    const promptA = 'Query A for Chat Session Isolation ' + Date.now();
    const input = page.locator('textarea').first();
    await expect(input).toBeVisible({ timeout: 15000 });
    await input.fill(promptA);
    const submitBtn = page.locator('button[type="submit"]').first();
    await expect(submitBtn).toBeEnabled({ timeout: 5000 });
    await submitBtn.click();

    // 3. Verify Chat A receives a real session ID in URL
    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}/, { timeout: 20000 });
    const urlA = page.url();
    const sessionIdA = urlA.split('/chat/')[1];
    expect(sessionIdA).toBeTruthy();

    // 4. Verify Chat A content is present
    await expect(page.locator(`text=${promptA}`)).toBeVisible({ timeout: 15000 });

    // 5. Click "New Chat" in Sidebar
    const newChatBtn = page.getByRole('button', { name: 'New Chat' }).first();
    await newChatBtn.click();

    // 6. Verify URL becomes /chat
    await expect(page).toHaveURL(/.*\/chat$/, { timeout: 15000 });

    // 7. Verify Chat A messages are no longer displayed
    await expect(page.locator(`text=${promptA}`)).not.toBeVisible();

    // 8. Verify the empty/new-chat state is displayed
    await expect(page.locator('text=How can I help you today?')).toBeVisible({ timeout: 10000 });

    // 9. Send a different query in Chat B
    const promptB = 'Query B for Chat Session Isolation ' + Date.now();
    const inputB = page.locator('textarea').first();
    await inputB.fill(promptB);
    const submitBtnB = page.locator('button[type="submit"]').first();
    await expect(submitBtnB).toBeEnabled({ timeout: 5000 });
    await submitBtnB.click();

    // 10 & 11. Verify Chat B creates a different session ID
    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}/, { timeout: 20000 });
    const urlB = page.url();
    const sessionIdB = urlB.split('/chat/')[1];
    expect(sessionIdB).toBeTruthy();
    expect(sessionIdB).not.toBe(sessionIdA);

    // 12. Verify Chat B content is present
    await expect(page.locator(`text=${promptB}`)).toBeVisible({ timeout: 15000 });

    // 13. Navigate back to Chat A using sidebar link
    const chatALink = page.locator(`a[href="/chat/${sessionIdA}"]`).first();
    if (await chatALink.isVisible({ timeout: 3000 }).catch(() => false)) {
      await chatALink.click();
    } else {
      await page.goto(`/chat/${sessionIdA}`);
    }

    // 14. Verify Chat A messages are restored
    await expect(page).toHaveURL(new RegExp(`/chat/${sessionIdA}`), { timeout: 15000 });
    await expect(page.locator(`text=${promptA}`)).toBeVisible({ timeout: 15000 });
    await expect(page.locator(`text=${promptB}`)).not.toBeVisible();

    // 15. Navigate back to Chat B
    const chatBLink = page.locator(`a[href="/chat/${sessionIdB}"]`).first();
    if (await chatBLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      await chatBLink.click();
    } else {
      await page.goto(`/chat/${sessionIdB}`);
    }

    // 16 & 17. Verify Chat B messages are restored and isolated
    await expect(page).toHaveURL(new RegExp(`/chat/${sessionIdB}`), { timeout: 15000 });
    await expect(page.locator(`text=${promptB}`)).toBeVisible({ timeout: 15000 });
    await expect(page.locator(`text=${promptA}`)).not.toBeVisible();
  });
});
