# WorkTicket Design System

Shared visual language for the marketing website (`src/marketing-website`) and SaaS dashboard (`src/web-dashboard`).

## Principles

- **Clean B2B SaaS** — professional, not flashy; contractors are the audience
- **Mobile-first** — responsive layouts from 320px up
- **Accessible** — WCAG 2.1 AA contrast, keyboard navigation, focus rings
- **Fast** — minimal animations, optimized images, route-level code splitting

## Typography

| Token | Marketing | Dashboard |
|-------|-----------|-----------|
| Font | Inter (Google Fonts) | System + Inter via Tailwind |
| H1 | `text-4xl`–`text-6xl` bold | `text-2xl` bold |
| Body | `text-base`/`text-lg` slate-600 | `text-sm` muted-foreground |

## Color Palette

### Marketing (Tailwind `brand`)

- Primary: `brand-600` (#2563eb)
- Background: white / `surface-muted` (#f8fafc)
- Text: `slate-900` / `slate-600`

### Dashboard (CSS variables)

Defined in `web-dashboard/app/globals.css`:

- `--primary` — actions, links, active nav
- `--background` / `--foreground` — page base
- `--card` — elevated surfaces
- `--muted` — secondary text and backgrounds
- `--border` — dividers and inputs
- `--destructive` — errors and delete actions

Dark mode toggled via `next-themes` (`class="dark"` on `<html>`).

## Spacing

- Page padding: `p-4 sm:p-6 lg:p-8` (dashboard), `container-content` (marketing)
- Section gaps: `gap-4` (tight), `gap-6` (default), `gap-8` (loose)
- Card padding: `p-5` or `p-6`

## Components

### Shared patterns

| Component | Location | Usage |
|-----------|----------|-------|
| `Button` | Both apps | Primary, secondary, ghost variants |
| `PageHeader` | Dashboard | Title + description + actions |
| `StatCard` | Dashboard | Overview metrics |
| `EmptyState` | Dashboard | Zero-data states |
| `ComingSoonBadge` | Dashboard | AI extension points |

### Dashboard layout

```
┌─────────────────────────┐
│ TopNav (org switcher)   │
├──────────┬──────────────┤
│ Sidebar  │ Main content │
│          │              │
└──────────┴──────────────┘
```

## Future enhancements (v1: manual-first)

WorkTicket v1 is **manual-first**. See `src/docs/PRODUCT_RULES.md`.

Future capabilities use **only** approved copy:

- Coming Soon
- Requires Advanced Plan (Future Release)
- Not available in current version

Use the `FutureFeature` component (dashboard) — never imply AI is active, in beta, or configurable.

## Accessibility Checklist

- [ ] All interactive elements keyboard-focusable
- [ ] `aria-label` on icon-only buttons
- [ ] `role="alert"` on error messages
- [ ] Skip link to `#main-content`
- [ ] Color contrast ≥ 4.5:1 for body text

## Performance Targets

Lighthouse scores ≥ 90 for Performance, Accessibility, SEO, and Best Practices on marketing pages.
