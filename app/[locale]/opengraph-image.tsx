import { ImageResponse } from "next/og";
import { siteConfig } from "@/site.config";

// Link-preview image (1200x630) in the site's warm paper, ink and adobe palette.
// Rendered per locale so Spanish pages get the Spanish tagline.
export const alt = "AddressPast - New Mexico property history";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpengraphImage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const tagline = locale === "es" ? siteConfig.tagline.es : siteConfig.tagline.en;
  const host = new URL(siteConfig.url).host;

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "72px 80px",
          background: "#f6f2ea",
          color: "#29241f",
          borderLeft: "24px solid #a35f3d",
        }}
      >
        <div style={{ display: "flex", alignItems: "center" }}>
          <div
            style={{
              display: "flex",
              width: 52,
              height: 52,
              borderRadius: 12,
              background: "#3d6957",
              marginRight: 20,
            }}
          />
          <div style={{ display: "flex", fontSize: 34, fontWeight: 700, color: "#3d6957" }}>{siteConfig.name}</div>
        </div>
        <div style={{ display: "flex", fontSize: 76, fontWeight: 700, lineHeight: 1.1, letterSpacing: -1, maxWidth: 1000 }}>
          {tagline}
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 28, color: "#5b5249" }}>
          <div style={{ display: "flex" }}>{host}</div>
          <div style={{ display: "flex" }}>{siteConfig.state.name}</div>
        </div>
      </div>
    ),
    { ...size }
  );
}
