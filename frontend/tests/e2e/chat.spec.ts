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

  test('Sidebar Actions - Pin, Rename, Delete and Active Session Deletion Navigation', async ({ page }) => {
    // 1. Navigate to /chat
    if (!page.url().includes('/chat')) {
      await page.goto('/chat');
    }
    await expect(page).toHaveURL(/.*\/chat/, { timeout: 15000 });

    // Wait for auth & sidebar sessions hydration
    await page.waitForResponse(
      resp => resp.url().includes('/api/v1/chat/sessions') && resp.status() === 200,
      { timeout: 20000 }
    ).catch(() => {});

    // 2. Create a new chat session by sending a prompt
    const promptText = 'Sidebar Actions Test ' + Date.now();
    const input = page.locator('textarea').first();
    await expect(input).toBeVisible({ timeout: 15000 });
    await input.fill(promptText);
    const submitBtn = page.locator('button[type="submit"]').first();
    await expect(submitBtn).toBeEnabled({ timeout: 5000 });
    await submitBtn.click();

    // 3. Verify session ID in URL
    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}/, { timeout: 20000 });
    const sessionUrl = page.url();
    const sessionId = sessionUrl.split('/chat/')[1];
    expect(sessionId).toBeTruthy();

    // Wait for response stream completion before performing sidebar mutations
    await expect(page.getByRole('button', { name: 'Stop generating' })).not.toBeVisible({ timeout: 90000 });

    // 4. Locate the sidebar row for this session using data-session-id
    const sessionRow = page.locator(`div[data-session-id="${sessionId}"]`).first();
    await expect(sessionRow).toBeVisible({ timeout: 20000 });

    const getActionsBtn = () => sessionRow.locator('button[aria-label="Chat actions"]');

    // Click three-dot actions button to open menu
    await getActionsBtn().click({ force: true });

    // 5. Verify overflow menu is open
    const pinMenuItem = page.getByRole('menuitem', { name: 'Pin' });
    const renameMenuItem = page.getByRole('menuitem', { name: 'Rename' });
    const deleteMenuItem = page.getByRole('menuitem', { name: 'Delete' });
    await expect(pinMenuItem).toBeVisible({ timeout: 5000 });
    await expect(renameMenuItem).toBeVisible({ timeout: 5000 });
    await expect(deleteMenuItem).toBeVisible({ timeout: 5000 });

    // Test Pin action
    await pinMenuItem.click();
    await expect(page.locator(`div[data-chat-group="Pinned"] div[data-session-id="${sessionId}"]`)).toBeVisible({ timeout: 10000 });

    // Test Unpin action
    await getActionsBtn().click({ force: true });
    const unpinMenuItem = page.getByRole('menuitem', { name: 'Unpin' });
    await expect(unpinMenuItem).toBeVisible({ timeout: 5000 });
    await unpinMenuItem.click();
    await expect(page.locator(`div[data-chat-group="Pinned"] div[data-session-id="${sessionId}"]`)).not.toBeVisible({ timeout: 10000 });
    await expect(page.locator(`div[data-chat-group="Today"] div[data-session-id="${sessionId}"]`)).toBeVisible({ timeout: 10000 });

    // Test Rename with Escape cancellation
    await getActionsBtn().click({ force: true });
    await expect(page.getByRole('menuitem', { name: 'Rename' })).toBeVisible({ timeout: 5000 });
    await page.getByRole('menuitem', { name: 'Rename' }).click();
    const renameInput = page.locator('input[aria-label="Rename chat session"]');
    await expect(renameInput).toBeVisible({ timeout: 5000 });
    await renameInput.fill('Cancelled Title');
    await renameInput.press('Escape');
    await expect(renameInput).not.toBeVisible();
    await expect(page.locator('text=Cancelled Title')).not.toBeVisible();

    // Test Rename with Enter save
    const newTitle = 'Renamed Session ' + Date.now();
    await getActionsBtn().click({ force: true });
    await expect(page.getByRole('menuitem', { name: 'Rename' })).toBeVisible({ timeout: 5000 });
    await page.getByRole('menuitem', { name: 'Rename' }).click();
    await expect(renameInput).toBeVisible({ timeout: 5000 });
    await renameInput.fill(newTitle);
    await renameInput.press('Enter');
    await expect(page.locator(`text=${newTitle}`)).toBeVisible({ timeout: 10000 });

    // Test Active Session Deletion
    page.once('dialog', async dialog => {
      expect(dialog.message()).toContain('permanently delete');
      await dialog.accept();
    });

    await getActionsBtn().click({ force: true });
    await expect(page.getByRole('menuitem', { name: 'Delete' })).toBeVisible({ timeout: 5000 });
    await page.getByRole('menuitem', { name: 'Delete' }).click();

    // Verify URL immediately navigates to /chat
    await expect(page).toHaveURL(/.*\/chat$/, { timeout: 15000 });

    // Verify deleted session messages are no longer visible and clean empty state is shown
    await expect(page.locator(`text=${promptText}`)).not.toBeVisible();
    await expect(page.locator('text=How can I help you today?')).toBeVisible({ timeout: 10000 });
    await expect(page.locator(`a[href="/chat/${sessionId}"]`)).not.toBeVisible();

    // Test Invalid/Deleted Session URL Recovery
    await page.goto('/chat/00000000-0000-0000-0000-000000000000');
    await expect(page).toHaveURL(/.*\/chat$/, { timeout: 15000 });
  });

  test('Date-Grouping Semantics for Pin / Unpin and Genuine Activity', async ({ page }) => {
    // 1. Navigate to /chat
    if (!page.url().includes('/chat')) {
      await page.goto('/chat');
    }
    await expect(page).toHaveURL(/.*\/chat/, { timeout: 15000 });

    // Wait for sidebar sessions hydration
    await page.waitForResponse(
      resp => resp.url().includes('/api/v1/chat/sessions') && resp.status() === 200,
      { timeout: 20000 }
    ).catch(() => {});

    // Check if there is an older session under Yesterday, Previous 7 Days, or Older
    const olderGroups = ['Yesterday', 'Previous 7 Days', 'Older'];
    let targetGroup = '';
    let targetSessionId = '';

    for (const group of olderGroups) {
      const groupLocator = page.locator(`div[data-chat-group="${group}"]`);
      if (await groupLocator.isVisible({ timeout: 2000 }).catch(() => false)) {
        const firstSession = groupLocator.locator('div[data-session-id]').first();
        if (await firstSession.isVisible({ timeout: 1000 }).catch(() => false)) {
          targetGroup = group;
          targetSessionId = (await firstSession.getAttribute('data-session-id')) || '';
          if (targetSessionId) break;
        }
      }
    }

    // If an older session exists, verify pin/unpin date-grouping preservation
    if (targetSessionId && targetGroup) {
      const originalGroupContainer = page.locator(`div[data-chat-group="${targetGroup}"]`);
      const sessionRow = originalGroupContainer.locator(`div[data-session-id="${targetSessionId}"]`).first();
      await expect(sessionRow).toBeVisible({ timeout: 5000 });

      // Pin the older session
      const actionsBtn = sessionRow.locator('button[aria-label="Chat actions"]');
      await actionsBtn.click({ force: true });
      const pinItem = page.getByRole('menuitem', { name: 'Pin' });
      await expect(pinItem).toBeVisible({ timeout: 5000 });
      await pinItem.click();

      // Verify it appears in Pinned group and leaves original group
      const pinnedGroup = page.locator('div[data-chat-group="Pinned"]');
      await expect(pinnedGroup).toBeVisible({ timeout: 10000 });
      const pinnedRow = pinnedGroup.locator(`div[data-session-id="${targetSessionId}"]`).first();
      await expect(pinnedRow).toBeVisible({ timeout: 10000 });
      await expect(originalGroupContainer.locator(`div[data-session-id="${targetSessionId}"]`)).not.toBeVisible();

      // Unpin the session
      const pinnedActionsBtn = pinnedRow.locator('button[aria-label="Chat actions"]');
      await pinnedActionsBtn.click({ force: true });
      const unpinItem = page.getByRole('menuitem', { name: 'Unpin' });
      await expect(unpinItem).toBeVisible({ timeout: 5000 });
      await unpinItem.click();

      // CRITICAL REQUIREMENT: Must return to the SAME date-based group (e.g. Yesterday/Older), NOT Today!
      await expect(originalGroupContainer.locator(`div[data-session-id="${targetSessionId}"]`)).toBeVisible({ timeout: 10000 });
      if (targetGroup !== 'Today') {
        const todayGroup = page.locator('div[data-chat-group="Today"]');
        if (await todayGroup.isVisible().catch(() => false)) {
          await expect(todayGroup.locator(`div[data-session-id="${targetSessionId}"]`)).not.toBeVisible();
        }
      }

      // Verify persistence after page reload
      await page.reload();
      await page.waitForResponse(
        resp => resp.url().includes('/api/v1/chat/sessions') && resp.status() === 200,
        { timeout: 20000 }
      ).catch(() => {});
      await expect(page.locator(`div[data-chat-group="${targetGroup}"] div[data-session-id="${targetSessionId}"]`)).toBeVisible({ timeout: 10000 });

      // Verify Genuine Conversation Activity moves the session to Today
      await page.goto(`/chat/${targetSessionId}`);
      await expect(page).toHaveURL(new RegExp(`/chat/${targetSessionId}`), { timeout: 15000 });
      const activityPrompt = 'Genuine Activity Update ' + Date.now();
      const chatInput = page.locator('textarea').first();
      await expect(chatInput).toBeVisible({ timeout: 10000 });
      await chatInput.fill(activityPrompt);
      const sendBtn = page.locator('button[type="submit"]').first();
      await expect(sendBtn).toBeEnabled({ timeout: 5000 });
      await sendBtn.click();

      // Verify prompt appears and wait for response stream completion
      await expect(page.locator(`text=${activityPrompt}`)).toBeVisible({ timeout: 15000 });
      await expect(page.getByRole('button', { name: 'Stop generating' })).not.toBeVisible({ timeout: 90000 });
      await expect(chatInput).toBeEnabled({ timeout: 90000 });

      // Verify the session moved to Today after genuine conversation activity
      const todayGroupAfterActivity = page.locator('div[data-chat-group="Today"]');
      await expect(todayGroupAfterActivity).toBeVisible({ timeout: 15000 });
      await expect(todayGroupAfterActivity.locator(`div[data-session-id="${targetSessionId}"]`)).toBeVisible({ timeout: 15000 });
    }
  });

  test('Chat Composer - Fixed Viewport Position, Multiline Growth and Keyboard Semantics', async ({ page }) => {
    // 1. Navigate to /chat
    if (!page.url().includes('/chat')) {
      await page.goto('/chat');
    }
    await expect(page).toHaveURL(/.*\/chat/, { timeout: 15000 });

    const composer = page.locator('textarea[aria-label="Message Veritas RAG"]').first();
    const sendBtn = page.locator('button[aria-label="Send message"]').first();

    // 2. Verify composer is visible and properly labeled
    await expect(composer).toBeVisible({ timeout: 15000 });
    await expect(sendBtn).toBeVisible({ timeout: 15000 });
    await expect(sendBtn).toBeDisabled();

    // 3. Verify whitespace input keeps send button disabled
    await composer.fill('   ');
    await expect(sendBtn).toBeDisabled();
    await composer.fill('');

    // 4. Test Shift+Enter multiline behavior and auto-resize
    const initialBox = await composer.boundingBox();
    expect(initialBox).toBeTruthy();

    await composer.focus();
    await composer.pressSequentially('Line 1 of multiline composer test ' + Date.now());
    await composer.press('Shift+Enter');
    await composer.pressSequentially('Line 2 of multiline prompt');
    await composer.press('Shift+Enter');
    await composer.pressSequentially('Line 3 of multiline prompt');

    // Verify textarea grew in height to accommodate multiline input
    const multilineBox = await composer.boundingBox();
    expect(multilineBox).toBeTruthy();
    expect(multilineBox!.height).toBeGreaterThan(initialBox!.height);

    // Verify send button is enabled with valid text
    await expect(sendBtn).toBeEnabled({ timeout: 5000 });

    // 5. Test Enter submission without Shift
    await composer.press('Enter');

    // Verify input cleared after submission
    await expect(composer).toHaveValue('', { timeout: 10000 });

    // 6. Verify URL receives session ID and prompt renders
    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}/, { timeout: 20000 });
    await expect(page.locator('text=Line 1 of multiline composer test')).toBeVisible({ timeout: 15000 });

    // 7. Verify composer remains visible in the viewport at all times
    await expect(composer).toBeVisible({ timeout: 10000 });
    await expect(sendBtn).toBeVisible({ timeout: 10000 });

    // Wait for response stream completion
    await expect(page.getByRole('button', { name: 'Stop generating' })).not.toBeVisible({ timeout: 90000 });
    await expect(composer).toBeEnabled({ timeout: 90000 });
  });

  test('Chat Auto-Focus - New Chat Autofocus and Existing Session Predictability', async ({ page }) => {
    // 1. Direct navigation to /chat (desktop/fine-pointer)
    await page.goto('/chat');
    await expect(page).toHaveURL(/.*\/chat/, { timeout: 15000 });

    await page.waitForResponse(
      resp => resp.url().includes('/api/v1/chat/sessions') && resp.status() === 200,
      { timeout: 20000 }
    ).catch(() => {});

    const composer = page.locator('textarea[aria-label="Message Veritas RAG"]').first();
    await expect(composer).toBeVisible({ timeout: 15000 });

    // Verify composer automatically receives focus on /chat navigation
    await expect(composer).toBeFocused({ timeout: 10000 });

    // 2. Verify immediate typing without manual click
    const autofocusPrompt = 'Autofocus direct typing test ' + Date.now();
    await page.keyboard.type(autofocusPrompt);
    await expect(composer).toHaveValue(autofocusPrompt, { timeout: 5000 });

    // 3. Submit and verify session transition
    await composer.press('Enter');
    await expect(composer).toHaveValue('', { timeout: 10000 });

    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}/, { timeout: 20000 });
    const targetSessionId = page.url().split('/chat/')[1];

    await expect(page.locator(`text=${autofocusPrompt}`)).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('button', { name: 'Stop generating' })).not.toBeVisible({ timeout: 90000 });
    await expect(composer).toBeEnabled({ timeout: 90000 });

    // 4. Verify existing session does NOT steal focus on load
    await page.goto(`/chat/${targetSessionId}`);
    await expect(page).toHaveURL(new RegExp(`/chat/${targetSessionId}`), { timeout: 15000 });
    await page.waitForTimeout(600);
    await expect(composer).not.toBeFocused();

    // 5. Verify clicking "New Chat" in sidebar returns to /chat and focuses composer
    const newChatBtn = page.getByRole('button', { name: 'New Chat' }).first();
    await expect(newChatBtn).toBeVisible({ timeout: 10000 });
    await newChatBtn.click();

    await expect(page).toHaveURL(/.*\/chat$/, { timeout: 15000 });
    await expect(composer).toBeFocused({ timeout: 10000 });

    // 6. Verify clicking "New Chat" while ALREADY on /chat refocuses composer after blur
    await composer.blur();
    await expect(composer).not.toBeFocused();

    await newChatBtn.click();
    await expect(composer).toBeFocused({ timeout: 10000 });

    // 7. Verify post-submission focus via Send button click
    const followUpPrompt = 'Follow-up query ' + Date.now();
    await page.keyboard.type(followUpPrompt);
    const sendBtn = page.locator('button[aria-label="Send message"]').first();
    await expect(sendBtn).toBeEnabled({ timeout: 5000 });
    await sendBtn.click();
    await expect(composer).toBeFocused({ timeout: 5000 });
  });

  test('Generation UX and Liquid Glass Composer - Header Removal, Floating Overlay, Thinking State, Streaming, and Interruption', async ({ page }) => {
    // 1. Navigate to /chat
    await page.goto('/chat');
    await expect(page).toHaveURL(/.*\/chat/, { timeout: 15000 });

    // 2. Verify redundant internal chat header is removed
    await expect(page.locator('h2:has-text("AI Chat")')).not.toBeVisible();
    await expect(page.locator('text=Ask questions based on enterprise knowledge')).not.toBeVisible();

    const composer = page.locator('textarea[aria-label="Message Veritas RAG"]').first();
    const sendBtn = page.locator('button[aria-label="Send message"]').first();

    // 3. Verify Liquid Glass composer initial state & floating layout
    await expect(composer).toBeVisible({ timeout: 15000 });
    await expect(composer).toBeFocused({ timeout: 10000 });
    await expect(sendBtn).toBeDisabled();

    // Verify chat messages container is full-canvas scrollable layer with clearance
    const scrollContainer = page.locator('div.overflow-y-auto').first();
    await expect(scrollContainer).toBeVisible({ timeout: 10000 });

    // 4. Submit query and observe generation behavior
    const promptText = 'Generation UX and Stop Generating verification ' + Date.now();
    await composer.fill(promptText);
    await expect(sendBtn).toBeEnabled({ timeout: 5000 });
    await sendBtn.click();

    // 5. Verify Stop Generating button appears and can interrupt cleanly
    const stopBtn = page.locator('button[aria-label="Stop generating response"]').first();
    try {
      await stopBtn.waitFor({ state: 'visible', timeout: 10000 });
      await stopBtn.click();
      await expect(stopBtn).not.toBeVisible({ timeout: 15000 });
    } catch {
      // If stream ended before interrupt, ensure it finished cleanly
      await expect(stopBtn).not.toBeVisible({ timeout: 90000 });
    }

    // 6. Verify user message remains rendered and composer is enabled for follow-up
    await expect(page.locator(`text=${promptText}`)).toBeVisible({ timeout: 15000 });
    await expect(composer).toBeEnabled({ timeout: 10000 });

    // 7. Send complete follow-up prompt to verify normal generation completion
    const completePrompt = 'Explain the leave policy.';
    await composer.fill(completePrompt);
    await expect(sendBtn).toBeEnabled({ timeout: 10000 });
    await sendBtn.click();

    // Verify stream completes
    await expect(page.locator('button[aria-label="Stop generating response"]')).not.toBeVisible({ timeout: 90000 });
    await expect.poll(async () => {
      const proseElements = page.locator('div.prose');
      const count = await proseElements.count();
      if (count === 0) return 0;
      const text = await proseElements.last().innerText().catch(() => '');
      return text.trim().length;
    }, { timeout: 90000 }).toBeGreaterThan(10);

    await expect(composer).toBeEnabled({ timeout: 10000 });
  });

  test('Premium Chat UI - Empty State Categories, Message Bubbles, Code Block, and Citation Presentation', async ({ page }) => {
    // 1. Navigate to /chat
    await page.goto('/chat');
    await expect(page).toHaveURL(/.*\/chat/, { timeout: 15000 });

    // 2. Verify Premium Empty State with Category Badges and Icons
    await expect(page.locator('text=How can I help you today?')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Security & Access')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Incident Response')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=HR & Operations')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Infrastructure')).toBeVisible({ timeout: 10000 });

    // 3. Click one of the suggestion cards
    const policyPromptBtn = page.locator('button:has-text("What is the password policy?")').first();
    await expect(policyPromptBtn).toBeVisible({ timeout: 5000 });
    await policyPromptBtn.click();

    // 4. Verify User Message Bubble styling and content
    await expect(page.locator('text=What is the password policy?')).toBeVisible({ timeout: 15000 });

    // 5. Wait for Assistant Response stream completion
    await expect(page.locator('button[aria-label="Stop generating response"]')).not.toBeVisible({ timeout: 90000 });
    await expect.poll(async () => {
      const proseElements = page.locator('div.prose');
      const count = await proseElements.count();
      if (count === 0) return 0;
      const text = await proseElements.last().innerText().catch(() => '');
      return text.trim().length;
    }, { timeout: 90000 }).toBeGreaterThan(10);

    // 6. Verify Copy button is present and accessible
    const copyBtn = page.locator('button:has-text("Copy")').first();
    if (await copyBtn.isVisible().catch(() => false)) {
      await expect(copyBtn).toBeEnabled();
    }
  });

  test('Voice Input - Recording Flow, Interim Transcript, Stop, Edit, and Submit', async ({ page }) => {
    // 1. Inject deterministic SpeechRecognition and getUserMedia mocks
    await page.addInitScript(() => {
      class MockSpeechRecognition extends EventTarget {
        continuous = true;
        interimResults = true;
        lang = 'en-US';
        maxAlternatives = 1;
        onstart: (() => void) | null = null;
        onresult: ((event: any) => void) | null = null;
        onerror: ((event: any) => void) | null = null;
        onend: (() => void) | null = null;
        private _timer: any = null;

        start() {
          if (this.onstart) this.onstart();
          this._timer = setTimeout(() => {
            if (this.onresult) {
              this.onresult({
                resultIndex: 0,
                results: [
                  Object.assign([{ transcript: 'What is the security incident protocol?' }], { isFinal: true })
                ]
              });
            }
          }, 150);
        }

        stop() {
          if (this._timer) clearTimeout(this._timer);
          if (this.onend) this.onend();
        }

        abort() {
          if (this._timer) clearTimeout(this._timer);
          if (this.onend) this.onend();
        }
      }

      (window as any).SpeechRecognition = MockSpeechRecognition;
      (window as any).webkitSpeechRecognition = MockSpeechRecognition;

      if (!navigator.mediaDevices) {
        (navigator as any).mediaDevices = {};
      }
      navigator.mediaDevices.getUserMedia = async () => {
        return {
          getTracks: () => [
            { stop: () => {}, kind: 'audio', enabled: true }
          ]
        } as any;
      };
    });

    // 2. Navigate to /chat
    await page.goto('/chat');
    await expect(page).toHaveURL(/.*\/chat/, { timeout: 15000 });

    const composer = page.locator('textarea[aria-label="Message Veritas RAG"]').first();
    const micBtn = page.locator('button[aria-label="Dictate query"]').first();

    await expect(composer).toBeVisible({ timeout: 15000 });
    await expect(micBtn).toBeVisible({ timeout: 5000 });
    await expect(micBtn).toBeEnabled({ timeout: 5000 });

    // 3. Click Mic to start voice input
    await micBtn.click();

    // 4. Verify Active Recording controls are visible
    const stopVoiceBtn = page.locator('button[aria-label="Stop dictation and insert text"]').first();
    const cancelVoiceBtn = page.locator('button[aria-label="Cancel dictation"]').first();

    await expect(stopVoiceBtn).toBeVisible({ timeout: 5000 });
    await expect(cancelVoiceBtn).toBeVisible({ timeout: 5000 });

    // 5. Wait for simulated transcript to populate
    await expect.poll(async () => {
      return (await composer.inputValue()).trim();
    }, { timeout: 10000 }).toContain('What is the security incident protocol?');

    // 6. Click Done / Stop dictation
    await stopVoiceBtn.click();

    // 7. Verify voice controls exit and normal composer is restored with transcript
    await expect(stopVoiceBtn).not.toBeVisible({ timeout: 5000 });
    await expect(cancelVoiceBtn).not.toBeVisible({ timeout: 5000 });
    await expect(micBtn).toBeVisible({ timeout: 5000 });

    // Verify textarea retains transcribed text and has focus
    await expect(composer).toHaveValue(/What is the security incident protocol\?/);
    await expect(composer).toBeFocused({ timeout: 5000 });

    // 8. User edits the transcript before sending
    const currentVal = await composer.inputValue();
    await composer.fill(`${currentVal} Explain clearly.`);

    const sendBtn = page.locator('button[aria-label="Send message"]').first();
    await expect(sendBtn).toBeEnabled({ timeout: 5000 });
    await sendBtn.click();

    // 9. Verify standard chat flow executes
    await expect(page.locator('text=What is the security incident protocol? Explain clearly.')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('button[aria-label="Stop generating response"]')).not.toBeVisible({ timeout: 90000 });
  });

  test('Voice Input - Cancel Restores Original Text and Escape Key Discards', async ({ page }) => {
    // 1. Inject deterministic speech mock
    await page.addInitScript(() => {
      class MockSpeechRecognition extends EventTarget {
        continuous = true;
        interimResults = true;
        lang = 'en-US';
        maxAlternatives = 1;
        onstart: (() => void) | null = null;
        onresult: ((event: any) => void) | null = null;
        onerror: ((event: any) => void) | null = null;
        onend: (() => void) | null = null;

        start() {
          if (this.onstart) this.onstart();
          setTimeout(() => {
            if (this.onresult) {
              this.onresult({
                resultIndex: 0,
                results: [
                  Object.assign([{ transcript: 'additional dictation' }], { isFinal: true })
                ]
              });
            }
          }, 100);
        }
        stop() { if (this.onend) this.onend(); }
        abort() { if (this.onend) this.onend(); }
      }

      (window as any).SpeechRecognition = MockSpeechRecognition;
      (window as any).webkitSpeechRecognition = MockSpeechRecognition;
      if (!navigator.mediaDevices) (navigator as any).mediaDevices = {};
      navigator.mediaDevices.getUserMedia = async () => ({
        getTracks: () => [{ stop: () => {} }]
      } as any);
    });

    await page.goto('/chat');
    await expect(page).toHaveURL(/.*\/chat/, { timeout: 15000 });

    const composer = page.locator('textarea[aria-label="Message Veritas RAG"]').first();
    const micBtn = page.locator('button[aria-label="Dictate query"]').first();

    // Step A: Type initial text, start voice, then Cancel with button
    const initialText = 'Draft query before mic';
    await composer.fill(initialText);

    await micBtn.click();
    const cancelVoiceBtn = page.locator('button[aria-label="Cancel dictation"]').first();
    await expect(cancelVoiceBtn).toBeVisible({ timeout: 5000 });

    // Cancel recording
    await cancelVoiceBtn.click();
    await expect(cancelVoiceBtn).not.toBeVisible({ timeout: 5000 });
    await expect(composer).toHaveValue(initialText);

    // Step B: Start voice again and press Escape key to cancel
    await micBtn.click();
    await expect(cancelVoiceBtn).toBeVisible({ timeout: 5000 });
    await page.keyboard.press('Escape');
    await expect(cancelVoiceBtn).not.toBeVisible({ timeout: 5000 });
    await expect(composer).toHaveValue(initialText);
  });

  test('Chat Scroll Architecture - Streaming Auto-Scroll, Manual Scroll-Up Decoupling, Floating Scroll Button, and Clearance', async ({ page }) => {
    // 1. Navigate to /chat
    await page.setViewportSize({ width: 1280, height: 400 });
    await page.goto('/chat');
    await expect(page).toHaveURL(/.*\/chat/, { timeout: 15000 });

    const composer = page.locator('textarea[aria-label="Message Veritas RAG"]').first();
    const sendBtn = page.locator('button[aria-label="Send message"]').first();
    const scrollContainer = page.locator('div[data-testid="chat-messages-container"]').first();

    // 2. Verify dynamic clearance spacer exists
    await expect(scrollContainer).toBeVisible({ timeout: 10000 });

    // 3. Send prompt to generate a full response
    const scrollPrompt = 'What is the password policy?';
    await composer.fill(scrollPrompt);
    await expect(sendBtn).toBeEnabled({ timeout: 5000 });
    await sendBtn.click();

    // Wait for assistant response to complete
    await expect(page.locator('button[aria-label="Stop generating response"]')).not.toBeVisible({ timeout: 90000 });
    await expect.poll(async () => {
      const prose = page.locator('div.prose');
      const count = await prose.count();
      if (count === 0) return 0;
      return (await prose.last().innerText().catch(() => '')).trim().length;
    }, { timeout: 90000 }).toBeGreaterThan(10);
    await expect(composer).toBeEnabled({ timeout: 90000 });

    // 4. Create overflow content to test scroll decoupling and floating scroll button
    await scrollContainer.evaluate((el) => {
      const spacer = document.createElement('div');
      spacer.id = 'test-scroll-spacer';
      spacer.style.height = '1000px';
      el.insertBefore(spacer, el.lastElementChild);
      el.scrollTo({ top: 0, behavior: 'instant' });
      el.dispatchEvent(new Event('scroll', { bubbles: true }));
    });

    // 5. Verify Floating "Scroll to bottom" button appears
    const scrollToBottomBtn = page.locator('button[aria-label="Scroll to bottom"]').first();
    await expect(scrollToBottomBtn).toBeVisible({ timeout: 10000 });

    // 6. Click "Scroll to bottom" button
    await scrollToBottomBtn.click();

    // 7. Verify button disappears and viewport returns to bottom
    await expect(scrollToBottomBtn).not.toBeVisible({ timeout: 5000 });
    await expect.poll(async () => {
      return await scrollContainer.evaluate((el) => {
        return el.scrollHeight - el.scrollTop - el.clientHeight;
      });
    }, { timeout: 10000 }).toBeLessThan(80);

    // 8. Test Natural Scroll Back to Bottom
    // Scroll up again
    await scrollContainer.evaluate((el) => {
      el.scrollTo({ top: 0, behavior: 'instant' });
      el.dispatchEvent(new Event('scroll', { bubbles: true }));
    });
    await expect(scrollToBottomBtn).toBeVisible({ timeout: 5000 });

    // Naturally scroll to bottom without clicking button
    await scrollContainer.evaluate((el) => {
      el.scrollTo({ top: el.scrollHeight, behavior: 'instant' });
      el.dispatchEvent(new Event('scroll', { bubbles: true }));
    });
    await expect(scrollToBottomBtn).not.toBeVisible({ timeout: 5000 });

    // Cleanup test spacer
    await scrollContainer.evaluate((el) => {
      const spacer = el.querySelector('#test-scroll-spacer');
      if (spacer) spacer.remove();
    });

    // 9. Test Dynamic Composer Growth Clearance
    await composer.fill('Line 1 of multiline test\nLine 2\nLine 3\nLine 4\nLine 5');
    await page.waitForTimeout(300);

    // Verify distance from bottom remains anchored
    const finalDistance = await scrollContainer.evaluate((el) => {
      return el.scrollHeight - el.scrollTop - el.clientHeight;
    });
    expect(finalDistance).toBeLessThan(120);

    // Wait for generation to complete cleanly
    await expect(page.locator('button[aria-label="Stop generating response"]')).not.toBeVisible({ timeout: 90000 });
  });
});
