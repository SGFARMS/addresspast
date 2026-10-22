"""Strict keyword pre-filter: only text near a death keyword AND a pilot-area place goes to Claude.

A Chronicling America page is a whole newspaper page (often 30k+ characters of OCR).
Instead of sending the page, we cut windows around each death keyword and keep a window
only if it also mentions a pilot town (or, for papers printed in the pilot area, a local
street cue). Overlapping windows are merged and the total is capped, so a page costs a few
thousand tokens at most.
"""
from __future__ import annotations

import re

from .lang import keyword_spans
from .places_nm import mentions_pilot_area

WINDOW = 700          # characters on each side of a keyword
MAX_CHARS = 12000     # per page, after merging
SEPARATOR = "\n-----\n"

# Cues that a local paper's item is about a place in its own town.
_LOCAL_CUE = re.compile(
    r"\b(street|st\.|avenue|ave\.|boulevard|road|alley|calle|plaza|this city|esta ciudad|this morning|"
    r"last night|anoche|esta ma[nñ]ana|residence|his home|her home|su casa|su residencia|hotel|rooming house)\b",
    re.I,
)

_WS = re.compile(r"\s+")


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[list[int]] = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def candidate_windows(text: str, local_paper: bool = False) -> list[str]:
    """Return merged text windows worth sending to the model ([] means skip the page)."""
    if not text:
        return []
    n = len(text)
    keep: list[tuple[int, int]] = []
    for a, b in keyword_spans(text):
        lo, hi = max(0, a - WINDOW), min(n, b + WINDOW)
        chunk = text[lo:hi]
        if mentions_pilot_area(chunk) or (local_paper and _LOCAL_CUE.search(chunk)):
            keep.append((lo, hi))
    windows = []
    total = 0
    for lo, hi in _merge(keep):
        w = _WS.sub(" ", text[lo:hi]).strip()
        if total + len(w) > MAX_CHARS:
            w = w[: max(0, MAX_CHARS - total)]
        if w:
            windows.append(w)
            total += len(w)
        if total >= MAX_CHARS:
            break
    return windows


def build_prompt_text(windows: list[str], paper: str | None, paper_city: str | None, date: str | None) -> str:
    head = f"Newspaper: {paper or 'unknown'}" + (f", printed in {paper_city}" if paper_city else "") + (f"; issue date {date}" if date else "")
    return head + "\n\n" + SEPARATOR.join(windows)
