"""Pure rules for the duplicate check (no database, no SDK), so they are easy to test."""
from __future__ import annotations

import re
from datetime import date


def _ymd(v: str | None) -> tuple[int | None, int | None, int | None]:
    m = re.match(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", str(v or ""))
    if not m:
        return None, None, None
    return tuple(int(x) if x else None for x in m.groups())  # type: ignore[return-value]


def could_be_same(a: dict, b: dict) -> bool:
    """Cheap date test before asking the model. Newspapers report a death within days, so two records whose
    incident or publication dates are clearly apart are different deaths (most same-town pairs are)."""
    (ay, am, ad), (by, bm, bd) = _ymd(a.get("incident_date")), _ymd(b.get("incident_date"))
    if ay and by:
        if am and bm and abs((ay * 12 + am) - (by * 12 + bm)) > 1:
            return False
        if am and bm and ad and bd and (ay, am) == (by, bm) and abs(ad - bd) > 10:
            return False
    pa, pb = a.get("published_date"), b.get("published_date")
    if pa and pb:
        try:
            if abs((date.fromisoformat(str(pa)[:10]) - date.fromisoformat(str(pb)[:10])).days) > 45:
                return False
        except ValueError:
            pass
    return True



_STOP = {"a", "an", "the", "was", "were", "of", "in", "at", "on", "near", "and", "to", "by", "from", "for", "with",
         "his", "her", "their", "reported", "after", "had", "been", "who", "which", "that", "as", "is"}


def _words(s: str | None) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", (s or "").lower()) if w not in _STOP and len(w) > 2}


def summary_similarity(a: dict, b: dict) -> float:
    """Word overlap of two summaries (0-1). Two papers retelling one death read almost the same."""
    wa, wb = _words(a.get("summary")), _words(b.get("summary"))
    if len(wa) < 4 or len(wb) < 4:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def date_gap_days(a: dict, b: dict) -> int:
    """Rough distance between two records' dates (incident date, else publication date); unknown = large."""
    def _d(r):
        for k in ("incident_date", "published_date"):
            y, m, d = _ymd(r.get(k))
            if y:
                return y * 372 + (m or 6) * 31 + (d or 15)
        return None
    da, db = _d(a), _d(b)
    return abs(da - db) if da is not None and db is not None else 10_000


def rule_verdict(a: dict, b: dict) -> bool | None:
    """True = surely the same death, False = surely different, None = ask the model.

    Same: the same exact day, same town and a compatible cause (two papers reporting one death); or the
    same town and cause with nearly identical summaries within a month.
    (Two finds on one page are left to the model: one page can report two different deaths.)
    Different: dates or publication dates too far apart (could_be_same is False)."""
    if not could_be_same(a, b):
        return False
    ca, cb = a.get("cause_category") or "unknown", b.get("cause_category") or "unknown"
    causes_fit = ca == cb or "unknown" in (ca, cb)
    (ay, am, ad), (by, bm, bd) = _ymd(a.get("incident_date")), _ymd(b.get("incident_date"))
    same_town = (a.get("city") or "").strip().lower() == (b.get("city") or "").strip().lower() != ""
    if ad and bd and (ay, am, ad) == (by, bm, bd) and same_town and causes_fit:
        return True
    # The same story in two papers (or two editions): same town and cause, nearly the same words, close in time.
    # Short generic lines ("A fatal shooting at a saloon was reported.") could be two different deaths: model.
    distinctive = min(len(_words(a.get("summary"))), len(_words(b.get("summary")))) >= 6
    sim, gap = summary_similarity(a, b), date_gap_days(a, b)
    if same_town and causes_fit and distinctive and sim >= 0.7 and gap <= 31:
        return True
    # Months apart and telling different stories: different deaths (saves a model call on most town pairs).
    if gap > 62 and sim < 0.3:
        return False
    return None
