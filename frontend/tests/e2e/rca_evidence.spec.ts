import { test, expect, chromium } from '@playwright/test';

test('Collect RCA Evidence via CDP', async () => {
  const browser = await chromium.launch({ devtools: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const evidence = {
    supabase_signup: null,
    supabase_session: null,
    fetch_profile_retries: [],
    fetch_profile_failure: null,
    clearAuth_stack: null,
    navigation_timeline: []
  };

  // Mock Backend Health
  await page.route('**/api/v1/health', route => route.abort('failed'));
  await page.route('**/api/v1/vectors/health', route => route.abort('failed'));
  
  // Mock /auth/me failure
  await page.route('**/auth/me', route => {
    evidence.fetch_profile_retries.push({ url: route.request().url(), time: Date.now() });
    route.abort('failed');
  });

  // Mock Supabase SignUp Success
  await page.route('**/auth/v1/signup*', async (route) => {
    evidence.supabase_signup = { url: route.request().url(), method: route.request().method(), postData: route.request().postData() };
    const mockBody = {
      access_token: 'fake-jwt',
      token_type: 'bearer',
      expires_in: 3600,
      refresh_token: 'fake-refresh',
      user: { id: 'test-user', email: 'test.admin@example.com' }
    };
    evidence.supabase_session = { status: 200, body: mockBody };
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockBody)
    });
  });

  // Track failed auth/me responses internally if any somehow bypass mock
  page.on('response', async response => {
    const url = response.url();
    if (url.includes('/auth/me')) {
      const status = response.status();
      if (status >= 400 || status === 0) {
        evidence.fetch_profile_failure = { status, url };
      }
    }
  });

  // 2. Monitor Navigation
  page.on('framenavigated', frame => {
    if (frame === page.mainFrame()) {
      evidence.navigation_timeline.push({ url: frame.url(), time: Date.now() });
    }
  });

  // 3. Attach CDP
  const client = await page.context().newCDPSession(page);
  await client.send('Debugger.enable');
  await client.send('Runtime.enable');
  await client.send('Debugger.setPauseOnExceptions', { state: 'all' });

  client.on('Debugger.paused', async (params) => {
    const callFrames = params.callFrames;
    const stack = callFrames.map(f => `${f.functionName} (${f.url}:${f.location.lineNumber})`);
    
    const isAuthError = stack.some(s => s.includes('fetchBackendProfile') || s.includes('clearAuth') || s.includes('AuthProvider'));
    
    if (isAuthError && !evidence.clearAuth_stack) {
      evidence.clearAuth_stack = stack;
    }
    await client.send('Debugger.resume');
  });

  // Navigate to register
  await page.goto('http://localhost:5174/auth/register?role=admin');
  await page.waitForTimeout(1000);

  // Fill form
  await page.fill('input[name="workspaceName"]', 'Test Workspace');
  await page.fill('input[name="fullName"]', 'Test Admin');
  await page.fill('input[name="email"]', 'test.admin@example.com');
  await page.fill('input[name="password"]', 'Password123!');
  await page.fill('input[name="confirmPassword"]', 'Password123!');
  await page.check('input[name="acceptTerms"]');

  // Click Register
  await page.click('button[type="submit"]');

  // Wait for redirect to login (the rollback)
  await page.waitForURL('**/auth/login', { timeout: 15000 }).catch(() => {});

  // For fetch_profile_failure, if it was aborted by route, response event doesn't fire. 
  // We can just assert it failed via the retries length.
  if (evidence.fetch_profile_retries.length > 0) {
     evidence.fetch_profile_failure = { status: 0, url: '**/auth/me' };
  }

  console.log("=== RCA EVIDENCE ===");
  console.log(JSON.stringify(evidence, null, 2));

  await browser.close();
});
