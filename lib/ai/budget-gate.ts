/**
 * Daily spend gate for site-side AI. Pure (no server or database imports) so it can be unit tested.
 * Fails closed: if spend can't be read, the answer is "not ok", and callers use the free fallback.
 */
export interface GateOptions {
  capUsd: number;
  /** Total logged spend (USD) since the given ISO time; may stop counting once `stopAt` is reached. */
  getSpend: (sinceIso: string, stopAt: number) => Promise<number>;
  /** How long a spend reading is reused (ms). Keeps this from being a database query on every request. */
  ttlMs?: number;
  now?: () => number;
  onError?: (e: unknown) => void;
}

export function utcDayStartIso(ms: number) {
  const d = new Date(ms);
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate())).toISOString();
}

export function createBudgetGate(opts: GateOptions) {
  const ttl = opts.ttlMs ?? 60_000;
  const now = opts.now ?? Date.now;
  let cache: { day: string; at: number; ok: boolean } | null = null;

  return async function budgetOk(): Promise<boolean> {
    const t = now();
    const day = utcDayStartIso(t);
    // Once the cap is hit it stays hit until the UTC day rolls over; no need to re-read.
    if (cache && cache.day === day && (!cache.ok || t - cache.at < ttl)) return cache.ok;
    try {
      const spent = await opts.getSpend(day, opts.capUsd);
      cache = { day, at: t, ok: spent < opts.capUsd };
    } catch (e) {
      opts.onError?.(e);
      cache = { day, at: t, ok: false };
    }
    return cache.ok;
  };
}
