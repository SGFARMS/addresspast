"""Keywords, language detection and prompts for harvest.py (English + Spanish).

Many territorial-era NM papers were in Spanish (Chronicling America has several,
e.g. La Voz del Pueblo, El Nuevo Mexicano, La Bandera Americana).
"""
import re

ENGLISH_KEYWORDS = [
    "killed", "murdered", "shot and killed", "drowned", "died", "body found", "fatally",
    "burned to death", "suicide", "inquest", "coroner", "slain", "found dead",
    "fatal", "homicide", "shooting", "stabbed", "stabbing", "deadly", "dead", "killing",
    "asphyxiated", "electrocuted", "overdose", "medical investigator",
]

SPANISH_KEYWORDS = [
    "asesinado", "asesinada", "asesinato", "fue muerto", "fue muerta", "se ahogó", "se ahogo", "ahogado",
    "murió", "murio", "falleció", "fallecio", "cadáver", "cadaver", "balazo", "balazos", "incendio",
    "quemado", "suicidio", "se suicidó", "homicidio", "pereció", "perecio", "difunto", "difunta",
    "juez de paz", "jurado del coroner",
]

ALL_KEYWORDS = ENGLISH_KEYWORDS + SPANISH_KEYWORDS

# Everyday words that alone are mostly noise ("dead letter", "deadly dull", obituary columns from elsewhere):
# they only count when another death keyword is close by. Everything else is a strong keyword.
WEAK_KEYWORDS = {"died", "dead", "deadly", "fatal", "shooting", "killing", "stabbing", "murió", "murio",
                 "falleció", "fallecio", "difunto", "difunta", "incendio", "quemado", "pereció", "perecio", "juez de paz"}
_KEYWORD_RE = re.compile(r"\b(?:" + "|".join(re.escape(k) for k in sorted(ALL_KEYWORDS, key=len, reverse=True)) + r")\b", re.I)

_ES_MARKERS = re.compile(r"\b(el|la|los|las|del|que|por|para|una|con|señor|condado|ayer)\b", re.I)
_EN_MARKERS = re.compile(r"\b(the|and|of|was|that|with|for|county|yesterday)\b", re.I)


def has_keyword(text: str) -> bool:
    return bool(_KEYWORD_RE.search(text or ""))


def keyword_spans(text: str) -> list[tuple[int, int]]:
    return [m.span() for m in _KEYWORD_RE.finditer(text or "")]


def keyword_hits(text: str) -> list[tuple[int, int, bool]]:
    """(start, end, strong) for every death keyword."""
    return [(m.start(), m.end(), m.group(0).lower() not in WEAK_KEYWORDS) for m in _KEYWORD_RE.finditer(text or "")]


def detect_language(text: str) -> str:
    """Cheap heuristic: 'es' if Spanish function words clearly dominate."""
    sample = (text or "")[:5000]
    es = len(_ES_MARKERS.findall(sample))
    en = len(_EN_MARKERS.findall(sample))
    return "es" if es > en * 1.3 else "en"


EXTRACTION_SYSTEM = """You extract reported deaths from New Mexico newspaper text for a property-history database.
The text may be English or Spanish, may be noisy OCR, and may be several excerpts from one page separated by "-----".
Only deaths that happened in New Mexico count, anywhere in the state. Newspapers also carried wire stories from other
states and countries (datelines like "DENVER, Colo.", "EL PASO, Tex.", "NEW YORK"): skip those; city and county must be in New Mexico.
Local items without a town name ("at his home on North Fourth street") are in the town where the paper is printed.

For each qualifying death that has ANY location (street address, intersection, landmark, or at least a town), return one item with:
- address_raw: the location exactly as printed, without the apartment/room number (keep historic street names; translate nothing)
- unit: apartment, room, or unit number if printed, else null
- city, county: best reading; null if not stated
- location_precision: street_address | intersection | landmark | city_only
- place_kind: house | apartment_building | boarding_house_or_hotel | business | public_place | road | other | unknown
  (boarding houses, rooming houses, hotels, motels, saloons, stores, ranch names count as their kind, not house)
- incident_date: as precise as the text allows ("1932-03-08", "1932-03", "1932"); use the paper's date only if the article says "yesterday/ayer/this morning" etc.
- cause_category: natural | accident | homicide | suicide | fire | unknown (a suicide is labeled suicide)
- summary: ONE neutral English sentence, under 25 words, with NO personal names, ages, or graphic detail. Example: "A fatal shooting at a residence was reported." Even for Spanish articles, write the summary in English.
- confidence: 0-1 that this is a real death at that location (lower for OCR damage, rumor, vague places, or if you are unsure the place is in New Mexico)

Rules: Never include names of victims, suspects, or relatives anywhere. Never copy article text. Skip deaths outside New Mexico, war casualty lists, executions reported from elsewhere, and obituaries with no location. One death reported twice in the excerpts is one item. If nothing qualifies, return an empty list."""

TRIAGE_SYSTEM = """You are a cheap first-pass filter. Answer only with the tool call.
Does this New Mexico newspaper page (English or Spanish, OCR text) report at least one death that happened in New Mexico AND mention where it happened (a street, place, landmark, or town)?"""
