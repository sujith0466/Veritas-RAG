# VERITAS-RAG — SETTINGS MODERNIZATION PREMIUM UI/UX DESIGN SPECIFICATION
## Comprehensive Design System, Tokens, Page Layouts & Component Guidelines

- **Date:** 2026-10-10
- **Lead:** Senior Staff Enterprise UI/UX Architect & Design Lead
- **Skill Engine:** `ui-ux-pro-max` (Domain: `style`, `ux`, `react`, `icons`)
- **Theme Support:** 100% Dark / Light / System Theme Parity

---

## 1. UI UX Pro Max Design Intelligence & Style Archetype

### 1.1 Archetype: AI-Native Enterprise SaaS
- **Visual Personality:** Purpose-built, precise, restrained, and trustworthy. Avoids consumer gradients, heavy neon glows, or gratuitous 3D artifacts.
- **Design Dials:**
  - **Variance (5/10):** Balanced, clean visual structure aligned to existing enterprise dashboards.
  - **Motion (4/10):** Restrained micro-interactions (150–250ms transitions, subtle badge scale, spring easing). Honors `prefers-reduced-motion`.
  - **Density (7/10):** Compact enterprise hierarchy (8–24px spacing rhythm) allowing dense data inspection without clutter.

### 1.2 Color Strategy & Semantic Token Mapping

| Token Name | Light Mode Hex | Dark Mode Hex | Usage |
| :--- | :--- | :--- | :--- |
| `--color-background` | `#F8FAFC` (Slate 50) | `#0B0F19` (Deep Charcoal) | Canvas background |
| `--color-surface` | `#FFFFFF` | `#111827` (Gray 900) | Standard cards and containers |
| `--color-surface-elevated`| `#FFFFFF` | `#1F2937` (Gray 800) | Modals, popovers, floating menus |
| `--color-border` | `#E2E8F0` (Slate 200)| `#374151` (Gray 700) | Structural card and panel borders |
| `--color-border-subtle` | `#F1F5F9` | `#1F2937` | List item dividers |
| `--color-primary` | `#6366F1` (Indigo 500)| `#818CF8` (Indigo 400)| Interactive controls, active states |
| `--color-primary-subtle` | `#EEF2FF` | `#312E81` (10% tint) | Selected backgrounds, chips |
| `--color-success` | `#10B981` (Emerald) | `#34D399` | Document indexed, healthy scans |
| `--color-warning` | `#F59E0B` (Amber) | `#FBBF24` | Quota thresholds, circuit breakers |
| `--color-destructive` | `#EF4444` (Rose) | `#F87171` | Security alerts, failed ingestion |
| `--color-info` | `#0EA5E9` (Sky) | `#38BDF8` | Ingestion in progress, system updates|

### 1.3 Typography Hierarchy
- **Primary Font:** Inter (`sans-serif`), weight range 400 (regular), 500 (medium), 600 (semibold).
- **Numeric & Timestamp Font:** Inter with `tabular-nums` for timestamps, unread counters, and token budgets to eliminate layout jitter.
- **Scale:**
  - Page Title: `text-2xl font-bold tracking-tight text-foreground` (24px)
  - Section Header: `text-base font-semibold text-foreground` (16px)
  - Card Body / Form Label: `text-sm font-medium text-foreground` (14px)
  - Helper / Subtitle / Timestamps: `text-xs text-muted-foreground` (12px)
  - Micro Badges: `text-[11px] font-semibold tracking-wide uppercase` (11px)

---

## 2. Shared Shell Navigation Modernization (`SettingsLayout.tsx`)

### 2.1 The Responsive Defect & Resolution
- **Defect:** Currently, the desktop navigation `<aside className="hidden md:block">` disappears on mobile, leaving no way to switch tabs.
- **Modernized Layout Specification:**
  - **Desktop (>= 768px):** Retains vertical sidebar with refined active indicator pill, icon alignment, and border divider.
  - **Mobile (< 768px):** Implements a horizontal overflow tab bar (`overflow-x-auto scrollbar-none flex gap-2 border-b border-border pb-3 mb-6 px-4`) with scroll snap and touch padding.
- **Tab Item Navigation Structure:**
  1. Profile (`/settings/profile`)
  2. Security (`/settings/security`)
  3. **Notifications** (`/settings/notifications`) — Includes real-time unread badge counter pill!
  4. **AI Preferences** (`/settings/ai`)
  5. Workspace (`/settings/workspace`)
  6. Webhooks (`/settings/webhooks`)
  7. Privacy (`/settings/privacy`)

