# RAGuard Enterprise QA Playwright Suite

This directory contains the automated Playwright End-to-End test suite for validating the RAGuard v1.0 UI workflows and network stability.

## Test Strategy
The suite is divided into modular sections:
- `@smoke`: Validates core API health and frontend navigation.
- `@auth`: Validates login, logout, and route protection.
- `@knowledge`: Validates document upload, processing states, and deletion.
- `@chat`: Validates sending prompts, streaming responses, and completion.
- `@retrieval`: Validates presence of citations, lack of "Unknown" source metadata, and reliability score generation.
- `@network`: Validates that no HTTP 500s or unhandled frontend exceptions occur during a full user flow.

*Note: These tests validate the UI functionality and DOM rendering. They do NOT evaluate the semantic correctness of AI-generated answers.*

## Execution
Run all tests:
```bash
npm run test:e2e
```

Run specific tags:
```bash
npm run test:e2e:smoke
npm run test:e2e:auth
npm run test:e2e:knowledge
npm run test:e2e:chat
npm run test:e2e:retrieval
npm run test:e2e:network
```

## Reporting
The suite automatically takes screenshots, records videos, and preserves full traces on failure.
An HTML report is generated on every run and can be viewed using:
```bash
npm run test:e2e:report
```

## Continuous Integration (CI)
The suite is configured to run efficiently in CI environments (disabling `test.only`, enabling 2 retries, and limiting workers to 1 to avoid race conditions). Test results are exported in both HTML and JSON formats.
