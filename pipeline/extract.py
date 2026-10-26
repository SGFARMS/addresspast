"""Extraction: Haiku first, Sonnet only for unclear or important records, then write.

Shared by harvest.py (live) and batches.py (Message Batches backlog).
"""
from __future__ import annotations

import os
import threading

from .common.ai import tool_input, tool_params
from .common.config import MODEL_FAST, MODEL_SMART
from .common.scrub import scrub_names
from .lang import EXTRACTION_SYSTEM, detect_language

PLACE_KINDS = ["house", "apartment_building", "boarding_house_or_hotel", "business", "public_place", "road", "other", "unknown"]
PRECISIONS = {"street_address", "intersection", "landmark", "city_only"}
CAUSES = {"natural", "accident", "homicide", "suicide", "fire", "unknown"}
_PRECISION_ALIASES = {"street": "street_address", "address": "street_address", "city": "city_only", "town": "city_only",
                      "county": "city_only", "town_only": "city_only", "corner": "intersection", "place": "landmark"}


def clean_precision(v, address: str | None) -> str:
    """The database accepts four values; the model sometimes says 'town', 'city' or nothing."""
    p = str(v or "").strip().lower().replace(" ", "_")
    p = _PRECISION_ALIASES.get(p, p)
    if p in PRECISIONS:
        return p
    return "landmark" if (address or "").strip() else "city_only"


def clean_cause(v) -> str:
    c = str(v or "").strip().lower()
    return c if c in CAUSES else "unknown"


REVIEW_KINDS = {"boarding_house_or_hotel": "boarding house or hotel", "business": "business address"}

EXTRACT_TOOL = {
    "name": "record_deaths",
    "description": "Record each qualifying death found in the text.",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "address_raw": {"type": "string"},
                        "unit": {"type": ["string", "null"]},
                        "city": {"type": ["string", "null"]},
                        "county": {"type": ["string", "null"]},
                        "location_precision": {"type": "string", "enum": ["street_address", "intersection", "landmark", "city_only"]},
                        "place_kind": {"type": "string", "enum": PLACE_KINDS},
                        "incident_date": {"type": ["string", "null"]},
                        "cause_category": {"type": "string", "enum": ["natural", "accident", "homicide", "suicide", "fire", "unknown"]},
                        "summary": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["address_raw", "location_precision", "place_kind", "cause_category", "summary", "confidence"],
                },
            }
        },
        "required": ["items"],
    },
}

_client = None
_client_lock = threading.Lock()


def client():
    global _client
    with _client_lock:
        if _client is None:
            from anthropic import Anthropic  # lazy so pure helpers import without the SDK

            _client = Anthropic(max_retries=4)
        return _client


def extraction_params(text: str, model: str = MODEL_SMART) -> dict:
    """Request params (also used for Message Batches). tool_choice fits the model: see common/ai.py."""
    return tool_params({
        "model": model,
        "max_tokens": 2000,
        "system": [{"type": "text", "text": EXTRACTION_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        "tools": [EXTRACT_TOOL],
        "messages": [{"role": "user", "content": text[:60000]}],
    }, "record_deaths")


def items_from_message(msg) -> list[dict]:
    items = (tool_input(msg) or {}).get("items", [])
    return [i for i in items if isinstance(i, dict) and (i.get("address_raw") or i.get("city"))]


def needs_sonnet(items: list[dict]) -> bool:
    """Worth a second, pricier look: a specific street address or intersection Haiku isn't sure about.
    (Town-level records don't pin a house, so Haiku's read stands; that keeps the full archive affordable.)"""
    for it in items:
        c = float(it.get("confidence", 0.5) or 0)
        if it.get("location_precision") in ("street_address", "intersection") and 0.3 <= c < 0.8:
            return True
    return False


def extract(text: str, run, allow_sonnet=lambda: True) -> tuple[list[dict], str]:
    """Haiku pass; re-run on Sonnet when needs_sonnet() and the Sonnet budget allows. Returns (items, model)."""
    msg = client().messages.create(**extraction_params(text, MODEL_FAST))
    run.ai("harvest_extract_fast", MODEL_FAST, msg.usage)
    items = items_from_message(msg)
    if items and needs_sonnet(items) and allow_sonnet():
        msg2 = client().messages.create(**extraction_params(text, MODEL_SMART))
        run.ai("harvest_extract_smart", MODEL_SMART, msg2.usage)
        if tool_input(msg2) is not None:  # Sonnet answered through the tool; otherwise keep Haiku's read
            return items_from_message(msg2), MODEL_SMART
    return items, MODEL_FAST


def review_reason(it: dict) -> str | None:
    # Boarding houses, hotels and businesses used to wait for a person; Joe chose to publish them like
    # every other record (Oct 26). Their place_kind is still stored and shown on the record.
    if os.environ.get("AP_HOLD_FOR_REVIEW") == "1":
        # Spot-check runs: every record waits in /admin until a person approves it.
        return "spot-check"
    return None


def to_rows(page: dict, items: list[dict], model: str | None = None) -> list[dict]:
    """Turn model items into ap_incidents rows. Names are scrubbed here, before anything is stored."""
    rows = []
    lang = page.get("language") or detect_language(page.get("text", ""))
    for it in items:
        summary, _hits = scrub_names(it.get("summary"))
        reason = review_reason(it)
        kind = it.get("place_kind") if it.get("place_kind") in PLACE_KINDS else "unknown"
        unit = (it.get("unit") or "").strip() or None
        rows.append({
            "source_url": page["url"],
            "source_name": page.get("source_name"),
            "published_date": page.get("published_date"),
            "incident_date": it.get("incident_date"),
            "address_raw": (it.get("address_raw") or "").strip()[:300],
            "unit": unit[:40] if unit else None,
            "city": it.get("city"),
            "county": (it.get("county") or "").replace(" County", "").strip() or None,
            "location_precision": clean_precision(it.get("location_precision"), it.get("address_raw")),
            "place_kind": kind,
            "cause_category": clean_cause(it.get("cause_category")),
            "summary": summary,
            "summary_scrubbed": True,
            "confidence": round(max(0.0, min(1.0, float(it.get("confidence", 0.5) or 0))), 3),
            "source_language": "es" if lang == "es" else "en",
            "needs_review": reason is not None,
            "review_reason": reason,
            **({"extract_model": model} if model else {}),
        })
    # One page can report the same place twice; keep the most confident row per address.
    best: dict[str, dict] = {}
    for r in rows:
        k = r["address_raw"]
        if k not in best or r["confidence"] > best[k]["confidence"]:
            best[k] = r
    return list(best.values())


def write_items(page: dict, items: list[dict], model: str | None = None) -> int:
    """Upsert incidents for one page and mark the page scanned."""
    from .common.db import db

    rows = to_rows(page, items, model)
    if rows:
        db().table("ap_incidents").upsert(rows, on_conflict="source_url,address_raw", ignore_duplicates=True).execute()
    db().table("ap_scanned_pages").upsert({"url": page["url"]}).execute()
    return len(rows)