---

## 3. Workstream A: Premium Notifications Experience

### 3.1 Global Navbar Bell & Notification Popover (`NotificationBell.tsx`)

#### Visual & Interaction Specification
- **Trigger Button:**
  - High-precision 36x36px icon button (`h-9 w-9 rounded-lg border border-transparent hover:border-border hover:bg-muted/80`).
  - Active hover micro-interaction: Subtle 10° rotation on the bell icon (`group-hover:rotate-12 transition-transform duration-200 motion-reduce:group-hover:rotate-0`).
  - **Unread Badge:** When `unreadCount > 0`, renders a tabular numeric pill:
    ```tsx
    <span
      role="status"
      aria-atomic="true"
      className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold text-white shadow-sm"
    >
      {unreadCount > 99 ? '99+' : unreadCount}
    </span>
    ```
- **Popover Dropdown Panel:**
  - Position: Pinned to bottom-right of bell trigger (`align="end" sideOffset={8}`).
  - Dimensions: Width `380px`, max-height `480px`.
  - Surface Treatment: Subtle glassmorphism:
    `bg-surface-elevated/95 backdrop-blur-md border border-border shadow-2xl rounded-xl overflow-hidden`.
  - Header:
    - Left: "Notifications" title with total unread pill.
    - Right: "Mark all read" button (`text-xs text-primary hover:underline font-medium`).
  - Content Stream:
    - Lists latest 5–8 unread and recent notifications.
    - Category icons with semantic colors:
      - Document Ingestion: FileText (Blue / Info)
      - Security Alert: ShieldAlert (Rose / Destructive)
      - AI Reliability / Circuit Breaker: AlertTriangle (Amber / Warning)
      - System: Info (Slate / Neutral)
    - Clickable card routes to destination (e.g. document viewer, security settings).
  - Footer:
    - Pinned bottom bar: "View all notifications in Settings" linking to `/settings/notifications`.

### 3.2 Full Notification Center (`/settings/notifications`)

#### Layout Architecture
The modernized `/settings/notifications` page features a cohesive **dual-mode interface**:

```text
┌────────────────────────────────────────────────────────────────────────┐
│  Settings  >  Notifications                                            │
│  Manage workspace notifications, view alert history, and channels.     │
├────────────────────────────────────────────────────────────────────────┤
│  [ Notifications Inbox (3) ]        [ Notification Preferences ]       │
├────────────────────────────────────────────────────────────────────────┤
│  Filters: [ All ]  [ Unread ]  [ Documents ]  [ Security ]  [ AI ]     │
├────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 🛡️ Security Alert: Password Changed                  10m ago  •  │  │
│  │ Your account password was changed from Chrome on Windows.        │  │
│  │ [ View Security Settings ]                                       │  │
│  ├──────────────────────────────────────────────────────────────────┤  │
│  │ 📄 Document Ingestion Completed                      1h ago      │  │
│  │ "Q3_Financial_Report.pdf" successfully indexed into Qdrant.      │  │
│  │ [ View Document ]                                                │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  [ Showing 1-10 of 42 notifications ]              [ < Prev ] [ Next > ]│
└────────────────────────────────────────────────────────────────────────┘
```

#### Tab 1: Notifications Inbox & Alert History
- **Category Filter Pills:** Segmented buttons filtering by `ALL`, `UNREAD`, `SECURITY`, `DOCUMENT`, `AI_RELIABILITY`.
- **Card States:**
  - **Unread Card:** Elevated subtle tint (`bg-primary/5 dark:bg-primary/10 border-l-4 border-l-primary`).
  - **Read Card:** Clean neutral surface with subtle border.
  - **Hover Micro-interaction:** Displays action menu (Mark as Read / Dismiss) on hover.
  - **Action Button:** Contextual button linking directly to verified target (e.g., `/documents?id=...` or `/settings/security`).

#### Tab 2: Notification Preferences & Channels
- **In-App Channel:** Toggle subscriptions for Document Processing, AI System Alerts, Workspace Member changes.
- **Email Channel:**
  - Toggle Security Alerts (Mandatory recommended badge).
  - Toggle Ingestion Completion Digest.
  - Weekly Digest Schedule: Clearly displays cadence (e.g. "Every Monday at 09:00 UTC") with active status.

