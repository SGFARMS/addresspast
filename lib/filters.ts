import { z } from "zod";
import { CAUSES, RECORD_TYPES, type MapFilters } from "./types";
import { siteConfig } from "@/site.config";

const list = <T extends string>(allowed: readonly T[]) =>
  z
    .string()
    .optional()
    .transform((v) => (v ? (v.split(",").filter((x) => (allowed as readonly string[]).includes(x)) as T[]) : undefined));

export const mapQuerySchema = z.object({
  bbox: z
    .string()
    .transform((v) => v.split(",").map(Number))
    .refine((a) => a.length === 4 && a.every(Number.isFinite), "bbox must be w,s,e,n"),
  types: list(RECORD_TYPES),
  causes: list(CAUSES),
  natural: z.enum(["0", "1"]).optional(),
  minConf: z.coerce.number().min(0).max(1).optional(),
  verified: z.enum(["0", "1"]).optional(),
});

export function filtersFromQuery(q: z.infer<typeof mapQuerySchema>): MapFilters {
  return {
    recordTypes: q.types?.length ? q.types : ["death"],
    causes: q.causes?.length ? q.causes : null,
    includeNatural: q.natural ? q.natural === "1" : siteConfig.features.showNaturalByDefault,
    minConfidence: q.minConf ?? 0,
    verifiedOnly: q.verified === "1",
  };
}

export function filtersToQuery(f: MapFilters): Record<string, string> {
  const q: Record<string, string> = {
    types: f.recordTypes.join(","),
    natural: f.includeNatural ? "1" : "0",
    minConf: String(f.minConfidence),
    verified: f.verifiedOnly ? "1" : "0",
  };
  if (f.causes?.length) q.causes = f.causes.join(",");
  return q;
}

export const defaultFilters: MapFilters = {
  recordTypes: ["death"],
  causes: null,
  includeNatural: siteConfig.features.showNaturalByDefault,
  minConfidence: 0,
  verifiedOnly: false,
};

export function passesFilters(
  e: { recordType: string; cause: string; confidence: number; verified: boolean },
  f: MapFilters,
) {
  if (!f.recordTypes.includes(e.recordType as never)) return false;
  if (f.causes && !f.causes.includes(e.cause as never)) return false;
  if (!f.includeNatural && e.cause === "natural") return false;
  if (e.confidence < f.minConfidence) return false;
  if (f.verifiedOnly && !e.verified) return false;
  return true;
}
