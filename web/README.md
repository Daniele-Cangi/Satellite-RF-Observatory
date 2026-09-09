# Experimental position archive

A read-only Italian interface for five closed inverse-position attempts.
The first screen opens the passing G14 DOY246 event. Tabs retain both uncertainty
failures (G08 and G12 DOY248) and both structural failures (G12 DOY250 and G13
DOY247). G14's success is conditional on one historical event and does not
establish general accuracy or coverage. Operational completion is distinct from
the scientific outcome. The G14 network report explains candidate selection.

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

Schema version 2 pins evidence to a repository revision per event: the original
three use `7fcd71f9428c20202f98079955e8fac76aa0f6ad`, G13 uses
`6e9bfadb96224d73e51b6a940b9343895ef3b820`, and G14 uses
`2ee7d0ab060f21e24d182968d4d94ea3ddcd17ca`. These are archive references;
executed sources and their hashes remain in the original experimental records.
Website publication is separate from scientific event timing. Generated files
are checked for drift in CI; frozen solution and terminal receipt checks reject
changed evidence. The exporter rejects contradictory success/failure metrics.

The implementation roadmap is in `docs/WEBSITE_ROADMAP.md` at the repository
root. P0 provides the five-event archive. P1 must validate the remote executor's
authenticated connection and durable job contract before web submission ships.

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
