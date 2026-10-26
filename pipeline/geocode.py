"""Geocode new incidents: Census Geocoder -> Photon -> town centroid.

    python -m pipeline.geocode [--limit 2000]

Rules (approximate locations are always labeled; nothing is placed more precisely than we know):
  - street_address, 1960 or later: US Census Geocoder. A match near the stated town -> precision 'street'.
  - street_address before 1960: Albuquerque and other towns renamed streets and renumbered houses, so a modern
    match may be the wrong lot. We store the Census candidate in matched_address for the reviewer, place the
    record at the town (precision 'city', status 'fallback'), and historic_geo.py suggests a location for review.
  - landmark: Photon (OSM). Accepted only if the result's name matches the landmark and it's near the town.
  - intersection: placed at the town for now (status 'fallback'); a street-line intersection lookup comes later.
  - city_only, or anything that fails: the town centroid, precision 'city'.
geocode_status: ok | fallback | failed (no recognizable pilot town).
"""
from __future__ import annotations

import argparse
import math
import re
import time
from datetime import datetime, timezone

import requests

from .places_nm import NM_COUNTIES, NM_PLACE_NAMES, Town, find_towns, town_by_name

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
PHOTON_URL = "https://photon.komoot.io/api/"
NM_BBOX = (-109.06, 31.33, -103.0, 37.0)
USER_AGENT = "AddressPast-geocoder/1.0 (+https://history.skyhighwebsites.dev)"
HISTORIC_BEFORE = 1960
MAX_KM_FROM_TOWN = {"street": 25.0, "landmark": 15.0}

_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT
_cache: dict[str, object] = {}
_last_call = {"census": 0.0, "photon": 0.0}
_MIN_GAP = {"census": 0.4, "photon": 1.0}


def _pace(name: str):
    gap = time.monotonic() - _last_call[name]
    if gap < _MIN_GAP[name]:
        time.sleep(_MIN_GAP[name] - gap)
    _last_call[name] = time.monotonic()


def km(lat1, lng1, lat2, lng2) -> float:
    p = math.pi / 180
    a = 0.5 - math.cos((lat2 - lat1) * p) / 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lng2 - lng1) * p)) / 2
    return 12742 * math.asin(math.sqrt(a))


def in_nm(lat, lng) -> bool:
    return NM_BBOX[0] <= lng <= NM_BBOX[2] and NM_BBOX[1] <= lat <= NM_BBOX[3]


def census(address: str) -> tuple[float, float, str] | None:
    key = "c:" + address.lower()
    if key in _cache:
        return _cache[key]  # type: ignore[return-value]
    _pace("census")
    try:
        r = _session.get(CENSUS_URL, params={"address": address, "benchmark": "Public_AR_Current", "format": "json"}, timeout=30)
        r.raise_for_status()
        matches = r.json().get("result", {}).get("addressMatches") or []
    except (requests.RequestException, ValueError):
        return None  # not cached: a transient failure is retried next run
    hit = None
    if matches:
        m = matches[0]
        hit = (float(m["coordinates"]["y"]), float(m["coordinates"]["x"]), m.get("matchedAddress", ""))
    _cache[key] = hit
    return hit


def photon(query: str, places_only: bool = False) -> dict | None:
    key = ("pp:" if places_only else "p:") + query.lower()
    if key in _cache:
        return _cache[key]  # type: ignore[return-value]
    _pace("photon")
    try:
        params = {"q": query, "limit": 1, "lang": "en", "bbox": ",".join(map(str, NM_BBOX))}
        if places_only:
            params["osm_tag"] = "place"  # towns and villages only, not a same-named street or building
        r = _session.get(PHOTON_URL, params=params, timeout=30)
        r.raise_for_status()
        feats = r.json().get("features") or []
    except (requests.RequestException, ValueError):
        return None
    hit = feats[0] if feats else None
    _cache[key] = hit
    return hit


_STOP = {"the", "of", "de", "la", "el", "los", "las", "hotel", "house", "a", "at", "near", "old", "new"}


def _tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-záéíóúñ]+", (s or "").lower()) if w not in _STOP and len(w) > 2}


