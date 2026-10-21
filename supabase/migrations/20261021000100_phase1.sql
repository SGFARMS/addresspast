-- =====================================================================
-- AddressPast · Phase 1 migration
-- supabase/migrations/20261021000100_phase1.sql
--
-- Builds on the pipeline's existing tables: incidents, scanned_pages.
-- ASSUMPTION: incidents.id is bigint (Supabase identity default).
--             If it's uuid, change the bigint FK columns marked [incident-fk].
-- Safe to re-run: every step uses IF NOT EXISTS / OR REPLACE / DROP IF EXISTS.
-- =====================================================================

create extension if not exists postgis  with schema extensions;
create extension if not exists citext   with schema extensions;
create extension if not exists pgcrypto with schema extensions;


-- ---------------------------------------------------------------------
-- 1. Lookup: record types (new layers plug in here, no schema change)
-- ---------------------------------------------------------------------
create table if not exists public.record_types (
  slug          text primary key,
  label_en      text not null,
  label_es      text not null,
  marker_shape  text not null check (marker_shape in ('circle','square','diamond','triangle','hexagon')),
  color_token   text not null,            -- maps to a theme token in site.config.ts, never a hex here
  sort_order    int  not null default 0,
  enabled       boolean not null default false
);

insert into public.record_types (slug, label_en, label_es, marker_shape, color_token, sort_order, enabled) values
  ('death',      'Reported death',       'Muerte reportada',              'circle',   'slate', 10, true),
  ('fire',       'Structure fire',       'Incendio de estructura',        'triangle', 'ochre', 20, false),
  ('drug_lab',   'Former drug lab site', 'Antiguo laboratorio de drogas', 'diamond',  'plum',  30, false),
  ('flood_zone', 'FEMA flood zone',      'Zona de inundación (FEMA)',     'square',   'river', 40, false)
on conflict (slug) do nothing;
-- Note: a death in a fire is record_type 'death' + cause_category 'fire'.
-- record_type 'fire' is reserved for structure fires with no reported death (Phase 4).


-- ---------------------------------------------------------------------
-- 2. Extend incidents
-- ---------------------------------------------------------------------
alter table public.incidents
  add column if not exists hidden            boolean not null default false,
  add column if not exists verified          boolean not null default false,
  add column if not exists verified_by       uuid references auth.users(id) on delete set null,
  add column if not exists verified_at       timestamptz,
  add column if not exists record_type       text not null default 'death' references public.record_types(slug),
  add column if not exists source_language   text not null default 'en',
  add column if not exists geocode_status    text,
  add column if not exists geocode_source    text,
  add column if not exists geocode_precision text,
  add column if not exists matched_address   text,
  add column if not exists geocoded_at       timestamptz,
  add column if not exists geom              geography(Point, 4326),
  add column if not exists incident_year     int,
  add column if not exists date_precision    text,
  add column if not exists parcel_id         text,
  add column if not exists event_id          uuid,
  add column if not exists summary_scrubbed  boolean not null default false,
  add column if not exists updated_at        timestamptz not null default now();

alter table public.incidents drop constraint if exists incidents_geocode_precision_chk;
alter table public.incidents add  constraint incidents_geocode_precision_chk
  check (geocode_precision is null
         or geocode_precision in ('street','street_historic','intersection','landmark','city'));

alter table public.incidents drop constraint if exists incidents_date_precision_chk;
alter table public.incidents add  constraint incidents_date_precision_chk
  check (date_precision is null or date_precision in ('day','month','year','decade'));

alter table public.incidents drop constraint if exists incidents_source_language_chk;
alter table public.incidents add  constraint incidents_source_language_chk
  check (source_language in ('en','es'));

