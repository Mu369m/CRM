import { NextRequest, NextResponse } from "next/server";

const tenantIdFromHost = (host: string): string | null => {
  const firstLabel = host.split(":", 1)[0].split(".", 1)[0];
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(firstLabel) ? firstLabel : null;
};

export function middleware(request: NextRequest) {
  const host = request.headers.get("host")?.toLowerCase().split(":", 1)[0] ?? "";
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-tenant-host", host);
  const tenantId = request.headers.get("x-tenant-id") ?? tenantIdFromHost(host);
  if (tenantId) requestHeaders.set("x-tenant-id", tenantId);
  return NextResponse.next({ request: { headers: requestHeaders } });
}

export const config = { matcher: ["/api/:path*", "/trader/:path*", "/trader-cabinet/:path*", "/admin/:path*", "/owner/:path*"] };