def name_matches(wanted: str, got: str) -> bool:
    a, b = _tokens(wanted), _tokens(got)
    return bool(a) and len(a & b) / len(a) >= 0.5


_PLACE_KINDS = {"city", "town", "village", "hamlet", "locality", "suburb", "neighbourhood", "isolated_dwelling"}


_KNOWN_NM = {n.lower() for n in NM_PLACE_NAMES}
_NM_COUNTY_NAMES = set(NM_COUNTIES)


def _norm_county(c: str | None) -> str:
    """'Doña Ana County' / 'Dona Ana' / 'DeBaca' all compare equal to their usual spelling."""
    c = (c or "").replace(" County", "").replace(" county", "").strip().lower().replace("ñ", "n")
    return {"debaca": "de baca"}.get(c, c)


def plausibly_nm(city: str, county: str | None) -> bool:
    """Is this record really about a New Mexico town? Papers carried wire news from everywhere, and some
    out-of-state names exist as tiny NM spots too ("New York" in Cibola County). Accept a statewide
    match only for a well-known NM town, or when the record itself names a New Mexico county."""
    if city.strip().lower() in _KNOWN_NM:
        return True
    return _norm_county(county) in _NM_COUNTY_NAMES


def nm_town(name: str | None, county: str | None = None, recheck: bool = False, trusted: bool = False) -> Town | None:
    """Any New Mexico town, looked up on Photon (OpenStreetMap), for places outside the pilot list.

    recheck: the record was placed before, so its county may be one this geocoder filled in from
    Photon itself; a county that merely repeats Photon's answer is then no evidence the place is in NM."""
    if not name or not name.strip() or not (trusted or plausibly_nm(name, county)):
        return None
    key = "t:" + name.strip().lower()
    if key in _cache:
        town = _cache[key]
    else:
        town = None
        f = photon(f"{name.strip()}, New Mexico", places_only=True)
        if f:
            lng, lat = f["geometry"]["coordinates"][:2]
            props = f.get("properties") or {}
            label = props.get("name") or ""
            kind = props.get("osm_value") or props.get("type") or ""
            if kind in _PLACE_KINDS and in_nm(lat, lng) and name_matches(name, label):
                osm_county = (props.get("county") or "").replace(" County", "").strip()  # keep OSM's casing (McKinley)
                town = Town(label, osm_county, float(lat), float(lng), ())
        _cache[key] = town
    if (recheck and not trusted and town and name.strip().lower() not in _KNOWN_NM
            and _norm_county(county) == _norm_county(town.county)):
        return None
    return town  # type: ignore[return-value]


def _county_name(c: str) -> str | None:
    """Pilot towns carry lowercase slugs ("valencia"); statewide lookups keep OSM's casing ("McKinley")."""
    if not c:
        return None
    return c if any(ch.isupper() for ch in c) else c.title()


_LCCN_RE = re.compile(r"/resource/([a-z]{0,3}\d{6,12})/")


def paper_town(source_url: str | None) -> str | None:
    """The town a Chronicling America paper was printed in (from the page URL's LCCN)."""
    m = _LCCN_RE.search(source_url or "")
    if not m:
        return None
    from .sources.bulk_ocr import paper_info

    cities = paper_info(m.group(1)).get("cities") or []
    return cities[0].title() if cities else None


