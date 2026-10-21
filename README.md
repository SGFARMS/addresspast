# AddressPast

**What happened here?** A free, sourced property-history check for New Mexico addresses, starting with reported deaths. The pilot covers Bernalillo and Valencia counties, plus Rio Rancho in Sandoval County.

- Live (pre-launch, noindex): https://history.skyhighwebsites.dev
- Vercel: team `sgfarms-s-projects`, project `nm-property-history`
- Every site setting lives in [`site.config.ts`](site.config.ts): name, URL, flags, models, pricing, counties, and colors.

## Quick start (no accounts needed)

```bash
npm install
cp .env.example .env.local     # leave everything blank for demo mode
npm run dev                    # http://localhost:3000
```

With no Supabase keys, the app runs on **demo data**: about 40 fake records across Albuquerque, Belen, Los Lunas and Rio Rancho, covering every precision type, record type and decade. A banner says so.

While `launched: false`, the home page is the waitlist. To see the app, set `PREVIEW_SECRET=anything` in `.env.local` and open `/preview?key=anything`. `/preview?off` turns the preview back off.

## Connect Supabase

1. Create a project, or use your existing one. In **Database → Extensions**, PostGIS is enabled by the migration.
2. Run the migrations in order, using the SQL editor or `supabase db push`:
   - `supabase/migrations/20261021000000_base_pipeline_tables.sql`: no-op if your pipeline tables already exist
   - `supabase/migrations/20261021000100_phase1.sql`
   > It assumes `incidents.id` is `bigint`. If yours is `uuid`, change the lines marked `[incident-fk]` first.
3. Put `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in `.env.local` and in the Vercel project env.
   The service key is only used server-side; `lib/supabase/server.ts` imports `server-only`.
4. Load the fake records: `npm run seed`. Use `npm run seed -- --reset` to reload them. All seed rows have ids `00000000-0000-4000-8000-*`, so they're easy to delete before launch.
5. **Backups:** turn on daily backups (Pro plan) and, before launch, do one test restore into a scratch project.

### Security model
- RLS is enabled on every table, and the default is deny. Admins (`profiles.role = 'admin'`) get full access to ops tables.
- The public never queries tables. Next.js route handlers call `api_*` Postgres functions with the service role, and **only `service_role` can execute them**. Each route is rate-limited per IP.
- Hidden records are excluded inside every `api_*` function. Hiding an event also deletes its area's cached AI summary (a DB trigger).

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
