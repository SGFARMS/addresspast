"""Library of Congress loc.gov API client for Chronicling America (free, public).

Limits we respect (https://www.loc.gov/apis/json-and-yaml/working-within-limits/):
  - Search/collection endpoints: 20 requests per minute. Going over blocks the IP for an hour,
    so we pace at one request every 3.3 s and back off hard on 429 / CAPTCHA pages.
  - Keep any single query under ~100k results, so we slice by year (and by half-year if a
    year is too big).

Search results with dl=page include each page's OCR text in `full_text`, so one request
returns up to `c` pages of text and we never download page files one by one.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date
from typing import Iterator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests

BASE = "https://www.loc.gov/collections/chronicling-america/"
USER_AGENT = "AddressPast-harvester/1.0 (+https://history.skyhighwebsites.dev; property-history research)"

# One OR query per request. Single words only: ops=OR matches any of them.
QUERY_WORDS = [
    "killed", "murdered", "murder", "drowned", "shot", "coroner", "inquest", "suicide", "slain", "dead",
    "asesinado", "asesinato", "ahogado", "cadaver", "balazo", "suicidio", "homicidio", "muerto", "difunto",
]

MAX_SLICE = 60000  # results per query before we split the date range


class Blocked(RuntimeError):
    """loc.gov says we're rate limited (429 or a CAPTCHA page). Stop and resume later."""


@dataclass
class Throttle:
    min_interval: float = 3.3
    _last: float = 0.0

    def wait(self):
        delta = time.monotonic() - self._last
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)
        self._last = time.monotonic()


@dataclass
class LocPage:
    url: str
    date: str | None
    paper: str | None
    paper_cities: list[str]
    county: list[str]
    languages: list[str]
    text: str


