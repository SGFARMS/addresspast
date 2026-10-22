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
from .extract import extraction_params, items_from_message, write_items

client = Anthropic()


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
                page = pages.get(entry.custom_id)
                if page:
                    written += write_items(page, items_from_message(msg), MODEL_SMART)
            run.items_out = written
        db().table("ap_pipeline_runs").update({"status": "ok", "items_out": written}).eq("id", row["id"]).execute()
        print(batch.id, "wrote", written)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "poll"
    submit(sys.argv[2]) if cmd == "submit" else poll()
