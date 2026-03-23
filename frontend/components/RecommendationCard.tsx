interface Explanation {
  bullets: string[];
  source_id: string;
  matched_fields: string[];
}

interface Recommendation {
  id?: string;
  name: string;
  university: string;
  city: string;
  level: string;
  language: string;
  study_pace?: string;
  source_url?: string;
  explanation?: Explanation;
}

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
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm transition hover:shadow-md">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <span className="mr-2 text-xs font-semibold text-indigo-500">
            #{index + 1}
          </span>
          {rec.source_url ? (
            <a
              href={rec.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-gray-900 hover:text-indigo-600 hover:underline"
            >
              {rec.name}
            </a>
          ) : (
            <span className="font-semibold text-gray-900">{rec.name}</span>
          )}
        </div>
      </div>

      <div className="mt-1 flex flex-wrap gap-1.5 text-xs">
        <span className="rounded bg-gray-100 px-2 py-0.5 text-gray-600">
          {rec.university}
        </span>
        <span className="rounded bg-gray-100 px-2 py-0.5 text-gray-600">
          {rec.city}
        </span>
        <span className="rounded bg-indigo-50 px-2 py-0.5 text-indigo-700">
          {level}
        </span>
        <span className="rounded bg-gray-100 px-2 py-0.5 text-gray-600">
          {lang}
        </span>
        {rec.study_pace && (
          <span className="rounded bg-gray-100 px-2 py-0.5 text-gray-600">
            {rec.study_pace}%
          </span>
        )}
      </div>

      {rec.explanation?.bullets && rec.explanation.bullets.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs text-gray-600">
          {rec.explanation.bullets.map((b, i) => (
            <li key={i} className="flex gap-1.5">
              <span className="mt-0.5 text-indigo-400">•</span>
              <span>{b}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
