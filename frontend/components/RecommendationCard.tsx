import type { Recommendation } from "@/lib/types";

interface Props {
  rec: Recommendation;
  index: number;
}

const LEVEL_LABELS: Record<string, string> = {
  bachelor: "Kandidat",
  master: "Master",
  vocational: "Yrkesexamen",
  research: "Forskning",
};

const LANG_LABELS: Record<string, string> = {
  swedish: "Svenska",
  english: "Engelska",
};

export default function RecommendationCard({ rec, index }: Props) {
  const level = LEVEL_LABELS[rec.level] ?? rec.level;
  const lang = LANG_LABELS[rec.language] ?? rec.language;

  return (
    <article className="rounded-[28px] border border-[color:var(--line)] bg-[color:var(--card)] p-4 shadow-[var(--shadow)] transition duration-200 hover:-translate-y-0.5 hover:border-[color:var(--accent)]/25 sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex-1 space-y-2">
          <div
            className="text-[10px] uppercase tracking-[0.24em] text-[color:var(--ink-soft)]"
            style={{ fontFamily: "var(--font-mono), monospace" }}
          >
            Match #{index + 1}
          </div>
          {rec.source_url ? (
            <a
              href={rec.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-lg font-semibold text-[color:var(--ink)] transition hover:text-[color:var(--accent-strong)]"
            >
              {rec.name}
            </a>
          ) : (
            <span className="text-lg font-semibold text-[color:var(--ink)]">
              {rec.name}
            </span>
          )}
          <p className="text-sm text-[color:var(--ink-soft)]">
            {rec.university} {rec.city ? `· ${rec.city}` : ""}
          </p>
        </div>
        {rec.source_url && (
          <a
            href={rec.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex w-full justify-center rounded-full border border-[color:var(--line)] bg-white/80 px-3 py-2 text-xs font-medium text-[color:var(--accent-strong)] transition hover:border-[color:var(--accent)] hover:bg-[color:var(--accent-soft)] sm:w-auto sm:py-1"
          >
            Öppna
          </a>
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-2 text-xs">
        <span className="rounded-full bg-[color:var(--accent-soft)] px-3 py-1 text-[color:var(--accent-strong)]">
          {level}
        </span>
        <span className="rounded-full border border-[color:var(--line)] bg-white/75 px-3 py-1 text-[color:var(--ink-soft)]">
          {lang}
        </span>
        {rec.study_pace && (
          <span className="rounded-full border border-[color:var(--line)] bg-white/75 px-3 py-1 text-[color:var(--ink-soft)]">
            {rec.study_pace}%
          </span>
        )}
      </div>

      {rec.explanation && rec.explanation.length > 0 && (
        <ul className="mt-4 space-y-2 text-sm text-[color:var(--ink-soft)]">
          {rec.explanation.map((bullet, itemIndex) => (
            <li key={itemIndex} className="flex gap-2.5">
              <span className="mt-1 h-2.5 w-2.5 rounded-full bg-[color:var(--warm)]" />
              <span>{bullet}</span>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