# Counties New Mexico carved out of older ones (modern county -> counties its land used to belong to).
# A record naming the older county for a town in the newer one is right for its time (Cubero, Valencia
# County, 1910); a record naming an unrelated county (an Albuquerque pin for a Grant County item) is not.
COUNTY_PARENTS = {
    "cibola": {"valencia"}, "los alamos": {"sandoval", "santa fe"}, "catron": {"socorro"}, "harding": {"mora", "union"},
    "lea": {"chaves", "eddy"}, "curry": {"quay", "roosevelt"}, "roosevelt": {"chaves", "guadalupe"},
    "quay": {"guadalupe"}, "torrance": {"valencia", "lincoln", "bernalillo", "santa fe", "san miguel"},
    "sandoval": {"bernalillo", "rio arriba"}, "mckinley": {"bernalillo", "valencia"},
    "otero": {"doña ana", "dona ana", "lincoln", "socorro"}, "luna": {"grant", "doña ana", "dona ana"},
    "sierra": {"socorro", "doña ana", "dona ana", "grant"}, "hidalgo": {"grant"},
    "de baca": {"chaves", "guadalupe", "roosevelt"}, "debaca": {"chaves", "guadalupe", "roosevelt"},
    "union": {"colfax", "mora", "san miguel"}, "san juan": {"rio arriba"}, "eddy": {"lincoln", "chaves"},
    "chaves": {"lincoln"}, "guadalupe": {"san miguel"}, "grant": {"doña ana", "dona ana"}, "colfax": {"mora"},
    "lincoln": {"socorro", "doña ana", "dona ana"}, "valencia": {"bernalillo"},
}


def county_fits(record_county: str | None, town_county: str | None) -> bool:
    """False only when the record names a New Mexico county that the town has never belonged to."""
    rc, tc = _norm_county(record_county), _norm_county(town_county)
    if not rc or not tc or rc not in _NM_COUNTY_NAMES or rc == tc:
        return True
    return rc in COUNTY_PARENTS.get(tc, set()) or tc in COUNTY_PARENTS.get(rc, set())


_COUNTY_PHRASE = re.compile(r"\b[\w ]{0,20}?\b(?:county|co\.)\b|\bcondado\s+de\s+\w+", re.I)


def resolve_town(row: dict, recheck: bool = False) -> Town | None:
    """Find the town for a record.

    1. The record's own town: the built-in pilot list (with OCR variants), then anywhere in NM via Photon.
    2. A pilot town named in the address text ("county" phrases removed, so "Valencia county" isn't the
       village of Valencia).
    3. No town at all: a local item, so the town the paper was printed in (trusted as New Mexico).
    """
    city = (row.get("city") or "").strip()
    if city:
        t = town_by_name(city) or nm_town(city, row.get("county"), recheck)
        if t and county_fits(row.get("county"), t.county):
            return t
        if t:
            return None  # the town says one county, the record another: don't guess (Albuquerque pin for Grant County)
    address = _COUNTY_PHRASE.sub(" ", row.get("address_raw") or "")
    found = find_towns(address)
    if found:
        return found[0]
    if not city:
        town_from_paper = paper_town(row.get("source_url"))
        if town_from_paper:
            t = town_by_name(town_from_paper) or nm_town(town_from_paper, row.get("county"), recheck, trusted=True)
            # An Albuquerque paper's item about Grant County is not in Albuquerque.
            return t if t and county_fits(row.get("county"), t.county) else None
    return None


def geocode_row(row: dict, recheck: bool = False) -> dict:
    """Return the ap_incidents update for one row (pure apart from the HTTP lookups)."""
    now = datetime.now(timezone.utc).isoformat()
    town = resolve_town(row, recheck)
    if not town:
        # Clear any earlier placement so a re-check can take a wrong pin off the map.
        return {"geocode_status": "failed", "geocode_source": None, "geocoded_at": now,
                "lat": None, "lng": None, "geocode_precision": None}

    base = {"city": row.get("city") or town.name, "county": row.get("county") or _county_name(town.county), "geocoded_at": now}
    at_town = {**base, "lat": town.lat, "lng": town.lng, "geocode_precision": "city", "geocode_source": "town_centroid"}
    precision = row.get("location_precision")
    year = row.get("incident_year")
    historic = year is not None and year < HISTORIC_BEFORE
    addr = (row.get("address_raw") or "").strip()

    if precision == "street_address" and addr:
        hit = census(f"{addr}, {town.name}, NM")
        if hit and in_nm(hit[0], hit[1]) and km(hit[0], hit[1], town.lat, town.lng) <= MAX_KM_FROM_TOWN["street"]:
            if historic:
                return {**at_town, "geocode_status": "fallback", "matched_address": f"census candidate (unverified for {year}): {hit[2]}"}
            return {**base, "lat": hit[0], "lng": hit[1], "geocode_precision": "street", "geocode_source": "census",
                    "geocode_status": "ok", "matched_address": hit[2]}
        return {**at_town, "geocode_status": "fallback"}

    if precision == "landmark" and addr:
        f = photon(f"{addr}, {town.name}, New Mexico")
        if f:
            lng, lat = f["geometry"]["coordinates"][:2]
            props = f.get("properties") or {}
            label = props.get("name") or ""
            kind = props.get("type") or props.get("osm_value") or ""
            if (kind not in ("city", "county", "state", "country", "district", "locality")
                    and name_matches(addr, label)
                    and in_nm(lat, lng)
                    and km(lat, lng, town.lat, town.lng) <= MAX_KM_FROM_TOWN["landmark"]):
                return {**base, "lat": lat, "lng": lng, "geocode_precision": "landmark", "geocode_source": "photon",
                        "geocode_status": "ok", "matched_address": label}
        return {**at_town, "geocode_status": "fallback"}

    if precision == "intersection":
        return {**at_town, "geocode_status": "fallback"}

    return {**at_town, "geocode_status": "ok"}  # city_only: the town is exactly what we know


