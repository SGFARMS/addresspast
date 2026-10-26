import { expect, test } from "@playwright/test";

// Runs against demo data (fake seed records). Geocoder calls are mocked so tests are offline-safe.
const DOWNTOWN = { label: "Sample St, Albuquerque", lat: 35.0849, lng: -106.651, city: "Albuquerque", county: "Bernalillo", kind: "address" };
const EMPTY_SPOT = { label: "Quiet Rd, Belen", lat: 34.7, lng: -106.9, city: "Belen", county: "Valencia", kind: "address" };

test.describe("launched", () => {
  test("home page is open to everyone and indexable", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "What happened here?" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Join the waitlist" })).toHaveCount(0);
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /index/);
    await expect(page.locator('meta[name="robots"]')).not.toHaveAttribute("content", /noindex/);
    const robots = await (await page.request.get("/robots.txt")).text();
    expect(robots).toContain("Disallow: /admin");
    expect(robots).toContain("Sitemap:");
  });
});

test.describe("app (preview)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/preview?key=e2e-preview");
    await page.route("**/api/places/suggest**", async (route) => {
      const q = new URL(route.request().url()).searchParams.get("q") ?? "";
      const places = /quiet/i.test(q) ? [EMPTY_SPOT] : [DOWNTOWN];
      await route.fulfill({ json: { places } });
    });
  });

  test("search shows the free check with records", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "What happened here?" })).toBeVisible();
    await page.getByRole("combobox").fill("100 Sample St");
    await page.getByRole("option").first().click();
    await expect(page.getByText(/records? at this address/)).toBeVisible();
    await expect(page.getByText(/within 250 m/)).toBeVisible();
    await expect(page.getByText(/not a legal disclosure/).first()).toBeVisible();
  });

  test("free check with no records never says clean", async ({ page }) => {
    await page.getByRole("combobox").fill("Quiet Rd");
    await page.getByRole("option").first().click();
    await expect(page.getByText("No reported deaths found at or near this address in our records.")).toBeVisible();
    await expect(page.getByText(/clean|confirmed/i)).toHaveCount(0);
  });

  test("record card shows precision, confidence and sources", async ({ page }) => {
    await page.getByRole("combobox").fill("100 Sample St");
    await page.getByRole("option").first().click();
    await page.getByRole("button", { name: /1932/ }).click();
    await expect(page.getByText("Exact address").first()).toBeVisible();
    await expect(page.getByTitle(/Match confidence/)).toBeVisible();
    await expect(page.getByRole("link", { name: "View original newspaper page" }).first()).toBeVisible();
  });

  test("older-than-building note and removal request", async ({ page }) => {
    await page.getByRole("combobox").fill("100 Sample St");
    await page.getByRole("option").first().click();
    await expect(page.getByText("The building on this lot was built in 1948.", { exact: false })).toBeVisible();
    await page.getByRole("button", { name: /1932/ }).click();
    await expect(page.getByText(/may refer to an earlier building/)).toBeVisible();
    await page.getByRole("button", { name: "Report an error or request removal" }).click();
    await page.getByLabel("Your email").fill("e2e@example.com");
    await page.getByRole("button", { name: "Send request" }).click();
    await expect(page.getByText(/A person will review/)).toBeVisible();
  });

  test("natural deaths show by default and can be hidden", async ({ page }) => {
    await page.route("**/api/places/suggest**", (r) =>
      r.fulfill({ json: { places: [{ ...DOWNTOWN, label: "Belen spot", lat: 34.6616, lng: -106.7759, city: "Belen", county: "Valencia" }] } }),
    );
    await page.getByRole("combobox").fill("Belen spot");
    await page.getByRole("option").first().click();
    const hidden = page.getByText(/natural-cause records? hidden/);
    await expect(hidden).toHaveCount(0);
    await page.getByRole("button", { name: "Hide", exact: true }).click();
    await expect(hidden).toBeVisible();
    await page.getByRole("button", { name: "Show", exact: true }).click();
    await expect(hidden).toHaveCount(0);
  });

  test("plain-English question sets filter chips", async ({ page }) => {
    await page.getByRole("combobox").fill("fires in Belen before 1950");
    await page.getByRole("combobox").press("Enter");
    await expect(page.getByRole("button", { name: /Remove filter: Before 1950/ })).toBeVisible();
  });

  test("Spanish toggle", async ({ page }) => {
    await page.getByRole("link", { name: "Cambiar a español" }).click();
    await expect(page.getByRole("heading", { name: "¿Qué pasó aquí?" })).toBeVisible();
  });

  test("area page is aggregate only", async ({ page }) => {
    await page.goto("/nm/valencia/belen");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Belen");
    await expect(page.getByText("Records by decade").first()).toBeVisible();
  });
});

// Phase 2 / Phase 3 flows: specs are in place and skipped until those features ship.
test.skip("dispute form submits (Phase 2)", async () => {});
test.skip("checkout creates a report (Phase 3)", async () => {});

test.describe("admin review", () => {
  test("password gate and queue", async ({ page }) => {
    await page.goto("/admin");
    await page.getByLabel("Password").fill("wrong");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText("That password didn't work.")).toBeVisible();
    await page.getByLabel("Password").fill("e2e-admin");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("heading", { name: "Review queue" })).toBeVisible();
    await expect(page.getByText(/Demo data/)).toBeVisible();
    await page.getByRole("button", { name: /Held records/ }).click();
    await expect(page.getByText("Held records", { exact: false }).first()).toBeVisible();
  });

  test("queue API refuses without the cookie", async ({ request }) => {
    const r = await request.get("/api/admin/queue");
    expect(r.status()).toBe(401);
  });
});

test("town-level records list for a town badge", async ({ request }) => {
  const res = await request.get("/api/city?city=Belen&natural=0");
  expect(res.ok()).toBeTruthy();
  const j = await res.json();
  expect(j.items.map((i: { year: number }) => i.year)).toContain(2021); // demo: Belen 2021, town-level
  expect(j.items.every((i: { precision: string; cause: string }) => i.precision === "city" && i.cause !== "natural")).toBeTruthy();
  const withNatural = await (await request.get("/api/city?city=Belen&natural=1")).json();
  expect(withNatural.items.length).toBeGreaterThan(j.items.length);
  expect((await request.get("/api/city?city=x")).status()).toBe(400);
});
