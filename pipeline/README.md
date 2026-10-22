# Data pipeline

| File | What it does | Schedule |
|---|---|---|
| `harvest.py` | Free sources → strict pre-filter → Haiku (Sonnet for unclear records) → `ap_incidents` | RSS daily; Chronicling America by hand (`harvest` workflow) |
| `sources/loc.py` | Library of Congress loc.gov API, NM papers, English + Spanish, paced under 20 requests/min | used by harvest |
| `sources/rss.py` | Local news feeds (Journal, KRQE, KOB, KOAT, News-Bulletin, Observer, Source NM, Searchlight) | used by harvest |
| `prefilter.py` | Keeps only text near a death keyword AND a pilot town; caps each page at 12k characters | used by harvest |
| `extract.py` | Extraction tool + prompt, Sonnet escalation rules, name scrubbing, review flags | harvest, batches |
| `geocode.py` | Census Geocoder → Photon → town centroid; pre-1960 street addresses go to review | daily, after harvest |
| `places_nm.py` | Pilot towns, OCR spellings, counties, centroids | shared |
| `lang.py` | English/Spanish keywords, language detection, prompts | shared |
| `batches.py` | Optional: backlog via Message Batches (50% off) | `submit` by hand, `poll` every 3h |
| `dedupe.py` | Groups incidents into events, with a Claude check per candidate pair | nightly |
| `historic_geo.py` | Claude suggests modern locations for pre-1960 addresses; suggestions go to review | daily |
| `parcels.py` | Load county parcel GeoJSON and attach street-level records to lots | `load` by hand, `match` nightly |
| `translate.py` | Fills `ap_events.summary_es` | nightly |
| `common/runlog.py` | Every run → `ap_pipeline_runs`, every Claude call → `ap_ai_usage`, spend caps | all |
| `common/scrub.py` | Name scrubber, run before any summary is stored | all |

## Running the harvester

Actions → **harvest** → Run workflow. Start with a dry run:

1. `mode: dry-run`, `extract_limit: 0`, a few years: counts candidates and estimates the Claude cost. No keys needed.
2. `mode: dry-run`, `extract_limit: 150`: extracts 150 candidates into `records.csv` (in the run's `harvest-out` artifact) for a spot-check. Needs the `ANTHROPIC_API_KEY` repo secret.
3. `mode: live`: writes to the database and geocodes. Needs the database secrets from the baas `connect-tenant-site` task.

The run summary says where it stopped. In live mode, `start_page: resume` continues from there.

**Daily live jobs:** the scheduled `pipeline` runs (daily news harvest, nightly dedupe/translate/parcel match, batch collection) write to the live site, so they only run while an empty file `pipeline/LIVE_ON` exists. Add it after the first spot-check is approved; running a job by hand works either way.

**Backlog autopilot:** add an empty file `pipeline/BACKFILL_ON` and a live run starts every 6 hours, picks up where the last one stopped, and stops for good once 1860–1963 is done (or the $20 cap is spent). Delete the file to pause it.

Measured on 1910–1911 Albuquerque papers: about 5% of pages pass the pre-filter, and Haiku costs about $0.0002 per page sent. loc.gov speed varies a lot by day; a good day does about 80 pages a minute.

### What gets kept
- A page is sent to Claude only if a death keyword (English or Spanish) appears within ~700 characters of a pilot town, or, for papers printed in Albuquerque/Belen/Bernalillo/Los Lunas/Rio Rancho, near a local cue like "street" or "his home".
- Haiku extracts first. Sonnet re-reads the page when Haiku is unsure (confidence 0.3–0.6) or names a specific house with confidence under 0.8. Sonnet may use at most 40% of a run's budget.
- Suicides stay labeled as suicide. Apartment units are kept in `unit` and the site says "this building".
- Boarding houses, hotels and businesses get `needs_review = true` and stay off the public site until reviewed.
- Article text is only held in memory. We store the source link, structured fields and our own one-line summary (names scrubbed).

### Spend
- `AP_HARVEST_CAP_USD` (default $20) is one cap across all harvest runs, measured from `ap_ai_usage`.
- `--max-cost` caps a single run; `AP_MAX_RUN_COST_USD` caps other jobs.
- Also set a monthly spend limit in the Anthropic Console.

## Parcel data

- **Bernalillo County** publishes parcels on its public GIS portal. Export them as GeoJSON in EPSG:4326, then:
  `python -m pipeline.parcels load bernalillo parcels.geojson --apn-field UPC --situs-field SITUS`. Check the real field names first.
- **Valencia County:** confirm a public parcel download exists. If not, ask the assessor's office for a GIS export.

