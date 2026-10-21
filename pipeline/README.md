# Data pipeline

`harvest.py` and `geocode.py` are your existing scripts. Drop them into this folder unchanged. Everything else here is new and is designed to plug into them.

| File | What it does | Schedule |
|---|---|---|
| `lang.py` | Spanish keywords, language detection, bilingual extraction prompt | used by harvest |
| `triage.py` | Haiku first pass: is there an NM death with a location? Only "yes" pages go to Sonnet | used by harvest |
| `batches.py` | Historical backlog via Message Batches (50% off) + cached prompt | `submit` by hand, `poll` every 3h |
| `dedupe.py` | Groups incidents into `events`, with a Claude check per candidate pair | nightly |
| `historic_geo.py` | Claude suggests modern locations for pre-1960 addresses that didn't geocode; suggestions go to the review queue | daily |
| `parcels.py` | Load county parcel GeoJSON and attach street-level records to lots | `load` by hand, `match` nightly |
| `translate.py` | Fills `events.summary_es` | nightly |
| `common/runlog.py` | Every run goes to `pipeline_runs`, every Claude call to `ai_usage`, with a per-run spend cap | all |
| `common/scrub.py` | Name scrubber, run before any summary is stored | all |

## Wiring into `harvest.py` (about 10 lines)

```python
from pipeline.lang import has_keyword, EXTRACTION_SYSTEM
from pipeline.triage import worth_extracting
from pipeline.batches import extraction_params, write_items
from pipeline.common.runlog import PipelineRun

with PipelineRun("harvest_rss") as run:
    for page in pages:                                   # your existing loop
        if not has_keyword(page["text"]):                # now matches Spanish too
            continue
        run.items_in += 1
        if not worth_extracting(page["text"], run):      # cheap Haiku gate
            continue
        msg = client.messages.create(**extraction_params(page["text"]))  # Sonnet, cached system prompt
        run.ai("extract", msg.model, msg.usage)
        block = next(b for b in msg.content if b.type == "tool_use")
        run.items_out += write_items(page, block.input["items"])   # scrubs names, upserts, marks scanned
```

For the 1860s–1963 backlog, write pages to a JSONL file and run `python -m pipeline.batches submit pages.jsonl` instead of calling Claude live.

`geocode.py` needs one change: when a pre-1960 street address fails or falls back to the city centroid, set `geocode_status = 'failed'` or `'fallback'`. `historic_geo.py` picks those up.

> **Nominatim:** if `geocode.py` falls back to the public Nominatim server, keep it to at most 1 request per second, send an identifying User-Agent, and cache results. That's their usage policy.

## Parcel data

- **Bernalillo County** publishes parcels on its public GIS portal. Export them as GeoJSON in EPSG:4326, then:
  `python -m pipeline.parcels load bernalillo parcels.geojson --apn-field UPC --situs-field SITUS`. Check the real field names first.
- **Valencia County:** confirm a public parcel download exists. If not, ask the assessor's office for a GIS export.

## Cost controls

- `AP_MAX_RUN_COST_USD` (default $5) stops any single run once it passes that amount.
- Also set a monthly spend limit in the Anthropic Console.
