# VERITAS-RAG — SETTINGS MODERNIZATION MASTER AUDIT
## Notifications, AI Preferences, Navbar Bell & Workspace Integration Forensic Report

- **Date:** 2026-10-10
- **Auditor:** Senior Staff Engineer, Enterprise Product Architect, Security Engineer, Premium UI/UX Lead
- **Project:** Veritas-RAG — Enterprise Knowledge Reliability Platform
- **Repository Baseline:** Commit `e614062c7af5a5dbff7420f0a90d95f7b64d5101` (`HEAD == origin/main`)
- **Status:** Complete Master Audit (Read-Only)

---

## 1. Executive Summary & Baseline Verification

### 1.1 Git Working Tree Baseline
- **Branch:** `main`
- **Commit HEAD:** `e614062c7af5a5dbff7420f0a90d95f7b64d5101` (synchronized with `origin/main`)
- **Working Tree:** Pristine (0 modified application files; `backend/tests/integration/api/v1/test_concurrent_password_change.py` untracked and verified ignored via `.gitignore`).
- **Containers:** All Docker containers (`api`, `worker`, `frontend`, `postgres`, `redis`, `qdrant`, `minio`) active and healthy.

### 1.2 Audit Verdicts
1. **Workstream A (Notifications):** **CRITICAL ARCHITECTURAL GAPS (P0/P1)**.
   - The `/settings/notifications` page is a decorative facade with 3 static toggles.
   - **Silent Data Loss Bug (P0):** `backend/api/v1/schemas/users.py:UserPreferencesSchema` defines only `ai: AISettingsSchema` with `model_config = {"extra": "ignore"}`. When the frontend saves notification toggles via `userService.updatePreferences`, Pydantic silently strips the `notifications` payload. Notification preferences are **never saved to the database**.
   - **Missing Persistence (P0):** There is **no `notifications` table** in the PostgreSQL schema. In-app notifications rely entirely on ephemeral Redis Pub/Sub broadcast over a single WebSocket endpoint (`/api/v1/notifications/ws`). If a user is offline or refreshes the page, all notifications are permanently lost.
   - **Missing REST API (P0):** The backend has zero REST endpoints to list notification history, query unread count, mark notifications as read, or perform bulk actions.
   - **Navbar Bell Disconnect (P1):** The global navbar bell (`NotificationBell.tsx`) stores incoming WebSocket payloads in ephemeral React component state (`useState([])`). On navigation or reload, the inbox completely wipes. It features no link to settings, no categories, no actionable links, and no persistent badge count.
   - **Security Notification Disconnect (P1):** Password change, recovery, and security events emit email notifications via `EmailProvider`, but are never published to the notification event bus.

2. **Workstream B (AI Preferences):** **RUNTIME DISCONNECT & PHANTOM SETTINGS (P1)**.
   - `AIPrefSettings.tsx` presents a model selector, temperature slider, and "Global System Prompt" textarea, saving them to `user.preferences.ai`.
   - **Runtime Disconnect (P1):** The chat execution pipeline (`ChatOrchestrator.stream_chat` and `AIWrapperService.stream_request`) **never reads `user.preferences.ai`**. `GenerationRequestDTOv2` hardcodes temperature to `0.1` and leaves `custom_system_prompt` unpopulated. Saved user AI preferences have **zero runtime effect on generation**.
   - **Model Catalogue Discrepancy (P2):** The frontend dropdown hardcodes proprietary models (`gpt-4-turbo`, `claude-3-opus`, `gemini-1.5-pro`). In reality, `ProviderRegistry` registers `gemini`, `openrouter`, and `v1_engine`. Standalone OpenAI and Anthropic SDKs are not active providers.
   - **Scope Ambiguity (P2):** The UI labels the prompt as "Global System Prompt - appended to all queries in your workspace", but saves it to personal user preferences. Workspace-wide AI configuration already exists authoritatively in `WorkspaceSettings.ai` (`workspace_settings.py`), governed by RBAC (Owner/Admin only).

3. **Shared Shell & UI/UX (P2):**
   - `SettingsLayout.tsx` completely hides navigation on mobile (`hidden md:block`) without providing mobile tabs or dropdown navigation, rendering Settings inaccessible on mobile devices.
   - Zero test coverage exists across both target pages and the navbar bell.

