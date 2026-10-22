"""Load county parcel polygons and attach street-level incidents to the lot they fall on.

    python -m pipeline.parcels fetch bernalillo          # straight from the county's public ArcGIS layer
    python -m pipeline.parcels load bernalillo parcels_bernalillo.geojson --apn-field UPC --situs-field SITUS
    python -m pipeline.parcels match

Only the parcel id, situs address and shape are stored (never owner names or values).
Year built: Bernalillo's public parcel layer doesn't include it. When a source has it, pass
--year-built-field and the free check shows "this building was built in ...".

Download parcel layers from the county GIS portals as GeoJSON in WGS84 (EPSG:4326):
  - Bernalillo County: public parcel layer on the county's open GIS / ArcGIS Hub
  - Valencia County: assessor parcel layer (confirm a public download is available)
"""
import argparse
import json
import time

import requests

from .common.db import db
from .common.runlog import PipelineRun


def to_multipolygon_wkt(geom: dict) -> str | None:
    def ring(r):
        return "(" + ", ".join(f"{x} {y}" for x, y, *_ in r) + ")"

    if geom["type"] == "Polygon":
        polys = [geom["coordinates"]]
    elif geom["type"] == "MultiPolygon":
        polys = geom["coordinates"]
    else:
        return None
    return "SRID=4326;MULTIPOLYGON(" + ", ".join("(" + ", ".join(ring(r) for r in p) + ")" for p in polys) + ")"


# Public ArcGIS layers we can page through directly (id field, situs field, optional year-built field).
ARCGIS_SOURCES = {
    "bernalillo": {
        "url": "https://gismap.bernco.gov/arcgis/rest/services/Public_Permits/MapServer/15/query",
        "apn": "UPC", "situs": "SITUSADD", "year_built": None,
    },
}


def fetch_arcgis(county: str, page: int = 1000):
    """Yield GeoJSON features page by page (WGS84), ordered by OBJECTID so paging is stable."""
    src = ARCGIS_SOURCES[county]
    fields = ",".join(f for f in ("OBJECTID", src["apn"], src["situs"], src["year_built"]) if f)
    s = requests.Session()
    s.headers["User-Agent"] = "AddressPast-parcels/1.0 (+https://history.skyhighwebsites.dev)"
    last = -1
    while True:
        params = {"where": f"OBJECTID > {last}", "outFields": fields, "outSR": 4326, "f": "geojson",
                  "orderByFields": "OBJECTID", "resultRecordCount": page, "returnGeometry": "true"}
        for attempt in range(4):
            try:
                r = s.get(src["url"], params=params, timeout=120)
                r.raise_for_status()
                feats = r.json().get("features") or []
                break
            except (requests.RequestException, ValueError):
                if attempt == 3:
                    raise
                time.sleep(15 * (attempt + 1))
        if not feats:
            return
        yield from feats
        last = max(int((f.get("properties") or {}).get("OBJECTID") or f.get("id") or last) for f in feats)
        time.sleep(0.5)


def load(county: str, path: str, apn_field: str, situs_field: str | None, chunk: int = 500,
         year_built_field: str | None = None, features=None, source: str | None = None):
    feats = features if features is not None else json.load(open(path, encoding="utf-8"))["features"]
    with PipelineRun("parcels", trigger="manual", meta={"county": county, "source": source or path}) as run:
        batch = []
        for f in feats:
            props = f.get("properties") or {}
            apn = str(props.get(apn_field) or "").strip()
            wkt = to_multipolygon_wkt(f.get("geometry") or {})
            if not apn or not wkt:
                continue
            batch.append({
                "id": f"{county}:{apn}", "county": county, "apn": apn,
                "situs_address": props.get(situs_field) if situs_field else None,
                "year_built": _year(props.get(year_built_field)) if year_built_field else None,
                "geom": wkt, "source_url": source or path,
            })
            run.items_in += 1
            if len(batch) >= chunk:
                db().table("ap_parcels").upsert(batch).execute()
                run.items_out += len(batch)
                batch = []
        if batch:
            db().table("ap_parcels").upsert(batch).execute()
            run.items_out += len(batch)


def _year(v) -> int | None:
    try:
        y = int(str(v)[:4])
    except (TypeError, ValueError):
        return None
    return y if 1700 <= y <= 2100 else None


def match():
    with PipelineRun("parcel_match") as run:
        n = db().rpc("ap_match_incident_parcels", {}).execute().data
        run.items_out = int(n or 0)
        print("matched", n)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("load")
    l.add_argument("county")
    l.add_argument("path")
    l.add_argument("--apn-field", required=True)
    l.add_argument("--situs-field")
    l.add_argument("--year-built-field")
    fe = sub.add_parser("fetch")
    fe.add_argument("county", choices=sorted(ARCGIS_SOURCES))
    sub.add_parser("match")
    a = ap.parse_args()
    if a.cmd == "load":
        load(a.county, a.path, a.apn_field, a.situs_field, year_built_field=a.year_built_field)
    elif a.cmd == "fetch":
        src = ARCGIS_SOURCES[a.county]
        load(a.county, "", src["apn"], src["situs"], year_built_field=src["year_built"],
             features=fetch_arcgis(a.county), source=src["url"].rsplit("/query", 1)[0])
    else:
        match()
