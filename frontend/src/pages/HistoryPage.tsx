import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listHistory } from "../api/endpoints";
import type { EvaluationListItem } from "../api/types";

export default function HistoryPage() {
  const [rows, setRows] = useState<EvaluationListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listHistory()
      .then(setRows)
      .catch(() => setError("Failed to load history."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-slate-600 dark:text-slate-400">Loading history…</p>;
  if (error) return <p className="text-red-600 dark:text-red-400">{error}</p>;

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100 mb-4">Past evaluations</h1>
      {rows.length === 0 ? (
        <p className="text-slate-600 dark:text-slate-400">No evaluations yet.</p>
      ) : (
        <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-900 text-slate-600 dark:text-slate-400 text-left">
              <tr>
                <th className="px-4 py-2 font-medium">Question</th>
                <th className="px-4 py-2 font-medium w-32">Trust score</th>
                <th className="px-4 py-2 font-medium w-48">Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/50">
                  <td className="px-4 py-3">
                    <Link to={`/results/${r.id}`} className="text-slate-900 dark:text-slate-100 hover:underline">
                      {r.question.length > 80 ? `${r.question.slice(0, 80)}…` : r.question}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">
                    {r.trust_score.toFixed(0)}
                  </td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-400">
                    {new Date(r.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
