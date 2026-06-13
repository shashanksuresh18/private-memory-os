Window 2 (Sonnet) completed React/Vite migration.
13/13 green. Vanilla deleted. React live at port 3003.

Files Sonnet added/changed — do NOT touch these:
- src/ui/App.tsx
- src/ui/api.ts
- src/ui/app.css
- src/ui/index.html
- src/ui/main.tsx
- src/ui/tsconfig.json
- src/ui/vite.config.ts
- src/ui/dashboard/components/index.ts
- package.json
- package-lock.json

Your go-ahead for §5 is cancelled — Sonnet already 
did it. Do NOT re-do React/Vite migration.

Do §6 ONLY — Knowledge Graph View.
Build it inside the existing React app Sonnet created.
Do not touch any file in the list above unless 
strictly required, and flag it if you do.

## §6 Knowledge Graph View

Source data: graphify-out/graph.json (already exists)

Build src/ui/GraphView.tsx

Nodes colored by tier token:
  S1 = var(--tier-s1)   sky blue
  S2 = var(--tier-s2)   amber
  S3 = var(--tier-s3)   rose

Edge types to render:
  attended / works_at / audience /
  related_to / invested_in / founded

Rules:
  - Use D3 or plain SVG — no external graph CDN
  - Click node → fires query to /retrieve with 
    that page as filter, opens Citation Viewer
  - S3 node labels hidden when tier context is S1/S2
  - Tier gate: S3 nodes only fully visible in S3 context
  - Wire into Sidebar as a nav route "Graph"
  - SafetyBar must remain visible on this screen

Invariants (unchanged):
  - No external calls, no CDN
  - Offline build must work
  - vite build must pass with zero errors

After building:
  - vite build → zero errors
  - python -m pytest tests/ -q → all still green
  - Open graph view in browser, confirm nodes render
    with correct tier colors

✅/⛔ after each step.
End with: graph view live, test count, any files 
touched from the protected list above.