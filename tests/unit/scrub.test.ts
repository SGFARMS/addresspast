import { describe, expect, it } from "vitest";
import { scrubNames } from "@/lib/scrub/names";

describe("scrubNames", () => {
  it("removes full names", () => {
    const r = scrubNames("John Smith was found at the residence.");
    expect(r.text).not.toContain("John");
    expect(r.text).not.toContain("Smith");
    expect(r.hits).toContain("John Smith");
  });

  it("removes Spanish names with particles", () => {
    const r = scrubNames("María de la Cruz Sandoval murió en su casa.");
    expect(r.text).not.toMatch(/María|Cruz/);
    expect(r.hits.length).toBeGreaterThan(0);
  });

  it("removes titled single names", () => {
    const r = scrubNames("Mrs. Garcia reported the fire to Don Baca.");
    expect(r.text).not.toMatch(/Garcia|Baca/);
  });

  it("removes name followed by an age", () => {
    const r = scrubNames("Victim Lopez, 34, died at the scene.");
    expect(r.text).not.toContain("Lopez");
  });

  it("removes middle initials", () => {
    const r = scrubNames("A man identified as Robert J. Allen died.");
    expect(r.text).not.toMatch(/Robert|Allen/);
  });

  it("keeps place and institution names", () => {
    const s = "A fatal crash was reported in Rio Rancho near Old Town in Bernalillo County, New Mexico.";
    const r = scrubNames(s);
    expect(r.text).toBe(s);
    expect(r.hits).toHaveLength(0);
  });

  it("keeps ordinary neutral summaries untouched", () => {
    const s = "A house fire on a Barelas street was reported to have claimed one life.";
    expect(scrubNames(s).text).toBe(s);
  });

  it("keeps sentence-initial words and months", () => {
    const s = "Police said the accident happened in March near Albuquerque.";
    expect(scrubNames(s).text).toBe(s);
  });

  it("handles empty input", () => {
    expect(scrubNames(null).text).toBe("");
    expect(scrubNames("").hits).toEqual([]);
  });

  it("never leaves a name in any seed summary", async () => {
    const { SEED_RECORDS } = await import("@/data/seed-records");
    for (const r of SEED_RECORDS) {
      expect(scrubNames(r.summary).hits).toEqual([]);
    }
  });
});
