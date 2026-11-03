import { describe, expect, it, vi } from "vitest";
import { createBudgetGate, utcDayStartIso } from "@/lib/ai/budget-gate";

const T0 = Date.UTC(2026, 10, 2, 15, 0, 0);

describe("site AI daily budget gate", () => {
  it("allows spend under the cap and blocks at or over it", async () => {
    let spend = 1.5;
    const g = createBudgetGate({ capUsd: 2, getSpend: async () => spend, ttlMs: 0, now: () => T0 });
    expect(await g()).toBe(true);
    spend = 2;
    expect(await g()).toBe(false);
  });

  it("reuses a reading for the ttl, then re-reads", async () => {
    let t = T0;
    const getSpend = vi.fn(async () => 0.1);
    const g = createBudgetGate({ capUsd: 2, getSpend, ttlMs: 60_000, now: () => t });
    await g(); await g();
    expect(getSpend).toHaveBeenCalledTimes(1);
    t += 61_000;
    await g();
    expect(getSpend).toHaveBeenCalledTimes(2);
  });

  it("stays blocked without re-reading until the UTC day rolls over", async () => {
    let t = T0;
    const getSpend = vi.fn(async () => 5);
    const g = createBudgetGate({ capUsd: 2, getSpend, ttlMs: 1, now: () => t });
    expect(await g()).toBe(false);
    t += 3_600_000;
    expect(await g()).toBe(false);
    expect(getSpend).toHaveBeenCalledTimes(1);
    t = Date.UTC(2026, 10, 3, 0, 5, 0); // next UTC day
    getSpend.mockResolvedValueOnce(0);
    expect(await g()).toBe(true);
    expect(getSpend).toHaveBeenCalledTimes(2);
  });

  it("fails closed when spend can't be read", async () => {
    const onError = vi.fn();
    const g = createBudgetGate({ capUsd: 2, getSpend: async () => { throw new Error("db down"); }, now: () => T0, onError });
    expect(await g()).toBe(false);
    expect(onError).toHaveBeenCalled();
  });

  it("measures from the start of the UTC day", () => {
    expect(utcDayStartIso(T0)).toBe("2026-11-02T00:00:00.000Z");
  });
});
