export type RecordType = "death" | "fire" | "drug_lab" | "flood_zone";
export type Cause = "natural" | "accident" | "homicide" | "suicide" | "fire" | "unknown";
export type GeoPrecision = "street" | "street_historic" | "intersection" | "landmark" | "city";
export type DatePrecision = "day" | "month" | "year" | "decade";
export type Bbox = [west: number, south: number, east: number, north: number];

export const RECORD_TYPES: RecordType[] = ["death", "fire", "drug_lab", "flood_zone"];
export const CAUSES: Cause[] = ["accident", "homicide", "suicide", "fire", "natural", "unknown"];
export const APPROXIMATE: GeoPrecision[] = ["street_historic", "intersection", "landmark"];

export interface MapFilters {
  recordTypes: RecordType[];
  causes: Cause[] | null; // null = all
  includeNatural: boolean;
  minConfidence: number; // 0..1
  verifiedOnly: boolean;
}

export interface MapEvent {
  id: string;
  lng: number;
  lat: number;
  recordType: RecordType;
  cause: Cause;
  year: number | null;
  precision: GeoPrecision;
  confidence: number;
  verified: boolean;
  sourceCount: number;
}

export interface CityBucket {
  county: string;
  city: string;
  decade: number;
  n: number;
  lng: number;
  lat: number;
}

export interface CheckItem {
  id: string;
  year: number | null;
  datePrecision: DatePrecision | null;
  recordType: RecordType;
  cause: Cause;
  precision: GeoPrecision;
  verified: boolean;
  distanceM: number;
}

export interface Coverage {
  county: string;
  firstYear: number | null;
  lastYear: number | null;
  sourceCount: number;
  gapEraRecords: number;
}

export interface FreeCheck {
  parcelMatched: boolean;
  atAddress: CheckItem[];
  nearby: CheckItem[];
  cityOnlyCount: number;
  coverage: Coverage | null;
  asOf: string | null;
}

export interface EventSource {
  name: string;
  published: string | null;
  url: string | null;
  isLocScan: boolean;
}

export interface EventDetail {
  id: string;
  year: number | null;
  datePrecision: DatePrecision | null;
  recordType: RecordType;
  cause: Cause;
  precision: GeoPrecision;
  confidence: number;
  verified: boolean;
  city: string | null;
  county: string | null;
  sourceCount: number;
  summary: string | null;
  sources: EventSource[];
}

export interface AreaStats {
  total: number;
  byDecade: Record<string, number>;
  byCause: Record<string, number>;
  byPrecision: Record<string, number>;
  verified: number;
  coverage: Coverage | null;
}

export interface Place {
  label: string;
  lat: number;
  lng: number;
  city: string | null;
  county: string | null;
  kind: "address" | "street" | "place" | "area";
}

export interface AskResult {
  place: Place | null;
  radiusM: number | null;
  recordTypes: RecordType[] | null;
  causes: Cause[] | null;
  yearFrom: number | null;
  yearTo: number | null;
  includeNatural: boolean | null;
  via: "claude" | "rules";
}
