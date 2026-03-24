import { NextRequest, NextResponse } from "next/server";

import { backendHeaders, backendUrl } from "@/lib/backend";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const res = await fetch(backendUrl("/chat"), {
      method: "POST",
      headers: backendHeaders(true),
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(60_000),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("chat proxy error:", err);
    return NextResponse.json(
      { error: "Kunde inte nå servern. Försök igen." },
      { status: 503 }
    );
  }
}