@dataclass
class LocClient:
    throttle: Throttle = field(default_factory=Throttle)
    session: requests.Session = field(default_factory=requests.Session)
    requests_made: int = 0
    skipped: int = 0
    seconds_waiting: float = 0.0
    city: str | None = None  # restrict to papers printed in this city (None = all NM papers)
    max_retries: int = 1

    def __post_init__(self):
        self.session.headers["User-Agent"] = USER_AGENT

    def get_json(self, params: dict) -> dict:
        """GET with pacing. Raises Blocked on rate limiting, requests.RequestException when retries run out.

        Server errors and timeouts get one quick retry; pages() then shrinks the page size or skips.
        (Long backoffs on loc.gov's flaky days cost hours and rarely helped.)"""
        throttled = 0
        failed = 0
        while True:
            self.throttle.wait()
            self.requests_made += 1
            t0 = time.monotonic()
            try:
                r = self.session.get(BASE, params=params, timeout=(10, 45))
                self.seconds_waiting += time.monotonic() - t0
                ctype = r.headers.get("content-type", "")
                if r.status_code == 429 or (r.status_code == 200 and "json" not in ctype):
                    # 429, or an HTML CAPTCHA/challenge page instead of JSON
                    throttled += 1
                    if throttled > 3:
                        raise Blocked(f"loc.gov rate limited us (status {r.status_code}); resume in an hour")
                    wait = int(r.headers.get("retry-after", "0") or 0) or 60 * throttled
                    print(f"  loc.gov throttled (status {r.status_code}); waiting {wait}s", flush=True)
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                return r.json()
            except Blocked:
                raise
            except (requests.RequestException, ValueError) as e:
                # timeouts, broken chunked responses, 5xx, truncated JSON
                self.seconds_waiting += time.monotonic() - t0
                failed += 1
                if failed > self.max_retries:
                    raise requests.RequestException(f"{type(e).__name__}: {e}", response=getattr(e, "response", None)) from e
                time.sleep(10)

    def search_params(self, start: str, end: str, page: int, per_page: int) -> dict:
        return {
            "dl": "page",
            "qs": " ".join(QUERY_WORDS),
            "ops": "OR",
            "searchType": "advanced",
            "location_state": "new mexico",
            **({"location_city": self.city} if self.city else {}),
            "start_date": start,
            "end_date": end,
            "c": per_page,
            "sp": page,
            "at": "results,pagination",
            "fo": "json",
        }

    def count(self, start: str, end: str) -> int:
        data = self.get_json(self.search_params(start, end, 1, 1))
        return int((data.get("pagination") or {}).get("of") or 0)

    def slices(self, start_year: int, end_year: int) -> Iterator[tuple[str, str, int]]:
        """Yield (start, end, n_results) date ranges small enough to page through safely."""
        for y in range(start_year, end_year + 1):
            s, e = f"{y}-01-01", f"{y}-12-31"
            if self.city:  # one city's papers never come near the 100k-result limit in a year
                yield s, e, -1
                continue
            n = self.count(s, e)
            if n == 0:
                continue
            if n <= MAX_SLICE:
                yield s, e, n
                continue
            for a, b in ((f"{y}-01-01", f"{y}-06-30"), (f"{y}-07-01", f"{y}-12-31")):
                yield a, b, self.count(a, b)

    def pages(self, start: str, end: str, per_page: int = 50, start_offset: int = 0) -> Iterator[tuple[int, list[LocPage]]]:
        """Yield (offset_after_this_batch, pages) for one date slice, starting at result number start_offset.

        Pages carry full OCR text, so big result pages can fail on loc.gov's side (520/504/timeouts).
        When that happens we drop to a smaller page size (50 -> 20 -> 5) and carry on from the same
        offset; a stretch that still fails is skipped (counted in `skipped`).
        """
        size = per_page
        offset = start_offset
        total: int | None = None
        skips_in_a_row = 0
        while total is None or offset < total:
            try:
                data = self.get_json(self.search_params(start, end, offset // size + 1, size))
            except requests.RequestException as e:
                resp = getattr(e, "response", None)
                status = resp.status_code if resp is not None else 599
                smaller = next((n for n in (20, 5) if n < size and offset % n == 0), None)
                if status == 404 and resp is not None:
                    # Seen mid-range (result 51 of 1706), so it is not "past the end": handle it like a
                    # server error (smaller pages, then skip), and log the URL so we can see why.
                    print(f"  loc.gov 404 at result {offset + 1} of {total}: {resp.url}", flush=True)
                    status = 503
                if status >= 500 and smaller:
                    print(f"  loc.gov {status} at {size}/page; retrying at {smaller}/page", flush=True)
                    size = smaller
                    continue
                if status >= 500 and skips_in_a_row < 5:
                    print(f"  loc.gov {status}; skipping results {offset + 1}-{offset + size}", flush=True)
                    offset += size
                    self.skipped += size
                    skips_in_a_row += 1
                    continue
                raise
            skips_in_a_row = 0
            results = data.get("results") or []
            pag = data.get("pagination") or {}
            total = int(pag.get("of") or 0)
            offset += size
            if not results and offset == start_offset + size:
                # An empty first answer is either a genuinely empty slice or loc.gov having a bad day;
                # say which in the log so a run that "saw 0 pages" explains itself.
                print(f"  loc.gov returned no results for {start}..{end}{' (' + self.city + ')' if self.city else ''}: "
                      f"reported total {total}, keys {sorted(data)[:6]}", flush=True)
            yield offset, [p for p in (parse_result(r) for r in results) if p]
            if not pag.get("next") or not results:
                return
            if size < per_page and offset % per_page == 0:
                size = per_page  # back to full-size pages once we're past the bad stretch


def _as_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if x]
    return [str(v)]


def _as_text(v) -> str:
    if isinstance(v, list):
        return "\n".join(str(x) for x in v if x)
    return str(v or "")


def normalize_url(u: str) -> str:
    """https, no search-term params; keep sp/st so the link opens the right page."""
    p = urlparse(u)
    keep = {k: v for k, v in parse_qs(p.query).items() if k in ("sp", "st")}
    return urlunparse(("https", p.netloc or "www.loc.gov", p.path, "", urlencode(keep, doseq=True), ""))


def parse_result(r: dict) -> LocPage | None:
    url = r.get("id") or r.get("url")
    if not url:
        return None
    text = _as_text(r.get("full_text"))
    if not text:
        text = _as_text(r.get("description"))
    d = r.get("date")
    try:
        d = date.fromisoformat(str(d)[:10]).isoformat() if d else None
    except ValueError:
        d = None
    title = _as_list(r.get("partof_title"))
    return LocPage(
        url=normalize_url(url),
        date=d,
        paper=(title[0] if title else None),
        paper_cities=[c.lower() for c in _as_list(r.get("location_city"))],
        county=[c.lower() for c in _as_list(r.get("location_county"))],
        languages=[c.lower() for c in _as_list(r.get("language"))],
        text=text,
    )