-- Keep geom + year in sync. Year parsing is tolerant because incident_date
-- may be a date or free text depending on what the extractor wrote.
create or replace function public.incidents_sync_derived()
returns trigger language plpgsql
set search_path = public, extensions as $$
begin
  if new.lat is not null and new.lng is not null then
    new.geom := st_setsrid(st_makepoint(new.lng, new.lat), 4326)::geography;
  else
    new.geom := null;
  end if;

  new.incident_year := coalesce(
    substring(new.incident_date::text  from '(1[89]\d\d|20\d\d)')::int,
    substring(new.published_date::text from '(1[89]\d\d|20\d\d)')::int
  );

  new.updated_at := now();
  return new;
end $$;

drop trigger if exists incidents_sync_derived on public.incidents;
create trigger incidents_sync_derived
  before insert or update on public.incidents
  for each row execute function public.incidents_sync_derived();

-- Backfill existing rows through the trigger
update public.incidents set lat = lat;

create index if not exists incidents_geom_gix   on public.incidents using gist (geom);
create index if not exists incidents_event_idx  on public.incidents (event_id);
create index if not exists incidents_year_idx   on public.incidents (incident_year);
create index if not exists incidents_review_idx on public.incidents (geocode_status, geocode_precision, confidence)
  where not hidden;


