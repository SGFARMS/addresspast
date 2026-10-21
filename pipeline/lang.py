"""Spanish-language support for harvest.py.

Many territorial-era NM papers were in Spanish (Chronicling America has several,
e.g. La Voz del Pueblo, El Nuevo Mexicano, La Bandera Americana). harvest.py should:
  1. add SPANISH_KEYWORDS to its page filter,
  2. pass source_language=detect_language(text) when writing incidents,
  3. use EXTRACTION_SYSTEM (below) as the cached system prompt.
"""
import re

ENGLISH_KEYWORDS = [
    "killed", "murdered", "shot and killed", "drowned", "died", "body found", "fatally",
    "burned to death", "suicide", "inquest", "coroner", "slain", "found dead",
]

SPANISH_KEYWORDS = [
    "asesinado", "asesinada", "asesinato", "fue muerto", "fue muerta", "se ahogó", "se ahogo", "ahogado",
    "murió", "murio", "falleció", "fallecio", "cadáver", "cadaver", "balazo", "balazos", "incendio",
    "quemado", "suicidio", "se suicidó", "homicidio", "pereció", "perecio", "difunto", "difunta",
    "juez de paz", "jurado del coroner",
]

ALL_KEYWORDS = ENGLISH_KEYWORDS + SPANISH_KEYWORDS
_KEYWORD_RE = re.compile("|".join(re.escape(k) for k in ALL_KEYWORDS), re.I)

_ES_MARKERS = re.compile(r"\b(el|la|los|las|del|que|por|para|una|con|señor|condado|ayer)\b", re.I)
_EN_MARKERS = re.compile(r"\b(the|and|of|was|that|with|for|county|yesterday)\b", re.I)


def has_keyword(text: str) -> bool:
    return bool(_KEYWORD_RE.search(text or ""))


def detect_language(text: str) -> str:
    """Cheap heuristic: 'es' if Spanish function words clearly dominate."""
    sample = (text or "")[:5000]
    es = len(_ES_MARKERS.findall(sample))
    en = len(_EN_MARKERS.findall(sample))
    return "es" if es > en * 1.3 else "en"


EXTRACTION_SYSTEM = """You extract reported deaths from New Mexico newspaper pages for a property-history database.
Pages may be English or Spanish, and OCR text may be noisy.

For each death that happened in New Mexico and has ANY location (street address, intersection, landmark, or at least a town), return one item with:
- address_raw: the location exactly as printed (keep historic street names; translate nothing)
- city, county: best reading; null if not stated
- location_precision: street_address | intersection | landmark | city_only
- incident_date: as precise as the page allows ("1932-03-08", "1932-03", "1932"); use the paper's date only if the article says "yesterday/ayer" etc.
- cause_category: natural | accident | homicide | suicide | fire | unknown
- summary: ONE neutral English sentence, under 25 words, with NO personal names, ages, or graphic detail. Example: "A fatal shooting at a residence was reported." Even for Spanish articles, write the summary in English.
- confidence: 0–1 that this is a real NM death at that location (lower for OCR damage, rumor, or vague places)

Rules: Never include names of victims, suspects, or relatives anywhere. Never copy article text. Skip deaths outside New Mexico, war casualty lists, and obituaries with no location. If nothing qualifies, return an empty list."""

TRIAGE_SYSTEM = """You are a cheap first-pass filter. Answer only with the tool call.
Does this New Mexico newspaper page (English or Spanish, OCR text) report at least one death that happened in New Mexico AND mention where it happened (a street, place, landmark, or town)?"""
