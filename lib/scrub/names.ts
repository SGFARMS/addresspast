/**
 * Server-side name scrubber. Every summary passes through this before it is
 * returned to a browser. It is deliberately aggressive: a false positive costs
 * a few words of a summary; a false negative puts a victim's name on the site.
 * Phase 2 adds a Claude check on top of this before publication.
 */

const PLACEHOLDER = "[name removed]";

/** Multi-word proper nouns that are places or institutions, not people. */
const ALLOWED_PHRASES = [
  "New Mexico", "Rio Grande", "Rio Rancho", "Los Lunas", "Los Ranchos", "Old Town", "Nob Hill",
  "North Valley", "South Valley", "Santa Fe", "Las Cruces", "Bosque Farms", "Isleta Pueblo",
  "Route 66", "Central Avenue", "Fourth Street", "Rail Yards", "Sandia Mountains", "Kirtland Air Force Base",
  "Bernalillo County", "Valencia County", "Sandoval County", "Albuquerque Police Department",
  "Fire Department", "Fire Rescue", "Sheriff's Office", "State Police", "Medical Investigator",
  "Office of the Medical Investigator", "United States", "Chronicling America", "Library of Congress",
  "San Felipe de Neri", "Old Town Plaza", "Peralta", "Tome",
];

/** Single capitalized words that are never names on their own. */
const ALLOWED_WORDS = new Set(
  [
    "A", "An", "The", "In", "On", "At", "Near", "After", "Before", "During", "Police", "Fire", "Officials",
    "County", "City", "State", "Deputies", "Authorities", "Investigators", "Firefighters", "Witnesses",
    "January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
    "November", "December", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "Albuquerque", "Belen", "Bernalillo", "Valencia", "Sandoval", "Barelas", "Corrales", "Isleta",
    "Highway", "Interstate", "Avenue", "Street", "Road", "Boulevard", "Drive", "Lane", "Plaza", "Church",
    "Route", "Railroad", "Depot", "Park", "Hospital", "School", "Mesa", "Valley", "Mexico", "New",
    "American", "Spanish", "English", "Native", "Hispanic", "Catholic", "Methodist", "Baptist",
    "Se", "El", "La", "Los", "Las", "Un", "Una", "En", "De", "Del", "Y",
  ].map((w) => w.toLowerCase()),
);

const TITLES = /\b(Mr|Mrs|Ms|Miss|Dr|Sr|Sra|Srta|Don|Doña|Dona|Señor|Señora|Senor|Senora|Rev|Capt|Sgt|Officer|Deputy|Judge|Father|Padre|Hermano|Hermana)\.?\s+/;

const NAME_WORD = "[A-ZÁÉÍÓÚÑ][a-záéíóúñü'’-]+";
const PARTICLE = "(?:de|del|la|las|los|y|van|von|di|da|st\\.?)";
// Two to five capitalized words, allowing Spanish particles in between: "María de la Cruz", "John R. Smith"
const MULTI = new RegExp(
  `\\b${NAME_WORD}(?:\\s+(?:${PARTICLE}\\s+)*(?:${NAME_WORD}|[A-Z]\\.))+`,
  "g",
);
const AFTER_TITLE = new RegExp(`${TITLES.source}(${NAME_WORD}(?:\\s+${NAME_WORD})*)`, "g");
// "Smith, 42," → age pattern that almost always follows a name
const NAME_AGE = new RegExp(`\\b(${NAME_WORD}),\\s*\\d{1,3}\\b`, "g");

export interface ScrubResult {
  text: string;
  hits: string[];
}

function isAllowedPhrase(phrase: string) {
  const p = phrase.trim();
  if (ALLOWED_PHRASES.some((a) => a.toLowerCase() === p.toLowerCase())) return true;
  const words = p.split(/\s+/).filter((w) => !new RegExp(`^${PARTICLE}$`, "i").test(w));
  return words.every((w) => ALLOWED_WORDS.has(w.replace(/[.,]/g, "").toLowerCase()));
}

export function scrubNames(input: string | null | undefined): ScrubResult {
  if (!input) return { text: input ?? "", hits: [] };
  const hits: string[] = [];
  let text = input;

  // Protect allowed multi-word phrases from the generic pattern
  const protectedMap = new Map<string, string>();
  ALLOWED_PHRASES.forEach((phrase, i) => {
    const re = new RegExp(`\\b${phrase.replace(/[.*+?^${}()|[\]\\']/g, "\\$&")}\\b`, "gi");
    text = text.replace(re, (m) => {
      const key = `\u0000${i}\u0000`;
      protectedMap.set(key, m);
      return key;
    });
  });

  text = text.replace(AFTER_TITLE, (m, _title, name: string) => {
    hits.push(m.trim());
    return m.replace(name, PLACEHOLDER);
  });

  text = text.replace(NAME_AGE, (m, name: string) => {
    if (ALLOWED_WORDS.has(name.toLowerCase())) return m;
    hits.push(name);
    return m.replace(name, PLACEHOLDER);
  });

  text = text.replace(MULTI, (m) => {
    // Strip a leading sentence-starter word ("The Smith home" → check "Smith")
    const words = m.split(/\s+/);
    while (words.length && ALLOWED_WORDS.has(words[0].toLowerCase())) words.shift();
    const rest = words.join(" ");
    if (!rest || rest.split(/\s+/).length < 2 && !/[A-Z]\./.test(rest)) {
      // Only one remaining capitalized word: names need two words unless titled
      return m;
    }
    if (isAllowedPhrase(m) || isAllowedPhrase(rest)) return m;
    hits.push(rest);
    return m.replace(rest, PLACEHOLDER);
  });

  for (const [key, val] of protectedMap) text = text.split(key).join(val);

  // Collapse repeated placeholders
  text = text.replace(new RegExp(`(${escape(PLACEHOLDER)})(\\s*(and|y|,)\\s*\\1)+`, "g"), PLACEHOLDER);
  return { text, hits };
}

function escape(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
