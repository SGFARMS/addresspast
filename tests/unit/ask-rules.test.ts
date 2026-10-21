import { describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));
vi.mock("@/lib/places", () => ({ suggestPlaces: vi.fn(async () => []) }));
vi.mock("@/lib/data", () => ({ repo: () => ({ logAiUsage: async () => undefined }) }));

const { parseWithRules } = await import("@/lib/ai/ask");

describe("plain-English rules fallback", () => {
  it("fires in Belen before 1950", () => {
    const p = parseWithRules("fires in Belen before 1950");
    expect(p.record_types).toContain("fire");
    expect(p.causes).toContain("fire");
    expect(p.year_to).toBe(1949);
    expect(p.place).toBe("Belen");
  });

  it("anything near Old Town in the last 10 years", () => {
    const p = parseWithRules("anything near Old Town in the last 10 years");
    expect(p.place).toBe("Old Town");
    expect(p.radius_m).toBe(500);
    expect(p.year_from).toBe(new Date().getFullYear() - 10);
  });

  it("Spanish: incendios en Los Lunas antes de 1930", () => {
    const p = parseWithRules("incendios en Los Lunas antes de 1930");
    expect(p.record_types).toContain("fire");
    expect(p.year_to).toBe(1929);
    expect(p.place).toBe("Los Lunas");
  });

  it("decades", () => {
    const p = parseWithRules("homicides in Albuquerque in the 1930s");
    expect(p.causes).toContain("homicide");
    expect(p.year_from).toBe(1930);
    expect(p.year_to).toBe(1939);
  });
});
