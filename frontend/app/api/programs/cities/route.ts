import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
const BACKEND_API_KEY = process.env.BACKEND_API_KEY ?? "";

export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/api/programs/cities`, {
      headers: { "X-API-Key": BACKEND_API_KEY },
      next: { revalidate: 3600 },
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("cities proxy error:", err);
    return NextResponse.json({ cities: [] }, { status: 503 });
  }
}
