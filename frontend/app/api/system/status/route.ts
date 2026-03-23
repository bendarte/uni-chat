import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
const BACKEND_API_KEY = process.env.BACKEND_API_KEY ?? "";

export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/api/system/status`, {
      headers: { "X-API-Key": BACKEND_API_KEY },
      next: { revalidate: 30 },
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("system status proxy error:", err);
    return NextResponse.json({ status: "unavailable" }, { status: 503 });
  }
}
