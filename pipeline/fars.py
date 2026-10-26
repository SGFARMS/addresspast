"""Fatal traffic crashes in New Mexico from NHTSA's FARS (Fatality Analysis Reporting System).

Public-domain federal data: one row per fatal crash on a public road, with GPS coordinates, date,
county/city and number of people killed. No names. Each crash becomes one ap_incidents row with
record_type 'road_death' (a separate map layer, off until a visitor turns it on), already placed,
so it skips the geocoder; dedupe then makes it a public event without any AI calls.

    python -m pipeline.fars inspect 2022              # print the file names and accident.csv columns
    python -m pipeline.fars load --from 2000 --to 2024 [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import zipfile

import requests

NM = 35  # state FIPS
UA = "AddressPast-fars/1.0 (+https://history.skyhighwebsites.dev)"
SOURCE_NAME = "NHTSA Fatality Analysis Reporting System (FARS)"
SOURCE_PAGE = "https://www.nhtsa.gov/research-data/fatality-analysis-reporting-system-fars"

URLS = [
    "https://static.nhtsa.gov/nhtsa/downloads/FARS/{y}/National/FARS{y}NationalCSV.zip",
    "https://static.nhtsa.gov/nhtsa/downloads/FARS/{y}/National/FARS{y}NationalCSV.ZIP",
]

# NM county FIPS (older FARS years have codes only)
NM_COUNTIES = {
    1: "Bernalillo", 3: "Catron", 5: "Chaves", 6: "Cibola", 7: "Colfax", 9: "Curry", 11: "De Baca", 13: "Doña Ana",
    15: "Eddy", 17: "Grant", 19: "Guadalupe", 21: "Harding", 23: "Hidalgo", 25: "Lea", 27: "Lincoln", 28: "Los Alamos",
    29: "Luna", 31: "McKinley", 33: "Mora", 35: "Otero", 37: "Quay", 39: "Rio Arriba", 41: "Roosevelt", 43: "Sandoval",
    45: "San Juan", 47: "San Miguel", 49: "Santa Fe", 51: "Sierra", 53: "Socorro", 55: "Taos", 57: "Torrance",
    59: "Union", 61: "Valencia",
}


def download(year: int) -> zipfile.ZipFile:
    last = None
    for u in URLS:
        try:
            r = requests.get(u.format(y=year), headers={"User-Agent": UA}, timeout=300)
            if r.status_code == 200:
                return zipfile.ZipFile(io.BytesIO(r.content))
            last = f"HTTP {r.status_code} for {u.format(y=year)}"
        except requests.RequestException as e:
            last = str(e)
    raise RuntimeError(f"FARS {year}: {last}")


def accident_rows(z: zipfile.ZipFile):
    name = next((n for n in z.namelist() if re.search(r"(^|/)accident\.csv$", n, re.I)), None)
    if not name:
        raise RuntimeError(f"no accident.csv in {z.namelist()[:10]}")
    raw = z.read(name)
    text = raw.decode("utf-8") if raw[:3] == b"\xef\xbb\xbf" or _utf8(raw) else raw.decode("latin-1")
    return csv.DictReader(io.StringIO(text.lstrip("﻿")))


def _utf8(b: bytes) -> bool:
    try:
        b.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _name(v: str | None) -> str | None:
    """'ALBUQUERQUE (40)' -> 'Albuquerque'; 'NOT APPLICABLE' / 'Unknown' -> None."""
    if not v:
        return None
    v = re.sub(r"\s*\(\d+\)\s*$", "", v).strip()
    if not v or re.search(r"not applicable|unknown|not reported|other", v, re.I):
        return None
    return " ".join(w if w.lower() in ("de", "la", "del") else w.capitalize() for w in v.lower().split())


def to_incident(row: dict, year: int) -> dict | None:
    if int(_num(row.get("STATE")) or 0) != NM:
        return None
    lat, lng = _num(row.get("LATITUDE")), _num(row.get("LONGITUD"))
    if lat is None or lng is None or not (31.0 <= lat <= 37.5 and -109.5 <= lng <= -102.5):
        return None  # 77.7777 / 88.8888 / 99.9999 = not reported
    case = row.get("ST_CASE") or ""
    m, d = int(_num(row.get("MONTH")) or 0), int(_num(row.get("DAY")) or 0)
    date = f"{year}-{m:02d}-{d:02d}" if 1 <= m <= 12 and 1 <= d <= 31 else (f"{year}-{m:02d}" if 1 <= m <= 12 else str(year))
    county = _name(row.get("COUNTYNAME")) or NM_COUNTIES.get(int(_num(row.get("COUNTY")) or 0))
    city = _name(row.get("CITYNAME"))
    road = (row.get("TWAY_ID") or "").strip()
    road2 = (row.get("TWAY_ID2") or "").strip()
    where = f"{road} at {road2}" if road and road2 else road or "a public road"
    n = int(_num(row.get("FATALS")) or 1)
    summary = f"A fatal traffic crash on {where} was recorded; {n} {'person' if n == 1 else 'people'} died."
    return {
        "source_url": f"{SOURCE_PAGE}#case-{year}-{case}",
        "source_name": f"{SOURCE_NAME}, case {case}",
        "published_date": None,
        "incident_date": date,
        "address_raw": where[:300],
        "city": city,
        "county": county,
        "location_precision": "intersection" if road and road2 else "street_address",
        "place_kind": "road",
        "cause_category": "accident",
        "summary": summary,
        "summary_scrubbed": True,
        "confidence": 0.99,
        "source_language": "en",
        "record_type": "road_death",
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "geocode_status": "ok",
        "geocode_source": "fars",
        # A GPS point on the road: shown as a pin, but never counted "at this address" (see lib/data/supabase.ts)
        "geocode_precision": "street",
        "matched_address": f"FARS GPS {lat:.5f}, {lng:.5f}",
        "verified": True,
        "needs_review": False,
    }


def inspect(year: int):
    z = download(year)
    print("files:", z.namelist()[:30])
    rows = accident_rows(z)
    print("columns:", rows.fieldnames)
    nm = [r for r in rows if int(_num(r.get("STATE")) or 0) == NM]
    coord_cols = [c for c in (rows.fieldnames or []) if re.search(r"lat|lon", c, re.I)]
    print(f"{year} coordinate columns: {coord_cols}; first 5 NM values:",
          [{c: r.get(c) for c in coord_cols} for r in nm[:5]])
    print(f"{year}: {len(nm)} New Mexico crashes; sample:", {k: nm[0].get(k) for k in list(nm[0])[:40]} if nm else None)
    if nm:
        print("as incident:", to_incident(nm[0], year))


def load(first: int, last: int, dry_run: bool):
    from .common.runlog import PipelineRun

    total = 0
    by_year: dict[int, int] = {}
    with PipelineRun("fars") as run:
        for y in range(first, last + 1):
            try:
                rows = [i for i in (to_incident(r, y) for r in accident_rows(download(y))) if i]
            except RuntimeError as e:
                print(f"{y}: skipped ({e})", flush=True)
                continue
            by_year[y] = len(rows)
            total += len(rows)
            if not dry_run:
                from .common.db import db

                for i in range(0, len(rows), 500):
                    db().table("ap_incidents").upsert(rows[i : i + 500], on_conflict="source_url,address_raw",
                                                      ignore_duplicates=True).execute()
            print(f"{y}: {len(rows)} fatal crashes in New Mexico" + (" (dry run)" if dry_run else ""), flush=True)
        run.items_out = total
        run.meta = {"by_year": by_year, "dry_run": dry_run}
    print(f"FARS total: {total} crashes, {first}-{last}" + (" (dry run, nothing written)" if dry_run else ""))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("inspect")
    i.add_argument("year", type=int)
    lp = sub.add_parser("load")
    lp.add_argument("--from", dest="first", type=int, default=2000)
    lp.add_argument("--to", dest="last", type=int, default=2024)
    lp.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    inspect(a.year) if a.cmd == "inspect" else load(a.first, a.last, a.dry_run)
    sys.exit(0)
