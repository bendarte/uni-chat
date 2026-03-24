import { NextResponse } from "next/server";

import { backendHeaders, backendUrl } from "@/lib/backend";

export async function GET() {
  try {
    const res = await fetch(backendUrl("/programs/cities"), {
      headers: backendHeaders(),
      next: { revalidate: 3600 },
      signal: AbortSignal.timeout(5_000),
    });
    const data = await res.json();
    const cities = Array.isArray(data)
      ? data
      : Array.isArray(data?.cities)
      ? data.cities
      : [];
    return NextResponse.json({ cities }, { status: res.status });
  } catch (err) {
    console.error("cities proxy error:", err);
    return NextResponse.json({ cities: [] }, { status: 503 });
  }
}
