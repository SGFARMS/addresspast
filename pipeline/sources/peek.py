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


if __name__ == "__main__":
    {"fra": fra, "msha": msha}[sys.argv[1]]()
