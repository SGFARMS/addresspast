"""Load county parcel polygons and attach street-level incidents to the lot they fall on.

    python -m pipeline.parcels load bernalillo parcels_bernalillo.geojson --apn-field UPC --situs-field SITUS
    python -m pipeline.parcels match

Download parcel layers from the county GIS portals as GeoJSON in WGS84 (EPSG:4326):
  - Bernalillo County: public parcel layer on the county's open GIS / ArcGIS Hub
  - Valencia County: assessor parcel layer (confirm a public download is available)
"""
import argparse
import json

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


def load(county: str, path: str, apn_field: str, situs_field: str | None, chunk: int = 500):
    data = json.load(open(path, encoding="utf-8"))
    with PipelineRun("parcels", trigger="manual", meta={"county": county, "file": path}) as run:
        batch = []
        for f in data["features"]:
            props = f.get("properties") or {}
            apn = str(props.get(apn_field) or "").strip()
            wkt = to_multipolygon_wkt(f.get("geometry") or {})
            if not apn or not wkt:
                continue
            batch.append({
                "id": f"{county}:{apn}", "county": county, "apn": apn,
                "situs_address": props.get(situs_field) if situs_field else None,
                "geom": wkt, "source_url": path,
            })
            run.items_in += 1
            if len(batch) >= chunk:
                db().table("parcels").upsert(batch).execute()
                run.items_out += len(batch)
                batch = []
        if batch:
            db().table("parcels").upsert(batch).execute()
            run.items_out += len(batch)


def match():
    with PipelineRun("parcel_match") as run:
        n = db().rpc("match_incident_parcels", {}).execute().data
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
    sub.add_parser("match")
    a = ap.parse_args()
    load(a.county, a.path, a.apn_field, a.situs_field) if a.cmd == "load" else match()
