"""Read-only counts: how many records we have and where each one stands.

    python -m pipeline.stats
"""
from __future__ import annotations

from .common.db import db


def count(table: str, col: str = "id", **filters) -> int:
    q = db().table(table).select(col, count="exact")
    for k, v in filters.items():
        if k == "placed":
            q = q.not_.is_("geom", "null") if v else q.is_("geom", "null")
        elif k.endswith("__isnull"):
            q = q.is_(k[:-8], "null") if v else q.not_.is_(k[:-8], "null")
        else:
            q = q.eq(k, v)
    return q.limit(1).execute().count or 0


def main():
    total = count("ap_incidents")
    rows = [
        ("Records found (all sources)", total),
        ("  hidden by you or by a removal request", count("ap_incidents", hidden=True)),
        ("  waiting in /admin (boarding house, business, spot-check)", count("ap_incidents", hidden=False, needs_review=True)),
        ("  not placed yet (geocoder hasn't run on them)", count("ap_incidents", hidden=False, geocode_status__isnull=True)),
        ("  no New Mexico town (wire news from elsewhere)", count("ap_incidents", hidden=False, geocode_status="failed")),
        ("  placed, waiting for the nightly publish", count("ap_incidents", hidden=False, needs_review=False, event_id__isnull=True)
         - count("ap_incidents", hidden=False, needs_review=False, event_id__isnull=True, geocode_status="failed")
         - count("ap_incidents", hidden=False, needs_review=False, event_id__isnull=True, geocode_status__isnull=True)),
        ("Deaths on the public map (events)", count("ap_events", hidden=False, placed=True, record_type="death")),
        ("  natural causes (hidden on the map until turned on)",
         count("ap_events", hidden=False, placed=True, record_type="death", cause_category="natural")),
        ("  placed at a street, landmark or intersection", count("ap_events", hidden=False, placed=True, record_type="death")
         - count("ap_events", hidden=False, placed=True, record_type="death", geocode_precision="city")),
        ("  placed at town level only", count("ap_events", hidden=False, placed=True, record_type="death", geocode_precision="city")),
        ("Fatal traffic crashes on the map (FARS layer)", count("ap_events", hidden=False, placed=True, record_type="road_death")),
        ("Fatal traffic crashes loaded", count("ap_incidents", record_type="road_death")),
        ("Site entries with no map spot (should be 0)", count("ap_events", hidden=False, placed=False)),
        ("Newspaper pages read so far", count("ap_scanned_pages", col="url")),
    ]
    lines = ["## AddressPast record counts", "", "| | |", "|---|---|"] + [f"| {k} | {v:,} |" for k, v in rows]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
