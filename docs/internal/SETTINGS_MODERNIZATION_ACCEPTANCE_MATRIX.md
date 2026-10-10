# VERITAS-RAG — SETTINGS MODERNIZATION ACCEPTANCE MATRIX
## Requirement-by-Requirement Verification & Quality Certification Criteria

- **Date:** 2026-10-10
- **Stage:** Planning & Pre-Implementation Gate
- **Status Legend:**
  - `READY FOR EXECUTION`: Test criteria defined, implementation planned in WP-0–WP-8.
  - `NOT RUN (PRE-IMPLEMENTATION)`: Test awaiting code execution.
  - `FAIL (CURRENT DEFECT)`: Current baseline behavior confirmed broken during audit.

---

## 1. Acceptance Criteria Matrix

| Req ID | Domain | Requirement Statement | Verification Method | Pre-Impl Status | Target Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **AC-01** | Notifications | User notification preferences survive page reload and persist in database. | Automated API test + browser reload | **FAIL (CURRENT DEFECT)**<br>*(Pydantic schema strips payload)* | Payload saved to PostgreSQL `users.preferences`, re-hydrated on reload with 100% fidelity. |
| **AC-02** | Notifications | Persistent in-app notifications stored in database with workspace tenant isolation. | Pytest integration test | **FAIL (CURRENT DEFECT)**<br>*(No DB table exists)* | Notifications queryable via `GET /notifications`; cross-tenant access returns empty or 403. |
| **AC-03** | Notifications | Navbar bell displays accurate numeric unread count from server on cold load. | Vitest component + REST probe | **FAIL (CURRENT DEFECT)**<br>*(Bell state ephemeral)* | Badge fetches `/notifications/unread-count` on mount and displays exact count with `role="status"`. |
| **AC-04** | Notifications | Navbar popover lists recent notifications with category icons and deep link to settings. | Vitest component test | **FAIL (CURRENT DEFECT)**<br>*(Bell popover isolated)* | Top 5–8 notifications render; footer links directly to `/settings/notifications`. |
| **AC-05** | Notifications | Mark-as-read updates server state and decrements unread badge immediately across tabs. | Pytest + WebSocket / Web Lock test | **NOT RUN (PRE-IMPLEMENTATION)** | `PATCH /notifications/{id}/read` succeeds with 200; badge decrements without reload. |
| **AC-06** | Notifications | Security events (password change, recovery) generate in-app notifications. | Integration test | **FAIL (CURRENT DEFECT)**<br>*(Auth events not connected)* | Completing password change creates notification record with `SECURITY` category and actionable link. |
| **AC-07** | Notifications | `/settings/notifications` provides dual-tab inbox and channel preference controls. | Vitest component test | **NOT RUN (PRE-IMPLEMENTATION)** | Users can filter by category, paginate history, and toggle email/in-app channels. |
| **AC-08** | AI Preferences| AI Preferences displays only real, active backend models (Gemini, OpenRouter). | Frontend inspection + Vitest | **FAIL (CURRENT DEFECT)**<br>*(Hardcoded fake options)* | Model dropdown displays only models registered in `ProviderRegistry` with accurate provider labels. |
| **AC-09** | AI Preferences| Temperature slider allows dual numeric and slider adjustment with semantic guides. | Vitest component test | **NOT RUN (PRE-IMPLEMENTATION)** | Slider and numeric input stay synchronized; values restricted between 0.0 and 1.0. |
| **AC-10** | AI Preferences| Saved AI settings are consumed by `ChatOrchestrator` and passed to LLM stream. | Pytest integration test | **FAIL (CURRENT DEFECT)**<br>*(Settings never consumed)* | `AIWrapperRequest` receives active temperature and custom system prompt at runtime. |
| **AC-11** | AI Preferences| Clear RBAC distinction between Workspace defaults (Admin) and user overrides. | RBAC permission test | **NOT RUN (PRE-IMPLEMENTATION)** | Non-admin sees read-only badge for workspace defaults; admin can patch workspace settings. |
| **AC-12** | Settings Shell| Settings navigation is accessible and fully usable on mobile viewports (< 768px). | Mobile viewport responsive test | **FAIL (CURRENT DEFECT)**<br>*(Sidebar hidden on mobile)* | Mobile users can navigate between all 7 settings tabs via horizontal scroll tab bar. |
| **AC-13** | Accessibility | High-contrast WCAG 2.1 AA parity across Dark and Light themes with reduced motion. | Automated Axe / Vitest audit | **NOT RUN (PRE-IMPLEMENTATION)** | Text contrast >= 4.5:1; zero motion or layout shift under `prefers-reduced-motion`. |
| **AC-14** | Security | Zero credentials, raw tokens, or document content leaked in notification payloads. | Security payload audit test | **READY FOR EXECUTION** | Notification titles and messages contain only sanitized metadata; no secrets exposed. |

---

## 2. Release Gates & Sign-Off Criteria

1. **Gate 1: Schema & Data Integrity:**
   - Alembic migration applies cleanly forward and backward (`upgrade` and `downgrade`).
   - Tenant isolation verified on all database operations.
2. **Gate 2: API & Runtime Functional Coverage:**
   - 100% pass on all new Pytest integration tests for notifications and AI preferences.
   - Zero regressions in existing authentication, workspace, or chat test suites.
3. **Gate 3: Frontend Quality & Responsiveness:**
   - 100% pass on all Vitest component tests.
   - Mobile and desktop responsive layouts certified.
   - No React console errors, memory leaks, or unhandled promise rejections.
4. **Gate 4: Single-Approval Completeness:**
   - Both pages (`/settings/notifications` and `/settings/ai`) and the navbar bell verified working together as one unified system.
