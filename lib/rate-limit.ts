import "server-only";
import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";
import { siteConfig } from "@/site.config";

type Bucket = keyof typeof siteConfig.rateLimit;

const limiters = new Map<Bucket, Ratelimit>();
const memory = new Map<string, number[]>();

function upstash(bucket: Bucket) {
  if (!process.env.UPSTASH_REDIS_REST_URL || !process.env.UPSTASH_REDIS_REST_TOKEN) return null;
  let l = limiters.get(bucket);
  if (!l) {
    const { requests, window } = siteConfig.rateLimit[bucket];
    l = new Ratelimit({
      redis: Redis.fromEnv(),
      limiter: Ratelimit.slidingWindow(requests, window as `${number} ${"s" | "m" | "h"}`),
      prefix: `ap:${bucket}`,
      analytics: false,
    });
    limiters.set(bucket, l);
  }
  return l;
}

function windowMs(w: string) {
  const [n, unit] = w.split(" ");
  return Number(n) * (unit === "s" ? 1000 : unit === "m" ? 60_000 : 3_600_000);
}

/** Per-IP limit. Upstash in production; a per-instance memory fallback for local dev. */
export async function rateLimit(bucket: Bucket, ip: string): Promise<{ ok: boolean; retryAfter: number }> {
  const l = upstash(bucket);
  if (l) {
    const r = await l.limit(ip);
    return { ok: r.success, retryAfter: Math.max(0, Math.ceil((r.reset - Date.now()) / 1000)) };
  }
  const { requests, window } = siteConfig.rateLimit[bucket];
  const ms = windowMs(window);
  const key = `${bucket}:${ip}`;
  const now = Date.now();
  const hits = (memory.get(key) ?? []).filter((t) => now - t < ms);
  if (hits.length >= requests) return { ok: false, retryAfter: Math.ceil((ms - (now - hits[0])) / 1000) };
  hits.push(now);
  memory.set(key, hits);
  return { ok: true, retryAfter: 0 };
}

export function clientIp(req: Request) {
  const fwd = req.headers.get("x-forwarded-for");
  return (fwd?.split(",")[0] ?? req.headers.get("x-real-ip") ?? "local").trim();
}

export function tooMany(retryAfter: number) {
  return Response.json(
    { error: "rate_limited" },
    { status: 429, headers: { "Retry-After": String(retryAfter) } },
  );
}
