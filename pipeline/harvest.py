"""Newspaper harvester: free sources -> strict pre-filter -> Haiku (Sonnet when unclear) -> incidents.

    # Chronicling America (Library of Congress), New Mexico papers, English + Spanish
    python -m pipeline.harvest --loc --start-year 1880 --end-year 1925

    # Local news RSS (daily cron)
    python -m pipeline.harvest --rss

    # No database: search + pre-filter only, and count what would be sent to Claude
    python -m pipeline.harvest --loc --dry-run --start-year 1910 --end-year 1912
    # ...and extract the first 150 candidates for a spot-check sample (writes records.csv)
    python -m pipeline.harvest --loc --dry-run --extract-limit 150 --start-year 1910 --end-year 1912

Spend: one hard cap across every harvest run, AP_HARVEST_CAP_USD (default $20), measured from
ap_ai_usage. A run also stops at --max-cost. At most 40% of a run's budget may go to Sonnet.
Outputs (always): <out>/records.csv, records.jsonl, candidates.jsonl, usage.jsonl, stats.json.
Article text is held in memory only; output files hold URLs, our structured fields and our summaries.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from dataclasses import asdict, dataclass, field

from .common.config import MODEL_FAST, MODEL_SMART
from .common.runlog import BudgetExceeded, LocalRun, PipelineRun
from .extract import extract, to_rows
from .lang import detect_language, has_keyword
from .prefilter import build_prompt_text, candidate_windows

# Papers printed in the pilot area (Chronicling America location_city values). Most local news is here.
LOCAL_PAPER_CITIES = ["albuquerque", "belen", "los lunas", "bernalillo"]

HARVEST_CAP_USD = float(os.environ.get("AP_HARVEST_CAP_USD", "20"))
SONNET_SHARE = float(os.environ.get("AP_SONNET_SHARE", "0.4"))
MIN_CALL_BUDGET = 0.02  # stop queuing work when less than this is left

CSV_FIELDS = [
    "source_name", "published_date", "incident_date", "address_raw", "unit", "city", "county",
    "location_precision", "place_kind", "cause_category", "summary", "confidence", "needs_review",
    "review_reason", "source_language", "extract_model", "source_url",
]


@dataclass
class Stats:
    source: str
    dry_run: bool
    loc_requests: int = 0
    loc_results_skipped: int = 0
    pages_seen: int = 0
    pages_skipped_scanned: int = 0
    candidates: int = 0
    candidate_chars: int = 0
    extracted_pages: int = 0
    pages_with_records: int = 0
    records: int = 0
    needs_review: int = 0
    sonnet_calls: int = 0
    errors: int = 0
    first_error: str | None = None
    failed_slices: list = field(default_factory=list)
    cost_usd: float = 0.0
    cost_by_model: dict = field(default_factory=dict)
    by_year: dict = field(default_factory=dict)
    by_precision: dict = field(default_factory=dict)
    by_cause: dict = field(default_factory=dict)
    feeds: dict = field(default_factory=dict)
    stopped_reason: str | None = None
    resume_from: str | None = None
    resume: dict | None = None
    elapsed_s: float = 0.0


class Output:
    def __init__(self, out_dir: str):
        os.makedirs(out_dir, exist_ok=True)
        self.dir = out_dir
        self.records = open(os.path.join(out_dir, "records.jsonl"), "a", encoding="utf-8")
        self.cands = open(os.path.join(out_dir, "candidates.jsonl"), "a", encoding="utf-8")
        csv_path = os.path.join(out_dir, "records.csv")
        new = not os.path.exists(csv_path)
        self._csv_f = open(csv_path, "a", encoding="utf-8", newline="")
        self.csv = csv.DictWriter(self._csv_f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        if new:
            self.csv.writeheader()

    def candidate(self, page: dict, chars: int, windows: int):
        self.cands.write(json.dumps({"url": page["url"], "paper": page.get("source_name"), "date": page.get("published_date"),
                                     "windows": windows, "chars": chars}) + "\n")

    def rows(self, rows: list[dict]):
        for r in rows:
            self.records.write(json.dumps(r, ensure_ascii=False) + "\n")
            self.csv.writerow(r)
        self.records.flush()
        self._csv_f.flush()

    def close(self, stats: Stats):
        for f in (self.records, self.cands, self._csv_f):
            f.close()
        with open(os.path.join(self.dir, "stats.json"), "w", encoding="utf-8") as f:
            json.dump(asdict(stats), f, indent=2)


class Harvester:
    def __init__(self, args, run, out: Output, stats: Stats):
        self.args = args
        self.run = run
        self.out = out
        self.stats = stats
        self.pool = ThreadPoolExecutor(max_workers=args.workers)
        self.ai_calls_left = args.extract_limit if args.dry_run else None
        self.loc_clients: list = []
        self.stop = False

    # ── database helpers (live mode only) ────────────────────────────────
    def already_scanned(self, urls: list[str]) -> set[str]:
        if self.args.dry_run or not urls:
            return set()
        from .common.db import db

        seen: set[str] = set()
        for i in range(0, len(urls), 100):
            rows = db().table("ap_scanned_pages").select("url").in_("url", urls[i : i + 100]).execute().data
            seen.update(r["url"] for r in rows)
        return seen

    def mark_scanned(self, urls: list[str]):
        if self.args.dry_run or not urls:
            return
        from .common.db import db

        db().table("ap_scanned_pages").upsert([{"url": u} for u in urls], ignore_duplicates=True).execute()

    def write(self, page: dict, items: list[dict], model: str) -> int:
        rows = to_rows(page, items, model)
        for r in rows:
            r["source_name"] = page.get("source_name")
        if rows and not self.args.dry_run:
            from .common.db import db

            db().table("ap_incidents").upsert(rows, on_conflict="source_url,address_raw", ignore_duplicates=True).execute()
        self.out.rows(rows)
        s = self.stats
        s.records += len(rows)
        s.pages_with_records += 1 if rows else 0
        for r in rows:
            s.needs_review += 1 if r["needs_review"] else 0
            s.by_precision[r["location_precision"] or "?"] = s.by_precision.get(r["location_precision"] or "?", 0) + 1
            s.by_cause[r["cause_category"]] = s.by_cause.get(r["cause_category"], 0) + 1
        return len(rows)

    # ── AI work ──────────────────────────────────────────────────────────
    def allow_sonnet(self) -> bool:
        return self.run.by_model.get(MODEL_SMART, 0.0) < SONNET_SHARE * self.run.max_cost

    def can_spend(self) -> bool:
        if self.ai_calls_left is not None and self.ai_calls_left <= 0:
            return False
        return self.run.remaining() > MIN_CALL_BUDGET

    def _job(self, page: dict, prompt: str):
        items, model = extract(prompt, self.run, self.allow_sonnet)
        return page, items, model

    def process(self, cands: list[tuple[dict, str]]) -> list[str]:
        """Extract a batch of (page, prompt) candidates in parallel. Returns URLs that finished."""
        futures = []
        for page, prompt in cands:
            if not self.can_spend():
                break
            if self.ai_calls_left is not None:
                self.ai_calls_left -= 1
            futures.append(self.pool.submit(self._job, page, prompt))
        done = []
        for fut in futures:
            try:
                page, items, model = fut.result()
            except BudgetExceeded as e:
                self.stats.stopped_reason = str(e)
                self.stop = True
                continue
            except Exception as e:  # API error after SDK retries: leave the page unscanned so it's retried
                self.stats.errors += 1
                self.stats.first_error = self.stats.first_error or f"{type(e).__name__}: {str(e)[:300]}"
                print(f"  extraction error: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
                continue
            self.stats.extracted_pages += 1
            self.stats.sonnet_calls += 1 if model == MODEL_SMART else 0
            self.write(page, items, model)
            done.append(page["url"])
        if not self.can_spend() and not self.stop:
            if self.ai_calls_left is not None and self.ai_calls_left <= 0:
                self.stats.stopped_reason = self.stats.stopped_reason or "extract limit reached"
            else:
                self.stats.stopped_reason = self.stats.stopped_reason or f"budget reached (${self.run.max_cost:.2f})"
                self.stop = True
        return done

    def ai_enabled(self) -> bool:
        return not (self.args.dry_run and self.args.extract_limit == 0)

    # ── Chronicling America ─────────────────────────────────────────────
    def harvest_loc(self):
        from .sources.loc import Blocked, LocClient

        cities = LOCAL_PAPER_CITIES if self.args.scope == "local" else [None]
        if self.args.start_city and self.args.start_city in cities:
            cities = cities[cities.index(self.args.start_city):]
        t0 = time.monotonic()
        try:
            for ci, city in enumerate(cities):
                loc = LocClient(city=city)
                self.loc_clients.append(loc)
                first_year = self.args.start_year if ci == 0 else self.args.range_start
                for start, end, n in loc.slices(first_year, self.args.end_year):
                    year = int(start[:4])
                    where = city or "all NM papers"
                    print(f"{start}..{end} ({where})" + (f": {n} matching pages" if n >= 0 else ""), flush=True)
                    first = self.args.start_offset if (ci == 0 and year == self.args.start_year and start.endswith("01-01")) else 0
                    try:
                        done = self._loc_slice(loc, start, end, first, year, city, where, t0)
                    except requests.RequestException as e:  # this slice keeps failing: note it and move on
                        self.stats.errors += 1
                        self.stats.failed_slices.append(f"{year} {where}: {str(e)[:120]}")
                        print(f"  giving up on {year} ({where}): {e}", file=sys.stderr, flush=True)
                        continue
                    if done:
                        return
                    self._mark_resume(year + 1, 0, city)
                # the next city starts from the beginning of the range
                nxt = cities[ci + 1] if ci + 1 < len(cities) else None
                self._mark_resume(self.args.range_start, 0, nxt) if nxt else self._mark_resume(None, 0, None)
        except Blocked as e:
            self.stats.stopped_reason = str(e)
        finally:
            self.stats.loc_requests = sum(c.requests_made for c in self.loc_clients)
            self.stats.loc_results_skipped = sum(c.skipped for c in self.loc_clients)

    def _mark_resume(self, year: int | None, offset: int, city: str | None):
        if year is None or year > self.args.end_year:
            self.stats.resume = None
            self.stats.resume_from = "done: the whole range is harvested"
            return
        self.stats.resume = {"year": year, "offset": offset, "city": city, "start_year": self.args.range_start,
                             "end_year": self.args.end_year, "scope": self.args.scope}
        self.stats.resume_from = f"--start-year {year} --start-offset {offset}" + (f" --start-city '{city}'" if city else "")

    def _loc_slice(self, loc, start, end, first, year, city, where, t0) -> bool:
        """Page through one date slice for one city. Returns True when the whole run should stop."""
        batches = 0
        for offset, pages in loc.pages(start, end, per_page=self.args.per_page, start_offset=first):
            self._mark_resume(year, offset, city) if start.endswith("01-01") and end.endswith("12-31") else None
            self.handle_loc_pages(pages, str(year))
            batches += 1
            if batches % 10 == 0:
                mins = (time.monotonic() - t0) / 60
                print(f"  {year} {where} result {offset}: seen {self.stats.pages_seen}, candidates {self.stats.candidates}, "
                      f"{mins:.0f} min, avg loc.gov wait {loc.seconds_waiting / max(loc.requests_made, 1):.1f}s", flush=True)
            if self.stop or (self.args.max_pages and self.stats.pages_seen >= self.args.max_pages):
                self.stats.stopped_reason = self.stats.stopped_reason or "max pages reached"
                return True
            if self.args.max_minutes and (time.monotonic() - t0) / 60 >= self.args.max_minutes:
                self.stats.stopped_reason = f"time limit ({self.args.max_minutes:.0f} min)"
                return True
        return False

    def handle_loc_pages(self, pages, year: str):
        s = self.stats
        urls = [p.url for p in pages]
        seen = self.already_scanned(urls)
        s.pages_seen += len(pages)
        s.pages_skipped_scanned += len(seen)
        cands, plain = [], []
        for p in pages:
            if p.url in seen:
                continue
            # Every Chronicling America NM paper is local to its own town (statewide coverage).
            local = True
            windows = candidate_windows(p.text, local_paper=local)
            if not windows:
                plain.append(p.url)
                continue
            lang = "es" if any(l.startswith("span") for l in p.languages) else detect_language(" ".join(windows))
            page = {"url": p.url, "source_name": clean_title(p.paper), "published_date": p.date, "language": lang}
            prompt = build_prompt_text(windows, page["source_name"], (p.paper_cities or [None])[0], p.date)
            s.candidates += 1
            s.candidate_chars += len(prompt)
            s.by_year[year] = s.by_year.get(year, 0) + 1
            self.out.candidate(page, len(prompt), len(windows))
            cands.append((page, prompt))
        done = self.process(cands) if (cands and self.ai_enabled()) else []
        # Pages with no candidate text are done for good; candidates only once extracted.
        self.mark_scanned(plain + done)

    # ── RSS ─────────────────────────────────────────────────────────────
    def harvest_rss(self):
        from .sources.rss import FEEDS, fetch_article_text, fetch_feed, new_session

        session = new_session()
        for name, url, city in FEEDS:
            try:
                arts = fetch_feed(name, url, city, session)
            except Exception as e:
                self.stats.feeds[name] = f"failed: {type(e).__name__}"
                print(f"feed {name}: {e}", file=sys.stderr, flush=True)
                continue
            self.stats.feeds[name] = f"{len(arts)} items"
            seen = self.already_scanned([a.url for a in arts])
            cands, plain = [], []
            for a in arts:
                self.stats.pages_seen += 1
                if a.url in seen:
                    self.stats.pages_skipped_scanned += 1
                    continue
                if not has_keyword(f"{a.title} {a.teaser}"):
                    plain.append(a.url)
                    continue
                try:
                    text = fetch_article_text(a.url, session)
                    time.sleep(1)
                except Exception:
                    text = f"{a.title}. {a.teaser}"
                windows = candidate_windows(f"{a.title}. {text}", local_paper=bool(city))
                if not windows:
                    plain.append(a.url)
                    continue
                page = {"url": a.url, "source_name": a.source_name, "published_date": a.published,
                        "language": detect_language(text)}
                prompt = build_prompt_text(windows, a.source_name, city, a.published)
                self.stats.candidates += 1
                self.stats.candidate_chars += len(prompt)
                self.out.candidate(page, len(prompt), len(windows))
                cands.append((page, prompt))
            done = self.process(cands) if (cands and self.ai_enabled()) else []
            self.mark_scanned(plain + done)
            if self.stop:
                return


def last_resume_point():
    """The resume point the most recent live Chronicling America run saved (None = start fresh, 'done' = finished)."""
    from .common.db import db

    rows = (
        db().table("ap_pipeline_runs").select("meta").eq("job", "harvest_loc")
        .in_("status", ["ok", "partial", "error"]).order("started_at", desc=True).limit(1).execute().data
    )
    if not rows:
        return None
    st = (rows[0].get("meta") or {}).get("stats") or {}
    if st.get("resume"):
        return st["resume"]
    return "done" if (st.get("resume_from") or "").startswith("done") else None


def clean_title(t: str | None) -> str | None:
    """'the albuquerque morning journal. [volume] (albuquerque, n.m.) 1903-1922' -> 'The Albuquerque Morning Journal'."""
    if not t:
        return None
    base = t.split("[")[0].split("(")[0].strip().rstrip(".").strip()
    small = {"of", "the", "and", "del", "de", "la", "el", "y"}
    words = base.split()
    return " ".join(w if (i and w in small) else w[:1].upper() + w[1:] for i, w in enumerate(words)) or None


def summarize(stats: Stats, out_dir: str):
    s = stats
    est = ""
    if s.candidates and s.extracted_pages < s.candidates:
        if s.extracted_pages:
            per = s.cost_usd / s.extracted_pages
            est = f"\nAt ${per:.4f} per page so far, extracting all {s.candidates} candidates would cost about ${per * s.candidates:.2f}"
        else:
            # ~3.5 characters per token for OCR text; system prompt + tool ~900 tokens; ~250 output tokens
            tok_in = s.candidate_chars / 3.5 + 900 * s.candidates
            haiku = tok_in * 0.10 / 1e6 + 250 * s.candidates * 0.50 / 1e6
            est = f"\nEstimated Haiku cost to extract all {s.candidates} candidates: ${haiku:.2f} (plus Sonnet re-checks)"
    lines = [
        f"## Harvest ({s.source}{', dry run' if s.dry_run else ''})",
        "",
        "| | |", "|---|---|",
        f"| loc.gov requests | {s.loc_requests} (results skipped after server errors: {s.loc_results_skipped}) |",
        f"| Pages seen | {s.pages_seen} |",
        f"| Already scanned (skipped) | {s.pages_skipped_scanned} |",
        f"| Candidates after pre-filter | {s.candidates} |",
        f"| Pages sent to Claude | {s.extracted_pages} (Sonnet re-checks: {s.sonnet_calls}) |",
        f"| Records found | {s.records} on {s.pages_with_records} pages |",
        f"| Held for review in /admin | {s.needs_review} |",
        f"| Errors | {s.errors}{' (first: ' + s.first_error + ')' if s.first_error else ''} |",
        f"| Claude cost | ${s.cost_usd:.4f} {json.dumps({k: round(v, 4) for k, v in s.cost_by_model.items()})} |",
        f"| Time | {s.elapsed_s / 60:.1f} min |",
        f"| Stopped because | {s.stopped_reason or 'finished'} |",
        f"| Resume with | `{s.resume_from or '-'}` |",
        "",
        f"By cause: {json.dumps(s.by_cause)}",
        f"By precision: {json.dumps(s.by_precision)}",
        f"Candidates by year: {json.dumps(s.by_year)}",
        f"Feeds: {json.dumps(s.feeds)}" if s.feeds else "",
        f"Gave up on: {'; '.join(s.failed_slices)}" if s.failed_slices else "",
        est,
        f"\nFiles in `{out_dir}/`: records.csv (spot-check sheet), records.jsonl, candidates.jsonl, usage.jsonl, stats.json",
    ]
    text = "\n".join(lines)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(text + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--loc", action="store_true", help="Chronicling America (Library of Congress)")
    src.add_argument("--rss", action="store_true", help="local news RSS feeds")
    ap.add_argument("--start-year", type=int, default=1860)
    ap.add_argument("--end-year", type=int, default=1963)
    ap.add_argument("--start-page", type=int, default=1, help="resume inside --start-year (pages of --per-page)")
    ap.add_argument("--start-offset", type=int, default=None, help="resume inside --start-year at this result number")
    ap.add_argument("--start-city", default=None, help="local scope: start with this paper city")
    ap.add_argument("--resume", action="store_true", help="continue where the last live Chronicling America run stopped")
    ap.add_argument("--per-page", type=int, default=50)
    ap.add_argument("--max-pages", type=int, default=0, help="stop after this many search-result pages (0 = no limit)")
    ap.add_argument("--dry-run", action="store_true", help="no database reads or writes")
    ap.add_argument("--extract-limit", type=int, default=0, help="dry run only: send this many candidates to Claude")
    ap.add_argument("--max-cost", type=float, default=None, help="USD cap for this run (also bounded by AP_HARVEST_CAP_USD)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--scope", choices=["local", "state"], default="local",
                    help="local = papers printed in Albuquerque, Belen, Los Lunas, Bernalillo; state = every NM paper")
    ap.add_argument("--max-minutes", type=float, default=0, help="stop cleanly after this long (0 = no limit)")
    ap.add_argument("--out", default="harvest-out")
    args = ap.parse_args(argv)
    if args.start_offset is None:
        args.start_offset = (args.start_page - 1) * args.per_page
    if args.resume and not args.dry_run and args.loc:
        last = last_resume_point()
        if last == "done":
            print("Chronicling America backlog is already complete; nothing to resume.")
            return
        if last and last.get("scope", "local") != args.scope:
            print(f"Last run was scope '{last.get('scope', 'local')}'; starting scope '{args.scope}' from {args.start_year} "
                  "(pages already read are skipped)", flush=True)
            last = None
        if last:
            args.start_year, args.start_offset, args.start_city = last["year"], last["offset"], last.get("city")
            args.range_start = last.get("start_year", args.start_year)
            args.end_year = last.get("end_year", args.end_year)
            print(f"Resuming at {args.start_year} result {args.start_offset} ({args.start_city or 'all NM papers'})", flush=True)
    if not hasattr(args, "range_start"):
        args.range_start = args.start_year

    source = "loc" if args.loc else "rss"
    stats = Stats(source=source, dry_run=args.dry_run)
    out = Output(args.out)
    t0 = time.monotonic()

    if args.dry_run:
        cap = args.max_cost if args.max_cost is not None else HARVEST_CAP_USD
        run_cm = LocalRun(f"harvest_{source}", os.path.join(args.out, "usage.jsonl"), max_cost=cap)
    else:
        from .common.runlog import spent_so_far

        left = HARVEST_CAP_USD - spent_so_far("harvest_")
        cap = min(left, args.max_cost) if args.max_cost is not None else left
        print(f"Harvest budget: ${HARVEST_CAP_USD:.2f} total, ${left:.2f} left, this run ${cap:.2f}", flush=True)
        if cap <= MIN_CALL_BUDGET:
            stats.stopped_reason = f"harvest cap of ${HARVEST_CAP_USD:.2f} already spent"
        run_cm = PipelineRun(f"harvest_{source}", trigger="cron" if args.rss else "manual",
                             meta={"args": vars(args)}, max_cost=max(cap, 0.0))

    with run_cm as run:
        h = Harvester(args, run, out, stats)
        crashed = None
        try:
            if not stats.stopped_reason:
                h.harvest_loc() if args.loc else h.harvest_rss()
        except Exception as e:  # keep what we have: write the files and the summary, then fail the job
            import traceback

            traceback.print_exc()
            crashed = e
            stats.stopped_reason = f"error: {type(e).__name__}: {str(e)[:200]}"
        finally:
            h.pool.shutdown(wait=True)
            stats.cost_usd = round(run.cost, 4)
            stats.cost_by_model = dict(run.by_model)
            stats.elapsed_s = time.monotonic() - t0
            run.items_in = stats.candidates
            run.items_out = stats.records
            run.meta = {**run.meta, "stats": asdict(stats)}
    out.close(stats)
    summarize(stats, args.out)
    if crashed:
        sys.exit(1)


if __name__ == "__main__":
    main()
