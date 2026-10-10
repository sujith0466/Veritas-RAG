# VERITAS-RAG — SETTINGS MODERNIZATION MASTER IMPLEMENTATION PLAN
## Unified Implementation Architecture for Notifications, AI Preferences, Navbar Bell & Shell

- **Date:** 2026-10-10
- **Architect:** Senior Staff Engineer, Enterprise Product Architect, Security Engineer, QA Certification Lead
- **Execution Model:** Single-Approval Execution Model (One authorization executes all Work Packages WP-0 through WP-8)
- **Scope:** Notifications (`/settings/notifications`), AI Preferences (`/settings/ai`), Navbar Bell, Backend Services, Data Models, and Tests

---

## 1. Execution Principles & Single-Approval Protocol

1. **Single User Approval Mandate:** A single explicit user authorization initiates sequential execution of Work Packages **WP-0 through WP-8** in dependency order without pausing for mid-stream approvals.
2. **Preserve Frozen Baselines:** Do not alter the Appearance settings removal baseline, authentication session restoration baseline, or frozen Epic 1–15 features.
3. **Additive, Non-Destructive Migrations:** Database schema additions are strictly non-destructive (nullable foreign keys, indexed query columns).
4. **Security & Data Isolation:** Tenant isolation (`tenant_id`) is strictly enforced on every database query, count, mutation, and event dispatch. Sensitive payloads (tokens, passwords, raw document contents) are never stored in notification records.
5. **Real-to-Runtime Verification:** Every UI control must map to a real, working backend schema and runtime path.

---

## 2. Work Package Breakdown & Dependency Graph

```text
[WP-0: Baseline Verification]
         │
         ▼
[WP-1: Notification DB Model & Migration]
         │
         ├──────────────────────────────────────────┐
         ▼                                          ▼
[WP-2: Notification REST APIs & Producers]    [WP-3: User Preferences Schema Fix]
         │                                          │
         ├────────────────────┬─────────────────────┘
         ▼                    ▼
[WP-4: Navbar Bell Popover] [WP-5: Notification Center UI]
         │                    │
         └──────────┬─────────┘
                    ▼
[WP-6: AI Preferences Pipeline Wiring & UI]
                    │
                    ▼
[WP-7: SettingsLayout Mobile Navigation]
                    │
                    ▼
[WP-8: Integrated Testing & Final Certification]
```

---

## 3. Detailed Work Package Specifications

### Work Package 0: Baseline Verification & Safety Gates (WP-0)
- **Objective:** Re-verify repository cleanliness and test harness stability before commencing implementation.
- **Tasks:**
  - `TASK-0.1`: Verify Git branch is `main`, `HEAD` is `e614062c7af5a5dbff7420f0a90d95f7b64d5101`, and working tree is clean.
  - `TASK-0.2`: Verify `backend/tests/integration/api/v1/test_concurrent_password_change.py` remains untouched and ignored.
  - `TASK-0.3`: Run existing test suite (`pytest -m "not slow"` and `npm test -- --run`) to verify clean green baseline.

---

### Work Package 1: Notification Data Model & Migration (WP-1)
- **Objective:** Establish persistent storage for in-app workspace and user notifications.
- **Affected Files:**
  - `backend/models/entities/notification.py` (New model)
  - `backend/models/entities/__init__.py` (Model registration)
  - `backend/database/migrations/versions/<timestamp>_in_app_notifications.py` (New Alembic migration)
- **Specification:**
  ```python
  class NotificationCategory(str, enum.Enum):
      SYSTEM = "SYSTEM"
      DOCUMENT = "DOCUMENT"
      SECURITY = "SECURITY"
      AI_RELIABILITY = "AI_RELIABILITY"

  class NotificationSeverity(str, enum.Enum):
      INFO = "INFO"
      SUCCESS = "SUCCESS"
      WARNING = "WARNING"
      CRITICAL = "CRITICAL"

  class Notification(BaseModel):
      __tablename__ = "notifications"

      id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
      tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
      user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True, nullable=True) # Null = workspace-wide
      category: Mapped[str] = mapped_column(String(50), nullable=False, default=NotificationCategory.SYSTEM.value)
      severity: Mapped[str] = mapped_column(String(50), nullable=False, default=NotificationSeverity.INFO.value)
      title: Mapped[str] = mapped_column(String(255), nullable=False)
      message: Mapped[str] = mapped_column(Text, nullable=False)
      action_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
      payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
      is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
      read_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
      created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.UTC), nullable=False)
  ```
  - **Indexes:** Composite index on `(tenant_id, user_id, is_read, created_at)` for high-speed inbox queries.

