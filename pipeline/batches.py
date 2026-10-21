"""Historical backlog through the Message Batches API (50% off), with the extraction prompt cached.

    python -m pipeline.batches submit pages.jsonl   # {"url":..., "source_name":..., "published_date":..., "text":...} per line
    python -m pipeline.batches poll                 # collect finished batches, write incidents

Pending batch ids are tracked in pipeline_runs (job='harvest_historic', batch_id, status='running').
"""
import json
import sys

from anthropic import Anthropic

from .common.config import MODEL_SMART
from .common.db import db
from .common.runlog import PipelineRun
from .common.scrub import scrub_names
from .lang import EXTRACTION_SYSTEM, detect_language

client = Anthropic()

EXTRACT_TOOL = {
    "name": "record_deaths",
    "description": "Record each qualifying New Mexico death found on the page.",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "address_raw": {"type": "string"},
                        "city": {"type": ["string", "null"]},
                        "county": {"type": ["string", "null"]},
                        "location_precision": {"type": "string", "enum": ["street_address", "intersection", "landmark", "city_only"]},
                        "incident_date": {"type": ["string", "null"]},
                        "cause_category": {"type": "string", "enum": ["natural", "accident", "homicide", "suicide", "fire", "unknown"]},
                        "summary": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["address_raw", "location_precision", "cause_category", "summary", "confidence"],
                },
            }
        },
        "required": ["items"],
    },
}


def extraction_params(text: str) -> dict:
    return {
        "model": MODEL_SMART,
        "max_tokens": 2000,
        "system": [{"type": "text", "text": EXTRACTION_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        "tools": [EXTRACT_TOOL],
        "tool_choice": {"type": "tool", "name": "record_deaths"},
        "messages": [{"role": "user", "content": text[:60000]}],
    }


def write_items(page: dict, items: list[dict]) -> int:
    """Shared by live extraction and batch results. Scrubs names before anything is stored."""
    rows = []
    lang = detect_language(page.get("text", ""))
    for it in items:
        summary, _hits = scrub_names(it.get("summary"))
        rows.append({
            "source_url": page["url"],
            "source_name": page.get("source_name"),
            "published_date": page.get("published_date"),
            "incident_date": it.get("incident_date"),
            "address_raw": it.get("address_raw") or "",
            "city": it.get("city"),
            "county": it.get("county"),
            "location_precision": it.get("location_precision"),
            "cause_category": it.get("cause_category", "unknown"),
            "summary": summary,
            "summary_scrubbed": True,
            "confidence": max(0.0, min(1.0, float(it.get("confidence", 0.5)))),
            "source_language": lang,
        })
    if rows:
        db().table("ap_incidents").upsert(rows, on_conflict="source_url,address_raw", ignore_duplicates=True).execute()
    db().table("ap_scanned_pages").upsert({"url": page["url"]}).execute()
    return len(rows)


def submit(path: str, chunk: int = 5000):
    pages = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    for i in range(0, len(pages), chunk):
        part = pages[i : i + chunk]
        with PipelineRun("harvest_historic", trigger="batch", meta={"pages": [p["url"] for p in part]}) as run:
            batch = client.messages.batches.create(
                requests=[{"custom_id": f"p{i + j}", "params": extraction_params(p["text"])} for j, p in enumerate(part)]
            )
            run.batch_id = batch.id
            run.items_in = len(part)
            run.status = "running"
            # Pages are kept in a sidecar file so poll() can match custom_id → page
            with open(f"batch_{batch.id}.jsonl", "w", encoding="utf-8") as f:
                for j, p in enumerate(part):
                    f.write(json.dumps({"custom_id": f"p{i + j}", **p}) + "\n")
            print("submitted", batch.id, len(part))


def poll():
    pending = db().table("ap_pipeline_runs").select("id,batch_id").eq("job", "harvest_historic").eq("status", "running").execute().data
    for row in pending:
        batch = client.messages.batches.retrieve(row["batch_id"])
        if batch.processing_status != "ended":
            print(row["batch_id"], batch.processing_status)
            continue
        pages = {}
        try:
            with open(f"batch_{batch.id}.jsonl", encoding="utf-8") as f:
                pages = {json.loads(l)["custom_id"]: json.loads(l) for l in f}
        except FileNotFoundError:
            print("missing sidecar for", batch.id)
            continue
        written = 0
        with PipelineRun("harvest_historic_results", trigger="batch") as run:
            for entry in client.messages.batches.results(batch.id):
                if entry.result.type != "succeeded":
                    continue
                msg = entry.result.message
                run.ai("extract", MODEL_SMART, msg.usage, batched=True)
                block = next((b for b in msg.content if b.type == "tool_use"), None)
                page = pages.get(entry.custom_id)
                if block and page:
                    written += write_items(page, block.input.get("items", []))
            run.items_out = written
        db().table("ap_pipeline_runs").update({"status": "ok", "items_out": written}).eq("id", row["id"]).execute()
        print(batch.id, "wrote", written)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "poll"
    submit(sys.argv[2]) if cmd == "submit" else poll()
