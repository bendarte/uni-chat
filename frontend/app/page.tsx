"use client";

import { useEffect, useRef, useState } from "react";
import ChatMessage from "@/components/ChatMessage";
import FilterSidebar, { Filters } from "@/components/FilterSidebar";
import RecommendationCard from "@/components/RecommendationCard";

interface Recommendation {
  id?: string;
  name: string;
  university: string;
  city: string;
  level: string;
  language: string;
  study_pace?: string;
  source_url?: string;
  explanation?: {
    bullets: string[];
    source_id: string;
    matched_fields: string[];
  };
}

interface Message {
  role: "user" | "assistant";
  content: string;
  recommendations?: Recommendation[];
}

const SESSION_KEY = "uni-chat-session";

function getSessionId(): string {
  if (typeof window === "undefined") return "";
  let sid = sessionStorage.getItem(SESSION_KEY);
  if (!sid) {
    sid = `session-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    sessionStorage.setItem(SESSION_KEY, sid);
  }
  return sid;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState<Filters>({
    level: "",
    cities: [],
    language: "",
    study_pace: "",
  });
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send() {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);

    const activeFilters: Record<string, string | string[]> = {};
    if (filters.level) activeFilters.level = filters.level;
    if (filters.cities.length) activeFilters.cities = filters.cities;
    if (filters.language) activeFilters.language = filters.language;
    if (filters.study_pace) activeFilters.study_pace = filters.study_pace;

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          session_id: getSessionId(),
          filters: Object.keys(activeFilters).length ? activeFilters : undefined,
        }),
      });

      const data = await res.json();
      const answer: string =
        data.answer ?? data.error ?? "Något gick fel. Försök igen.";
      const recs: Recommendation[] = data.recommendations ?? [];

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: answer, recommendations: recs },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Kunde inte nå servern. Kontrollera din anslutning.",
        },
      ]);
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  const hasActiveFilters =
    filters.level ||
    filters.language ||
    filters.study_pace ||
    filters.cities.length > 0;

  return (
    <div className="flex h-screen flex-col bg-gray-50">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-gray-200 bg-white px-4 py-3 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white font-bold text-sm">
            U
          </div>
          <h1 className="text-lg font-semibold text-gray-900">UniChat</h1>
          <span className="hidden text-xs text-gray-400 sm:block">
            Hitta rätt utbildning
          </span>
        </div>
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm transition lg:hidden ${
            hasActiveFilters
              ? "border-indigo-300 bg-indigo-50 text-indigo-700"
              : "border-gray-200 text-gray-600 hover:bg-gray-50"
          }`}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4h18M7 8h10M11 12h2" />
          </svg>
          Filter {hasActiveFilters && "•"}
        </button>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar — desktop always visible, mobile overlay */}
        <div
          className={`${
            sidebarOpen ? "flex" : "hidden"
          } lg:flex absolute lg:relative z-10 flex-col bg-gray-50 border-r border-gray-200 lg:border-0 p-4 h-full overflow-y-auto`}
          style={{ width: "17rem" }}
        >
          <FilterSidebar filters={filters} onChange={setFilters} />
        </div>

        {/* Chat area */}
        <main className="flex flex-1 flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto px-4 py-6">
            {messages.length === 0 && (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-100 text-2xl">
                  🎓
                </div>
                <h2 className="mb-2 text-xl font-semibold text-gray-800">
                  Hej! Jag hjälper dig hitta rätt utbildning.
                </h2>
                <p className="max-w-sm text-sm text-gray-500">
                  Berätta vad du vill bli, vad du är intresserad av, eller skriv
                  ett programnamn — så hittar vi alternativen.
                </p>
                <div className="mt-6 grid grid-cols-2 gap-2 text-xs">
                  {[
                    "Jag vill bli läkare",
                    "Civilingenjör i Stockholm",
                    "Master i datavetenskap",
                    "Ekonomiutbildning på engelska",
                  ].map((s) => (
                    <button
                      key={s}
                      onClick={() => setInput(s)}
                      className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-left text-gray-600 hover:border-indigo-300 hover:text-indigo-700 transition"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="mx-auto max-w-2xl space-y-4">
              {messages.map((msg, i) => (
                <div key={i}>
                  <ChatMessage role={msg.role} content={msg.content} />
                  {msg.recommendations && msg.recommendations.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {msg.recommendations.map((rec, j) => (
                        <RecommendationCard key={j} rec={rec} index={j} />
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {loading && (
                <div className="flex justify-start">
                  <div className="rounded-2xl rounded-bl-sm border border-gray-200 bg-white px-4 py-3 shadow-sm">
                    <div className="flex gap-1.5">
                      {[0, 1, 2].map((i) => (
                        <span
                          key={i}
                          className="h-2 w-2 animate-bounce rounded-full bg-indigo-400"
                          style={{ animationDelay: `${i * 150}ms` }}
                        />
                      ))}
                    </div>
                  </div>
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          </div>

          {/* Input */}
          <div className="border-t border-gray-200 bg-white px-4 py-3">
            <div className="mx-auto flex max-w-2xl items-end gap-2">
              <textarea
                ref={inputRef}
                rows={1}
                className="flex-1 resize-none rounded-xl border border-gray-200 px-4 py-2.5 text-sm focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
                placeholder="Vad vill du bli, eller vad är du intresserad av?"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                style={{ maxHeight: "6rem" }}
              />
              <button
                onClick={send}
                disabled={!input.trim() || loading}
                className="rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-40"
              >
                Skicka
              </button>
            </div>
            <p className="mt-1 text-center text-xs text-gray-400">
              Enter för att skicka · Shift+Enter för ny rad
            </p>
          </div>
        </main>
      </div>
    </div>
  );
}
