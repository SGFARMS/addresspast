/**
 * ~40 FAKE records for local testing and the demo data mode.
 * Every place, summary and source here is invented. No real incidents, no names.
 * Covers every geocode precision, record type, cause and decade (1860s → 2020s).
 */
import type { Cause, DatePrecision, GeoPrecision, RecordType } from "@/lib/types";

export interface SeedSource {
  name: string;
  url: string;
  published: string;
  confidence: number;
  language?: "en" | "es";
}

export interface SeedRecord {
  id: string;
  city: string;
  county: "Bernalillo" | "Valencia" | "Sandoval";
  lat: number;
  lng: number;
  year: number;
  datePrecision: DatePrecision;
  recordType: RecordType;
  cause: Cause;
  precision: GeoPrecision;
  verified: boolean;
  summary: string;
  summaryEs: string;
  sources: SeedSource[];
}

const LOC = "https://www.loc.gov/collections/chronicling-america/";
const news = (slug: string) => `https://example.org/sample-news/${slug}`;
const uid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;

// Neighborhood anchors (approximate, for fake data only)
const P = {
  oldTown: [35.0961, -106.6697],
  downtown: [35.0849, -106.651],
  barelas: [35.0712, -106.6556],
  nobHill: [35.0806, -106.6156],
  northValley: [35.1361, -106.6514],
  belen: [34.6628, -106.7764],
  losLunas: [34.8062, -106.7334],
  rioRancho: [35.2334, -106.6645],
} as const;

type Row = [
  n: number,
  anchor: keyof typeof P,
  dLat: number,
  dLng: number,
  year: number,
  recordType: RecordType,
  cause: Cause,
  precision: GeoPrecision,
  verified: boolean,
  summary: string,
  summaryEs: string,
  sources: SeedSource[],
];

const CITY: Record<keyof typeof P, [string, SeedRecord["county"]]> = {
  oldTown: ["Albuquerque", "Bernalillo"],
  downtown: ["Albuquerque", "Bernalillo"],
  barelas: ["Albuquerque", "Bernalillo"],
  nobHill: ["Albuquerque", "Bernalillo"],
  northValley: ["Albuquerque", "Bernalillo"],
  belen: ["Belen", "Valencia"],
  losLunas: ["Los Lunas", "Valencia"],
  rioRancho: ["Rio Rancho", "Sandoval"],
};

