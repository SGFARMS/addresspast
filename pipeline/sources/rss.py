"""Local news RSS feeds (free). Article text is read in memory for extraction and never stored.

A feed that fails (moved, blocked, empty) is reported and skipped; it never stops the run.
Edit FEEDS to add or drop sources.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser

import requests

USER_AGENT = "AddressPast-harvester/1.0 (+https://history.skyhighwebsites.dev; property-history research)"

# (name, feed url, printed-in city or None for statewide outlets)
FEEDS: list[tuple[str, str, str | None]] = [
    ("Albuquerque Journal", "https://www.abqjournal.com/feed/", "albuquerque"),
    ("KRQE News 13", "https://www.krqe.com/feed/", "albuquerque"),
    ("KOB 4", "https://www.kob.com/feed/", "albuquerque"),
    ("KOAT Action 7", "https://www.koat.com/topstories-rss", "albuquerque"),
    ("Valencia County News-Bulletin", "https://www.news-bulletin.com/feed/", "belen"),
    ("Rio Rancho Observer", "https://www.rrobserver.com/feed/", "rio rancho"),
    ("Source NM", "https://sourcenm.com/feed/", None),
    ("Searchlight New Mexico", "https://searchlightnm.org/feed/", None),
]


@dataclass
class Article:
    url: str
    source_name: str
    paper_city: str | None
    published: str | None
    title: str
    teaser: str


class _TextExtractor(HTMLParser):
    """Collect paragraph text, skipping scripts, styles, nav and footers."""

    SKIP = {"script", "style", "nav", "footer", "header", "aside", "form", "noscript", "figure"}

    def __init__(self):
        super().__init__()
        self.depth_skip = 0
        self.in_p = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.depth_skip += 1
        elif tag in ("p", "h1", "h2", "li") and not self.depth_skip:
            self.in_p += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth_skip:
            self.depth_skip -= 1
        elif tag in ("p", "h1", "h2", "li") and self.in_p:
            self.in_p -= 1
            self.parts.append("\n")

    def handle_data(self, data):
        if self.in_p and not self.depth_skip:
            self.parts.append(data)


def html_to_text(raw: str) -> str:
    p = _TextExtractor()
    try:
        p.feed(raw)
    except Exception:  # malformed HTML: fall back to tag stripping
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw))
    return re.sub(r"[ \t]+", " ", "".join(p.parts)).strip()


def _strip(s: str | None) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", s or "")).strip()


def fetch_feed(name: str, url: str, city: str | None, session: requests.Session) -> list[Article]:
    import feedparser  # lazy: only needed for RSS runs

    r = session.get(url, timeout=30)
    r.raise_for_status()
    feed = feedparser.parse(r.content)
    out = []
    for e in feed.entries:
        link = e.get("link")
        if not link:
            continue
        published = None
        t = e.get("published_parsed") or e.get("updated_parsed")
        if t:
            published = datetime(*t[:6], tzinfo=timezone.utc).date().isoformat()
        out.append(Article(link.split("?")[0], name, city, published, _strip(e.get("title")), _strip(e.get("summary"))))
    return out


def fetch_article_text(url: str, session: requests.Session) -> str:
    r = session.get(url, timeout=30)
    r.raise_for_status()
    return html_to_text(r.text)


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s
