"use client";

import { useEffect, useState } from "react";

export interface Filters {
  level: string;
  cities: string[];
  language: string;
  study_pace: string;
}

interface Props {
  filters: Filters;
  onChange: (filters: Filters) => void;
}

const LEVELS = [
  { value: "", label: "Alla nivåer" },
  { value: "bachelor", label: "Kandidat" },
  { value: "master", label: "Master" },
  { value: "vocational", label: "Yrkesexamen" },
];

const LANGUAGES = [
  { value: "", label: "Alla språk" },
  { value: "swedish", label: "Svenska" },
  { value: "english", label: "Engelska" },
];

const STUDY_PACES = [
  { value: "", label: "Alla" },
  { value: "100", label: "Heltid (100%)" },
  { value: "75", label: "75%" },
  { value: "50", label: "Halvfart (50%)" },
  { value: "25", label: "25%" },
];

export default function FilterSidebar({ filters, onChange }: Props) {
  const [cities, setCities] = useState<string[]>([]);

  useEffect(() => {
    fetch("/api/programs/cities")
      .then((r) => r.json())
      .then((d) => setCities(d.cities ?? []))
      .catch(() => {});
  }, []);

  function set(key: keyof Filters, value: string | string[]) {
    onChange({ ...filters, [key]: value });
  }

  function toggleCity(city: string) {
    const next = filters.cities.includes(city)
      ? filters.cities.filter((c) => c !== city)
      : [...filters.cities, city];
    set("cities", next);
  }

  return (
    <aside className="w-full max-w-[19rem] shrink-0 space-y-6 rounded-[28px] border border-[color:var(--line)] bg-[color:var(--card)] p-5 shadow-[var(--shadow)]">
      <div className="space-y-2">
        <p
          className="text-[10px] uppercase tracking-[0.24em] text-[color:var(--ink-soft)]"
          style={{ fontFamily: "var(--font-mono), monospace" }}
        >
          Filter
        </p>
        <h2 className="text-lg font-semibold text-[color:var(--ink)]">
          Förfina träffarna
        </h2>
        <p className="text-sm text-[color:var(--ink-soft)]">
          Välj stad, nivå, språk och studietakt för att styra rekommendationerna.
        </p>
      </div>

      <div>
        <label className="mb-2 block text-xs font-medium uppercase tracking-[0.18em] text-[color:var(--ink-soft)]">
          Nivå
        </label>
        <select
          className="w-full rounded-2xl border border-[color:var(--line)] bg-white/80 px-3 py-2.5 text-sm text-[color:var(--ink)] outline-none transition focus:border-[color:var(--accent)]"
          value={filters.level}
          onChange={(e) => set("level", e.target.value)}
        >
          {LEVELS.map((l) => (
            <option key={l.value} value={l.value}>
              {l.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="mb-2 block text-xs font-medium uppercase tracking-[0.18em] text-[color:var(--ink-soft)]">
          Språk
        </label>
        <select
          className="w-full rounded-2xl border border-[color:var(--line)] bg-white/80 px-3 py-2.5 text-sm text-[color:var(--ink)] outline-none transition focus:border-[color:var(--accent)]"
          value={filters.language}
          onChange={(e) => set("language", e.target.value)}
        >
          {LANGUAGES.map((l) => (
            <option key={l.value} value={l.value}>
              {l.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="mb-2 block text-xs font-medium uppercase tracking-[0.18em] text-[color:var(--ink-soft)]">
          Studietakt
        </label>
        <select
          className="w-full rounded-2xl border border-[color:var(--line)] bg-white/80 px-3 py-2.5 text-sm text-[color:var(--ink)] outline-none transition focus:border-[color:var(--accent)]"
          value={filters.study_pace}
          onChange={(e) => set("study_pace", e.target.value)}
        >
          {STUDY_PACES.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
      </div>

      {cities.length > 0 && (
        <div>
          <label className="mb-2 block text-xs font-medium uppercase tracking-[0.18em] text-[color:var(--ink-soft)]">
            Stad
          </label>
          <div className="max-h-56 space-y-2 overflow-y-auto pr-1">
            {cities.map((city) => (
              <label
                key={city}
                className="flex cursor-pointer items-center gap-3 rounded-2xl border border-transparent bg-white/70 px-3 py-2 text-sm text-[color:var(--ink)] transition hover:border-[color:var(--line)]"
              >
                <input
                  type="checkbox"
                  className="rounded border-[color:var(--line)] text-[color:var(--accent)] focus:ring-[color:var(--accent)]"
                  checked={filters.cities.includes(city)}
                  onChange={() => toggleCity(city)}
                />
                {city}
              </label>
            ))}
          </div>
        </div>
      )}

      {(filters.level ||
        filters.language ||
        filters.study_pace ||
        filters.cities.length > 0) && (
        <button
          onClick={() =>
            onChange({ level: "", cities: [], language: "", study_pace: "" })
          }
          className="w-full rounded-full border border-[color:var(--line)] bg-white/80 px-4 py-2 text-xs font-medium uppercase tracking-[0.18em] text-[color:var(--ink-soft)] transition hover:border-[color:var(--accent)] hover:text-[color:var(--accent-strong)]"
        >
          Rensa filter
        </button>
      )}
    </aside>
  );
}
