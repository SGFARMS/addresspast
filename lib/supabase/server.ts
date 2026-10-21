import "server-only";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let client: SupabaseClient | null = null;

/**
 * The SkyHigh BaaS (self-hosted Supabase). `connect-tenant-site` writes NEXT_PUBLIC_SUPABASE_URL to Vercel
 * and SUPABASE_URL to GitHub Actions; either works here. The service key is tenant-scoped (tenant_id claim).
 */
function supabaseUrl() {
  return process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL || "";
}

export function hasSupabase() {
  return Boolean(supabaseUrl() && process.env.SUPABASE_SERVICE_ROLE_KEY);
}

/** Service-role client. Server only — the `server-only` import makes a client bundle fail to build. */
export function serviceClient(): SupabaseClient {
  if (!client) {
    client = createClient(supabaseUrl()!, process.env.SUPABASE_SERVICE_ROLE_KEY!, {
      auth: { persistSession: false, autoRefreshToken: false },
    });
  }
  return client;
}
