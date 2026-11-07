import { NextRequest, NextResponse } from "next/server";
import { applicationPath, isPublicDemo, withoutBasePath } from "@/lib/deployment";

export function proxy(request: NextRequest) {
  const pathname = withoutBasePath(request.nextUrl.pathname);
  if (isPublicDemo() && (pathname === "/admin" || pathname.startsWith("/admin/"))) {
    return new NextResponse("Not found", { status: 404 });
  }
  if (isPublicDemo() && pathname === "/register") {
    return NextResponse.redirect(new URL(
      applicationPath("/login"), process.env.NEXT_PUBLIC_DEMO_ORIGIN || request.url,
    ));
  }
  const nonce = btoa(crypto.randomUUID());
  const production = process.env.NODE_ENV === "production";
  const localHost = ["127.0.0.1", "localhost", "::1"].includes(request.nextUrl.hostname);
  const enforceHttps = production && !localHost;
  const development = production ? "" : " 'unsafe-eval'";
  const csp = [
    "default-src 'self'",
    `script-src 'nonce-${nonce}' 'strict-dynamic'${development}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    enforceHttps ? "upgrade-insecure-requests" : "",
  ].filter(Boolean).join("; ");
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);
  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: [
    {
      source: "/((?!api|health|_next/static|_next/image|favicon.ico).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