const rows: Row[] = [
  [1, "oldTown", 0.0004, 0.0011, 1868, "death", "accident", "street_historic", false,
    "A fatal wagon accident was reported near the plaza.",
    "Se reportó un accidente fatal de carreta cerca de la plaza.",
    [{ name: "Weekly territorial paper (sample)", url: LOC, published: "1868-05-14", confidence: 0.55 }]],
  [2, "oldTown", -0.0006, -0.0004, 1879, "death", "homicide", "landmark", false,
    "A fatal shooting was reported near the old church on the plaza.",
    "Se reportó un tiroteo fatal cerca de la antigua iglesia de la plaza.",
    [{ name: "Spanish-language weekly (sample)", url: LOC, published: "1879-09-02", confidence: 0.5, language: "es" },
     { name: "Weekly territorial paper (sample)", url: LOC, published: "1879-09-05", confidence: 0.45 }]],
  [3, "barelas", 0.0009, 0.0003, 1884, "death", "fire", "street_historic", false,
    "A house fire on a Barelas street was reported to have claimed one life.",
    "Se reportó que un incendio de casa en una calle de Barelas cobró una vida.",
    [{ name: "Daily territorial paper (sample)", url: LOC, published: "1884-01-22", confidence: 0.5 }]],
  [4, "losLunas", 0.002, -0.001, 1889, "death", "natural", "city", false,
    "A death from illness was noted in Los Lunas.",
    "Se registró una muerte por enfermedad en Los Lunas.",
    [{ name: "Spanish-language weekly (sample)", url: LOC, published: "1889-03-11", confidence: 0.7, language: "es" }]],
  [5, "belen", 0.0015, 0.0022, 1893, "death", "accident", "intersection", true,
    "A railroad yard accident near the depot was reported as fatal.",
    "Se reportó como fatal un accidente en el patio ferroviario cerca de la estación.",
    [{ name: "Daily territorial paper (sample)", url: LOC, published: "1893-07-30", confidence: 0.6 },
     { name: "Valley weekly (sample)", url: LOC, published: "1893-08-03", confidence: 0.55 }]],
  [6, "downtown", 0.0012, -0.0015, 1897, "death", "homicide", "street", false,
    "A fatal altercation at a downtown lodging house was reported.",
    "Se reportó un altercado fatal en una casa de huéspedes del centro.",
    [{ name: "Daily territorial paper (sample)", url: LOC, published: "1897-11-19", confidence: 0.8 }]],
  [7, "belen", -0.0021, -0.0008, 1902, "death", "suicide", "street_historic", false,
    "A death at a residence was reported as a suicide.",
    "Se reportó como suicidio una muerte en una residencia.",
    [{ name: "Valley weekly (sample)", url: LOC, published: "1902-04-08", confidence: 0.55 }]],
  [8, "barelas", -0.0011, 0.0016, 1906, "death", "accident", "street", false,
    "A fatal fall at a home under construction was reported.",
    "Se reportó una caída fatal en una casa en construcción.",
    [{ name: "Daily territorial paper (sample)", url: LOC, published: "1906-06-12", confidence: 0.75 }]],
  [9, "losLunas", -0.003, 0.0028, 1911, "death", "accident", "landmark", false,
    "A drowning was reported at an irrigation ditch on the edge of town.",
    "Se reportó un ahogamiento en una acequia en las afueras del pueblo.",
    [{ name: "Spanish-language weekly (sample)", url: LOC, published: "1911-07-21", confidence: 0.6, language: "es" }]],
  [10, "northValley", 0.0007, 0.0009, 1918, "death", "natural", "street", false,
    "A death during the influenza epidemic was reported at a farmhouse.",
    "Se reportó una muerte en una granja durante la epidemia de influenza.",
    [{ name: "Daily state paper (sample)", url: LOC, published: "1918-10-28", confidence: 0.7 }]],
  [11, "belen", 0.0009, -0.0031, 1921, "death", "fire", "street", true,
    "A residential fire was reported to have caused one death.",
    "Se reportó que un incendio residencial causó una muerte.",
    [{ name: "Valley weekly (sample)", url: LOC, published: "1921-02-02", confidence: 0.7 },
     { name: "Daily state paper (sample)", url: LOC, published: "1921-02-04", confidence: 0.6 }]],
  [12, "nobHill", 0.0003, -0.0006, 1927, "death", "accident", "intersection", false,
    "A fatal automobile collision was reported at a Route 66 intersection.",
    "Se reportó un choque automovilístico fatal en un cruce de la Ruta 66.",
    [{ name: "Daily state paper (sample)", url: LOC, published: "1927-08-16", confidence: 0.8 }]],
  [13, "downtown", 0.0, 0.0, 1932, "death", "homicide", "street", true,
    "A fatal shooting at a downtown residence was reported in several papers.",
    "Varios periódicos reportaron un tiroteo fatal en una residencia del centro.",
    [{ name: "Daily state paper (sample)", url: LOC, published: "1932-03-09", confidence: 0.8 },
     { name: "Evening paper (sample)", url: LOC, published: "1932-03-09", confidence: 0.7 },
     { name: "Spanish-language weekly (sample)", url: LOC, published: "1932-03-12", confidence: 0.6, language: "es" }]],
  [14, "losLunas", 0.0012, 0.0005, 1936, "death", "accident", "street", false,
    "A fatal accident involving farm equipment was reported at a residence.",
    "Se reportó un accidente fatal con maquinaria agrícola en una residencia.",
    [{ name: "Valley weekly (sample)", url: LOC, published: "1936-09-25", confidence: 0.6 }]],
  [15, "belen", 0.004, 0.001, 1941, "death", "natural", "city", false,
    "An elderly resident's death was noted in Belen.",
    "Se registró la muerte de un residente de edad avanzada en Belen.",
    [{ name: "Valley weekly (sample)", url: LOC, published: "1941-12-03", confidence: 0.6 }]],
  [16, "oldTown", 0.0013, 0.0021, 1947, "death", "suicide", "street", false,
    "A death at a residence was reported as a suicide.",
    "Se reportó como suicidio una muerte en una residencia.",
    [{ name: "Daily state paper (sample)", url: LOC, published: "1947-05-06", confidence: 0.65 }]],
  [17, "barelas", -0.0025, -0.0012, 1953, "death", "accident", "landmark", false,
    "A fatal accident was reported at the railroad shops.",
    "Se reportó un accidente fatal en los talleres del ferrocarril.",
    [{ name: "Daily state paper (sample)", url: LOC, published: "1953-01-14", confidence: 0.7 }]],
  [18, "losLunas", -0.0017, -0.0024, 1959, "death", "homicide", "street_historic", false,
    "A fatal stabbing was reported at a home on a since-renamed street.",
    "Se reportó un apuñalamiento fatal en una casa de una calle que luego cambió de nombre.",
    [{ name: "Valley weekly (sample)", url: LOC, published: "1959-10-01", confidence: 0.5 }]],
  [19, "belen", -0.0007, 0.0014, 1962, "death", "fire", "street", false,
    "A house fire was reported to have caused one death.",
    "Se reportó que un incendio de casa causó una muerte.",
    [{ name: "Valley weekly (sample)", url: LOC, published: "1962-12-19", confidence: 0.75 }]],
  [20, "rioRancho", 0.0018, -0.0021, 1974, "death", "accident", "street", false,
    "A fatal accident at a new subdivision home was reported.",
    "Se reportó un accidente fatal en una casa de una nueva urbanización.",
    [{ name: "County records summary (sample)", url: news("1974-rr"), published: "1974-06-03", confidence: 0.7 }]],
  [21, "nobHill", -0.0009, 0.0014, 1983, "death", "homicide", "street", false,
    "A fatal assault at an apartment was reported.",
    "Se reportó una agresión fatal en un apartamento.",
    [{ name: "Metro daily (sample)", url: news("1983-nh"), published: "1983-02-17", confidence: 0.8 }]],
  [22, "losLunas", 0.0026, 0.0019, 1991, "death", "accident", "intersection", false,
    "A fatal traffic collision was reported at a highway intersection.",
    "Se reportó un choque fatal en un cruce de carretera.",
    [{ name: "Valley weekly (sample)", url: news("1991-ll"), published: "1991-04-29", confidence: 0.7 }]],
  [23, "rioRancho", -0.004, 0.003, 1998, "death", "unknown", "city", false,
    "A death under unclear circumstances was reported in Rio Rancho.",
    "Se reportó una muerte en circunstancias poco claras en Rio Rancho.",
    [{ name: "Metro daily (sample)", url: news("1998-rr"), published: "1998-11-08", confidence: 0.45 }]],
  [24, "northValley", -0.0014, -0.0019, 2004, "death", "natural", "street", false,
    "A resident was found deceased at home; the death was reported as natural.",
    "Un residente fue encontrado sin vida en su casa; la muerte se reportó como natural.",
    [{ name: "Metro daily (sample)", url: news("2004-nv"), published: "2004-01-30", confidence: 0.6 }]],
  [25, "belen", 0.0028, 0.0026, 2009, "death", "accident", "street", false,
    "A fatal carbon monoxide accident was reported at a residence.",
    "Se reportó un accidente fatal por monóxido de carbono en una residencia.",
    [{ name: "Valley news site (sample)", url: news("2009-belen"), published: "2009-12-11", confidence: 0.75 }]],
  [26, "downtown", 0.0021, 0.0011, 2012, "death", "homicide", "street", true,
    "A fatal shooting at a downtown apartment building was reported.",
    "Se reportó un tiroteo fatal en un edificio de apartamentos del centro.",
    [{ name: "Metro daily (sample)", url: news("2012-dt"), published: "2012-07-04", confidence: 0.85 },
     { name: "Local TV news (sample)", url: news("2012-dt-tv"), published: "2012-07-04", confidence: 0.8 }]],
  [27, "rioRancho", 0.0011, 0.0008, 2015, "death", "suicide", "street", false,
    "A death at a residence was reported as a suicide.",
    "Se reportó como suicidio una muerte en una residencia.",
    [{ name: "Metro daily (sample)", url: news("2015-rr"), published: "2015-03-19", confidence: 0.7 }]],
  [28, "losLunas", -0.0008, 0.0011, 2017, "death", "fire", "street", false,
    "A house fire was reported to have caused one death.",
    "Se reportó que un incendio de casa causó una muerte.",
    [{ name: "Valley news site (sample)", url: news("2017-ll"), published: "2017-01-08", confidence: 0.8 },
     { name: "Local TV news (sample)", url: news("2017-ll-tv"), published: "2017-01-08", confidence: 0.7 }]],
  [29, "nobHill", 0.0016, 0.0024, 2019, "death", "accident", "intersection", false,
    "A fatal pedestrian collision was reported at a busy intersection.",
    "Se reportó un atropello fatal en un cruce concurrido.",
    [{ name: "Metro daily (sample)", url: news("2019-nh"), published: "2019-10-22", confidence: 0.85 }]],
  [30, "belen", -0.003, -0.0035, 2021, "death", "unknown", "city", false,
    "A death under investigation was reported in Belen.",
    "Se reportó una muerte bajo investigación en Belen.",
    [{ name: "Valley news site (sample)", url: news("2021-belen"), published: "2021-05-14", confidence: 0.5 }]],
  [31, "barelas", 0.0017, -0.0021, 2022, "death", "homicide", "street", false,
    "A fatal shooting at a residence was reported.",
    "Se reportó un tiroteo fatal en una residencia.",
    [{ name: "Metro daily (sample)", url: news("2022-bar"), published: "2022-08-27", confidence: 0.85 }]],
  [32, "rioRancho", -0.0019, -0.0013, 2023, "death", "natural", "street", false,
    "A resident's death at home was reported as natural causes.",
    "Se reportó como causa natural la muerte de un residente en su casa.",
    [{ name: "Metro daily (sample)", url: news("2023-rr"), published: "2023-02-02", confidence: 0.65 }]],
  [33, "losLunas", 0.0035, -0.0027, 2024, "death", "accident", "landmark", false,
    "A fatal accident was reported at a riverside park.",
    "Se reportó un accidente fatal en un parque junto al río.",
    [{ name: "Valley news site (sample)", url: news("2024-ll"), published: "2024-06-16", confidence: 0.7 }]],
  [34, "oldTown", -0.0011, 0.0016, 2025, "death", "accident", "street", false,
    "A fatal fall at a residence was reported.",
    "Se reportó una caída fatal en una residencia.",
    [{ name: "Metro daily (sample)", url: news("2025-ot"), published: "2025-03-03", confidence: 0.8 }]],
  [35, "downtown", -0.0016, 0.0024, 2016, "fire", "unknown", "street", false,
    "A structure fire damaged a commercial building; no deaths were reported.",
    "Un incendio dañó un edificio comercial; no se reportaron muertes.",
    [{ name: "Fire department open data (sample)", url: news("2016-fire"), published: "2016-09-09", confidence: 0.9 }]],
  [36, "belen", 0.0019, -0.0012, 2020, "fire", "unknown", "street", false,
    "A residential structure fire was reported; no deaths were reported.",
    "Se reportó un incendio en una vivienda; no se reportaron muertes.",
    [{ name: "Fire department open data (sample)", url: news("2020-fire"), published: "2020-04-21", confidence: 0.9 }]],
  [37, "barelas", -0.0004, 0.0027, 2007, "drug_lab", "unknown", "street", true,
    "Listed as a former clandestine drug lab site in a public register.",
    "Figura como antiguo laboratorio clandestino de drogas en un registro público.",
    [{ name: "Public lab register (sample)", url: news("2007-lab"), published: "2007-10-01", confidence: 0.9 }]],
  [38, "rioRancho", 0.0029, 0.0019, 2011, "drug_lab", "unknown", "street", false,
    "Listed as a former clandestine drug lab site in a public register.",
    "Figura como antiguo laboratorio clandestino de drogas en un registro público.",
    [{ name: "Public lab register (sample)", url: news("2011-lab"), published: "2011-05-01", confidence: 0.9 }]],
  [39, "losLunas", -0.0041, 0.0035, 2023, "flood_zone", "unknown", "landmark", false,
    "Inside a mapped flood hazard area near the river.",
    "Dentro de un área de riesgo de inundación cerca del río.",
    [{ name: "Flood map data (sample)", url: news("2023-flood"), published: "2023-01-01", confidence: 0.95 }]],
  [40, "belen", -0.0012, 0.0005, 2026, "death", "natural", "street", false,
    "A death at a residence was reported; details were limited.",
    "Se reportó una muerte en una residencia; los detalles fueron limitados.",
    [{ name: "Valley news site (sample)", url: news("2026-belen"), published: "2026-09-12", confidence: 0.35 }]],
  [41, "downtown", 0.00008, 0.00006, 1961, "death", "accident", "street", false,
    "A fatal fall down a stairwell was reported at a downtown residence.",
    "Se reportó una caída fatal por una escalera en una residencia del centro.",
    [{ name: "Daily state paper (sample)", url: LOC, published: "1961-02-20", confidence: 0.6 }]],
];

/** Combined confidence: more independent sources → higher, capped at 0.99. */
export function combineConfidence(cs: number[]) {
  const miss = cs.reduce((acc, c) => acc * (1 - Math.min(c, 0.95)), 1);
  return Math.min(0.99, Math.round((1 - miss) * 1000) / 1000);
}

export const SEED_RECORDS: SeedRecord[] = rows.map(
  ([n, anchor, dLat, dLng, year, recordType, cause, precision, verified, summary, summaryEs, sources]): SeedRecord => {
    const [lat, lng] = P[anchor];
    const [city, county] = CITY[anchor];
    return {
      id: uid(n),
      city,
      county,
      lat: Math.round((lat + dLat) * 1e6) / 1e6,
      lng: Math.round((lng + dLng) * 1e6) / 1e6,
      year,
      datePrecision: year < 1870 ? "year" : "day",
      recordType,
      cause,
      precision,
      verified,
      summary,
      summaryEs,
      sources,
    };
  },
);

/** A seeded address with records at and near it — handy for demos and tests. */
export const DEMO_ADDRESS = {
  label: "Downtown Albuquerque (sample address)",
  lat: P.downtown[0],
  lng: P.downtown[1],
  city: "Albuquerque",
  county: "Bernalillo",
};