---

### Work Package 2: Notification REST APIs & Event Bus Integration (WP-2)
- **Objective:** Expose secure, paginated REST endpoints and wire domain event producers into notification persistence.
- **Affected Files:**
  - `backend/api/v1/routes/notifications.py` (Add REST routes alongside WebSocket)
  - `backend/services/notification/notification_service.py` (New business logic service)
  - `backend/repositories/notification_repository.py` (Database repository)
  - `backend/core/events/dispatcher.py` (Persist incoming in-app events upon publishing)
  - `backend/services/auth/password_reset_service.py` (Emit security notification on password changes)
- **API Contracts:**
  1. `GET /api/v1/notifications`:
     - Params: `page=1`, `page_size=20`, `category=Optional[str]`, `unread_only=bool`.
     - Response: `{ items: NotificationDTO[], total: int, page: int, page_size: int, unread_count: int }`.
  2. `GET /api/v1/notifications/unread-count`:
     - Returns: `{ unread_count: int }`.
  3. `PATCH /api/v1/notifications/{id}/read`:
     - Marks individual notification as read.
  4. `POST /api/v1/notifications/read-all`:
     - Marks all unread notifications for calling user/workspace as read.
  5. `DELETE /api/v1/notifications/{id}`:
     - Soft-deletes or dismisses a notification.
- **Security Event Wiring:**
  - On password change completion in `PasswordResetService`, call:
    `notification_service.create_security_notification(user_id, tenant_id, title="Password Changed", message=..., action_url="/settings/security")`.

---

### Work Package 3: User Preferences Schema & Persistence Bug Fix (WP-3)
- **Objective:** Fix the silent data drop bug in `UserPreferencesSchema` so notification settings persist.
- **Affected Files:**
  - `backend/api/v1/schemas/users.py`
  - `backend/api/v1/routes/users.py`
- **Implementation:**
  ```python
  class NotificationPreferencesSchema(BaseModel):
      email_alerts: bool = True
      security_alerts: bool = True
      weekly_reports: bool = False
      in_app_document_alerts: bool = True
      in_app_system_alerts: bool = True

      model_config = {"extra": "ignore"}

  class UserPreferencesSchema(BaseModel):
      ai: AISettingsSchema | None = None
      notifications: NotificationPreferencesSchema | None = None

      model_config = {"extra": "ignore"}
  ```

---

### Work Package 4: Navbar Notification Bell & Popover Integration (WP-4)
- **Objective:** Transform decorative navbar bell into a real-time, stateful, persistent notification drawer.
- **Affected Files:**
  - `frontend/src/components/common/NotificationBell.tsx`
  - `frontend/src/services/notificationService.ts` (New frontend API client)
  - `frontend/src/stores/notificationStore.ts` (Zustand store for unread count & recent stream)
- **Key Capabilities:**
  - Initial hydration on mount via `GET /api/v1/notifications/unread-count` and `GET /api/v1/notifications?page_size=5`.
  - Real-time updates via WebSocket (`/api/v1/notifications/ws`) appending new items and bumping counter.
  - Fallback polling (60s interval) if WebSocket connection fails.
  - Radix UI Popover with subtle glassmorphism and keyboard escape.
  - Direct deep link to `/settings/notifications`.

---

### Work Package 5: Modernized Notification Center Page (WP-5)
- **Objective:** Deliver the complete, dual-tab Notification Center on `/settings/notifications`.
- **Affected Files:**
  - `frontend/src/pages/settings/NotificationSettings.tsx`
  - `frontend/src/components/notifications/NotificationCard.tsx` (New component)
  - `frontend/src/components/notifications/NotificationFilters.tsx` (New component)
