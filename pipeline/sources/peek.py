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
            # Which AI crawlers does the outlet turn away? (we honour these: no AI reading of opted-out sites)
            ai_blocks, agent = [], None
            for l in lines:
                if l.lower().startswith("user-agent"):
                    agent = l.split(":", 1)[1].strip()
                elif l.lower().startswith("disallow") and l.split(":", 1)[1].strip() == "/" and agent:
                    ai_blocks.append(agent)
            print(f"== {name}: robots {rb.status_code}; full site blocked for: {sorted(set(ai_blocks))}")
            maps = [l.split(":", 1)[1].strip() for l in lines if l.lower().startswith("sitemap")]
            for m in (maps or [site + "/sitemap.xml"])[:1]:
                sm = requests.get(m, headers=UA, timeout=60)
                locs = re.findall(r"<loc>([^<]+)</loc>", sm.text)
                print(f"   sitemap {m} -> {sm.status_code}, {len(locs)} entries, e.g. {locs[:3]} ... {locs[-2:]}")
        except Exception as e:
            print(f"== {name}: {type(e).__name__}: {str(e)[:150]}")


ARCHIVE_SITES = ["https://www.abqjournal.com", "https://www.news-bulletin.com", "https://www.rrobserver.com",
                 "https://searchlightnm.org"]
DEATH_SLUG = re.compile(r"(killed|dies|died|dead|death|fatal|shot|shooting|homicide|murder|stabb|crash|body|drown|slain)", re.I)


def archive():
    """Article sitemaps of the outlets that allow AI reading: shape, newest URLs, and one article's text."""
    from urllib.robotparser import RobotFileParser

    for site in ARCHIVE_SITES:
        try:
            rp = RobotFileParser(site + "/robots.txt")
            rp.read()
            ok = {a: rp.can_fetch(a, site + "/news/") for a in ("ClaudeBot", "Claude-User", "AddressPast-harvester")}
            print(f"== {site}: robots can_fetch {ok}; sitemaps listed {rp.site_maps()}")
            idx_urls = (rp.site_maps() or []) + [site + "/sitemapindex.xml", site + "/sitemap_index.xml", site + "/sitemap.xml"]
            for idx in dict.fromkeys(idx_urls):
                r = requests.get(idx, headers=UA, timeout=60)
                locs = [l.replace("&amp;", "&") for l in re.findall(r"<loc>([^<]+)</loc>", r.text)]
                print(f"   {idx} -> {r.status_code} {r.headers.get('content-type', '')[:30]}, {len(locs)} entries {locs[:2]} .. {locs[-2:]}")
                if not locs:
                    continue
                subs = [l for l in locs if "sitemap" in l]
                pick = subs[-1] if subs else None
                arts = locs if not subs else []
                if pick:
                    r2 = requests.get(pick, headers=UA, timeout=60)
                    arts = [l.replace("&amp;", "&") for l in re.findall(r"<loc>([^<]+)</loc>", r2.text)]
                    mods = re.findall(r"<lastmod>([^<]+)</lastmod>", r2.text)
                    print(f"   chunk {pick} -> {r2.status_code}, {len(arts)} urls, lastmod {mods[:1]}..{mods[-1:]}")
                    print(f"   first urls {arts[:3]}")
                    if subs and len(subs) > 1:
                        r3 = requests.get(subs[0], headers=UA, timeout=60)
                        m3 = re.findall(r"<lastmod>([^<]+)</lastmod>", r3.text)
                        a3 = re.findall(r"<loc>([^<]+)</loc>", r3.text)
                        print(f"   oldest chunk {subs[0]}: {len(a3)} urls, lastmod {m3[:1]}, e.g. {a3[:2]}")
                hits = [a for a in arts if DEATH_SLUG.search(a.rsplit("/", 2)[-2] if a.endswith("/") else a.rsplit("/", 1)[-1])]
                print(f"   death-word slugs in that chunk: {len(hits)} of {len(arts)}: {hits[:4]}")
                if hits:
                    from .rss import html_to_text

                    page = requests.get(hits[0], headers=UA, timeout=60)
                    text = html_to_text(page.text)
                    pay = bool(re.search(r"(subscribe to continue|subscriber[- ]only|paywall|already a subscriber)", page.text, re.I))
                    print(f"   article {page.status_code}: {len(text)} chars, paywall words {pay}; starts: {text[:400]!r}")
                break
        except Exception as e:
            print(f"== {site}: {type(e).__name__}: {str(e)[:200]}")


if __name__ == "__main__":
    {"fra": fra, "msha": msha, "news": news, "archive": archive}[sys.argv[1]]()
