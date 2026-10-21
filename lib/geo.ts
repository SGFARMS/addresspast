import type { Bbox } from "./types";

const R = 6371008.8;

export function distanceM(aLat: number, aLng: number, bLat: number, bLng: number) {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(bLat - aLat);
  const dLng = toRad(bLng - aLng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

/** Polygon ring approximating a circle of radiusM around a point (GeoJSON order: lng,lat). */
export function circleRing(lng: number, lat: number, radiusM: number, steps = 48): [number, number][] {
  const ring: [number, number][] = [];
  const dLat = (radiusM / R) * (180 / Math.PI);
  const dLng = dLat / Math.cos((lat * Math.PI) / 180);
  for (let i = 0; i <= steps; i++) {
    const t = (i / steps) * 2 * Math.PI;
    ring.push([lng + dLng * Math.cos(t), lat + dLat * Math.sin(t)]);
  }
  return ring;
}

export function inBbox(lng: number, lat: number, [w, s, e, n]: Bbox) {
  return lng >= w && lng <= e && lat >= s && lat <= n;
}

export function clampBbox(b: Bbox, limit: Bbox): Bbox {
  return [Math.max(b[0], limit[0]), Math.max(b[1], limit[1]), Math.min(b[2], limit[2]), Math.min(b[3], limit[3])];
}

export function isInNM(lat: number, lng: number) {
  return lat >= 31.3 && lat <= 37.05 && lng >= -109.1 && lng <= -102.95;
}
