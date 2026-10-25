"""Nightly: group incidents that describe the same death into one event.

1. Every incident without an event gets a singleton event.
2. For each new incident, the dedupe_candidates RPC finds nearby rows (same type,
   compatible cause, ±1 year, within 400 m or same town for city-level records).
3. Claude (Sonnet) confirms or rejects each pair; decisions are cached in dedupe_checks.
4. Confirmed pairs merge into one event; refresh_event recomputes location + combined confidence.
5. area_coverage is refreshed for the free-check footnote.

    python -m pipeline.dedupe [--limit 500]
"""
import argparse

from anthropic import Anthropic

from .common.ai import create_with_tool, tool_input
from .common.config import MODEL_SMART
from .common.db import db
from .common.runlog import PipelineRun

client = Anthropic()

SYSTEM = """You decide whether two newspaper-derived records describe the SAME death.
Same death = same event, even if wording, dates (±a few days), or address details differ slightly.
Different deaths can happen at the same place; be careful with common causes like accidents.
Answer only with the tool call."""

TOOL = {
    "name": "decide",
    "description": "Whether the two records are the same death.",
    "input_schema": {
        "type": "object",
        "properties": {"same_event": {"type": "boolean"}, "rationale": {"type": "string"}},
        "required": ["same_event", "rationale"],
    },
}

FIELDS = "id,event_id,source_name,published_date,incident_date,address_raw,city,county,cause_category,summary,geocode_precision,record_type,incident_year"


def describe(r: dict) -> str:
    return (
        f"source={r.get('source_name')} published={r.get('published_date')} date={r.get('incident_date')} "
        f"place={r.get('address_raw')}, {r.get('city')} ({r.get('geocode_precision')}) cause={r.get('cause_category')} "
        f"summary={r.get('summary')}"
    )


def ensure_events(run) -> list[dict]:
    # Only geocoded, visible records that aren't waiting for human review become events.
    rows = (
        db().table("ap_incidents").select(FIELDS)
        .is_("event_id", "null").eq("hidden", False).eq("needs_review", False)
        .not_.is_("geocode_status", "null")
        .neq("geocode_status", "failed")  # no New Mexico town: never becomes a public event
        .limit(5000).execute().data
    )
    for r in rows:
        ev = db().table("ap_events").insert({
            "record_type": r.get("record_type") or "death",
            "cause_category": r.get("cause_category") or "unknown",
            "event_year": r.get("incident_year"),
            "city": r.get("city"),
            "county": r.get("county"),
            "summary": r.get("summary"),
        }).execute().data[0]
        db().table("ap_incidents").update({"event_id": ev["id"]}).eq("id", r["id"]).execute()
        db().rpc("ap_refresh_event", {"p_event_id": ev["id"]}).execute()
        r["event_id"] = ev["id"]
        run.items_in += 1
    return rows


def merge(keep_event: str, drop_event: str):
    if keep_event == drop_event:
        return
    db().table("ap_incidents").update({"event_id": keep_event}).eq("event_id", drop_event).execute()
    db().table("ap_events").delete().eq("id", drop_event).execute()
    db().rpc("ap_refresh_event", {"p_event_id": keep_event}).execute()


def main(limit: int):
    with PipelineRun("dedupe") as run:
        fresh = ensure_events(run)[:limit]
        for r in fresh:
            if r.get("record_type") == "road_death":
                continue  # official crash records (FARS) are one row per crash: nothing to merge, no AI calls
            cands = db().rpc("ap_dedupe_candidates", {"p_incident_id": r["id"]}).execute().data or []
            for c in cands:
                other = db().table("ap_incidents").select(FIELDS).eq("id", c["candidate_id"]).single().execute().data
                msg = create_with_tool(
                    client,
                    "decide",
                    model=MODEL_SMART,
                    max_tokens=200,
                    system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
                    tools=[TOOL],
                    messages=[{"role": "user", "content": f"A: {describe(r)}\nB: {describe(other)}\nDistance: {round(c.get('distance_m') or 0)} m"}],
                )
                run.ai("dedupe", MODEL_SMART, msg.usage)
                d = tool_input(msg)
                if not d or "same_event" not in d:
                    continue  # no usable answer: leave the pair unchecked so the next run asks again
                a, b = sorted([r["id"], other["id"]])
                db().table("ap_dedupe_checks").upsert({
                    "incident_a": a, "incident_b": b, "same_event": d["same_event"], "rationale": d.get("rationale"), "model": MODEL_SMART,
                }).execute()
                if d["same_event"] and other.get("event_id"):
                    merge(other["event_id"], r["event_id"])
                    r["event_id"] = other["event_id"]
                    run.items_out += 1
        db().rpc("ap_refresh_area_coverage", {}).execute()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500)
    main(ap.parse_args().limit)