- **Key Capabilities:**
  - **Tab 1: Notification Inbox & History:**
    - Filter pills (All, Unread, Documents, Security, AI Reliability).
    - "Mark all as read" button.
    - Paginated list with skeleton loading and empty state.
    - Clickable action buttons navigating to documents or security settings.
  - **Tab 2: Notification Preferences:**
    - Granular channel toggles (In-App vs Email).
    - Clear honest explanation of cadence and active channels.
    - Optimistic saving with rollback on error.

---

### Work Package 6: AI Preferences Wiring & Precedence Integration (WP-6)
- **Objective:** Connect AI Preferences to the actual chat generation pipeline and align UI with real supported models.
- **Affected Files:**
  - `frontend/src/pages/settings/AIPrefSettings.tsx`
  - `backend/modules/chat/services/chat_orchestrator.py`
  - `backend/ai/wrapper/service.py`
  - `backend/services/workspace/settings_service.py`
- **Key Capabilities:**
  - **Model Catalogue Realignment:** Replace hardcoded models with active backend models:
    - Gemini 2.0 Flash (`gemini-2.0-flash`)
    - Gemini 2.0 Flash Lite (`gemini-2.0-flash-lite`)
    - OpenRouter Llama 3.3 70B (`meta-llama/llama-3.3-70b-instruct`)
    - OpenRouter GPT-4o Mini (`openai/gpt-4o-mini`)
  - **Dual-Scope Interface:**
    - For Admins/Owners: Modifies Workspace Default AI settings (persisted to `WorkspaceSettings.ai` via `workspaceSettingsService`).
    - For Members: Modifies personal default overrides where permitted; displays Workspace defaults badge.
  - **Chat Pipeline Wiring:**
    - `ChatOrchestrator` resolves active AI settings (from `WorkspaceSettings.ai` merged with user preferences).
    - Passes `temperature` and `custom_system_prompt` to `AIWrapperRequest` and `GenerationRequestDTOv2`.
    - `StreamingGroundedGenerationService` passes them to `LLMRequest`.
  - **Premium UI Controls:** Dual temperature slider + numeric stepper, character counter on system prompt, dirty state bottom bar.

---

### Work Package 7: Shared Settings Shell Mobile Navigation (WP-7)
- **Objective:** Fix the responsive navigation flaw in `SettingsLayout.tsx`.
- **Affected Files:**
  - `frontend/src/pages/settings/SettingsLayout.tsx`
- **Implementation:**
  - On desktop (>= 768px): Vertical sidebar navigation.
  - On mobile (< 768px): Horizontal scroll tab bar with pill indicators and unread count badge on Notifications tab.

---

### Work Package 8: Integrated Testing, Regression & Final Certification (WP-8)
- **Objective:** Comprehensive end-to-end verification and regression testing.
- **Affected Files:**
  - `frontend/src/tests/NotificationSettings.test.tsx` (New Vitest suite)
  - `frontend/src/tests/NotificationBell.test.tsx` (New Vitest suite)
  - `frontend/src/tests/AIPrefSettings.test.tsx` (New Vitest suite)
  - `backend/tests/integration/api/v1/test_notifications_api.py` (New Pytest suite)
  - `backend/tests/integration/api/v1/test_ai_preferences_pipeline.py` (New Pytest suite)
- **Verification Gates:**
  1. Unit tests pass with 100% success.
  2. Integration tests verify tenant isolation on notifications.
  3. End-to-end browser verification of navbar bell, notification center, and AI preferences.
  4. Working tree verified clean with zero unexpected diffs.

---

## 4. Rollback Strategy & Risk Mitigation

- **Database Rollback:** The Alembic migration has a fully reversible `downgrade()` dropping only the new `notifications` table and indexes. Existing tables are untouched.
- **API Graceful Fallback:** If the `notifications` table has no records or error occurs, the API returns empty list with 200 OK to prevent breaking the UI shell.
- **Generation Fallback:** If workspace AI settings fail to resolve, `ChatOrchestrator` falls back to default settings configuration (`temperature=0.1`, `model=gemini-2.0-flash`).
