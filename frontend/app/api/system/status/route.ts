import { NextResponse } from "next/server";
import { backendHeaders, backendUrl } from "@/lib/backend";

// This endpoint must reflect the current state, not a cached successful response.
export const dynamic = "force-dynamic";

const noStore = { "Cache-Control": "no-store" };

export async function GET() {
  try {
    // /ready validates PostgreSQL, Redis and Qdrant without returning their
    // internal connection details to the public frontend.
    const readiness = await fetch(backendUrl("/ready"), {
      cache: "no-store",
      signal: AbortSignal.timeout(8_000),
    });
    if (!readiness.ok) {
      return NextResponse.json(
        { status: "unavailable", ready: false },
        { status: 503, headers: noStore }
      );
    }

    const response = await fetch(backendUrl("/api/system/status"), {
      headers: backendHeaders(),
      cache: "no-store",
      signal: AbortSignal.timeout(5_000),
    });

    if (!response.ok) {
      return NextResponse.json(
        { status: "unavailable", ready: false },
        { status: 503, headers: noStore }
      );
    }

    const data = await response.json();
    if (!data || data.status !== "ok") {
      return NextResponse.json(
        { status: "unavailable", ready: false },
        { status: 503, headers: noStore }
      );
    }

    return NextResponse.json(
      { ...data, ready: true },
      { status: 200, headers: noStore }
    );
  } catch (error) {
    console.error("Backend availability check failed:", error);
    return NextResponse.json(
      { status: "unavailable", ready: false },
      { status: 503, headers: noStore }
    );
  }
}
