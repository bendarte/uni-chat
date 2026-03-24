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
  explanation?: string[];
}

interface Message {
  role: "user" | "assistant";
  content: string;
  recommendations?: Recommendation[];
}

const SESSION_KEY = "uni-chat-session";
const QUICK_PROMPTS = [
  "Jag vill bli läkare",
  "Civilingenjör i Stockholm",
  "Master i datavetenskap",
  "Ekonomiutbildning på engelska",
];

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
  const activeFilterLabels = [
    filters.level ? `Nivå: ${filters.level}` : null,
    filters.language ? `Språk: ${filters.language}` : null,
    filters.study_pace ? `Takt: ${filters.study_pace}%` : null,
    filters.cities.length ? `Städer: ${filters.cities.join(", ")}` : null,
  ].filter((label): label is string => Boolean(label));

  return (
    <div className="min-h-screen">
      <header className="border-b border-[color:var(--line)] bg-[color:var(--surface-muted)] backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 lg:px-6">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-[18px] bg-[color:var(--accent)] text-lg font-semibold text-white shadow-lg shadow-[color:var(--accent)]/25">
              U
            </div>
            <div>
              <p
                className="text-[10px] uppercase tracking-[0.28em] text-[color:var(--ink-soft)]"
                style={{ fontFamily: "var(--font-mono), monospace" }}
              >
                UniChat
              </p>
              <h1 className="text-lg font-semibold text-[color:var(--ink)]">
                Hitta rätt utbildning med mer precision
              </h1>
            </div>
          </div>

          <div className="hidden items-center gap-2 lg:flex">
            <span className="rounded-full border border-[color:var(--line)] bg-white/70 px-3 py-1 text-xs text-[color:var(--ink-soft)]">
              277 program indexerade
            </span>
            <span className="rounded-full border border-[color:var(--line)] bg-white/70 px-3 py-1 text-xs text-[color:var(--ink-soft)]">
              Live filter + multi-turn
            </span>
          </div>

          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition lg:hidden ${
              hasActiveFilters
                ? "border-[color:var(--accent)] bg-[color:var(--accent-soft)] text-[color:var(--accent-strong)]"
                : "border-[color:var(--line)] bg-white/75 text-[color:var(--ink-soft)]"
            }`}
          >
            Filter {hasActiveFilters ? "•" : ""}
          </button>
        </div>
      </header>

      <div className="mx-auto flex max-w-7xl gap-6 px-4 py-6 lg:px-6">
        <div
          className={`${
            sidebarOpen ? "fixed inset-0 z-40 flex bg-black/25 backdrop-blur-sm" : "hidden"
          } lg:static lg:flex lg:bg-transparent lg:backdrop-blur-none`}
        >
          <button
            aria-label="Stäng filter"
            className="flex-1 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="relative z-10 ml-auto h-full p-4 lg:ml-0 lg:h-auto lg:p-0">
            <FilterSidebar filters={filters} onChange={setFilters} />
          </div>
        </div>

        <main className="flex min-h-[calc(100vh-126px)] flex-1 flex-col gap-5">
          <section className="overflow-hidden rounded-[32px] border border-[color:var(--line)] bg-[color:var(--card)] shadow-[var(--shadow)]">
            <div className="grid gap-6 p-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(280px,0.8fr)] lg:p-8">
              <div className="space-y-4">
                <p
                  className="text-[10px] uppercase tracking-[0.28em] text-[color:var(--ink-soft)]"
                  style={{ fontFamily: "var(--font-mono), monospace" }}
                >
                  Svensk utbildningssök
                </p>
                <h2 className="max-w-2xl text-3xl font-semibold leading-tight text-[color:var(--ink)] lg:text-4xl">
                  Få programförslag som känns relevanta, inte bara generiska.
                </h2>
                <p className="max-w-2xl text-sm leading-6 text-[color:var(--ink-soft)] lg:text-base">
                  Beskriv vad du vill bli, vilket ämne du dras till eller vilka
                  ramar du har. UniChat kombinerar fritext, filter och
                  uppföljningsfrågor för att hitta rätt utbildningar snabbare.
                </p>
                <div className="flex flex-wrap gap-2">
                  {activeFilterLabels.length > 0 ? (
                    activeFilterLabels.map((label) => (
                      <span
                        key={label}
                        className="rounded-full border border-[color:var(--line)] bg-white/80 px-3 py-1 text-xs text-[color:var(--ink-soft)]"
                      >
                        {label}
                      </span>
                    ))
                  ) : (
                    <span className="rounded-full bg-[color:var(--accent-soft)] px-3 py-1 text-xs text-[color:var(--accent-strong)]">
                      Inga filter aktiva ännu
                    </span>
                  )}
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
                <div className="rounded-[24px] border border-[color:var(--line)] bg-white/80 p-4">
                  <p
                    className="text-[10px] uppercase tracking-[0.22em] text-[color:var(--ink-soft)]"
                    style={{ fontFamily: "var(--font-mono), monospace" }}
                  >
                    Styrka
                  </p>
                  <p className="mt-2 text-lg font-semibold text-[color:var(--ink)]">
                    Fritext först
                  </p>
                  <p className="mt-1 text-sm text-[color:var(--ink-soft)]">
                    Börja med ett mål eller ett ämne. Lägg till filter först när
                    du vill snäva in.
                  </p>
                </div>
                <div className="rounded-[24px] border border-[color:var(--line)] bg-white/80 p-4">
                  <p
                    className="text-[10px] uppercase tracking-[0.22em] text-[color:var(--ink-soft)]"
                    style={{ fontFamily: "var(--font-mono), monospace" }}
                  >
                    Passar bra för
                  </p>
                  <p className="mt-2 text-lg font-semibold text-[color:var(--ink)]">
                    Snabba jämförelser
                  </p>
                  <p className="mt-1 text-sm text-[color:var(--ink-soft)]">
                    Filtrera på stad, språk och nivå utan att tappa bort
                    ämnesrelevansen.
                  </p>
                </div>
              </div>
            </div>
          </section>

          <section className="flex min-h-[calc(100vh-320px)] flex-1 flex-col overflow-hidden rounded-[32px] border border-[color:var(--line)] bg-[color:var(--card)] shadow-[var(--shadow)]">
            <div className="border-b border-[color:var(--line)] px-4 py-4 lg:px-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-lg font-semibold text-[color:var(--ink)]">
                    Konversation
                  </h3>
                  <p className="text-sm text-[color:var(--ink-soft)]">
                    Ställ en fråga och förfina stegvis tills träffbilden känns rätt.
                  </p>
                </div>
                <div
                  className="rounded-full border border-[color:var(--line)] bg-white/80 px-3 py-1 text-[10px] uppercase tracking-[0.22em] text-[color:var(--ink-soft)]"
                  style={{ fontFamily: "var(--font-mono), monospace" }}
                >
                  {messages.length > 0 ? `${messages.length} meddelanden` : "Redo"}
                </div>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto px-4 py-5 lg:px-6">
              <div className="mx-auto max-w-3xl space-y-4">
                {messages.length === 0 && (
                  <div className="rounded-[28px] border border-dashed border-[color:var(--line)] bg-white/60 p-6 text-center lg:p-10">
                    <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-[22px] bg-[color:var(--accent-soft)] text-2xl text-[color:var(--accent-strong)] shadow-lg shadow-[color:var(--accent)]/10">
                      U
                    </div>
                    <h2 className="mt-5 text-2xl font-semibold text-[color:var(--ink)]">
                      Börja brett, snäva in snabbt.
                    </h2>
                    <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-[color:var(--ink-soft)]">
                      Skriv ett yrke, ett ämne, en stad eller en kombination. Du kan
                      vara vag i första frågan och låta filtren göra resten.
                    </p>
                    <div className="mt-6 grid gap-3 text-left sm:grid-cols-2">
                      {QUICK_PROMPTS.map((prompt) => (
                        <button
                          key={prompt}
                          onClick={() => setInput(prompt)}
                          className="rounded-[22px] border border-[color:var(--line)] bg-white/80 px-4 py-3 text-sm text-[color:var(--ink)] transition hover:border-[color:var(--accent)] hover:bg-[color:var(--accent-soft)]"
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                </div>
                )}

              {messages.map((msg, i) => (
                <div key={i}>
                  <ChatMessage role={msg.role} content={msg.content} />
                  {msg.recommendations && msg.recommendations.length > 0 && (
                    <div className="mt-3 space-y-3">
                      {msg.recommendations.map((rec, j) => (
                        <RecommendationCard key={j} rec={rec} index={j} />
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {loading && (
                <div className="flex justify-start">
                  <div className="rounded-[24px] rounded-bl-md border border-[color:var(--line)] bg-white/90 px-4 py-3 shadow-[0_18px_45px_rgba(31,42,42,0.08)]">
                    <div className="flex gap-1.5">
                      {[0, 1, 2].map((i) => (
                        <span
                          key={i}
                          className="h-2.5 w-2.5 animate-bounce rounded-full bg-[color:var(--accent)]"
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

            <div className="border-t border-[color:var(--line)] bg-[color:var(--surface-strong)] px-4 py-4 lg:px-6">
              <div className="mx-auto flex max-w-3xl items-end gap-3 rounded-[28px] border border-[color:var(--line)] bg-white/90 p-3 shadow-[0_16px_40px_rgba(31,42,42,0.08)]">
                <textarea
                  ref={inputRef}
                  rows={1}
                  className="flex-1 resize-none bg-transparent px-3 py-2 text-sm text-[color:var(--ink)] outline-none placeholder:text-[color:var(--ink-soft)]"
                  placeholder="Vad vill du bli, eller vad är du intresserad av?"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  style={{ maxHeight: "6rem" }}
                />
                <button
                  onClick={send}
                  disabled={!input.trim() || loading}
                  className="rounded-full bg-[color:var(--accent)] px-5 py-3 text-sm font-medium text-white transition hover:bg-[color:var(--accent-strong)] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Skicka
                </button>
              </div>
              <p className="mt-2 text-center text-xs text-[color:var(--ink-soft)]">
                Enter för att skicka · Shift+Enter för ny rad
              </p>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
