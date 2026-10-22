import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Public_Sans, Source_Serif_4 } from "next/font/google";
import { siteConfig } from "@/site.config";

const body = Public_Sans({ subsets: ["latin"], variable: "--font-body", display: "swap" });
const display = Source_Serif_4({ subsets: ["latin"], variable: "--font-display", display: "swap" });

export const metadata: Metadata = {
  title: `Review · ${siteConfig.name}`,
  robots: { index: false, follow: false, nocache: true },
};

const themeScript = `try{var t=localStorage.getItem('ap-theme');var d=t?t==='dark':matchMedia('(prefers-color-scheme: dark)').matches;document.documentElement.classList.toggle('dark',d)}catch(e){}`;

/** Owner-only review area. English only, outside the locale routes. */
export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${body.variable} ${display.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-dvh bg-bg text-ink">{children}</body>
    </html>
  );
}
