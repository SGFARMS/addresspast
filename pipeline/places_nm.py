"""Pilot-area towns: name variants (incl. common OCR damage), county, and a centroid.

Used by the harvest pre-filter (is a pilot town near the death keyword?) and by the
geocoder's last-resort city fallback. Centroids are approximate town centers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Town:
    name: str
    county: str  # lowercase county slug
    lat: float
    lng: float
    patterns: tuple[str, ...]
    case_sensitive: bool = False  # for names that are also ordinary words ("Tome")


TOWNS: list[Town] = [
    # Bernalillo County
    Town("Albuquerque", "bernalillo", 35.0844, -106.6504, (
        r"albuquerque", r"alburquerque", r"albuqu?erqu?e", r"albnquerque", r"albuqnerque",
        r"albuquerqne", r"albuquer-\s*que", r"duke city",
    )),
    Town("Los Ranchos de Albuquerque", "bernalillo", 35.1620, -106.6428, (r"los ranchos",)),
    Town("Alameda", "bernalillo", 35.1906, -106.6178, (r"alameda",)),
    Town("Atrisco", "bernalillo", 35.0700, -106.7000, (r"atrisco",)),
    Town("Barelas", "bernalillo", 35.0700, -106.6550, (r"barelas",)),
    Town("Isleta", "bernalillo", 34.9089, -106.6942, (r"isleta",)),
    Town("Tijeras", "bernalillo", 35.0870, -106.3842, (r"tijeras",)),
    Town("Pajarito", "bernalillo", 35.0060, -106.6950, (r"pajarito",)),
    Town("Los Padillas", "bernalillo", 34.9860, -106.6920, (r"los padillas",)),
    # Sandoval County (pilot covers the Rio Rancho area)
    Town("Rio Rancho", "sandoval", 35.2328, -106.6630, (r"rio rancho",)),
    Town("Corrales", "sandoval", 35.2378, -106.6067, (r"corrales",)),
    Town("Bernalillo", "sandoval", 35.3000, -106.5511, (r"bernalillo",)),
    Town("Placitas", "sandoval", 35.3070, -106.4245, (r"placitas",)),
    Town("Algodones", "sandoval", 35.3820, -106.4789, (r"algodones",)),
    # Valencia County
    Town("Belen", "valencia", 34.6628, -106.7764, (r"belen", r"belén")),
    Town("Los Lunas", "valencia", 34.8062, -106.7334, (r"los lunas", r"loa lunas", r"los innas")),
    Town("Bosque Farms", "valencia", 34.8548, -106.7053, (r"bosque farms",)),
    Town("Peralta", "valencia", 34.8370, -106.6900, (r"peralta",)),
    Town("Tomé", "valencia", 34.7400, -106.7290, (r"Tom[eé]",), case_sensitive=True),
    Town("Jarales", "valencia", 34.6170, -106.7650, (r"jarales",)),
    Town("Los Chavez", "valencia", 34.7300, -106.7600, (r"los ch[aá]vez",)),
    Town("Meadow Lake", "valencia", 34.8040, -106.5470, (r"meadow lake",)),
    Town("Rio Communities", "valencia", 34.6487, -106.7339, (r"rio communities",)),
    Town("Valencia", "valencia", 34.8000, -106.7000, (r"valencia",)),
]

# "Bernalillo county" / "Valencia county" / "condado de Valencia" also count as pilot mentions.
_COUNTY_RE = re.compile(r"\b(bernalillo|valencia)\s+(county|co\.)|\bcondado\s+de\s+(bernalillo|valencia)\b", re.I)

_TOWN_RES: list[tuple[Town, re.Pattern]] = [
    (t, re.compile(r"\b(?:" + "|".join(t.patterns) + r")\b", 0 if t.case_sensitive else re.I)) for t in TOWNS
]

# Newspapers printed in the pilot area. Local news from these papers often skips the town name
# ("at his home on North Fourth street"), so the pre-filter is looser for them.
PILOT_PAPER_CITIES = {"albuquerque", "belen", "los lunas", "bernalillo", "rio rancho", "corrales"}


def find_towns(text: str) -> list[Town]:
    found = [t for t, rx in _TOWN_RES if rx.search(text or "")]
    return found


def mentions_pilot_area(text: str) -> bool:
    return bool(_COUNTY_RE.search(text or "")) or any(rx.search(text or "") for _, rx in _TOWN_RES)


def town_by_name(name: str | None) -> Town | None:
    if not name:
        return None
    n = name.strip().lower()
    for t, rx in _TOWN_RES:
        if t.name.lower() == n or rx.fullmatch(name.strip()):
            return t
    return None


def is_pilot_paper(cities: list[str] | None) -> bool:
    return any((c or "").strip().lower() in PILOT_PAPER_CITIES for c in (cities or []))


# ── Statewide ────────────────────────────────────────────────────────────────────────────────
# Names only (no centroids: the geocoder looks statewide towns up on Photon/OSM). Used by the
# pre-filter so a death anywhere in New Mexico counts, not just in the three pilot counties.
# Names that are also everyday words or common surnames (Hope, Golden, Lincoln, Columbus, Roy...)
# are left out; a "<name> county" mention or the paper's own town still catches those items.
NM_PLACE_NAMES = [
    "Santa Fe", "Las Vegas", "East Las Vegas", "Las Cruces", "Mesilla", "Socorro", "Silver City", "Gallup", "Raton",
    "Roswell", "Carlsbad", "Eddy", "Artesia", "Hobbs", "Lovington", "Clovis", "Portales", "Tucumcari", "Santa Rosa",
    "Fort Sumner", "Vaughn", "Estancia", "Moriarty", "Mountainair", "Willard", "Clayton", "Springer", "Cimarron",
    "Wagon Mound", "Mora", "Taos", "Ranchos de Taos", "Questa", "Red River", "Espanola", "Española", "Chama",
    "Tierra Amarilla", "Abiquiu", "Chimayo", "Chimayó", "Pecos", "Galisteo", "Lamy", "Glorieta", "Cerrillos",
    "Farmington", "Aztec", "Bloomfield", "Shiprock", "Dulce", "Cuba", "Jemez", "Zuni", "Laguna", "Acoma", "Grants",
    "Thoreau", "Crownpoint", "Fort Wingate", "Ramah", "Quemado", "Datil", "Magdalena", "Reserve", "Mogollon",
    "Pinos Altos", "Fort Bayard", "Hurley", "Santa Rita", "Bayard", "Deming", "Lordsburg", "Hachita", "Animas",
    "Hillsboro", "Kingston", "Lake Valley", "Hot Springs", "Truth or Consequences", "San Marcial", "Hatch",
    "Alamogordo", "Tularosa", "Cloudcroft", "La Luz", "Ruidoso", "Capitan", "Carrizozo", "White Oaks", "Nogal",
    "Lincoln county", "Dawson", "Koehler", "Blossburg", "Elizabethtown", "Maxwell City", "Folsom", "Des Moines",
    "Nara Visa", "Logan", "Texico", "Elida", "Kenna", "Mosquero", "Puerto de Luna", "Anton Chico", "Watrous",
    "Ocate", "Rociada", "Sapello", "Romeroville", "Gallinas", "Tecolote", "Bernal", "Villanueva", "Encino",
    "Duran", "Corona", "Torrance", "Tajique", "Manzano", "Punta de Agua", "Chilili", "Cañoncito", "Hagerman",
    "Dexter", "Lake Arthur", "Loving", "Malaga", "Jal", "Eunice", "Tatum", "Anthony", "Organ", "Dona Ana",
    "Doña Ana", "Rincon", "Engle", "Cutter", "Cabezon", "San Ysidro", "Zia", "Cochiti", "Santo Domingo",
    "San Felipe", "Pena Blanca", "Peña Blanca", "Los Alamos", "White Rock", "Velarde", "Embudo", "Dixon", "Penasco",
    "Peñasco", "Trampas", "Truchas", "Ojo Caliente", "El Rito", "Tres Piedras", "Costilla", "Amalia",
    "Mora", "Kelly", "Sabinal", "Lemitar", "Polvadera", "San Acacia", "La Joya", "Bernardo", "Cubero", "San Rafael",
    "Seboyeta", "Cebolleta", "San Mateo", "Fort Stanton", "Picacho", "Lake Valley", "Chloride", "Winston",
    "Fairview", "Cuchillo", "Monticello", "Gallina", "Coyote", "Youngsville", "Ensenada", "Lumberton", "Monero",
    "Gallup", "Gibson", "Clarkville", "Allison", "Cimarron", "Van Houten", "Sugarite", "Yankee", "Brilliant",
]

NM_COUNTIES = [
    "bernalillo", "catron", "chaves", "cibola", "colfax", "curry", "de baca", "debaca", "dona ana", "doña ana", "eddy", "grant",
    "guadalupe", "harding", "hidalgo", "lea", "lincoln", "los alamos", "luna", "mckinley", "mora", "otero", "quay",
    "rio arriba", "roosevelt", "sandoval", "san juan", "san miguel", "santa fe", "sierra", "socorro", "taos",
    "torrance", "union", "valencia",
]

_NM_PLACE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(n) for n in sorted(NM_PLACE_NAMES, key=len, reverse=True)) + r")\b", re.I
)
_NM_COUNTY_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(c) for c in NM_COUNTIES) + r")\s+(?:county|co\.)|\bcondado\s+de\s+(?:"
    + "|".join(re.escape(c) for c in NM_COUNTIES) + r")\b",
    re.I,
)


def mentions_nm_place(text: str) -> bool:
    """Any New Mexico town or county (the pilot towns included)."""
    t = text or ""
    return mentions_pilot_area(t) or bool(_NM_PLACE_RE.search(t)) or bool(_NM_COUNTY_RE.search(t))
