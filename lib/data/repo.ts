import type { AreaStats, Bbox, CheckItem, CityBucket, EventDetail, FreeCheck, MapEvent, MapFilters, RemovalRequest } from "@/lib/types";

export interface AiUsage {
  feature: string;
  model: string;
  inputTokens: number;
  outputTokens: number;
  cacheReadTokens?: number;
  cacheWriteTokens?: number;
  costUsd: number;
}

export interface ScrubHit {
  eventId: string | null;
  field: string;
  matchedText: string;
  detector: "regex" | "claude";
  context: "pipeline" | "response";
}

/** Everything the public site reads or writes. Two backends: demo (seed data in memory) and Supabase. */
export interface Repo {
  readonly kind: "demo" | "supabase";
  freeCheck(args: { lat: number; lng: number; city: string | null; nearM: number; recordTypes: string[] }): Promise<FreeCheck>;
  mapEvents(bbox: Bbox, f: MapFilters): Promise<MapEvent[]>;
  cityDecades(f: MapFilters): Promise<CityBucket[]>;
  /** Records placed only at town level ("Gallup, 1912"), newest last. Up to 500. */
  cityEvents(city: string, f: MapFilters): Promise<CheckItem[]>;
  eventDetail(id: string, full: boolean, locale: string): Promise<EventDetail | null>;
  /** One-line summaries for list previews, by event id (Spanish when available for locale "es"). */
  eventSummaries(ids: string[], locale: string): Promise<Record<string, string>>;
  areaStats(county: string, city: string | null, includeNatural: boolean): Promise<AreaStats>;
  /** Fast lane: family/owner/tenant requests on records from the last 10 years hide the record at once. */
  requestRemoval(r: RemovalRequest): Promise<{ ok: boolean; fastLane: boolean }>;
  addToWaitlist(row: { email: string; locale: string; county: string | null; referrer: string | null }): Promise<"ok" | "exists">;
  getAreaSummary(county: string, city: string, locale: string): Promise<{ body: string; statsHash: string } | null>;
  saveAreaSummary(row: { county: string; city: string; locale: string; body: string; statsHash: string; model: string }): Promise<void>;
  logScrubHits(hits: ScrubHit[]): Promise<void>;
  logAiUsage(u: AiUsage): Promise<void>;
}
