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
import time

from anthropic import Anthropic

from .common.ai import create_with_tool, tool_input
from .common.config import MODEL_FAST as MODEL_DEDUPE
from .common.db import db, retry
from .common.runlog import PipelineRun
from .dedupe_rules import rule_verdict

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

FIELDS = "id,event_id,source_url,source_name,published_date,incident_date,address_raw,city,county,cause_category,summary,geocode_precision,record_type,incident_year"


def describe(r: dict) -> str:
    return (
        f"source={r.get('source_name')} published={r.get('published_date')} date={r.get('incident_date')} "
        f"place={r.get('address_raw')}, {r.get('city')} ({r.get('geocode_precision')}) cause={r.get('cause_category')} "
        f"summary={r.get('summary')}"
    )


def _make_event(r: dict) -> dict:
    return retry(lambda: _make_event_once(r))


def _make_event_once(r: dict) -> dict:
    if r.get("event_id"):  # a retry after the insert already went through
        return r
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
    return r


def ensure_events(run, max_minutes: float = 40) -> list[dict]:
    """Give every placed, visible, unheld record its own public event. Pages through the backlog (the API
    returns at most 1,000 rows per request) two at a time, until none are left."""
    from concurrent.futures import ThreadPoolExecutor

    t0 = time.monotonic()
    made: list[dict] = []
    # 2 at a time: each event is three requests including a recompute; more than that once knocked the
    # shared database over (Oct 26).
    with ThreadPoolExecutor(max_workers=2) as pool:
        while (time.monotonic() - t0) / 60 < max_minutes:
            # Only geocoded, visible records that aren't waiting for human review become events.
            rows = (
                db().table("ap_incidents").select(FIELDS)
                .is_("event_id", "null").eq("hidden", False).eq("needs_review", False)
                .not_.is_("geocode_status", "null")
                .neq("geocode_status", "failed")  # no New Mexico town: never becomes a public event
                .order("id").limit(1000).execute().data
            ) or []
            if not rows:
                break
            for r in pool.map(_make_event, rows):
                made.append(r)
                run.items_in += 1
            print(f"  published {len(made)} so far", flush=True)
    return made


def merge(keep_event: str, drop_event: str):
    if not keep_event or not drop_event or keep_event == drop_event:
        return
    retry(lambda: db().table("ap_incidents").update({"event_id": keep_event}).eq("event_id", drop_event).execute())
    try:
        retry(lambda: db().table("ap_events").delete().eq("id", drop_event).execute())
    except Exception as e:  # e.g. a removal request points at it: keep the empty event hidden instead
        print(f"  could not delete event {drop_event}: {str(e)[:120]}", flush=True)
        retry(lambda: db().table("ap_events").update({"hidden": True}).eq("id", drop_event).execute())
    retry(lambda: db().rpc("ap_refresh_event", {"p_event_id": keep_event}).execute())


def _record(a_id: int, b_id: int, same: bool, why: str, model: str):
    a, b = sorted([a_id, b_id])
    retry(lambda: db().table("ap_dedupe_checks").upsert({
        "incident_a": a, "incident_b": b, "same_event": same, "rationale": why[:500], "model": model,
    }).execute())


def check_incident(run, r: dict) -> int:
    """Compare one published record with its likely twins; merge the ones that are the same death.
    Rules first (free), the model only for pairs the rules can't settle. Returns merges made."""
    if r.get("record_type") == "road_death" or not r.get("event_id"):
        return 0  # official crash records are one row per crash
    merged = 0
    cands = retry(lambda: db().rpc("ap_dedupe_candidates", {"p_incident_id": r["id"]}).execute().data) or []
    for c in cands[:8]:
        other = retry(lambda: db().table("ap_incidents").select(FIELDS).eq("id", c["candidate_id"]).single().execute().data)
        verdict = rule_verdict(r, other)
        if verdict is not None:
            same, why, model = verdict, ("same day, town and cause" if verdict else "dates too far apart"), "rule"
        else:
            msg = create_with_tool(
                client,
                "decide",
                model=MODEL_DEDUPE,
                max_tokens=200,
                system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
                tools=[TOOL],
                messages=[{"role": "user", "content": f"A: {describe(r)}\nB: {describe(other)}\nDistance: {round(c.get('distance_m') or 0)} m"}],
            )
            run.ai("dedupe", MODEL_DEDUPE, msg.usage)
            d = tool_input(msg)
            if not d or "same_event" not in d:
                continue  # no usable answer: leave the pair unchecked so a later run asks again
            same, why, model = bool(d["same_event"]), d.get("rationale") or "", MODEL_DEDUPE
        _record(r["id"], other["id"], same, why, model)
        if same and other.get("event_id") and other["event_id"] != r.get("event_id"):
            merge(other["event_id"], r["event_id"])
            r["event_id"] = other["event_id"]
            merged += 1
    return merged


def _sweep_start() -> int:
    rows = retry(lambda: db().table("ap_pipeline_runs").select("meta").eq("job", "dedupe_sweep")
                 .order("started_at", desc=True).limit(1).execute().data) or []
    return int(((rows[0].get("meta") or {}) if rows else {}).get("last_id") or 0)


def sweep(max_minutes: float):
    """Go back over every published death record (oldest first, resuming where the last sweep stopped)
    and merge duplicates the publish step never got to. Wraps around when it reaches the end."""
    t0 = time.monotonic()
    with PipelineRun("dedupe_sweep") as run:
        last = _sweep_start()
        checked = merges = 0
        while (time.monotonic() - t0) / 60 < max_minutes:
            rows = retry(lambda: db().table("ap_incidents").select(FIELDS)
                         .eq("record_type", "death").eq("hidden", False).not_.is_("event_id", "null")
                         .gt("id", last).order("id").limit(200).execute().data) or []
            if not rows:
                last = 0  # start over next time
                break
            for r in rows:
                merges += check_incident(run, r)
                checked += 1
                last = r["id"]
                if (time.monotonic() - t0) / 60 >= max_minutes:
                    break
        run.items_in, run.items_out = checked, merges
        run.meta = {"last_id": last}
    print(f"dedupe sweep: checked {checked} records, merged {merges} duplicates (next start after id {last})")


def main(limit: int, max_minutes: float = 40):
    t0 = time.monotonic()
    with PipelineRun("dedupe") as run:
        fresh = ensure_events(run, max_minutes)[:limit]
        for r in fresh:
            if (time.monotonic() - t0) / 60 >= max_minutes * 1.5:
                print("  dedupe: time limit, the rest waits for the sweep", flush=True)
                break
            run.items_out += check_incident(run, r)
        retry(lambda: db().rpc("ap_refresh_area_coverage", {}).execute())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--max-minutes", type=float, default=40, help="stop publishing new events after this long")
    ap.add_argument("--sweep", action="store_true", help="go back over already-published records for duplicates")
    a = ap.parse_args()
    sweep(a.max_minutes) if a.sweep else main(a.limit, a.max_minutes)
