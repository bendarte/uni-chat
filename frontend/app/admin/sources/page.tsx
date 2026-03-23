"use client";

import { useEffect, useState } from "react";

interface SourceStat {
  source: string;
  total: number;
  valid: number;
  invalid: number;
  invalid_percent: number;
}

interface Stats {
  total_programs: number;
  valid_urls: number;
  invalid_urls: number;
  by_source: SourceStat[];
}

export default function AdminSourcesPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/sources/stats")
      .then((r) => r.json())
      .then((d) => setStats(d))
      .catch(() => setError("Kunde inte hämta statistik"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="mx-auto max-w-4xl">
        <h1 className="mb-6 text-2xl font-bold text-gray-900">
          Källstatistik
        </h1>

        {loading && (
          <p className="text-gray-500">Hämtar data...</p>
        )}

        {error && (
          <div className="rounded-lg bg-red-50 p-4 text-red-700">{error}</div>
        )}

        {stats && (
          <>
            <div className="mb-6 grid grid-cols-3 gap-4">
              <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                <p className="text-xs text-gray-500">Totalt antal program</p>
                <p className="mt-1 text-2xl font-bold text-gray-900">
                  {stats.total_programs}
                </p>
              </div>
              <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                <p className="text-xs text-gray-500">Giltiga URL:er</p>
                <p className="mt-1 text-2xl font-bold text-green-600">
                  {stats.valid_urls}
                </p>
              </div>
              <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
                <p className="text-xs text-gray-500">Ogiltiga URL:er</p>
                <p className="mt-1 text-2xl font-bold text-red-500">
                  {stats.invalid_urls}
                </p>
              </div>
            </div>

            <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
              <table className="w-full text-sm">
                <thead className="border-b border-gray-200 bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium text-gray-600">
                      Källa
                    </th>
                    <th className="px-4 py-3 text-right font-medium text-gray-600">
                      Totalt
                    </th>
                    <th className="px-4 py-3 text-right font-medium text-gray-600">
                      Giltiga
                    </th>
                    <th className="px-4 py-3 text-right font-medium text-gray-600">
                      Ogiltiga
                    </th>
                    <th className="px-4 py-3 text-right font-medium text-gray-600">
                      Fel %
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {(stats.by_source ?? []).map((row) => (
                    <tr key={row.source} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-gray-800">
                        {row.source || "—"}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-600">
                        {row.total}
                      </td>
                      <td className="px-4 py-3 text-right text-green-600">
                        {row.valid}
                      </td>
                      <td className="px-4 py-3 text-right text-red-500">
                        {row.invalid}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span
                          className={`rounded px-1.5 py-0.5 text-xs ${
                            row.invalid_percent > 20
                              ? "bg-red-100 text-red-700"
                              : row.invalid_percent > 5
                              ? "bg-yellow-100 text-yellow-700"
                              : "bg-green-100 text-green-700"
                          }`}
                        >
                          {row.invalid_percent.toFixed(1)}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
