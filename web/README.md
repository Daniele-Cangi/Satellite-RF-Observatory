# Experimental position archive

A read-only Italian interface for the three closed inverse-position attempts.
The first screen opens G12 DOY248; tabs select G08 and the G12 DOY250 structural
failure. Every event retains its scientific outcome. A product archive can ship
while the scientific uncertainty milestone remains unmet.

The public data files are generated from the repository's frozen receipts:

```powershell
python scripts/export_positioning_archive.py
python scripts/export_positioning_archive.py --check
python -m pytest scripts/tests/test_positioning_archive.py -q
```

Run those commands at the repository root. In `web/`:

```powershell
npm ci
npm run dev
npx tsc --noEmit
npm run build
```

The Sites/Vinext starter exports static public files into `dist/client`.
There is no browser-triggered position solver, oracle fetch, database, user
upload or real-time claim. Evidence links download JSON dossiers, with original
UTF-8 artifact text and SHA-256 checks; full RF payloads remain at linked public
sources. No new uncertainty thresholds are introduced by the interface.

Evidence is pinned to scientific repository revision
`7fcd71f9428c20202f98079955e8fac76aa0f6ad`. Website publication is separate from
scientific event timing. Generated files are checked for drift in CI, and a
changed frozen G12 solution prevents export.

The first Sites edition is owner-private. Public access requires a separate
release decision. The parent GitHub repository remains the source of truth;
hosting uses an exported subtree, without making this directory a nested Git
repository or committing build outputs.

Security maintenance: React/RSC, Vite/Vinext and Cloudflare tooling were updated
from the generated starter after npm's advisory checks. Miniflare
`5.20260908.0-alpha` pins sharp `0.35.2`; a narrowly scoped override selects the
patched `0.35.4` for that exact parent version. Reassess the override when the
parent is upgraded. Hosting packages only the static `dist/client` output;
the local build/preview tools are not shipped as a server runtime.
