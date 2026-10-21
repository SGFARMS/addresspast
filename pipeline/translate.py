"""Fill events.summary_es from the English summary with Haiku. Names are scrubbed before and after.

    python -m pipeline.translate [--limit 500]
"""
import argparse

from anthropic import Anthropic

from .common.config import MODEL_FAST
from .common.db import db
from .common.runlog import PipelineRun
from .common.scrub import scrub_names

client = Anthropic()

SYSTEM = """Translate one neutral property-record sentence from English to Spanish as used in New Mexico.
Keep the same calm, factual tone. Keep place names as they are. Never add names or details.
Return only the translation."""


def main(limit: int):
    rows = db().table("events").select("id,summary").is_("summary_es", "null").not_.is_("summary", "null").eq("hidden", False).limit(limit).execute().data
    with PipelineRun("translate") as run:
        for r in rows:
            run.items_in += 1
            src, _ = scrub_names(r["summary"])
            msg = client.messages.create(
                model=MODEL_FAST,
                max_tokens=200,
                system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": src}],
            )
            run.ai("translate", MODEL_FAST, msg.usage)
            es, _ = scrub_names("".join(b.text for b in msg.content if b.type == "text").strip())
            if es:
                db().table("events").update({"summary_es": es}).eq("id", r["id"]).execute()
                run.items_out += 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500)
    main(ap.parse_args().limit)
