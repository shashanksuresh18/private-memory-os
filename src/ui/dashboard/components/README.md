# components/ — REFERENCE ONLY (React migration path)

**These `.tsx` files are NOT loaded by the live app.** The shipping runtime is
vanilla and consists of exactly three files in the parent directory:

- `../index.html`
- `../app.js`
- `../styles.css`

…plus `../../types.js` (the runtime source of truth for `MOCK_CITATIONS`).

The `.tsx` components here are the **reference implementations** the vanilla
runtime was extracted from, and the migration target if/when this UI moves to
React/Vite. Decision of record (audit, 2026-05-31): **vanilla wins for now.**

## Rules

- **Do not import these from `app.js`.** Extract logic into vanilla JS/CSS instead.
- They are kept (not deleted) on purpose — they are the React migration path.
- Icons use the local inline-SVG `./icon.tsx` (`<Icon name="…" />`), never an
  external icon library. No network, no font/icon CDN.
- Active-route state is a plain `pathname` prop — no Next.js `Link` / `usePathname`.

## Where the live logic lives (TSX → vanilla map)

| Reference `.tsx`            | Lives in the vanilla runtime as |
|-----------------------------|---------------------------------|
| `tier-badge.tsx`            | `tierBadge()` in `app.js` + `.tier-badge--{s1,s2,s3}` in `styles.css` |
| `score-breakdown.tsx`       | `scoreBreakdown()` in `app.js` (4 bars, or collapsed ConfBar when `rerank === 0`) |
| `conf-bar.tsx`              | `confBar()` in `app.js` + `.conf-bar` in `styles.css` |
| `atom-chip.tsx` (+ Inspector) | `atomChips()` + `#viewerAtoms` delegate handler in `app.js`; S3 = "Sealed — resolve only" |
| `safety-bar.tsx`            | `.safety-bar` block in `index.html` (cloud allowed: false, hardcoded) |
| `top-bar.tsx`               | `.topbar` block in `index.html` |
| `sidebar.tsx`               | not surfaced in the single-screen runtime (kept for migration) |

Tier color tokens (`--tier-s1` sky / `--tier-s2` amber / `--tier-s3` rose) are
defined once in `../colors_and_type.css` and consumed by both planes.
