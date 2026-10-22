import "server-only";
import { createHmac, timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";

/**
 * Owner-only admin gate. One shared password (ADMIN_PASSWORD env). The cookie holds an HMAC of a
 * fixed label keyed by that password, so changing the password signs everyone out.
 * Without ADMIN_PASSWORD the admin area is closed (except in local dev on demo data).
 */
export const ADMIN_COOKIE = "ap_admin";
const LABEL = "addresspast-admin-v1";

function password(): string | null {
  const p = process.env.ADMIN_PASSWORD;
  if (p) return p;
  return process.env.NODE_ENV === "development" ? "admin" : null;
}

export function adminConfigured() {
  return password() !== null;
}

function token(pw: string) {
  return createHmac("sha256", pw).update(LABEL).digest("base64url");
}

function same(a: string, b: string) {
  const x = Buffer.from(a);
  const y = Buffer.from(b);
  return x.length === y.length && timingSafeEqual(x, y);
}

export function checkPassword(given: string): string | null {
  const pw = password();
  if (!pw || !same(given, pw)) return null;
  return token(pw);
}

export async function isAdmin(): Promise<boolean> {
  const pw = password();
  if (!pw) return false;
  const c = (await cookies()).get(ADMIN_COOKIE)?.value;
  return Boolean(c && same(c, token(pw)));
}

export function adminCookie(value: string, maxAge = 60 * 60 * 24 * 7) {
  return `${ADMIN_COOKIE}=${value}; Path=/; Max-Age=${maxAge}; HttpOnly; SameSite=Strict; Secure`;
}
