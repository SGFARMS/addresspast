"""Historic address matching: pre-1960 street addresses that didn't geocode cleanly.

Claude suggests a likely modern location from the article context. Suggestions go to
location_suggestions (status=pending) for the admin review queue. Nothing is published
automatically; an admin accepting a suggestion sets geocode_precision='street_historic'.

    python -m pipeline.historic_geo [--limit 100]
"""
import argparse

from anthropic import Anthropic

from .common.config import MODEL_SMART
from .common.db import db
from .common.runlog import PipelineRun

client = Anthropic()

SYSTEM = """You help place historic New Mexico newspaper addresses on a modern map.
Street names and house numbers in Albuquerque, Belen, Los Lunas and other towns changed over time
(e.g. old Railroad Avenue became Central Avenue; Albuquerque renumbered addresses in the 1950s).
Given an address as printed, its town, year, and a short summary, suggest the most likely modern location.
Only suggest coordinates if you have a specific, defensible reason. Otherwise return found=false.
Explain your reasoning in one or two sentences for a human reviewer."""

TOOL = {
    "name": "suggest",
    "description": "Suggest a modern location for a historic address.",
    "input_schema": {
        "type": "object",
        "properties": {
            "found": {"type": "boolean"},
            "lat": {"type": ["number", "null"]},
            "lng": {"type": ["number", "null"]},
            "modern_address": {"type": ["string", "null"]},
            "rationale": {"type": "string"},
        },
        "required": ["found", "rationale"],
    },
}


def main(limit: int):
    rows = (
        db().table("ap_incidents")
        .select("id,address_raw,city,county,incident_year,summary,geocode_status,geocode_precision,location_precision")
        .lt("incident_year", 1960)
        .eq("location_precision", "street_address")
        .in_("geocode_status", ["failed", "fallback"])
        .limit(limit)
        .execute()
        .data
    )
    with PipelineRun("historic_geo") as run:
        for r in rows:
            exists = db().table("ap_location_suggestions").select("id").eq("incident_id", r["id"]).limit(1).execute().data
            if exists:
                continue
            run.items_in += 1
            msg = client.messages.create(
                model=MODEL_SMART,
                max_tokens=300,
                system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
                tools=[TOOL],
                tool_choice={"type": "tool", "name": "suggest"},
                messages=[{"role": "user", "content": f"Address as printed: {r['address_raw']}\nTown: {r['city']}, {r['county']} County, NM\nYear: {r['incident_year']}\nSummary: {r['summary']}"}],
            )
            run.ai("historic_geo", MODEL_SMART, msg.usage)
            s = next(b for b in msg.content if b.type == "tool_use").input
            if s.get("found") and s.get("lat") and s.get("lng"):
                db().table("ap_location_suggestions").insert({
                    "incident_id": r["id"], "suggested_lat": s["lat"], "suggested_lng": s["lng"],
                    "suggested_address": s.get("modern_address"), "rationale": s.get("rationale"), "model": MODEL_SMART,
                }).execute()
                run.items_out += 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100)
    main(ap.parse_args().limit)
