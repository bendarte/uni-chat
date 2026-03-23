import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
const BACKEND_API_KEY = process.env.BACKEND_API_KEY ?? "";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const res = await fetch(`${BACKEND_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": BACKEND_API_KEY,
      },
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
