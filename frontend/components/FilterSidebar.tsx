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
    <aside className="w-64 shrink-0 space-y-6 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
        Filter
      </h2>

      <div>
        <label className="mb-1 block text-xs font-medium text-gray-600">
          Nivå
        </label>
        <select
          className="w-full rounded border border-gray-200 bg-gray-50 px-2 py-1.5 text-sm"
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
        <label className="mb-1 block text-xs font-medium text-gray-600">
          Språk
        </label>
        <select
          className="w-full rounded border border-gray-200 bg-gray-50 px-2 py-1.5 text-sm"
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
        <label className="mb-1 block text-xs font-medium text-gray-600">
          Studietakt
        </label>
        <select
          className="w-full rounded border border-gray-200 bg-gray-50 px-2 py-1.5 text-sm"
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
          <label className="mb-1 block text-xs font-medium text-gray-600">
            Stad
          </label>
          <div className="max-h-48 space-y-1 overflow-y-auto">
            {cities.map((city) => (
              <label
                key={city}
                className="flex cursor-pointer items-center gap-2 text-sm"
              >
                <input
                  type="checkbox"
                  className="rounded border-gray-300"
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
          className="w-full rounded border border-gray-200 py-1 text-xs text-gray-500 hover:bg-gray-50"
        >
          Rensa filter
        </button>
      )}
    </aside>
  );
}
