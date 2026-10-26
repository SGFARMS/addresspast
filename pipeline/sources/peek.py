"""Print the shape of candidate public datasets (fields + a few New Mexico rows). Read-only, no database.

    python -m pipeline.sources.peek fra|msha
"""
from __future__ import annotations

import io
import json
import sys
import zipfile

import requests

UA = {"User-Agent": "AddressPast-peek/1.0 (+https://history.skyhighwebsites.dev)"}


import re

KEEP = re.compile(r"lat|lon|stat|cnty|county|city|kil|kld|high|street|date|year|iyr|month|day|narr|degree|mine_name|name|no_inj|typ|crossing|gxid", re.I)


def fra():
    cols = requests.get("https://data.transportation.gov/api/views/icqf-xf4w/columns.json", headers=UA, timeout=120).json()
    for c in cols:
        if KEEP.search(c.get("fieldName") or ""):
            print("FRA col", c.get("fieldName"), "|", (c.get("description") or "")[:80])
    base = "https://data.transportation.gov/resource/icqf-xf4w.json"
    nm = requests.get(base, params={"$limit": 1, "$where": "state='35'"}, headers=UA, timeout=120).json()
    print("NM row:", nm if not isinstance(nm, list) else {k: v for k, v in (nm[0] if nm else {}).items() if KEEP.search(k)})
    cnt = requests.get(base, params={"$select": "count(*)", "$where": "state='35'"}, headers=UA, timeout=120).json()
    print("NM rows:", cnt)


def msha():
    for name in ("Accidents", "Mines"):
        r = requests.get(f"https://arlweb.msha.gov/OpenGovernmentData/DataSets/{name}.zip", headers=UA, timeout=300)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        with z.open(z.namelist()[0]) as fh:
            cols = fh.readline().decode("latin-1").rstrip().split("|")
        for c in cols:
            if KEEP.search(c):
                print(name, "col", c)


def news():
    """robots.txt rules and sitemap shape for each local outlet (for an archive of recent deaths)."""
    from .rss import FEEDS

    for name, feed, _city in FEEDS:
        site = "/".join(feed.split("/")[:3])
        try:
            rb = requests.get(site + "/robots.txt", headers=UA, timeout=30)
            lines = [l.strip() for l in rb.text.splitlines() if re.match(r"(?i)(user-agent|disallow|sitemap|crawl-delay)", l.strip())]
            print(f"== {name} robots {rb.status_code}: {lines[:25]}")
            maps = [l.split(":", 1)[1].strip() for l in lines if l.lower().startswith("sitemap")]
            for m in (maps or [site + "/sitemap.xml"])[:2]:
                sm = requests.get(m, headers=UA, timeout=60)
                locs = re.findall(r"<loc>([^<]+)</loc>", sm.text)
                print(f"   sitemap {m} -> {sm.status_code}, {len(locs)} entries, e.g. {locs[:3]} ... {locs[-2:]}")
        except Exception as e:
            print(f"== {name}: {type(e).__name__}: {str(e)[:150]}")


if __name__ == "__main__":
    {"fra": fra, "msha": msha, "news": news}[sys.argv[1]]()