-- ---------------------------------------------------------------------
-- 3. Events: one real-world death, many incident rows (sources)
--    The public site only ever shows events.
-- ---------------------------------------------------------------------
create table if not exists public.events (
  id                 uuid primary key default gen_random_uuid(),
  record_type        text not null default 'death' references public.record_types(slug),
  cause_category     text not null default 'unknown'
                     check (cause_category in ('natural','accident','homicide','suicide','fire','unknown')),
  event_year         int,
  event_date         date,
  date_precision     text check (date_precision in ('day','month','year','decade')),
  city               text,
  county             text,
  geocode_precision  text not null default 'city'
                     check (geocode_precision in ('street','street_historic','intersection','landmark','city')),
  geom               geography(Point, 4326),
  parcel_id          text,
  summary            text,      -- English, neutral, one line, name-scrubbed
  summary_es         text,      -- translated from summary
  confidence         numeric(4,3) not null default 0 check (confidence between 0 and 1),
  source_count       int not null default 1,
  verified           boolean not null default false,
  hidden             boolean not null default false,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

create index if not exists events_geom_gix   on public.events using gist (geom) where not hidden;
create index if not exists events_area_idx   on public.events (lower(county), lower(city)) where not hidden;
create index if not exists events_year_idx   on public.events (event_year) where not hidden;
create index if not exists events_parcel_idx on public.events (parcel_id) where parcel_id is not null;

alter table public.incidents drop constraint if exists incidents_event_fk;
alter table public.incidents add  constraint incidents_event_fk
  foreign key (event_id) references public.events(id) on delete set null;

-- Cache of Claude "same event?" decisions so pairs are never re-asked
create table if not exists public.dedupe_checks (
  incident_a  bigint not null references public.incidents(id) on delete cascade,  -- [incident-fk]
  incident_b  bigint not null references public.incidents(id) on delete cascade,  -- [incident-fk]
  same_event  boolean not null,
  rationale   text,
  model       text,
  checked_at  timestamptz not null default now(),
  primary key (incident_a, incident_b),
  check (incident_a < incident_b)
);

-- Nearby candidates for one incident (nightly dedupe job feeds these to Claude)
create or replace function public.dedupe_candidates(
  p_incident_id bigint,           -- [incident-fk]
  p_radius_m    int default 400,
  p_year_window int default 1
) returns table (candidate_id bigint, candidate_event_id uuid, distance_m double precision, year_diff int)
language sql stable
set search_path = public, extensions as $$
  select o.id,
         o.event_id,
         st_distance(i.geom, o.geom),
         abs(o.incident_year - i.incident_year)
  from public.incidents i
  join public.incidents o
    on o.id <> i.id
   and not o.hidden
   and o.record_type = i.record_type
   and (o.cause_category = i.cause_category or 'unknown' in (o.cause_category, i.cause_category))
   and abs(o.incident_year - i.incident_year) <= p_year_window
   and (
         (i.geom is not null and o.geom is not null
          and coalesce(i.geocode_precision,'city') <> 'city'
          and coalesce(o.geocode_precision,'city') <> 'city'
          and st_dwithin(i.geom, o.geom, p_radius_m))
      or ((coalesce(i.geocode_precision,'city') = 'city' or coalesce(o.geocode_precision,'city') = 'city')
          and lower(o.city) = lower(i.city))
       )
  where i.id = p_incident_id
    and not exists (
      select 1 from public.dedupe_checks d
      where d.incident_a = least(i.id, o.id) and d.incident_b = greatest(i.id, o.id))
  order by 3 nulls last
  limit 20;
$$;

-- Recompute an event from its visible incidents.
-- Location comes from the most precise, then most confident, source.
-- Confidence = 1 - Π(1 - c_i), capped at 0.99, so more independent sources raise it.
create or replace function public.refresh_event(p_event_id uuid)
returns void language plpgsql
set search_path = public, extensions as $$
declare
  best public.incidents%rowtype;
begin
  select * into best
  from public.incidents
  where event_id = p_event_id and not hidden
  order by array_position(array['street','street_historic','intersection','landmark','city'],
                          coalesce(geocode_precision, 'city')),
           confidence desc nulls last
  limit 1;

  if not found then
    update public.events set hidden = true, source_count = 0, updated_at = now()
    where id = p_event_id;
    return;
  end if;

  update public.events e set
    geom              = best.geom,
    geocode_precision = coalesce(best.geocode_precision, 'city'),
    parcel_id         = best.parcel_id,
    city              = best.city,
    county            = best.county,
    event_year        = s.yr,
    cause_category    = s.cause,
    source_count      = s.n,
    confidence        = s.combined,
    verified          = s.any_verified,
    updated_at        = now()
  from (
    select count(distinct coalesce(source_name, source_url))                                    as n,
           least(0.99, 1 - exp(sum(ln(1 - least(coalesce(confidence, 0)::numeric, 0.95)))))     as combined,
           bool_or(verified)                                                                   as any_verified,
           mode() within group (order by incident_year)                                        as yr,
           coalesce(mode() within group (order by cause_category)
                      filter (where cause_category <> 'unknown'), 'unknown')                   as cause
    from public.incidents
    where event_id = p_event_id and not hidden
  ) s
  where e.id = p_event_id;
end $$;

-- Hiding an incident refreshes its event (which hides it if no sources remain)
create or replace function public.incidents_on_hide()
returns trigger language plpgsql
set search_path = public as $$
begin
  if new.event_id is not null and new.hidden is distinct from old.hidden then
    perform public.refresh_event(new.event_id);
  end if;
  return new;
end $$;

drop trigger if exists incidents_on_hide on public.incidents;
create trigger incidents_on_hide
  after update of hidden on public.incidents
  for each row execute function public.incidents_on_hide();


-- ---------------------------------------------------------------------
-- 4. Historic address suggestions (Claude proposes, admin approves)
-- ---------------------------------------------------------------------
create table if not exists public.location_suggestions (
  id                 bigint generated always as identity primary key,
  incident_id        bigint not null references public.incidents(id) on delete cascade,  -- [incident-fk]
  suggested_lat      double precision not null,
  suggested_lng      double precision not null,
  suggested_address  text,
  rationale          text,
  model              text,
  status             text not null default 'pending' check (status in ('pending','accepted','rejected')),
  reviewed_by        uuid references auth.users(id) on delete set null,
  reviewed_at        timestamptz,
  created_at         timestamptz not null default now()
);
create index if not exists location_suggestions_pending_idx
  on public.location_suggestions (created_at) where status = 'pending';


-- ---------------------------------------------------------------------
-- 5. Parcels (Bernalillo + Valencia public parcel data)
-- ---------------------------------------------------------------------
create table if not exists public.parcels (
  id             text primary key,          -- '<county>:<apn>'
  county         text not null,
  apn            text not null,
  situs_address  text,
  geom           geography(MultiPolygon, 4326) not null,
  source_url     text,
  loaded_at      timestamptz not null default now()
);
create index if not exists parcels_geom_gix on public.parcels using gist (geom);

-- Attach street-level incidents to the lot they fall on
create or replace function public.match_incident_parcels(p_county text default null)
returns int language sql
set search_path = public, extensions as $$
  with m as (
    update public.incidents i
       set parcel_id = p.id
      from public.parcels p
     where i.geocode_precision = 'street'
       and i.geom is not null
       and i.parcel_id is null
       and (p_county is null or lower(p.county) = lower(p_county))
       and st_covers(p.geom, i.geom)
    returning 1
  )
  select count(*)::int from m;
$$;


-- ---------------------------------------------------------------------
-- 6. Ops: pipeline runs, AI usage, name-scrub hits
-- ---------------------------------------------------------------------
create table if not exists public.pipeline_runs (
  id           bigint generated always as identity primary key,
  job          text not null,   -- harvest_rss | harvest_historic | geocode | dedupe | parcels | translate | area_summaries
  trigger      text not null default 'cron' check (trigger in ('cron','manual','batch')),
  status       text not null default 'running' check (status in ('running','ok','partial','error')),
  started_at   timestamptz not null default now(),
  finished_at  timestamptz,
  items_in     int not null default 0,
  items_out    int not null default 0,
  tokens_in    bigint not null default 0,
  tokens_out   bigint not null default 0,
  cost_usd     numeric(10,4) not null default 0,
  batch_id     text,            -- Anthropic Message Batch id, when used
  error        text,
  meta         jsonb not null default '{}'
);
create index if not exists pipeline_runs_job_idx on public.pipeline_runs (job, started_at desc);

create table if not exists public.ai_usage (
  id                  bigint generated always as identity primary key,
  feature             text not null,   -- triage | extract | dedupe | historic_geo | translate | scrub_check | ask | area_summary
  model               text not null,
  input_tokens        int not null default 0,
  output_tokens       int not null default 0,
  cache_read_tokens   int not null default 0,
  cache_write_tokens  int not null default 0,
  batched             boolean not null default false,
  cost_usd            numeric(10,5) not null default 0,
  run_id              bigint references public.pipeline_runs(id) on delete set null,
  created_at          timestamptz not null default now()
);
create index if not exists ai_usage_feature_idx on public.ai_usage (feature, created_at desc);

create table if not exists public.scrub_hits (
  id            bigint generated always as identity primary key,
  event_id      uuid references public.events(id) on delete cascade,
  incident_id   bigint references public.incidents(id) on delete cascade,  -- [incident-fk]
  field         text not null,
  matched_text  text not null,
  detector      text not null check (detector in ('regex','claude')),
  context       text not null check (context in ('pipeline','response')),
  reviewed      boolean not null default false,
  created_at    timestamptz not null default now()
);


-- ---------------------------------------------------------------------
-- 7. App tables
-- ---------------------------------------------------------------------
create table if not exists public.profiles (
  id                  uuid primary key references auth.users(id) on delete cascade,
  role                text not null default 'user' check (role in ('user','pro','agent','admin')),
  display_name        text,
  brand_name          text,
  brand_logo_url      text,
  brand_color         text check (brand_color is null or brand_color ~ '^#[0-9a-fA-F]{6}$'),
  locale              text not null default 'en' check (locale in ('en','es')),
  stripe_customer_id  text unique,
  created_at          timestamptz not null default now()
);

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer
set search_path = public as $$
begin
  insert into public.profiles (id) values (new.id) on conflict (id) do nothing;
  return new;
end $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

create or replace function public.is_admin()
returns boolean language sql stable security definer
set search_path = public as $$
  select exists (select 1 from public.profiles where id = auth.uid() and role = 'admin');
$$;

create table if not exists public.disputes (
  id               bigint generated always as identity primary key,
  incident_id      bigint references public.incidents(id) on delete set null,  -- [incident-fk]
  event_id         uuid references public.events(id) on delete set null,
  requester_email  extensions.citext not null,
  relationship     text not null check (relationship in ('owner','family','tenant','agent','other')),
  reason           text not null,
  details          text,
  status           text not null default 'open'
                   check (status in ('open','resolved_removed','resolved_corrected','resolved_kept')),
  priority         int not null default 0,     -- set by moderation helper (Phase 2)
  ai_triage        jsonb,
  admin_notes      text,
  created_at       timestamptz not null default now(),
  resolved_at      timestamptz
);
create index if not exists disputes_open_idx on public.disputes (priority desc, created_at) where status = 'open';

create table if not exists public.watches (
  id                bigint generated always as identity primary key,
  user_id           uuid not null references auth.users(id) on delete cascade,
  label             text,
  lat               double precision not null,
  lng               double precision not null,
  radius_m          int not null default 250 check (radius_m between 50 and 5000),
  created_at        timestamptz not null default now(),
  last_notified_at  timestamptz
);
create index if not exists watches_user_idx on public.watches (user_id);

create table if not exists public.reports (
  id                 uuid primary key default gen_random_uuid(),
  user_id            uuid references auth.users(id) on delete set null,
  address            text not null,
  lat                double precision not null,
  lng                double precision not null,
  snapshot           jsonb not null,          -- frozen results at purchase time
  share_token        text not null unique default encode(extensions.gen_random_bytes(24), 'hex'),
  stripe_session_id  text unique,
  created_at         timestamptz not null default now()
);
create index if not exists reports_user_idx on public.reports (user_id, created_at desc);

create table if not exists public.submissions (
  id               bigint generated always as identity primary key,
  user_id          uuid references auth.users(id) on delete set null,
  email            extensions.citext,
  address          text not null,
  lat              double precision,
  lng              double precision,
  description      text not null,
  source_url       text,
  status           text not null default 'pending' check (status in ('pending','approved','rejected','duplicate')),
  moderator_notes  text,
  ai_triage        jsonb,
  created_at       timestamptz not null default now(),
  reviewed_at      timestamptz
);

create table if not exists public.waitlist (
  id          bigint generated always as identity primary key,
  email       extensions.citext not null unique,
  locale      text not null default 'en',
  county      text,
  referrer    text,
  created_at  timestamptz not null default now()
);

create table if not exists public.area_summaries (
  county        text not null,
  city          text not null default '',   -- '' = county-level page
  locale        text not null check (locale in ('en','es')),
  body          text not null,
  stats_hash    text not null,              -- regenerate only when stats change
  model         text,
  generated_at  timestamptz not null default now(),
  primary key (county, city, locale)
);

-- Hard rule: hiding an event purges any cached AI summary for its area.
-- (Next.js page revalidation is triggered from the admin action in Phase 2.)
create or replace function public.events_on_hide()
returns trigger language plpgsql
set search_path = public as $$
begin
  if new.hidden and not old.hidden then
    delete from public.area_summaries
     where lower(county) = lower(old.county)
       and (city = '' or lower(city) = lower(coalesce(old.city, '')));
  end if;
  return new;
end $$;

drop trigger if exists events_on_hide on public.events;
create trigger events_on_hide
  after update of hidden on public.events
  for each row execute function public.events_on_hide();

-- Coverage per county for the free-check footnote ("what we searched")
create materialized view if not exists public.area_coverage as
  select county,
         min(incident_year)                                              as first_year,
         max(incident_year)                                              as last_year,
         count(distinct source_name)                                     as source_count,
         count(*) filter (where incident_year between 1964 and 2010)     as gap_era_records,
         now()                                                           as refreshed_at
  from public.incidents
  where not hidden and county is not null
  group by county;
create unique index if not exists area_coverage_county_uq on public.area_coverage (county);
-- Refreshed nightly by the dedupe job: refresh materialized view concurrently public.area_coverage;


-- ---------------------------------------------------------------------
-- 8. Row Level Security
--    Default deny. Admins get full access to ops tables. The public never
--    reads tables directly — only the api_* functions below, server-side.
-- ---------------------------------------------------------------------
do $$
declare t text;
begin
  foreach t in array array[
    'record_types','incidents','scanned_pages','events','dedupe_checks','location_suggestions',
    'parcels','pipeline_runs','ai_usage','scrub_hits','profiles','disputes','watches',
    'reports','submissions','waitlist','area_summaries']
  loop
    execute format('alter table public.%I enable row level security', t);
  end loop;

  foreach t in array array[
    'record_types','incidents','scanned_pages','events','dedupe_checks','location_suggestions',
    'parcels','pipeline_runs','ai_usage','scrub_hits','disputes','submissions','waitlist','area_summaries']
  loop
    execute format('drop policy if exists admin_all on public.%I', t);
    execute format('create policy admin_all on public.%I for all to authenticated
                    using (public.is_admin()) with check (public.is_admin())', t);
  end loop;
end $$;

-- profiles: read/update own row; role is never user-editable
drop policy if exists profiles_read on public.profiles;
create policy profiles_read on public.profiles
  for select to authenticated using (id = auth.uid() or public.is_admin());

drop policy if exists profiles_update_self on public.profiles;
create policy profiles_update_self on public.profiles
  for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

revoke update on public.profiles from authenticated;
grant  update (display_name, brand_name, brand_logo_url, brand_color, locale) on public.profiles to authenticated;

-- watches: owner manages own
drop policy if exists watches_owner on public.watches;
create policy watches_owner on public.watches
  for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

-- reports: owner reads own; created only by the Stripe webhook (service role)
drop policy if exists reports_owner_read on public.reports;
create policy reports_owner_read on public.reports
  for select to authenticated using (user_id = auth.uid() or public.is_admin());

revoke all on public.area_coverage from anon, authenticated;


-- ---------------------------------------------------------------------
-- 9. Public API functions (limited fields, hidden excluded)
--    Executable ONLY by service_role, called from Next.js route handlers
--    that rate-limit per IP. The anon key can't reach records at all.
-- ---------------------------------------------------------------------

-- Free check for one point
create or replace function public.api_free_check(
  p_lat              double precision,
  p_lng              double precision,
  p_city             text    default null,
  p_near_m           int     default 250,
  p_record_types     text[]  default array['death']
) returns jsonb
language plpgsql stable
set search_path = public, extensions as $$
declare
  pt        geography := st_setsrid(st_makepoint(p_lng, p_lat), 4326)::geography;
  v_parcel  text;
  v_county  text;
  result    jsonb;
begin
  select id, county into v_parcel, v_county
  from public.parcels where st_covers(geom, pt) limit 1;

  with visible as (
    select e.* from public.events e
    where not e.hidden and e.record_type = any (p_record_types)
  ),
  at_addr as (       -- only exact street matches ever count as "at this address"
    select v.*, 0::double precision as distance_m from visible v
    where v.geocode_precision = 'street'
      and ( (v_parcel is not null and v.parcel_id = v_parcel)
         or (v_parcel is null and st_dwithin(v.geom, pt, 25)) )
  ),
  near as (
    select v.*, st_distance(v.geom, pt) as distance_m from visible v
    where v.geocode_precision <> 'city'
      and v.geom is not null
      and st_dwithin(v.geom, pt, p_near_m)
      and v.id not in (select id from at_addr)
  ),
  city_only as (
    select count(*) as n from visible v
    where v.geocode_precision = 'city' and p_city is not null and lower(v.city) = lower(p_city)
  )
  select jsonb_build_object(
    'parcel_matched', v_parcel is not null,
    'at_address', coalesce((select jsonb_agg(jsonb_build_object(
        'id', id, 'year', event_year, 'date_precision', date_precision,
        'record_type', record_type, 'cause', cause_category,
        'precision', geocode_precision, 'verified', verified)
        order by event_year) from at_addr), '[]'::jsonb),
    'nearby', coalesce((select jsonb_agg(jsonb_build_object(
        'id', id, 'year', event_year, 'date_precision', date_precision,
        'record_type', record_type, 'cause', cause_category,
        'precision', geocode_precision, 'verified', verified,
        'distance_m', round(distance_m)::int)
        order by distance_m) from near), '[]'::jsonb),
    'city_only_count', (select n from city_only),
    'coverage', (select to_jsonb(c) from public.area_coverage c
                 where lower(c.county) = lower(coalesce(v_county, '')) limit 1),
    'as_of', (select max(finished_at) from public.pipeline_runs where status = 'ok')
  ) into result;

  return result;
end $$;
-- Natural-cause records ARE returned here (tagged by cause) so the UI can say
-- "1 natural-cause record, hidden by default" instead of a false "nothing found".

-- Map points in a bounding box (city-only records excluded; see api_city_counts)
create or replace function public.api_map_events(
  p_west double precision, p_south double precision,
  p_east double precision, p_north double precision,
  p_year_from        int      default 1850,
  p_year_to          int      default 2100,
  p_record_types     text[]   default array['death'],
  p_causes           text[]   default null,      -- null = all
  p_include_natural  boolean  default false,
  p_min_confidence   numeric  default 0,
  p_verified_only    boolean  default false,
  p_limit            int      default 5000
) returns table (
  id uuid, lng double precision, lat double precision, record_type text, cause text,
  event_year int, geo_precision text, confidence numeric, verified boolean, source_count int
)
language sql stable
set search_path = public, extensions as $$
  select e.id,
         st_x(e.geom::geometry), st_y(e.geom::geometry),
         e.record_type, e.cause_category, e.event_year, e.geocode_precision,
         round(e.confidence, 2), e.verified, e.source_count
  from public.events e
  where not e.hidden
    and e.geocode_precision <> 'city'
    and e.geom && st_makeenvelope(p_west, p_south, p_east, p_north, 4326)::geography
    and e.event_year between p_year_from and p_year_to
    and e.record_type = any (p_record_types)
    and (p_causes is null or e.cause_category = any (p_causes))
    and (p_include_natural or e.cause_category <> 'natural')
    and e.confidence >= p_min_confidence
    and (not p_verified_only or e.verified)
  limit least(p_limit, 5000);
$$;

-- Per-city badge counts for city-only records
create or replace function public.api_city_counts(
  p_year_from        int      default 1850,
  p_year_to          int      default 2100,
  p_record_types     text[]   default array['death'],
  p_causes           text[]   default null,
  p_include_natural  boolean  default false,
  p_min_confidence   numeric  default 0,
  p_verified_only    boolean  default false
) returns table (county text, city text, n bigint, lng double precision, lat double precision)
language sql stable
set search_path = public, extensions as $$
  select e.county, e.city, count(*),
         st_x(st_centroid(st_collect(e.geom::geometry))),
         st_y(st_centroid(st_collect(e.geom::geometry)))
  from public.events e
  where not e.hidden
    and e.geocode_precision = 'city'
    and e.geom is not null
    and e.event_year between p_year_from and p_year_to
    and e.record_type = any (p_record_types)
    and (p_causes is null or e.cause_category = any (p_causes))
    and (p_include_natural or e.cause_category <> 'natural')
    and e.confidence >= p_min_confidence
    and (not p_verified_only or e.verified)
  group by e.county, e.city;
$$;

-- City-only records bucketed by decade, so the timeline can filter city badges client-side
create or replace function public.api_city_decades(
  p_record_types     text[]   default array['death'],
  p_causes           text[]   default null,
  p_include_natural  boolean  default false,
  p_min_confidence   numeric  default 0,
  p_verified_only    boolean  default false
) returns table (county text, city text, decade int, n bigint, lng double precision, lat double precision)
language sql stable
set search_path = public, extensions as $$
  select e.county, e.city, (e.event_year / 10) * 10, count(*),
         st_x(st_centroid(st_collect(e.geom::geometry))),
         st_y(st_centroid(st_collect(e.geom::geometry)))
  from public.events e
  where not e.hidden
    and e.geocode_precision = 'city'
    and e.geom is not null
    and e.event_year is not null
    and e.record_type = any (p_record_types)
    and (p_causes is null or e.cause_category = any (p_causes))
    and (p_include_natural or e.cause_category <> 'natural')
    and e.confidence >= p_min_confidence
    and (not p_verified_only or e.verified)
  group by e.county, e.city, (e.event_year / 10) * 10;
$$;

-- One record card. p_full = summary + source links (paywall flag in site.config.ts)
create or replace function public.api_event_detail(
  p_event_id  uuid,
  p_full      boolean default false,
  p_locale    text    default 'en'
) returns jsonb
language sql stable
set search_path = public, extensions as $$
  select jsonb_build_object(
    'id', e.id,
    'year', e.event_year,
    'date_precision', e.date_precision,
    'record_type', e.record_type,
    'cause', e.cause_category,
    'precision', e.geocode_precision,
    'confidence', round(e.confidence, 2),
    'verified', e.verified,
    'city', e.city,
    'county', e.county,
    'source_count', e.source_count,
    'summary', case when p_full then
                 case when p_locale = 'es' then coalesce(e.summary_es, e.summary) else e.summary end
               end,
    'sources', (
      select coalesce(jsonb_agg(distinct jsonb_build_object(
               'name', i.source_name,
               'published', i.published_date,
               'url', case when p_full then i.source_url end,
               'is_loc_scan', i.source_url ilike '%loc.gov%')), '[]'::jsonb)
      from public.incidents i
      where i.event_id = e.id and not i.hidden)
  )
  from public.events e
  where e.id = p_event_id and not e.hidden;
$$;

-- Aggregate stats for /nm/[county] and /nm/[county]/[city]
create or replace function public.api_area_stats(
  p_county           text,
  p_city             text    default null,
  p_include_natural  boolean default false
) returns jsonb
language sql stable
set search_path = public, extensions as $$
  with v as (
    select * from public.events
    where not hidden
      and lower(county) = lower(p_county)
      and (p_city is null or lower(city) = lower(p_city))
      and (p_include_natural or cause_category <> 'natural')
  )
  select jsonb_build_object(
    'total',        (select count(*) from v),
    'by_decade',    (select coalesce(jsonb_object_agg(d, n), '{}'::jsonb)
                     from (select ((event_year / 10) * 10)::text d, count(*) n
                           from v where event_year is not null group by 1) x),
    'by_cause',     (select coalesce(jsonb_object_agg(cause_category, n), '{}'::jsonb)
                     from (select cause_category, count(*) n from v group by 1) x),
    'by_precision', (select coalesce(jsonb_object_agg(geocode_precision, n), '{}'::jsonb)
                     from (select geocode_precision, count(*) n from v group by 1) x),
    'verified',     (select count(*) from v where verified),
    'coverage',     (select to_jsonb(c) from public.area_coverage c
                     where lower(c.county) = lower(p_county) limit 1)
  );
$$;

-- Refresh coverage (called nightly by the dedupe job and by the seed script)
create or replace function public.refresh_area_coverage()
returns void language sql security definer
set search_path = public as $$
  refresh materialized view public.area_coverage;
$$;

-- Lock every api_* and pipeline helper to service_role only
do $$
declare r record;
begin
  for r in
    select p.oid::regprocedure as sig
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public'
      and (p.proname like 'api\_%'
           or p.proname in ('dedupe_candidates','refresh_event','match_incident_parcels','refresh_area_coverage'))
  loop
    execute format('revoke execute on function %s from public, anon, authenticated', r.sig);
    execute format('grant  execute on function %s to service_role', r.sig);
  end loop;
end $$;
