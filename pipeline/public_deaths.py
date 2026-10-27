"""More public-domain death records with locations (federal data, no names stored):

- FRA highway-rail grade crossing incidents in New Mexico (1975-today) where someone was killed,
  pinned at the crossing's GPS point from the FRA crossing inventory; town level when the crossing
  has no coordinates. Layer: road_death ("Fatal traffic crash"), since they happen where a road
  crosses the tracks.
- MSHA fatal mine accidents in New Mexico (2000-today), pinned at the mine. Layer: death (accident).
- NTSB fatal aircraft accidents in New Mexico (1982-today), pinned at the crash site. Layer: death (accident).
  Needs mdbtools (mdb-export) for NTSB's Access database.
- NOAA Storm Events deaths in New Mexico (1950-today: floods, lightning, heat, cold, wind), at the
  event's GPS point when it has one, otherwise the town. Layer: death (accident).

    python -m pipeline.public_deaths fra|msha|ntsb|noaa|all [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import zipfile

import requests

UA = {"User-Agent": "AddressPast-public-deaths/1.0 (+https://history.skyhighwebsites.dev)"}
FRA_INCIDENTS = "https://data.transportation.gov/resource/icqf-xf4w.json"
FRA_INVENTORY = "https://data.transportation.gov/resource/m2f8-22s6.json"
FRA_COLUMNS = "https://data.transportation.gov/api/views/{id}/columns.json"
FRA_PAGE = "https://railroads.dot.gov/safety-data/highway-rail-crossings"
MSHA = "https://arlweb.msha.gov/OpenGovernmentData/DataSets/{name}.zip"
MSHA_PAGE = "https://www.msha.gov/data-and-reports/mine-data-retrieval-system"
NM_BOX = (31.0, 37.5, -109.5, -102.5)


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _in_nm(lat: float | None, lng: float | None) -> bool:
    return lat is not None and lng is not None and NM_BOX[0] <= lat <= NM_BOX[1] and NM_BOX[2] <= lng <= NM_BOX[3]


def _title(v: str | None) -> str | None:
    v = re.sub(r"(,?\s+(NEW MEXICO|N\.?\s?M\.?))+\s*$", "", (v or "").strip(), flags=re.I).strip()
    if not v or re.search(r"^(unknown|n/?a|none|0)$", v, re.I):
        return None
    return " ".join(w.capitalize() for w in v.lower().split())


def _coord(v) -> float | None:
    """Decimal degrees, or DDMMSS-style numbers some federal files use."""
    x = _num(v)
    if not x:
        return None
    if abs(x) > 180:  # e.g. 351234.5 = 35°12'34.5"
        sign = -1 if x < 0 else 1
        x = abs(x)
        d, rest = divmod(x, 10000)
        m, s = divmod(rest, 100)
        x = sign * (d + m / 60 + s / 3600)
    return x


# ── FRA ─────────────────────────────────────────────────────────────────────────────────────────
def _get(url: str, params: dict | None = None, timeout: int = 300):
    """data.transportation.gov is slow at times: three tries with a long timeout."""
    import time

    for i in range(3):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError):
            if i == 2:
                raise
            time.sleep(20 * (i + 1))


def _field(dataset: str, *patterns: str) -> str:
    cols = [c.get("fieldName") or "" for c in _get(FRA_COLUMNS.format(id=dataset))]
    for p in patterns:
        hit = next((c for c in cols if re.fullmatch(p, c, re.I)), None)
        if hit:
            return hit
    raise RuntimeError(f"{dataset}: no column like {patterns} in {cols[:60]}")


def fra_rows() -> list[dict]:
    data = _get(FRA_INCIDENTS, {"$where": "state='35'", "$limit": 50000})
    fatal = [r for r in data if max(_num(r.get("totkld")), _num(r.get("userkld")), _num(r.get("caskldrr"))) > 0]
    # GPS for each crossing from the inventory
    id_col = _field("m2f8-22s6", r"crossingid", r"crossing_id", r"crossing", r"gxid")
    lat_col = _field("m2f8-22s6", r"latitude", r"lat")
    lng_col = _field("m2f8-22s6", r"longitude", r"long", r"lon")
    ids = sorted({r.get("gxid") for r in fatal if r.get("gxid")})
    where: dict[str, tuple[float, float]] = {}
    for i in range(0, len(ids), 40):
        chunk = ids[i : i + 40]
        inv = _get(FRA_INVENTORY, {
            "$select": f"{id_col},{lat_col},{lng_col}",
            "$where": f"{id_col} in ({','.join(repr(x) for x in chunk)})",
            "$limit": 1000,
        })
        for row in inv if isinstance(inv, list) else []:
            lat, lng = _coord(row.get(lat_col)), _coord(row.get(lng_col))
            if _in_nm(lat, lng):
                where[row.get(id_col)] = (round(lat, 6), round(lng, 6))  # type: ignore[arg-type]
    out = []
    for r in fatal:
        y = int(_num(r.get("year4")) or 0) or (1900 + int(_num(r.get("year"))) if _num(r.get("year")) > 50 else 2000 + int(_num(r.get("year"))))
        m, d = int(_num(r.get("month"))), int(_num(r.get("day")))
        date = f"{y}-{m:02d}-{d:02d}" if 1 <= m <= 12 and 1 <= d <= 31 else str(y)
        killed = int(max(_num(r.get("totkld")), _num(r.get("userkld")), _num(r.get("caskldrr"))))
        highway = (r.get("highway") or "").strip()
        highway = _title(highway) or ""
        where_txt = f"the railroad crossing at {highway}" if highway else "a railroad crossing"
        gx = r.get("gxid") or ""
        row = {
            "source_url": f"{FRA_PAGE}#fra-{y}-{r.get('railroad', '')}-{r.get('incdtno', '')}",
            "source_name": f"Federal Railroad Administration crossing incident {r.get('railroad', '')} {r.get('incdtno', '')}".strip(),
            "published_date": None,
            "incident_date": date,
            "address_raw": (f"Railroad crossing {gx}" + (f", {highway}" if highway else ""))[:300],
            "city": _title(r.get("city")) or _title(r.get("station")),
            "county": _title(r.get("county")),
            "location_precision": "intersection",
            "place_kind": "road",
            "cause_category": "accident",
            "summary": f"A fatal collision at {where_txt} was recorded; {killed} {'person' if killed == 1 else 'people'} died.",
            "summary_scrubbed": True,
            "confidence": 0.99,
            "source_language": "en",
            "record_type": "road_death",
            "verified": True,
            "needs_review": False,
        }
        if gx in where:
            lat, lng = where[gx]
            row["county"] = None  # incident county is unreliable (e.g. Gallup filed under Valencia); the GPS point decides
            row.update({"lat": lat, "lng": lng, "geocode_status": "ok", "geocode_source": "fra_inventory",
                        "geocode_precision": "street", "matched_address": f"FRA crossing {gx}"})
        out.append(row)
    print(f"FRA: {len(data)} New Mexico crossing incidents, {len(fatal)} with deaths, {len(where)} crossings with GPS")
    return out


# ── MSHA ────────────────────────────────────────────────────────────────────────────────────────
def _pipe_rows(name: str):
    r = requests.get(MSHA.format(name=name), headers=UA, timeout=600)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    text = z.read(z.namelist()[0]).decode("latin-1")
    return csv.DictReader(io.StringIO(text), delimiter="|", quotechar='"')


def msha_rows() -> list[dict]:
    accidents = [a for a in _pipe_rows("Accidents")
                 if (a.get("FIPS_STATE_CD") or "").strip() == "35" and (a.get("DEGREE_INJURY_CD") or "").strip() == "01"]
    want = {a.get("MINE_ID") for a in accidents}
    mines = {m["MINE_ID"]: m for m in _pipe_rows("Mines") if m.get("MINE_ID") in want}
    out = []
    for a in accidents:
        m = mines.get(a.get("MINE_ID"), {})
        name = _title(m.get("CURRENT_MINE_NAME")) or f"Mine {a.get('MINE_ID')}"
        if len(name) <= 6:  # "Sx-Ew", "Mill": say whose mine it is
            name = f"{name} mine ({_title(m.get('FIPS_CNTY_NM')) or 'New Mexico'} County)"
        mm, dd, yy = (re.findall(r"\d+", a.get("ACCIDENT_DT") or "") + ["", "", ""])[:3]
        date = f"{yy}-{int(mm):02d}-{int(dd):02d}" if yy and mm and dd else (yy or None)
        kind = (a.get("ACCIDENT_TYPE") or "").strip().lower()
        kind = re.sub(r"[\s.]*\bnec\b\.?", "", kind).strip(" .,")
        kind = "" if not kind or "no value" in kind else f" ({kind})"
        lat, lng = _coord(m.get("LATITUDE")), _coord(m.get("LONGITUDE"))
        if lng and lng > 0:
            lng = -lng  # some rows store west longitude without the sign
        row = {
            "source_url": f"{MSHA_PAGE}#msha-{a.get('DOCUMENT_NO', '')}",
            "source_name": f"Mine Safety and Health Administration accident report {a.get('DOCUMENT_NO', '')}",
            "published_date": None,
            "incident_date": date,
            "address_raw": name[:300],
            "city": None,
            "county": _title(m.get("FIPS_CNTY_NM")),
            "location_precision": "landmark",
            "place_kind": "other",
            "cause_category": "accident",
            "summary": f"A fatal mining accident{kind} at a {(m.get('CURRENT_MINE_TYPE') or 'mine').lower()} mine was recorded.",
            "summary_scrubbed": True,
            "confidence": 0.99,
            "source_language": "en",
            "record_type": "death",
            "verified": True,
            "needs_review": False,
        }
        if _in_nm(lat, lng):
            row.update({"lat": round(lat, 6), "lng": round(lng, 6), "geocode_status": "ok", "geocode_source": "msha",  # type: ignore[arg-type]
                        "geocode_precision": "landmark", "matched_address": f"MSHA mine {a.get('MINE_ID')}"})
        out.append(row)
    print(f"MSHA: {len(accidents)} fatal New Mexico mine accidents since 2000, {sum(1 for r in out if r.get('lat'))} with mine GPS")
    return out


# ── NTSB ────────────────────────────────────────────────────────────────────────────────────────
NTSB = "https://data.ntsb.gov/avdata/FileDirectory/DownloadFile?fileID=C%3A%5Cavdata%5C{name}"
NTSB_PAGE = "https://www.ntsb.gov/Pages/investigations.aspx"


def ntsb_rows() -> list[dict]:
    import os
    import subprocess
    import tempfile

    out: list[dict] = []
    seen: set[str] = set()
    for name in ("avall.zip", "Pre2008.zip"):
        r = requests.get(NTSB.format(name=name), headers=UA, timeout=900)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        mdb = next(n for n in z.namelist() if n.lower().endswith((".mdb", ".accdb")))
        d = tempfile.mkdtemp()
        path = z.extract(mdb, d)
        text = subprocess.run(["mdb-export", path, "events"], capture_output=True, text=True, check=True).stdout
        os.remove(path)
        for e in csv.DictReader(io.StringIO(text)):
            if (e.get("ev_state") or "").upper() != "NM" or int(_num(e.get("inj_tot_f"))) <= 0:
                continue
            ev = e.get("ev_id") or ""
            if ev in seen:
                continue
            seen.add(ev)
            n = int(_num(e.get("inj_tot_f")))
            y = int(_num(e.get("ev_year"))) or None
            mo = re.match(r"(\d{1,2})/(\d{1,2})/", e.get("ev_date") or "")
            date = f"{y}-{int(mo.group(1)):02d}-{int(mo.group(2)):02d}" if (y and mo) else (str(y) if y else None)
            city = _title(e.get("ev_city"))
            apt = _title(e.get("apt_name"))
            near = f" near {city}" if city else ""
            row = {
                "source_url": f"{NTSB_PAGE}#ntsb-{e.get('ntsb_no') or ev}",
                "source_name": f"National Transportation Safety Board aviation accident {e.get('ntsb_no') or ev}",
                "published_date": None,
                "incident_date": date,
                "address_raw": (f"Aircraft crash site{near}" + (f" ({apt})" if apt else ""))[:300],
                "city": city,
                "county": None,
                "location_precision": "landmark",
                "place_kind": "other",
                "cause_category": "accident",
                "summary": f"A fatal aircraft accident{near} was recorded; {n} {'person' if n == 1 else 'people'} died.",
                "summary_scrubbed": True,
                "confidence": 0.99,
                "source_language": "en",
                "record_type": "death",
                "verified": True,
                "needs_review": False,
            }
            lat, lng = _coord(e.get("dec_latitude")), _coord(e.get("dec_longitude"))
            if _in_nm(lat, lng):
                row.update({"lat": round(lat, 6), "lng": round(lng, 6), "geocode_status": "ok", "geocode_source": "ntsb",  # type: ignore[arg-type]
                            "geocode_precision": "landmark", "matched_address": f"NTSB crash site {ev}"})
            out.append(row)
    print(f"NTSB: {len(out)} fatal New Mexico aircraft accidents, {sum(1 for r in out if r.get('lat'))} with GPS")
    return out


# ── NOAA Storm Events ───────────────────────────────────────────────────────────────────────────
NOAA_DIR = "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/"
NOAA_PAGE = "https://www.ncdc.noaa.gov/stormevents/eventdetails.jsp?id={id}"


def noaa_rows() -> list[dict]:
    import gzip

    listing = requests.get(NOAA_DIR, headers=UA, timeout=120).text
    files = sorted(set(re.findall(r'href="(StormEvents_details-ftp_v1\.0_d\d{4}_c\d+\.csv\.gz)"', listing)))
    out = []
    for f in files:
        txt = gzip.decompress(requests.get(NOAA_DIR + f, headers=UA, timeout=300).content).decode("latin-1")
        for e in csv.DictReader(io.StringIO(txt)):
            if e.get("STATE") != "NEW MEXICO":
                continue
            n = int(_num(e.get("DEATHS_DIRECT")) + _num(e.get("DEATHS_INDIRECT")))
            if n <= 0:
                continue
            ym = (e.get("BEGIN_YEARMONTH") or "").strip()
            day = int(_num(e.get("BEGIN_DAY")))
            date = f"{ym[:4]}-{ym[4:6]}-{day:02d}" if len(ym) == 6 and 1 <= day <= 31 else (ym[:4] or None)
            kind = (e.get("EVENT_TYPE") or "weather event").strip().lower()
            # "3W ALBUQUERQUE" / "(ABQ)ALBUQUERQUE INTL" -> "Albuquerque"
            place = _title(re.sub(r"^\d+(\.\d+)?\s*[NSEW]{1,3}\s+|^\([A-Z0-9]+\)", "", (e.get("BEGIN_LOCATION") or "").strip()))
            county = _title(e.get("CZ_NAME")) if (e.get("CZ_TYPE") or "").upper() == "C" else None
            near = f" near {place}" if place else (f" in {county} County" if county else "")
            row = {
                "source_url": NOAA_PAGE.format(id=e.get("EVENT_ID")),
                "source_name": f"NOAA Storm Events Database, event {e.get('EVENT_ID')}",
                "published_date": None,
                "incident_date": date,
                "address_raw": (f"{kind.capitalize()}{near}")[:300],
                "city": place,
                "county": county,
                "location_precision": "landmark" if e.get("BEGIN_LAT") else "city_only",
                "place_kind": "other",
                "cause_category": "accident",
                "summary": f"A weather-related death ({kind}){near} was recorded; {n} {'person' if n == 1 else 'people'} died.",
                "summary_scrubbed": True,
                "confidence": 0.95,
                "source_language": "en",
                "record_type": "death",
                "verified": True,
                "needs_review": False,
            }
            lat, lng = _coord(e.get("BEGIN_LAT")), _coord(e.get("BEGIN_LON"))
            if _in_nm(lat, lng):
                row.update({"lat": round(lat, 6), "lng": round(lng, 6), "geocode_status": "ok", "geocode_source": "noaa",  # type: ignore[arg-type]
                            "geocode_precision": "landmark", "matched_address": f"NOAA event {e.get('EVENT_ID')}"})
            out.append(row)
    print(f"NOAA: {len(out)} New Mexico weather events with deaths, {sum(1 for r in out if r.get('lat'))} with GPS")
    return out


def save(rows: list[dict], dry_run: bool):
    if dry_run or not rows:
        for r in rows[:3]:
            print("sample:", {k: r[k] for k in ("incident_date", "address_raw", "city", "county", "summary") if k in r},
                  "GPS" if r.get("lat") else "town-level")
        return
    from .common.db import db, retry

    # Rows with and without GPS have different columns; upsert each shape separately.
    for shape in (True, False):
        part = [r for r in rows if bool(r.get("lat")) == shape]
        for i in range(0, len(part), 200):
            chunk = part[i : i + 200]
            retry(lambda: db().table("ap_incidents").upsert(chunk, on_conflict="source_url,address_raw",
                                                            ignore_duplicates=True).execute())
    print(f"saved {len(rows)} rows")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("which", choices=["fra", "msha", "ntsb", "noaa", "all"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    failed = []
    for name, fn in (("fra", fra_rows), ("msha", msha_rows), ("ntsb", ntsb_rows), ("noaa", noaa_rows)):
        if a.which in (name, "all"):
            try:  # one slow or broken source never stops the others
                save(fn(), a.dry_run)
            except Exception as e:
                failed.append(name)
                print(f"{name}: failed: {type(e).__name__}: {str(e)[:300]}", flush=True)
    if failed:
        raise SystemExit(f"failed: {', '.join(failed)}")
