# AddressPast session note: 2026-11-02

## Found (audit)
- **No SSH in the app or pipeline.** They reach the BaaS over HTTPS (`SUPABASE_URL` + service key). The "SSH key fix" reminder is the optional cleanup of `~/.ssh/github_ops` on the droplet, not an AddressPast fault.
- **Harvesters are paused, not broken.** Scheduled `harvest` (6-hourly) and `pipeline` runs still fire but last 17-36 s and exit at the gate, because `pipeline/BACKFILL_ON` and `pipeline/LIVE_ON` were removed Oct 28. Last real harvest: Oct 28, 13:11 UTC. Bulk newspaper backlog was already fully read (318,486 pages).
- **Branches/PRs:** only `stop-idle-harvest` was left, already merged (PR #4). No other open PRs.
- **Library of Congress:** loc.gov JSON API allows 20 requests/min (1-hour block if exceeded); text/image services 150/min. Standalone Chronicling America API retired in 2025 (loc.gov only). Text is a U.S. Government Work.
- **Bernalillo parcels:** never loaded. Code points at `gismap.bernco.gov/.../Public_Permits/MapServer/15` (`UPC` / `SITUSADD`); the county's current parcel service appears to be `pdsgismaps.bernco.gov` BC_Platted_Parcels (`PIN` / `ADDRESS`, unincorporated county only, 2,000 rows/request). Not verifiable from the build sandbox. Terms: free, credit "GIS Technology Section / Bernalillo County Planning & Development Services", reference only.
- **Admin / removal page:** code review plus CI browser tests confirm the gate (401 without login, login flow, HMAC cookie, HttpOnly/SameSite=Strict/Secure, closed without `ADMIN_PASSWORD`). Live page and pending-request count not checked (needs Joe's login).
- **Vercel production variables (names only):** no `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN`, so per-IP rate limits are per-server-instance only.

## AI calls
Haiku 5.5 ($0.10/$0.50 per MTok) and Sonnet 5.5 ($2/$10). Paused: about $0/month on the pipeline. If resumed (estimates, token sizes assumed): historic location suggestions up to ~$12/month at first (Sonnet, 100/day, shrinking), nightly duplicate check up to ~$2, translation up to ~$1, others cents. Harvest spend to date about $19.08 of the $20 cap. Candidates for a local model on the Mac mini: translation, triage, duplicate checks. Keep extraction and historic-address reasoning on Claude unless a sample test says otherwise. These jobs run on GitHub Actions, so a local model needs a self-hosted runner or the jobs must move to the Mac.

## Changed (all merged to `main`, squash)
- **#7 `712086e`**: site-side daily AI spend cap for the Ask box and area summaries ($2 per UTC day via `siteConfig.ai.dailyCapUsd`, summed from `ap_ai_usage`; free rule-based fallback; fails closed). Verified: `ap_ai_usage.created_at` exists (migration 0026) and is indexed with `feature`.
- **#8 `b0d5f5b`**: newspaper info lookup asks loc.gov first; retired chroniclingamerica.loc.gov kept only as last resort.
- **#9 `06206a5`**: parcel puller fails loudly (error body, empty source, or no usable id field) instead of "succeeding" with zero rows. Endpoint and field names unchanged.
- This note.

Checks: CI green on each PR; 40 pipeline tests pass on combined `main`; 5 gate-logic checks pass.

## Undo
Revert the squash commits on `main` (`git revert 06206a5 b0d5f5b 712086e`), or roll back in Vercel to the previous production deployment (`70b36f8`). No schema, settings, secret or data changes were made.

## Still open (Joe)
1. **Upstash**: create a Redis database (Vercel integration) so `UPSTASH_REDIS_REST_URL` / `_TOKEN` exist. Until then use a long random `ADMIN_PASSWORD`.
2. **Removal queue**: log in at `/admin` and check pending requests.
3. **Parcel load**: source now points at the NM State Engineer statewide layer (Bernalillo only, 255,181 parcels, 254,793 with an address; fields `UPC`, `SitusAddress1`). Nothing has been loaded yet; run `python -m pipeline.parcels fetch bernalillo` after the PR merges, with your OK.
4. **Idle scheduled runs**: set repo variables `HARVEST_BACKFILL` and `PIPELINE_LIVE` to `false` when making the repo private again.
5. Chores: finish the duplicate sweep (stopped near 78%), switch repo back to private, delete `~/.ssh/github_ops` on the droplet, OSHA key (`DOL_API_KEY`), IPRA letters.
