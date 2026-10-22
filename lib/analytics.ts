"use client";

import { track as vercelTrack } from "@vercel/analytics";

type EventName = "search" | "free_check" | "record_open" | "report_click" | "waitlist_join" | "filter_change" | "conversion" | "removal_request";

/** Thin wrapper so event names stay consistent. Never send addresses or coordinates. */
export function track(name: EventName, props?: Record<string, string | number | boolean>) {
  try {
    vercelTrack(name, props);
  } catch {
    /* analytics is optional */
  }
}
