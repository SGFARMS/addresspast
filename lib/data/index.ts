import "server-only";
import { hasSupabase } from "@/lib/supabase/server";
import { demoRepo } from "./demo";
import { supabaseRepo } from "./supabase";
import type { Repo } from "./repo";

/** Supabase when configured, otherwise the in-memory demo dataset (fake seed records). */
export function repo(): Repo {
  return hasSupabase() ? supabaseRepo : demoRepo;
}

export type { Repo } from "./repo";
