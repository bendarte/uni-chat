import { NextResponse } from "next/server";

import { backendHeaders, backendUrl } from "@/lib/backend";

export async function GET() {
  try {
    const res = await fetch(backendUrl("/api/system/status"), {
      headers: backendHeaders(),
      next: { revalidate: 30 },
      signal: AbortSignal.timeout(5_000),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("system status proxy error:", err);
    return NextResponse.json({ status: "unavailable" }, { status: 503 });
  }
}
