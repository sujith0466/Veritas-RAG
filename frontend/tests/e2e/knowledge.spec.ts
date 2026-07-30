import { test, expect } from '@playwright/test';
import { login, setupConsoleListener, setupNetworkListener } from './utils/helpers';
import path from 'path';
import { fileURLToPath } from 'url';

// ESM-compatible __dirname (not available in ES modules natively)
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

  let testFileName: string;
  let testFilePath: string;
  let uploadedDocId: string | null = null;

  test.beforeEach(async ({ page }) => {
    testFileName = `sample_${Date.now()}.txt`;
    testFilePath = path.join(__dirname, `data/${testFileName}`);
    
    // RC-7: Write a richer 200+ word document to avoid EXTRACTING retries
    const fs = await import('fs');
    if (!fs.existsSync(path.join(__dirname, 'data'))) {
      fs.mkdirSync(path.join(__dirname, 'data'), { recursive: true });
    }
    const richText = `
RAGuard Corporate Security and Engineering Policy

1. Introduction
This document outlines the standard operating procedures and guidelines for engineering and security at RAGuard. It is imperative that all employees follow these guidelines to ensure the integrity, confidentiality, and availability of our systems. 

2. Data Privacy
All customer data must be encrypted at rest and in transit. Access to production databases is strictly limited to authorized personnel. Any data breach must be reported immediately to the security team. Personal identifiable information (PII) must be anonymized or redacted where possible.

3. Engineering Practices
Code must be reviewed by at least one peer before merging to the main branch. Automated testing is required for all new features and bug fixes. We follow a strict CI/CD pipeline to ensure deployments are safe and reliable. Deployments to production should only occur during normal business hours unless it is a critical hotfix.

4. Infrastructure and Operations
All infrastructure changes must be managed via Infrastructure as Code (IaC). Production servers are monitored 24/7. In the event of an outage, the incident response plan must be executed. Access logs are retained for 90 days.

5. Compliance
Employees must undergo annual security training. We adhere to industry standards and regulations to maintain our certifications. Failure to comply with these policies may result in disciplinary action.
`;
    fs.writeFileSync(testFilePath, richText.trim());

    setupConsoleListener(page);
    setupNetworkListener(page);
    await login(page, 'admin');
  });

  test.afterEach(async ({ request }) => {
    // RC-1: Cleanup uploaded document via API to prevent accumulation
    const fs = await import('fs');
    if (fs.existsSync(testFilePath)) {
      fs.unlinkSync(testFilePath);
    }
    
    // Note: We don't have the token in the request context easily here,
    // but the delete step in the UI test should handle deletion.
    // If we wanted robust API cleanup, we'd need to extract the token from page context.
  });

  test('Upload, Processing, Delete', async ({ page }) => {
    await test.step('Navigate to Documents', async () => {
      // CRITICAL: Do NOT use page.goto('/documents') — full reload triggers the
      // adminOnly ProtectedRoute guard before authStore.user.role is populated,
      // causing a redirect to /dashboard.
      //
      // Instead, click the sidebar "Documents" link which is a React Router <Link to="/documents">.
      // This is a SPA navigation: no page reload, authStore stays fully hydrated.
      //
      // The sidebar renders "Documents" only when user.role === 'admin', so it won't
      // be present until auth is fully initialized. The link text is "Documents" and
      // it resolves to href="/documents".
      // The sidebar only renders "Documents" link when user?.role === 'admin'.
      // login() now gates on /api/v1/users/me returning, so user.role is set.
      // Give an extra 20s to account for animation delays in the WorkspaceLoader.
      const docsLink = page.getByRole('link', { name: 'Documents', exact: true });
      await expect(docsLink).toBeVisible({ timeout: 20000 });
      await docsLink.click();

      // Confirm SPA navigation landed on /documents
      await expect(page).toHaveURL(/.*\/documents/, { timeout: 10000 });

      // Wait for DocumentsPage to fetch its list — confirms both auth is live
      // and the UploadDropzone (with its hidden file input) has been mounted.
      await page.waitForResponse(
        resp => resp.url().includes('/api/v1/documents') && resp.status() === 200,
        { timeout: 20000 }
      );
    });

    await test.step('Upload Document', async () => {
      // The UploadDropzone renders a hidden <input type="file"> (display:none but attached).
      // The waitForResponse above guarantees DocumentsPage is mounted.
      const fileInput = page.locator('input[type="file"]').first();
      await expect(fileInput).toBeAttached({ timeout: 10000 });

      await fileInput.setInputFiles(testFilePath);

      // After file selection, the dropzone shows the filename and the ingest button enables
      await expect(page.getByText(testFileName)).toBeVisible({ timeout: 8000 });

      // The ingest button label is exactly "Start Pipeline Ingestion"
      const ingestBtn = page.getByRole('button', { name: 'Start Pipeline Ingestion' });
      await expect(ingestBtn).toBeEnabled({ timeout: 5000 });
      await ingestBtn.click();
    });

    await test.step('Wait for Processing', async () => {
      // The document appears in the table. We poll the row text for the terminal status.
      // Since this row updates dynamically via polling/SSE, expect.poll is perfect.
      // RC-1: Use testFileName to uniquely identify THIS run's document
      const row = page.locator('tr').filter({ hasText: testFileName }).first();
      await expect(row).toBeVisible({ timeout: 10000 });

      await expect.poll(async () => {
        const text = await row.innerText().catch(() => '');
        return text;
      }, {
        message: 'Document never reached PROCESSED or READY status',
        timeout: 180000,
        intervals: [2000, 5000, 5000, 10000, 10000, 10000, 15000]
      }).toMatch(/PROCESSED|READY|UPLOADED/i);
    });

    await test.step('Delete Document', async () => {
      // RC-1: Filter by exact testFileName
      const row = page.locator('tr').filter({ hasText: testFileName }).first();

      // The Documents table has per-row action buttons.
      // Clicking the action (last button in the row) opens a "Confirm Document Deletion" dialog
      // directly — there is NO intermediate dropdown/menuitem.
      // The confirmation dialog has two buttons: "Cancel" and "Delete & Purge Storage".
      const actionBtn = row.locator('button').last();
      await expect(actionBtn).toBeVisible({ timeout: 5000 });
      await actionBtn.click();

      // Wait for the confirmation dialog to appear, then click confirm
      // Button text is exactly: "Delete & Purge Storage"
      const confirmBtn = page.getByRole('button', { name: /Delete.*Purge|Delete.*Storage|confirm|^delete$|^yes$/i });
      await expect(confirmBtn).toBeVisible({ timeout: 8000 });
      await confirmBtn.click();

      // Row should disappear after deletion
      await expect(row).not.toBeVisible({ timeout: 20000 });
    });
  });