def _select(retry_failed: bool, recheck_towns: bool, after_id: int, page: int):
    from .common.db import db, retry

    q = db().table("ap_incidents").select("id,address_raw,city,county,location_precision,incident_year,event_id,source_url")
    if recheck_towns:
        # Re-place every town-level record with the current rules (fixes earlier wrong statewide matches).
        q = q.or_("geocode_status.is.null,geocode_status.eq.failed,geocode_precision.eq.city")
    elif retry_failed:
        # Records that found no town before (e.g. outside the old three-county list)
        q = q.or_("geocode_status.is.null,geocode_status.eq.failed")
    else:
        q = q.is_("geocode_status", "null")
    return q.eq("hidden", False).gt("id", after_id).order("id").limit(page).execute().data or []


def main(limit: int, retry_failed: bool = False, recheck_towns: bool = False, max_minutes: float = 40):
    """Place records, a page at a time (the API returns at most 1,000 rows per request) until none are
    left, `limit` is reached or `max_minutes` pass. Paging by id, so a re-check never loops."""
    from .common.db import db, retry
    from .common.runlog import PipelineRun

    counts: dict[str, int] = {}
    done = 0
    last_id = 0
    t0 = time.monotonic()
    with PipelineRun("geocode") as run:
        while done < limit and (time.monotonic() - t0) / 60 < max_minutes:
            rows = retry(lambda: _select(retry_failed, recheck_towns, last_id, min(1000, limit - done)))
            if not rows:
                break
            for r in rows:
                last_id = r["id"]
                run.items_in += 1
                upd = geocode_row(r, recheck=recheck_towns)
                retry(lambda: db().table("ap_incidents").update(upd).eq("id", r["id"]).execute())
                if r.get("event_id"):
                    if upd["geocode_status"] == "failed":
                        # No New Mexico town after all: detach it, so its event loses this record (and is hidden
                        # if nothing else backs it). If it's placed later, dedupe gives it a fresh event.
                        retry(lambda: db().table("ap_incidents").update({"event_id": None}).eq("id", r["id"]).execute())
                    # Move (or remove) the event to match.
                    retry(lambda: db().rpc("ap_refresh_event", {"p_event_id": r["event_id"]}).execute())
                k = f"{upd['geocode_status']}/{upd.get('geocode_precision') or '-'}"
                counts[k] = counts.get(k, 0) + 1
                run.items_out += 1 if upd["geocode_status"] == "ok" else 0
                done += 1
                if (time.monotonic() - t0) / 60 >= max_minutes:
                    break
        run.meta = {"counts": counts}
    print("geocoded", done, counts)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100000)
    ap.add_argument("--max-minutes", type=float, default=40)
    ap.add_argument("--retry-failed", action="store_true", help="also retry records that found no town before")
    ap.add_argument("--recheck-towns", action="store_true", help="re-place every town-level record with the current rules")
    a = ap.parse_args()
    main(a.limit, a.retry_failed, a.recheck_towns, a.max_minutes)
