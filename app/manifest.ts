import type { MetadataRoute } from "next";
import { siteConfig } from "@/site.config";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: `${siteConfig.name}: New Mexico property history`,
    short_name: siteConfig.name,
    description: siteConfig.tagline.en,
    start_url: "/",
    display: "standalone",
    background_color: "#f6f2ea",
    theme_color: "#3d6957",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
      { src: "/icon-maskable.svg", sizes: "any", type: "image/svg+xml", purpose: "maskable" },
    ],
  };
}
