"""USGS place names (GNIS) for New Mexico, including towns that no longer exist.

Public domain. Two files: today's names (DomesticNames_NM) and the 2021 full archive, which still has
the abandoned camps, stage stops, forts and post offices the newer file dropped. Loaded once per run
(a few MB), so placing a town needs no web request.

    python -m pipeline.gnis "White Oaks" "Dawson" "Loma Parda/Mora"   # try lookups
"""
from __future__ import annotations

import csv
import io
import math
import re
import sys
import unicodedata
import zipfile
from functools import lru_cache

import requests

from .places_nm import Town

BUCKET = "https://prd-tnm.s3.amazonaws.com/StagedProducts/GeographicNames/"
FILES = ("DomesticNames/DomesticNames_NM_Text.zip", "Archive/MainDomestic/NM_Features_20210825.txt")
UA = {"User-Agent": "AddressPast-geocoder/1.0 (+https://history.skyhighwebsites.dev)"}

# Places a death can be "at", best first. ("Civil" is left out: those are counties and city limits.)
CLASS_RANK = {"populated place": 0, "military": 1, "locale": 2, "mine": 3, "post office": 4, "building": 5}

# Big places outside New Mexico that wire stories name and that also exist as tiny NM spots.
# A record naming one of these without a New Mexico county is taken to be about the famous one.
_ELSEWHERE = {
    "el paso", "juarez", "ciudad juarez", "chicago", "denver", "pueblo", "trinidad", "colorado springs",
    "kansas city", "los angeles", "new york", "new york city", "brooklyn", "washington", "phoenix", "tucson", "dallas", "fort worth",
    "amarillo", "san antonio", "houston", "st. louis", "saint louis", "topeka", "omaha", "salt lake city",
    "san francisco", "oakland", "sacramento", "san diego", "portland", "seattle", "boston", "philadelphia",
    "baltimore", "pittsburgh", "cleveland", "detroit", "cincinnati", "st. paul", "minneapolis", "milwaukee",
    "new orleans", "memphis", "nashville", "atlanta", "louisville", "indianapolis", "columbus", "buffalo",
    "albany", "richmond", "charleston", "jacksonville", "miami", "tampa", "galveston", "austin", "waco",
    "oklahoma city", "tulsa", "wichita", "dodge city", "leadville", "durango", "alamosa", "la junta",
    "las animas", "walsenburg", "globe", "bisbee", "tombstone", "prescott", "flagstaff", "yuma", "douglas",
    "nogales", "chihuahua", "mexico", "mexico city", "monterrey", "london", "paris", "berlin", "havana",
    "manila", "springfield", "jackson", "lincoln nebraska", "cheyenne", "laramie", "reno", "carson city",
    "boise", "butte", "helena", "spokane", "lubbock", "pecos", "big spring", "abilene", "san angelo",
}


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", (name or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\((historical|historic)\)", " ", s)
    s = re.sub(r"\bft\.?\s", "fort ", s)
    s = re.sub(r"\bst\.?\s", "saint ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _county_key(c: str | None) -> str:
    c = (c or "").lower().replace(" county", "").replace("ñ", "n").strip()
    return {"debaca": "de baca"}.get(c, c)


def _rows(path: str):
    r = requests.get(BUCKET + path, headers=UA, timeout=300)
    r.raise_for_status()
    if path.endswith(".zip"):
        z = zipfile.ZipFile(io.BytesIO(r.content))
        raw = z.read(next(n for n in z.namelist() if n.lower().endswith(".txt")))
    else:
        raw = r.content
    text = raw.decode("utf-8-sig", errors="replace")
    delim = "|" if text[:2000].count("|") > text[:2000].count(",") else ","
    for row in csv.DictReader(io.StringIO(text), delimiter=delim):
        yield {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}


@lru_cache(maxsize=1)
def index() -> dict[str, list[tuple[int, str, str, float, float]]]:
    """normalized name -> [(class rank, name, county, lat, lng)] for every New Mexico place a death can be at."""
    out: dict[str, list[tuple[int, str, str, float, float]]] = {}
    seen: set[str] = set()
    for path in FILES:
        try:
            rows = list(_rows(path))
        except Exception as e:  # one missing file never stops the geocoder
            print(f"gnis: {path} unavailable ({type(e).__name__})", flush=True)
            continue
        for row in rows:
            if (row.get("state_alpha") or "NM") != "NM" and (row.get("state_name") or "New Mexico") != "New Mexico":
                continue
            rank = CLASS_RANK.get((row.get("feature_class") or "").lower())
            fid = row.get("feature_id") or ""
            if rank is None or fid in seen:
                continue
            try:
                lat, lng = float(row.get("prim_lat_dec") or 0), float(row.get("prim_long_dec") or 0)
            except ValueError:
                continue
            if not (31.3 <= lat <= 37.1 and -109.1 <= lng <= -103.0):
                continue  # 0/0 = "unknown" in GNIS
            seen.add(fid)
            name = re.sub(r"\s*\((historical|historic)\)", "", row.get("feature_name") or "").strip()
            out.setdefault(_norm(name), []).append((rank, name, row.get("county_name") or "", lat, lng))
    print(f"gnis: {sum(len(v) for v in out.values())} New Mexico places loaded", flush=True)
    return out


def _km(a, b) -> float:
    return math.hypot((a[3] - b[3]) * 111, (a[4] - b[4]) * 111 * math.cos(math.radians(a[3])))


def gnis_town(name: str | None, county: str | None = None, county_fits=None) -> Town | None:
    """A New Mexico place by name (ghost towns too). With a county, only places that fit it (county_fits,
    which knows old county lines); without one, only when the best matches all sit within 25 km of each
    other; never for a famous out-of-state city name."""
    key = _norm(name or "")
    if not key or len(key) < 3:
        return None
    hits = index().get(key) or []
    if key in _ELSEWHERE:
        # Even with a county: on a re-check the county may be one an earlier lookup wrote onto the record.
        return None
    if county and county_fits:
        hits = [h for h in hits if county_fits(county, h[2])]
    if not hits:
        return None
    best = min(h[0] for h in hits)
    top = [h for h in hits if h[0] == best]
    if any(_km(top[0], h) > 25 for h in top[1:]):
        return None  # two different places share the name: don't guess
    h = top[0]
    return Town(h[1], h[2], round(h[3], 5), round(h[4], 5), ())  # GNIS casing (McKinley, Doña Ana)


if __name__ == "__main__":
    from .geocode import county_fits as _fits

    for arg in sys.argv[1:]:
        n, _, c = arg.partition("/")
        print(arg, "->", gnis_town(n, c or None, _fits))
