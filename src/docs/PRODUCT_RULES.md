# WorkTicket Product Rules

## Manual-first (v1) — locked decision

**WorkTicket v1 is a manual SaaS platform.**

AI is a **future enhancement** dependent on external funding or GPU infrastructure. **No AI logic is implemented in production until explicitly enabled** by product leadership.

### Official position

| Rule | Status |
|------|--------|
| AI is part of v1 product | ❌ No |
| AI is a workflow dependency | ❌ No |
| AI backend calls from client apps | ❌ No |
| UI placeholders for future expansion | ✔️ Yes |
| Prompts, model calls, GPU infrastructure | ❌ Not in v1 |

### Approved UI copy (dashboard & mobile)

Use **only** these phrases where a future capability is referenced:

- **Coming Soon**
- **Requires Advanced Plan (Future Release)**
- **Not available in current version**

Do **not** use:

- "AI Summary (beta)"
- "Enable AI"
- "Connect AI model"
- "Process with AI"
- "AI-assisted"
- "AI-powered"

### Marketing copy

- ✔️ "Optional AI enhancements planned for future updates"
- ✔️ "Manual job management for skilled trades"
- ❌ "AI-powered job management platform"

### Code enforcement

- `src/web-dashboard/lib/product-rules.ts` — `AI_FEATURES_ENABLED = false`
- `src/mobile-app/src/constants/product-rules.ts` — same constant
- Client apps must not call `/ai/*` endpoints in v1
