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


def fra():
    cols = requests.get("https://data.transportation.gov/api/views/icqf-xf4w/columns.json", headers=UA, timeout=120).json()
    print("FRA columns:", [(c.get("fieldName"), c.get("name")) for c in cols][:120])
    base = "https://data.transportation.gov/resource/icqf-xf4w.json"
    rows = requests.get(base, params={"$limit": 2}, headers=UA, timeout=120).json()
    print("FRA sample:", json.dumps(rows[:1])[:2500] if isinstance(rows, list) else rows)


def msha():
    for name in ("Accidents", "Mines"):
        r = requests.get(f"https://arlweb.msha.gov/OpenGovernmentData/DataSets/{name}.zip", headers=UA, timeout=300)
        print(name, r.status_code, len(r.content))
        z = zipfile.ZipFile(io.BytesIO(r.content))
        f = z.namelist()[0]
        with z.open(f) as fh:
            head = [fh.readline().decode("latin-1").rstrip() for _ in range(3)]
        cols = head[0].split("|")
        print(name, "file:", f, "columns:", cols)


if __name__ == "__main__":
    {"fra": fra, "msha": msha}[sys.argv[1]]()
