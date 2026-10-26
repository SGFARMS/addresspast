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
    base = "https://data.transportation.gov/resource/bda5-32at.json"
    rows = requests.get(base, params={"$limit": 2}, headers=UA, timeout=120).json()
    print("FRA fields:", sorted(rows[0]) if rows else rows)
    for k in ("statename", "state", "statecode"):
        if rows and k in rows[0]:
            print("state field:", k, rows[0][k])
    nm = requests.get(base, params={"$limit": 3, "$where": "upper(statename) like '%NEW MEXICO%'"}, headers=UA, timeout=120)
    print("NM sample:", nm.status_code, json.dumps(nm.json()[:2])[:2500])


def msha():
    for name in ("Accidents", "Mines"):
        r = requests.get(f"https://arlweb.msha.gov/OpenGovernmentData/DataSets/{name}.zip", headers=UA, timeout=300)
        print(name, r.status_code, len(r.content))
        z = zipfile.ZipFile(io.BytesIO(r.content))
        f = z.namelist()[0]
        with z.open(f) as fh:
            head = [fh.readline().decode("latin-1").rstrip() for _ in range(3)]
        print(name, "file:", f, "\n  header:", head[0][:1500], "\n  row:", head[1][:800])


if __name__ == "__main__":
    {"fra": fra, "msha": msha}[sys.argv[1]]()