---

## 2. Workstream A: Notifications Deep Audit

### 2.1 Frontend Component Analysis

#### 2.1.1 NotificationSettings.tsx (`frontend/src/pages/settings/NotificationSettings.tsx`)
- **Current Lines:** 1–149.
- **Controls:** 3 switches:
  1. `General Email Alerts` ("Receive notifications when documents finish indexing...")
  2. `Security & Hallucination Alerts` ("Get immediate alerts if high-severity security intervention occurs...")
  3. `Weekly Digest` ("Receive a weekly summary of workspace queries...")
- **Load Flow:** Calls `userService.getProfile()` and reads `data.preferences?.notifications || {}`.
- **Save Flow:** Calls `userService.updatePreferences({ preferences: { ...user?.preferences, notifications: preferences } })`.
- **Observed Defect:** Because the backend Pydantic schema discards the `notifications` key, `data.preferences?.notifications` is always empty on reload. The user's preferences revert to defaults upon page refresh.
- **Missing Capabilities:**
  - No notification history or inbox view.
  - No distinction between In-App and Email channels.
  - No category subscriptions (System, Documents, Security, AI Reliability).
  - No unread management.

#### 2.1.2 NotificationBell.tsx (`frontend/src/components/common/NotificationBell.tsx`)
- **Current Lines:** 1–125.
- **Implementation:**
  ```typescript
  const wsUrl = `${protocol}//${window.location.host}/api/v1/notifications/ws?token=${token}`
  const ws = new WebSocket(wsUrl)
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    setNotifications(prev => [newNotif, ...prev].slice(0, 50))
    setHasUnread(true)
  }
  ```
- **Observed Defects:**
  1. **Ephemeral State:** All notifications live exclusively in `useState<Notification[]>([])`. Reloading the page or closing the tab empties the array.
  2. **Coarse Read Transition:** Simply clicking the bell button sets `hasUnread = false` and mutates the in-memory array (`n.read = true`). No backend call is made.
  3. **No Navigation or Deep Links:** Notification cards display raw strings (`n.type` and `document_id`) with no clickable action to open the document, session, or audit log.
  4. **No Error Recovery:** If WebSocket connection drops, there is no exponential backoff reconnection, no status indicator, and no HTTP polling fallback.
  5. **No Routing to Notification Center:** The popover contains no "View all notifications" link to `/settings/notifications`.

### 2.2 Backend & Data Persistence Architecture

#### 2.2.1 Route Inspection: `backend/api/v1/routes/notifications.py`
- **Total Lines:** 99.
- **Exposed Endpoints:**
  - `@router.websocket("/ws")`: Accepts WebSocket connections authenticated via query param `?token=...`. Subscribes to Redis Pub/Sub channel `workspace:{tenant_id}:notifications`.
- **Missing Endpoints:**
  - `GET /api/v1/notifications`: **MISSING** (Cannot list persisted notifications, paginate, or filter).
  - `GET /api/v1/notifications/unread-count`: **MISSING** (Cannot hydrate navbar unread badge on initial page load).
  - `PATCH /api/v1/notifications/{id}/read`: **MISSING** (Cannot mark notification read on server).
  - `POST /api/v1/notifications/read-all`: **MISSING** (Cannot clear unread status across devices).
  - `DELETE /api/v1/notifications/{id}`: **MISSING** (Cannot dismiss notifications).

#### 2.2.2 Database Models & Migrations
- Migration `20260815_6c11701a28c5_epic11_notifications.py` defines:
  - `circuit_breaker_events`
  - `health_scan_jobs`
  - `retrieval_sla_logs`
  - `workspace_webhooks`
  - `notification_delivery_logs`: Columns `type` (EMAIL/WEBHOOK), `target`, `payload_snapshot` (JSONB), `status` (PENDING/SUCCESS/FAILED), `attempt_count`, `next_retry_at`, `tenant_id`.
- **Database Verdict:** There is **NO `notifications` table** for in-app user notifications.
- **Required Model:** An in-app `Notification` entity:
  - `id`: UUID (Primary Key)
  - `tenant_id`: UUID (Workspace isolation)
  - `user_id`: UUID | None (User-specific or workspace-wide broadcast)
  - `category`: Enum (`SYSTEM`, `DOCUMENT`, `SECURITY`, `AI_RELIABILITY`)
  - `severity`: Enum (`INFO`, `SUCCESS`, `WARNING`, `CRITICAL`)
  - `title`: String(255)
  - `message`: Text
  - `action_url`: String(512) | None
  - `payload_json`: JSONB
  - `is_read`: Boolean (default False)
  - `read_at`: DateTime | None
  - `created_at`: DateTime (Indexed with tenant_id, is_read)

#### 2.2.3 Event Dispatcher & Producers (`backend/core/events/dispatcher.py`)
- `EventDispatcher.publish(event)` publishes events to Redis Pub/Sub channel `workspace:{tenant_id}:notifications`.
- **Active Producers:**
  - Ingestion pipeline: `DOCUMENT_UPLOADED`, `DOCUMENT_INGESTION_COMPLETED`, `DOCUMENT_INGESTION_FAILED`.
  - Reliability: `CIRCUIT_BREAKER_TRIPPED`, `KNOWLEDGE_DRIFT_DETECTED`.
- **Missing Security Producers:**
  - `PasswordResetService` (`backend/services/auth/password_reset_service.py`) triggers `send_password_changed_notification_email()`, but does **not** publish any event to `EventDispatcher`.
  - No events exist in `backend/core/events/types.py` for:
    - `SECURITY_PASSWORD_CHANGED = "security.password_changed"`
    - `SECURITY_RECOVERY_COMPLETED = "security.recovery_completed"`
    - `SECURITY_MFA_UPDATED = "security.mfa_updated"`

#### 2.2.4 User Preferences Schema Bug (`backend/api/v1/schemas/users.py`)
```python
# CURRENT IMPLEMENTATION:
class UserPreferencesSchema(BaseModel):
    ai: AISettingsSchema | None = None
    model_config = {"extra": "ignore"}

