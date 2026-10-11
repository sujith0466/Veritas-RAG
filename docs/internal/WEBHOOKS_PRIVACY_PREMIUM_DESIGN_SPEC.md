# Veritas-RAG — Webhooks & Privacy UI/UX Premium Design Specification

**Design System:** Veritas-RAG Dark Enterprise Design System  
**Skill Compliance:** UI/UX Pro Max  
**Typography:** Plus Jakarta Sans & JetBrains Mono (monospace tokens)  
**Surface Hierarchy:**
- Background Canvas: `#0B0F19`
- Card Surfaces: `#111827`
- Border Tokens: `border-border/50` / `rgba(255, 255, 255, 0.08)`
- Primary Accent: `#3B82F6` (Electric Blue)
- Destructive Danger: `#EF4444` (Crimson Red)

---

## 1. Webhook Settings (`/settings/webhooks`)
1. **Endpoint Registration Card:**
   - Input field with HTTPS requirement label.
   - Expandable Accordion for Subscribed Topics:
     - Wildcard selector `*`
     - Granular categorical checkboxes (Document Intelligence, Workspace & Members, Reliability & Drift, Security & Audit, System & Operations).
   - Monospace, copyable HMAC secret reveal container shown strictly on creation.
2. **Endpoint Management Cards:**
   - Monospace truncated URL with active status badge (`Active` emerald pill vs `Inactive` muted pill).
   - "Test Ping" button with spinner loading state.
   - "Filter Logs" action to inspect endpoint-specific delivery attempts.
   - "Enable/Disable" toggle and "Delete" actions.
3. **Delivery Logs Card:**
   - Data table displaying status code badges (`200 OK` in emerald, `Pending` in amber, `Failed` in red).
   - Event topic in monospace pill.
   - Target destination and attempt counter.
   - Timestamp formatted via date-fns.

---

## 2. Privacy & Data Governance (`/settings/privacy`)
1. **Export Account Archive Card:**
   - Explanatory copy outlining exported data categories (Profile, Preferences, Memberships, Notifications).
   - Security assurance pill highlighting automated scrubbing of password hashes, salts, tokens, and external tenant documents.
   - "Download Data Archive" button with asynchronous compilation state (`Compiling Archive...`).
2. **Danger Zone: Account Deactivation Card:**
   - Contained within crimson border (`border-red-500/20 bg-red-500/[0.02]`).
   - Clear warning explaining soft-delete semantics, immediate session invalidation, and sole-owner workspace restrictions.
   - Deactivation Confirmation Modal:
     - Warning shield icon.
     - Password re-authentication field with password masking.
     - Explicit typed confirmation (`DELETE`).
     - Error banner displaying sole-owner conflict or invalid password details.
