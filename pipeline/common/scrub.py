"""Python port of lib/scrub/names.ts. Runs before any summary is written to the database.
The TypeScript scrubber runs again on every response, and Phase 2 adds a Claude check."""
import re

PLACEHOLDER = "[name removed]"

ALLOWED_PHRASES = [
    "New Mexico", "Rio Grande", "Rio Rancho", "Los Lunas", "Los Ranchos", "Old Town", "Nob Hill",
    "North Valley", "South Valley", "Santa Fe", "Las Cruces", "Bosque Farms", "Isleta Pueblo",
    "Route 66", "Central Avenue", "Rail Yards", "Bernalillo County", "Valencia County", "Sandoval County",
    "Albuquerque Police Department", "Fire Department", "State Police", "Medical Investigator",
    "United States", "Chronicling America", "Library of Congress", "San Felipe de Neri",
]
ALLOWED_WORDS = {w.lower() for w in """A An The In On At Near After Before During Police Fire Officials County City State
Deputies Authorities Investigators Firefighters Witnesses January February March April May June July August
September October November December Monday Tuesday Wednesday Thursday Friday Saturday Sunday Albuquerque Belen
Bernalillo Valencia Sandoval Barelas Corrales Isleta Highway Interstate Avenue Street Road Boulevard Drive Lane
Plaza Church Route Railroad Depot Park Hospital School Mesa Valley Mexico New American Spanish English Native
Hispanic Catholic Se El La Los Las Un Una En De Del Y""".split()}

NAME = r"[A-ZÁÉÍÓÚÑ][a-záéíóúñü'’-]+"
PARTICLE = r"(?:de|del|la|las|los|y|van|von|di|da)"
MULTI = re.compile(rf"\b{NAME}(?:\s+(?:{PARTICLE}\s+)*(?:{NAME}|[A-Z]\.))+")
TITLE = re.compile(rf"\b(?:Mr|Mrs|Ms|Miss|Dr|Sr|Sra|Srta|Don|Doña|Dona|Señor|Señora|Rev|Capt|Sgt|Officer|Deputy|Judge|Father|Padre)\.?\s+({NAME}(?:\s+{NAME})*)")
NAME_AGE = re.compile(rf"\b({NAME}),\s*\d{{1,3}}\b")


def _allowed(phrase: str) -> bool:
    if phrase.lower() in {a.lower() for a in ALLOWED_PHRASES}:
        return True
    words = [w for w in phrase.split() if not re.fullmatch(PARTICLE, w, re.I)]
    return all(w.strip(".,").lower() in ALLOWED_WORDS for w in words)


def scrub_names(text: str | None) -> tuple[str, list[str]]:
    if not text:
        return text or "", []
    hits: list[str] = []
    protected = {}
    for i, phrase in enumerate(ALLOWED_PHRASES):
        key = f"\x00{i}\x00"

        def keep(m, key=key):
            protected[key] = m.group(0)
            return key

        text = re.sub(rf"\b{re.escape(phrase)}\b", keep, text, flags=re.I)

    def title(m):
        hits.append(m.group(0))
        return m.group(0).replace(m.group(1), PLACEHOLDER)

    text = TITLE.sub(title, text)

    def age(m):
        if m.group(1).lower() in ALLOWED_WORDS:
            return m.group(0)
        hits.append(m.group(1))
        return m.group(0).replace(m.group(1), PLACEHOLDER)

    text = NAME_AGE.sub(age, text)

    def multi(m):
        words = m.group(0).split()
        while words and words[0].lower() in ALLOWED_WORDS:
            words.pop(0)
        rest = " ".join(words)
        if len(words) < 2 and not re.search(r"[A-Z]\.", rest):
            return m.group(0)
        if _allowed(m.group(0)) or _allowed(rest):
            return m.group(0)
        hits.append(rest)
        return m.group(0).replace(rest, PLACEHOLDER)

    text = MULTI.sub(multi, text)
    for k, v in protected.items():
        text = text.replace(k, v)
    return text, hits
