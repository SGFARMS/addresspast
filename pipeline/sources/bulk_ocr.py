"""Chronicling America bulk OCR: whole batches of New Mexico newspaper text, read straight from the archive.

Much faster than the search API (20 requests/minute, ~30 s each on a slow day). The Library of Congress
lists batches at https://www.loc.gov/collections/chronicling-america/datasets/ (JSON: ?fo=json&at=datasets);
each batch is one .tar.bz2 with an ocr.txt (plain text) and an ALTO XML file per page. We stream the
archive, read only the ocr.txt files and never write it to disk, so a 0.5 GB batch needs no disk space.

The text is public domain and stays permanently available from the Library (and mirrors), so we keep
only what we extract plus a record of which pages we've read.

    python -m pipeline.sources.bulk_ocr discover   # print the listing's shape + the New Mexico batches
    python -m pipeline.sources.bulk_ocr batches    # the New Mexico batches we would read
"""
from __future__ import annotations

import json
import re
import sys
import tarfile
import time
from functools import lru_cache
from typing import Iterator

import requests

from .loc import LocPage

DATASETS = "https://www.loc.gov/collections/chronicling-america/datasets/"
UA = "AddressPast-bulk/1.0 (+https://history.skyhighwebsites.dev; property-history research)"
NM_PREFIX = "nmu_"  # University of New Mexico, the state's NDNP awardee

# <lccn>/<yyyy>/<mm>/<dd>/ed-<n>/seq-<n>/ocr.txt, possibly under a batch folder
_PAGE_RE = re.compile(r"(?:^|/)([a-z]{0,3}\d{6,12})/(\d{4})/(\d{2})/(\d{2})/ed-(\d+)/seq-(\d+)/ocr\.txt$")

_session = requests.Session()
_session.headers["User-Agent"] = UA


def _get_json(url: str, params: dict | None = None) -> dict:
    r = _session.get(url, params=params, timeout=120)
    r.raise_for_status()
    return r.json()


def _items(data) -> list[dict]:
    ds = data.get("datasets", data) if isinstance(data, dict) else data
    if isinstance(ds, dict):
        ds = ds.get("items") or ds.get("results") or ds.get("batches") or []
    return [i for i in ds if isinstance(i, dict)]


def nm_batches() -> list[dict]:
    """New Mexico batches, oldest ingest first: {batch, url, size, page_count, lccns}."""
    items = _items(_get_json(DATASETS, {"fo": "json", "at": "datasets"}))
    out = []
    for i in items:
        name = i.get("batch") or ""
        if name.startswith(NM_PREFIX) and i.get("url"):
            out.append({"batch": name, "url": i["url"], "size": i.get("size"), "page_count": i.get("page_count"),
                        "lccns": i.get("lccns") or [], "ingested": i.get("ingested") or ""})
    return sorted(out, key=lambda b: b["ingested"])


@lru_cache(maxsize=None)
def paper_info(lccn: str) -> dict:
    """Title, city and languages for one newspaper (cached; one small request per paper)."""
    info = {"title": None, "cities": [], "languages": []}
    for url, params in ((f"https://chroniclingamerica.loc.gov/lccn/{lccn}.json", None),
                        (f"https://www.loc.gov/item/{lccn}/", {"fo": "json"})):
        try:
            time.sleep(1.0)
            d = _get_json(url, params)
        except (requests.RequestException, ValueError):
            continue
        item = d.get("item", d) if isinstance(d, dict) else {}
        title = item.get("name") or item.get("title")
        if isinstance(title, list):
            title = title[0] if title else None
        cities = []
        for p in item.get("place") or item.get("location_city") or []:
            # "New Mexico--Bernalillo--Albuquerque" or "albuquerque"
            cities.append(str(p).split("--")[-1].strip().lower())
        pop = item.get("place_of_publication") or ""
        if pop:
            cities.append(str(pop).split(",")[0].strip().lower())
        langs = []
        for x in item.get("languages") or item.get("language") or []:
            # plain strings, or {"english": "<search url>"} on loc.gov
            langs.extend(str(k).lower() for k in (x.keys() if isinstance(x, dict) else [x]))
        if title or cities:
            info = {"title": title, "cities": sorted(set(c for c in cities if c)), "languages": langs}
            break
    return info


def page_url(lccn: str, y: str, m: str, d: str, ed: str, seq: str) -> str:
    """Same form the search API gives us (normalize_url), so pages read either way are recognised."""
    return f"https://www.loc.gov/resource/{lccn}/{y}-{m}-{d}/ed-{ed}/?sp={seq}&st=text"


def stream_pages(batch: dict, start_year: int = 0, end_year: int = 9999) -> Iterator[LocPage]:
    """Yield every page of one batch (text only), straight from the compressed download."""
    with _session.get(batch["url"], stream=True, timeout=(30, 600)) as r:
        r.raise_for_status()
        r.raw.decode_content = True
        with tarfile.open(fileobj=r.raw, mode="r|bz2") as tf:
            for m in tf:
                if not m.isfile() or not m.name.endswith("ocr.txt"):
                    continue
                hit = _PAGE_RE.search(m.name)
                if not hit:
                    continue
                lccn, y, mo, d, ed, seq = hit.groups()
                if not (start_year <= int(y) <= end_year):
                    continue
                f = tf.extractfile(m)
                if f is None:
                    continue
                text = f.read().decode("utf-8", errors="replace")
                info = paper_info(lccn)
                yield LocPage(
                    url=page_url(lccn, y, mo, d, ed, seq),
                    date=f"{y}-{mo}-{d}",
                    paper=info["title"],
                    paper_cities=info["cities"],
                    county=[],
                    languages=info["languages"],
                    text=text,
                )


def discover():
    data = _get_json(DATASETS, {"fo": "json", "at": "datasets"})
    items = _items(data)
    print("items:", len(items))
    if items:
        print("first item:", json.dumps(items[0], indent=1)[:1500])
    batches()


def batches():
    bs = nm_batches()
    total = sum(b["page_count"] or 0 for b in bs)
    size = sum(b["size"] or 0 for b in bs)
    print(f"New Mexico batches: {len(bs)}, {total:,} pages, {size / 1e9:.1f} GB compressed")
    for b in bs:
        print(f"  {b['batch']}: {b['page_count']:,} pages, {(b['size'] or 0) / 1e6:.0f} MB, papers {', '.join(b['lccns'][:6])}")
    if bs:
        lccn = (bs[0]["lccns"] or [None])[0]
        if lccn:
            print("paper info sample:", lccn, paper_info(lccn))


if __name__ == "__main__":
    {"discover": discover, "batches": batches}[sys.argv[1] if len(sys.argv) > 1 else "discover"]()
