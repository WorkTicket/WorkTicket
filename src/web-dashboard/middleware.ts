import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const isPublicRoute = createRouteMatcher([
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/accept-invitation(.*)",
  "/maintenance(.*)",
]);

function applyCsp(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const cspHeader = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic' https://*.clerk.accounts.dev https://clerk.workticket.app`,
    `style-src 'self' 'nonce-${nonce}'`,
    "img-src 'self' https://img.clerk.com data: blob:",
    "font-src 'self'",
    "connect-src 'self' https://api.clerk.com https://*.clerk.accounts.dev https://clerk.workticket.app",
    "frame-src 'self' https://accounts.clerk.com https://*.clerk.accounts.dev",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join("; ");

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", cspHeader);
  return { response, nonce };
}

export default clerkMiddleware(async (auth, request) => {
  if (!isPublicRoute(request)) {
    await auth.protect();
  }

  const { response } = applyCsp(request);
  return response;
});

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
