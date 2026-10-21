import { cookies } from "next/headers";
import { setRequestLocale } from "next-intl/server";
import { siteConfig } from "@/site.config";
import { repo } from "@/lib/data";
import { AppShell } from "@/components/AppShell";
import { Waitlist } from "@/components/waitlist/Waitlist";

export default async function Home({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const preview = (await cookies()).get(siteConfig.previewCookie)?.value === "1";
  if (!siteConfig.launched && !preview) return <Waitlist />;
  return <AppShell demo={repo().kind === "demo"} />;
}
