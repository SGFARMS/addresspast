import type { Cause } from "@/lib/types";

/** A source record held off the public site until a person looks at it. */
export interface ReviewIncident {
  id: number;
  sourceName: string | null;
  sourceUrl: string;
  publishedDate: string | null;
  incidentDate: string | null;
  addressRaw: string;
  unit: string | null;
  city: string | null;
  county: string | null;
  placeKind: string | null;
  cause: Cause;
  summary: string | null;
  confidence: number | null;
  reviewReason: string | null;
  /** Geocoding found no town in our counties: approving it won't put it on the map. */
  outsideArea: boolean;
  createdAt: string;
}

/** Claude's guess at a modern location for an old address that didn't geocode. */
export interface ReviewSuggestion {
  id: number;
  incidentId: number;
  addressRaw: string;
  city: string | null;
  year: number | null;
  summary: string | null;
  sourceUrl: string;
  suggestedLat: number;
  suggestedLng: number;
  suggestedAddress: string | null;
  rationale: string | null;
}

export interface ReviewDispute {
  id: number;
  eventId: string | null;
  eventYear: number | null;
  eventCity: string | null;
  eventCause: Cause | null;
  eventHidden: boolean | null;
  requesterEmail: string;
  relationship: string;
  reason: string;
  details: string | null;
  fastLane: boolean;
  createdAt: string;
}

export interface AdminQueue {
  backend: "demo" | "supabase";
  incidents: ReviewIncident[];
  suggestions: ReviewSuggestion[];
  disputes: ReviewDispute[];
  stats: {
    incidentsTotal: number;
    eventsVisible: number;
    harvestSpendUsd: number;
    lastRun: { job: string; status: string; finishedAt: string | null } | null;
  };
}

export type AdminAction =
  | { type: "incident"; id: number; action: "approve" | "hide" }
  | { type: "suggestion"; id: number; action: "accept" | "reject" }
  | { type: "dispute"; id: number; action: "remove" | "restore" | "corrected" };
