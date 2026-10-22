import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";

// Next 16 renamed middleware → proxy. Handles locale routing only;
// the waitlist gate is checked in the home page so API routes stay unaffected.
const intl = createMiddleware(routing);

export function proxy(request: Parameters<typeof intl>[0]) {
  return intl(request);
}

export const config = {
  matcher: ["/((?!api|preview|admin|_next|_vercel|.*\\..*).*)"],
};
