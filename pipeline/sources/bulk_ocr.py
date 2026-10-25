"""Chronicling America bulk OCR: whole batches of newspaper text, downloaded once and read locally.

Much faster than the search API (20 requests/minute, ~30 s each on a slow day), and it gives us the
page text to keep. The Library of Congress lists batches at
https://www.loc.gov/collections/chronicling-america/datasets/ (JSON: ?fo=json&at=datasets).

    python -m pipeline.sources.bulk_ocr discover        # print the dataset listing's shape + New Mexico batches
"""
from __future__ import annotations

import json
import sys

import requests

DATASETS = "https://www.loc.gov/collections/chronicling-america/datasets/"
UA = "AddressPast-bulk/1.0 (+https://history.skyhighwebsites.dev)"


def _get_json(url: str, params: dict) -> dict:
    r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=120)
    r.raise_for_status()
    return r.json()


def discover():
    data = _get_json(DATASETS, {"fo": "json", "at": "datasets"})
    print("top-level keys:", list(data)[:20])
    ds = data.get("datasets", data)
    if isinstance(ds, dict):
        print("datasets keys:", list(ds)[:20])
        items = ds.get("items") or ds.get("results") or ds.get("batches") or []
    else:
        items = ds
    print("items:", len(items) if hasattr(items, "__len__") else type(items))
    if items:
        print("first item:", json.dumps(items[0], indent=1)[:2500])
    nm = [i for i in items if "nm" in json.dumps(i).lower()[:400] and ("nmu" in json.dumps(i).lower() or "new mexico" in json.dumps(i).lower())]
    print(f"New Mexico-looking items: {len(nm)}")
    for i in nm[:80]:
        print(json.dumps(i)[:600])


if __name__ == "__main__":
    {"discover": discover}[sys.argv[1] if len(sys.argv) > 1 else "discover"]()