class UserPreferencesUpdate(BaseModel):
    preferences: UserPreferencesSchema
```
- **Consequence:** Any `notifications` key submitted to `PATCH /api/v1/users/me/preferences` is stripped out.
- **Required Fix:** Add `notifications: NotificationPreferencesSchema | None = None` to `UserPreferencesSchema`.

---

## 3. Workstream B: AI Preferences Deep Audit

### 3.1 Frontend Component Analysis (`frontend/src/pages/settings/AIPrefSettings.tsx`)
- **Current Lines:** 1–170.
- **Form State:**
  ```typescript
  const [formData, setFormData] = useState({
    default_model: 'gpt-4o',
    temperature: 0.2,
    system_prompt: '',
  })
  ```
- **Model Dropdown Options:**
  - `gpt-4o` (OpenAI)
  - `gpt-4-turbo` (OpenAI)
  - `claude-3-5-sonnet` (Anthropic)
  - `claude-3-opus` (Anthropic)
  - `gemini-1.5-pro` (Google)
- **Save Operation:** Calls `userService.updatePreferences({ preferences: { ...user?.preferences, ai: formData } })`.
- **Observed Defect:** The component operates under the assumption that it is configuring the workspace's generation engine ("Global System Prompt: Add custom instructions appended to all queries in your workspace"). However, it only updates the caller's personal profile.

### 3.2 Backend Runtime & Consumption Audit

#### 3.2.1 Provider Registry Reality (`backend/ai/registry.py`)
```python
cls.register("gemini", GeminiProvider)
cls.register("openrouter", OpenRouterProvider)
cls.register("v1_engine", V1EngineProvider)
```
- The backend contains concrete adapters **only** for:
  1. `gemini`: Uses Google Gemini API (`GEMINI_MODEL=gemini-2.0-flash`, `GEMINI_LITE_MODEL=gemini-2.0-flash-lite`).
  2. `openrouter`: Uses OpenRouter unified API (`OPENROUTER_MODELS=meta-llama/llama-3.3-70b-instruct,openai/gpt-4o-mini,google/gemini-2.5-flash`).
  3. `v1_engine`: Internal pipeline provider.
- Direct OpenAI SDK and Anthropic SDK are **not registered** in `ProviderRegistry`. Direct model identifiers like `claude-3-opus` or `gpt-4-turbo` fail if invoked directly.

#### 3.2.2 Chat Generation Consumption Path
1. **Chat Route:** `POST /api/v1/chat/sessions/{id}/stream` calls `ChatOrchestrator.stream_chat(...)`.
2. **ChatOrchestrator (`backend/modules/chat/services/chat_orchestrator.py:340`):**
   ```python
   req = AIWrapperRequest(
       session_id=uuid.UUID(session_id) if '-' in session_id else None,
       workspace_id=workspace_id,
       tenant_id=tenant_uuid,
       query=query,
       conversation_history=conversation_history,
       stream=True
   )
   ```
   Notice: `req` does **not** include `model`, `temperature`, or `custom_system_prompt`.
3. **AIWrapperService (`backend/ai/wrapper/service.py:209`):**
   ```python
   gen_request = GenerationRequestDTOv2(
       query=request.query,
       evidence_chunks=evidence_chunks,
       correlation_id=correlation_id,
       tenant_id=str(request.tenant_id),
       conversation_history=request.conversation_history or [],
       stream=True
       # temperature defaults to 0.1
       # guardrail_config.custom_system_prompt is None
   )
   ```
4. **StreamingGroundedGenerationService (`backend/modules/generation/services/streaming_generation_service.py:91`):**
   ```python
   llm_req = LLMRequest(
       prompt=request.query,
       system_instruction=evidence_block,
       tenant_id=str(request.tenant_id),
       workspace_id=str(getattr(request, "workspace_id", request.tenant_id)),
       conversation_history=getattr(request, "conversation_history", None),
       # temperature is None -> Provider falls back to config setting
   )
   ```
- **Audit Conclusion:** Saved user AI preferences (`user.preferences.ai`) are **never passed down the call chain**. They are completely phantom settings.

#### 3.2.3 Existing Canonical Workspace Settings (`backend/api/v1/schemas/workspace_settings.py`)
- `AISettings` already exists authoritatively in `WorkspaceSettings`:
  ```python
  class AISettings(BaseModel):
      default_model: str = Field("gpt-4o", min_length=1, max_length=100)
      fallback_model: str = Field("claude-3-5-sonnet", min_length=1, max_length=100)
      temperature: float = Field(0.2, ge=0.0, le=2.0)
      max_output_tokens: int = Field(4096, ge=256, le=128000)
      enable_streaming: bool = Field(True)
      system_prompt_override: str | None = Field(None, max_length=5000)
  ```
- **Precedence Hierarchy:**
  1. **System Default:** `backend/core/config/` (`gemini.py`, `openrouter.py`).
  2. **Workspace Canonical Setting:** `WorkspaceSettings.ai` (applies to all members within a tenant).
  3. **User Personal Preference:** `User.preferences.ai` (personal defaults / overrides where permitted).

---

## 4. Shared Shell & Layout Audit

### 4.1 Settings Navigation (`frontend/src/pages/settings/SettingsLayout.tsx`)
- Sidebar markup:
  ```tsx
  <aside className="w-64 flex-shrink-0 border-r border-border overflow-y-auto hidden md:block">
  ```
- **Critical Flaw:** On mobile viewports (`< 768px`), the navigation sidebar is hidden (`hidden md:block`), and **no alternative navigation mechanism** (horizontal scroll tabs, dropdown selector, or mobile drawer) is rendered. Mobile users are trapped on whatever page they initially land on.
- **Theme Support:** Clean token usage (`bg-background`, `border-border`, `text-primary`, `text-muted-foreground`), fully compatible with Dark/Light mode tokens in `globals.css`.

---

## 5. Comprehensive Capability Matrix

| Feature / Area | Scope | Claimed State | Actual Audit Verdict | Code Location |
| :--- | :--- | :--- | :--- | :--- |
| **User Notification Toggles** | Notifications | Functional | **PARTIAL / BROKEN** (Pydantic drops payload) | `users.py:44`, `NotificationSettings.tsx:49` |
| **Notification Persistence** | Notifications | Functional | **MISSING** (No DB table or repository) | `models/`, `migrations/` |
| **Notification REST APIs** | Notifications | Functional | **MISSING** (0 endpoints for list/read) | `routes/notifications.py` |
| **Navbar Notification Bell** | Navbar | Functional | **PARTIAL** (Ephemeral state, resets on reload) | `NotificationBell.tsx:18` |
| **Security Notification Stream**| Notifications | Integrated | **MISSING** (Auth events not published) | `password_reset_service.py` |
| **Weekly Digest Dispatcher** | Notifications | Functional | **MISSING** (No Celery beat or aggregation task)| `tasks/` |
| **AI Model Selector** | AI Preferences| Functional | **DISCONNECTED** (Options invalid; not wired) | `AIPrefSettings.tsx:96`, `registry.py` |
| **Temperature Control** | AI Preferences| Functional | **DISCONNECTED** (Hardcoded to 0.1 at runtime) | `AIPrefSettings.tsx:118`, `service.py:209` |
| **Global System Prompt** | AI Preferences| Functional | **DISCONNECTED** (Not passed to LLMRequest) | `AIPrefSettings.tsx:149`, `streaming_generation_service.py:91` |
| **Workspace Settings Hierarchy**| AI Preferences| Enforced | **PARTIAL** (Stored in WorkspaceSettings but ignored) | `workspace_settings.py:33` |
| **Mobile Settings Navigation** | Shell | Responsive | **BROKEN** (Sidebar hidden on `< 768px`) | `SettingsLayout.tsx:30` |
| **Automated Test Coverage** | Both Pages | Certified | **MISSING** (0 tests for either page or bell) | `frontend/src/tests/`, `backend/tests/` |

---

## 6. Actionable Prioritized Issues Log

| ID | Priority | Area | Summary | Remediation Required |
| :--- | :--- | :--- | :--- | :--- |
| **NOTIF-01** | **P0 (Blocker)** | Backend Schema | Pydantic strips `notifications` from user preferences | Add `NotificationPreferencesSchema` to `UserPreferencesSchema`. |
| **NOTIF-02** | **P0 (Blocker)** | Backend DB | Missing persistent `notifications` table | Create Alembic migration and SQLAlchemy `Notification` model with tenant isolation. |
| **NOTIF-03** | **P0 (Blocker)** | Backend API | Missing notification list, unread-count, and read mutations | Implement `GET /notifications`, `GET /notifications/unread-count`, `PATCH /notifications/{id}/read`, `POST /notifications/read-all`. |
| **NOTIF-04** | **P1 (High)** | Frontend | Navbar bell has ephemeral state and wipes on refresh | Wire `NotificationBell` to REST endpoints + WebSocket real-time updates. |
| **NOTIF-05** | **P1 (High)** | Frontend | `/settings/notifications` lacks notification center / history | Build full notification center inbox with tabs, category filters, and actionable cards. |
| **NOTIF-06** | **P2 (Medium)** | Security | Security lifecycle events missing from notifications | Hook password change and recovery events into in-app notification creator. |
| **AIPREF-01** | **P1 (High)** | Backend Pipeline | AI settings in preferences are never consumed at runtime | Wire workspace/user AI settings into `AIWrapperService` & `StreamingGroundedGenerationService`. |
| **AIPREF-02** | **P1 (High)** | Frontend | Hardcoded unsupported models in AI preferences dropdown | Align model catalogue with real active models from `ProviderRegistry` (`Gemini`, `OpenRouter`). |
| **AIPREF-03** | **P2 (Medium)** | Architecture | Ambiguity between Workspace AI Settings vs User Preferences | Clarify RBAC: Admin/Owner controls workspace defaults; Members control personal interaction prefs. |
| **SHELL-01** | **P2 (Medium)** | Frontend Shell | Mobile navigation missing in Settings | Add responsive mobile tab/dropdown navigation to `SettingsLayout.tsx`. |
| **TEST-01** | **P1 (High)** | Testing | Zero test coverage across both pages and navbar bell | Implement comprehensive Vitest component tests and Pytest integration tests. |
