import { NextRequest, NextResponse } from "next/server";
import { backendHeaders, backendUrl } from "@/lib/backend";

export async function POST(req: NextRequest) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { error: "Ogiltig förfrågan. Kontrollera din inmatning." },
      { status: 400 }
    );
  }

  try {
    const response = await fetch(backendUrl("/chat"), {
      method: "POST",
      headers: backendHeaders(true),
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(60_000),
      cache: "no-store",
    });

    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const error =
        response.status >= 500
          ? "UniChats AI-tjänst är tillfälligt otillgänglig. Försök igen senare."
          : typeof data?.detail === "string"
          ? data.detail
          : "Kunde inte behandla förfrågan. Kontrollera uppgifterna och försök igen.";

      return NextResponse.json({ error }, { status: response.status });
    }

    if (!data || typeof data !== "object") {
      return NextResponse.json(
        { error: "AI-tjänsten returnerade ett ogiltigt svar." },
        { status: 502 }
      );
    }

    return NextResponse.json(data, { status: 200 });
  } catch (error) {
    console.error("Chat backend request failed:", error);
    return NextResponse.json(
      { error: "UniChats AI-tjänst är tillfälligt otillgänglig. Försök igen senare." },
      { status: 503 }
    );
  }
}