---

## 4. Workstream B: Premium AI Preferences Experience

### 4.1 Scope & Hierarchy Architecture

The interface explicitly resolves the ambiguity between **Workspace AI Configuration** and **Personal Interaction Overrides**:

```text
┌────────────────────────────────────────────────────────────────────────┐
│  Settings  >  AI Preferences                                           │
│  Configure workspace default language models, system prompt, and limits.│
├────────────────────────────────────────────────────────────────────────┤
│  🛡️ Workspace Configuration [ Role: Administrator (Editable) ]         │
├────────────────────────────────────────────────────────────────────────┤
│  Primary Language Model                                                │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Active: Google Gemini 2.0 Flash (Primary)                       │  │
│  │  Provider: Google DeepMind  •  Context: 1M tokens  •  Fast       │  │
│  │  [ Switch Model: Gemini 2.0 Flash | OpenRouter Llama 3.3 | ... ] │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  Generation Temperature: 0.10 (Deterministic & Factual)                │
│  [───────●───────────────────────────────────────────────────────]     │
│  0.0 Factual               0.2 Standard RAG             0.7 Creative   │
│                                                                        │
│  Workspace System Instructions (Prompt Override)                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Add custom instructions prepended to all grounded generation...  │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  Chars: 142 / 5,000  •  Est. Tokens: ~35      [ Reset to Default ]     │
├────────────────────────────────────────────────────────────────────────┤
│  [ Sticky Bar: Unsaved Changes ]              [ Discard ]  [ Save AI ] │
└────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Control Specifications

#### 1. Supported Model Catalogue Selector
- Replaces unverified hardcoded options with real, validated backend models:
  - **Google Gemini 2.0 Flash** (`gemini-2.0-flash` via Gemini Provider) — Fast, multimodal, factual default.
  - **Google Gemini 2.0 Flash Lite** (`gemini-2.0-flash-lite`) — Cost-efficient routing model.
  - **Meta Llama 3.3 70B Instruct** (`meta-llama/llama-3.3-70b-instruct` via OpenRouter).
  - **OpenAI GPT-4o Mini** (`openai/gpt-4o-mini` via OpenRouter).
- Each model card displays:
  - Model Name & Provider Badge.
  - Context Window & Latency Tier indicator.
  - Grounding reliability badge.

#### 2. Dual Temperature Controller
- Combines an interactive range slider (`min="0.0" max="1.0" step="0.05"`) with an adjacent high-precision numeric stepper (`Input type="number"`).
- Semantic Guide Marks:
  - `0.00 – 0.15`: Strict Grounding / Deterministic (Recommended for Compliance & RAG).
  - `0.20 – 0.40`: Balanced Enterprise (Default Veritas RAG).
  - `0.50 – 1.00`: Exploratory / Conversational.

#### 3. System Prompt Editor & Safety Counter
- Monospace font preview with auto-resizing textarea.
- Live character counter (`142 / 5,000 characters`) with token estimation counter (`~35 tokens`).
- "Reset to System Default" button with a confirmation modal explaining the restored baseline.

#### 4. Dirty State & Floating Action Bar
- When any field deviates from persisted baseline, a floating bottom action banner slides up smoothly (`slide-in-from-bottom-4 duration-200`):
  - "You have unsaved changes in AI Preferences."
  - "Discard" button (reverts form state to loaded baseline).
  - "Save AI Preferences" button with loading spinner and disabled state when clean.

---

## 5. Accessibility, Theme & Motion Rules

### 5.1 WCAG 2.1 AA Compliance Checklist
- **Color Contrast:** All body text meets `>= 4.5:1` ratio against surface backgrounds in both light and dark modes. Non-text UI controls and borders meet `>= 3:1`.
- **Keyboard Traversal:** Every interactive element has an explicit focus ring (`focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2`).
- **Screen Reader Semantics:**
  - Notification unread counter uses `<span role="status" aria-atomic="true">`.
  - Notification cards use semantic list tags (`<ul role="list">`, `<li role="listitem">`).
  - Temperature slider provides `aria-valuemin="0" aria-valuemax="1" aria-valuenow={temperature} aria-valuetext={`${temperature.toFixed(2)} - ${label}`}`.
- **Motion Reduction:** All animations wrap with `motion-reduce:transition-none motion-reduce:animate-none`.
