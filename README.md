# AddressPast

**What happened here?** A free, sourced property-history check for New Mexico addresses, starting with reported deaths. The pilot covers Bernalillo and Valencia counties, plus Rio Rancho in Sandoval County.

- Live (pre-launch, noindex): https://history.skyhighwebsites.dev
- Vercel: team `sgfarms-s-projects`, project `nm-property-history`
- Every site setting lives in [`site.config.ts`](site.config.ts): name, URL, flags, models, pricing, counties, and colors.
- Database: tenant `addresspast` on the SkyHigh BaaS.

## Quick start (no accounts needed)

```bash
npm install
cp .env.example .env.local     # leave everything blank for demo mode
npm run dev                    # http://localhost:3000
```

With no database keys, the app runs on **demo data**: about 40 fake records across Albuquerque, Belen, Los Lunas and Rio Rancho, covering every precision type, record type and decade. A banner says so.

While `launched: false`, the home page is the waitlist. To see the app, set `PREVIEW_SECRET=anything` in `.env.local` and open `/preview?key=anything`. `/preview?off` turns the preview back off.

## Database: SkyHigh BaaS

The data lives on your self-hosted Supabase ([skyhighwebsites-baas](https://github.com/SGFARMS/skyhighwebsites-baas)) as tenant `addresspast`. See [`supabase/README.md`](supabase/README.md).

1. Merge the `0026_addresspast_schema.sql` migration in the baas repo, then run **Actions → Droplet ops → `update-baas`** (confirm `RUN`).
2. Run **Actions → Droplet ops → `connect-tenant-site`** with slug `addresspast`, vercel_project `nm-property-history`, github_repo `addresspast` (confirm `RUN`). That provisions the tenant and writes:
   - Vercel env: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_TENANT_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
   - This repo's Actions secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
3. Redeploy, then load the fake records: put the two values in `.env.local` and run `npm run seed`. Use `npm run seed -- --reset` to reload them. Seed rows have ids `00000000-0000-4000-8000-*`, so they're easy to delete before launch.

The service key is tenant-scoped: rows get `tenant_id` from its claim, and it never reaches the browser (`lib/supabase/server.ts` imports `server-only`).

### Security model
- Every `ap_*` table has RLS enabled and forced, and anon/authenticated have no grants. Only the tenant service key can read or write.
- The public never queries tables. Next.js route handlers call the `ap_api_*` Postgres functions, which **only `service_role` can execute**. Each route is rate-limited per IP.
- Hidden records are excluded inside every `ap_api_*` function. Hiding an event also deletes its area's cached AI summary (a DB trigger).
- Backups and restores use the BaaS runbook (`docs/RUNBOOK.md`, `docs/RESTORE_DRILL.md` in that repo).

## Optional services

| Env var | What it turns on | Without it |
|---|---|---|
| `ANTHROPIC_API_KEY` | "Ask in plain English" via Claude Haiku, weekly AI area summaries | Rule-based question parser, template area summaries |
| `UPSTASH_REDIS_REST_URL` / `_TOKEN` | Shared per-IP rate limits | Per-instance memory limits (dev only) |
| `PREVIEW_SECRET` | `/preview?key=…` waitlist bypass | Waitlist only |
| `CRON_SECRET` | Auth for `/api/cron/*` | Cron route is open |

Tokens and cost per AI feature are logged to `ai_usage`.

## Pipeline

See [`pipeline/README.md`](pipeline/README.md). The pipeline runs on GitHub Actions (`.github/workflows/pipeline.yml`), not Vercel Cron: it's Python with long-running jobs. Add `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` and `ANTHROPIC_API_KEY` as repo secrets. Vercel Cron only runs the weekly area-summary refresh (`vercel.json`).

## Tests

```bash
npm test                 # unit: name scrubber, question parser
npm run build && npm run e2e   # Playwright: waitlist, search, free check, record card, natural toggle, ask, Spanish, area page
python -m pytest pipeline/tests -q
```

CI (`.github/workflows/ci.yml`) runs typecheck, lint, unit tests, build and e2e on every push.

## Geocoding and map tiles

- **Autocomplete:** [Photon](https://photon.komoot.io), which is OSM-based and limited to NM. The public Nominatim server's usage policy forbids autocomplete, so it isn't used for search. Results are cached for 24 hours. For heavy traffic, self-host Photon or switch providers in `lib/places.ts`.
- **Tiles:** [OpenFreeMap](https://openfreemap.org), which is free with no key. Swap `map.styleLight` / `map.styleDark` in `site.config.ts` for Mapbox or MapTiler.

## Error monitoring

Add Sentry before launch: `npx @sentry/wizard@latest -i nextjs`, then set `SENTRY_DSN` in Vercel.

## Switching domains

Change `url` in `site.config.ts`, add the domain to the Vercel project, and redeploy. Canonicals, sitemap and links all read from that one value.
