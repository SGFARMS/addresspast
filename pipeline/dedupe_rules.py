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



def rule_verdict(a: dict, b: dict) -> bool | None:
    """True = surely the same death, False = surely different, None = ask the model.

    Same: the same exact day, same town and a compatible cause (two papers reporting one death).
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
    return None
