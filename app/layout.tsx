import type { ReactNode } from "react";
import "./globals.css";

// The real <html> lives in app/[locale]/layout.tsx so the lang attribute matches the locale.
export default function RootLayout({ children }: { children: ReactNode }) {
  return children;
}
