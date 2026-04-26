import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { evaluate } from "../api/endpoints";
import type { EvaluationListItem, EvaluationOut } from "../api/types";

const HISTORY_KEY = "sourcemd_history";
const EVAL_KEY = (id: string) => `sourcemd_eval_${id}`;

export function saveEvaluation(result: EvaluationOut): void {
  // Store full result
  localStorage.setItem(EVAL_KEY(result.id), JSON.stringify(result));
  // Update history index
  const existing: EvaluationListItem[] = getHistoryIndex();
  const item: EvaluationListItem = {
    id: result.id,
    question: result.question,
    trust_score: result.trust_score,
    created_at: result.created_at,
  };
  localStorage.setItem(HISTORY_KEY, JSON.stringify([item, ...existing]));
}

export function getHistoryIndex(): EvaluationListItem[] {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

export function getEvaluationById(id: string): EvaluationOut | null {
  try {
    const raw = localStorage.getItem(EVAL_KEY(id));
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function deleteEvaluationById(id: string): void {
  localStorage.removeItem(EVAL_KEY(id));
  localStorage.removeItem(`sourcemd_chat_${id}`);
  const updated = getHistoryIndex().filter((item) => item.id !== id);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(updated));
}

export function renameEvaluation(id: string, name: string): void {
  const history = getHistoryIndex().map((item) =>
    item.id === id ? { ...item, question: name } : item
  );
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
  // Also update the full eval
  const full = getEvaluationById(id);
  if (full) {
    localStorage.setItem(EVAL_KEY(id), JSON.stringify({ ...full, question: name }));
  }
}

export default function EvaluatePage() {
  const navigate = useNavigate();
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await evaluate(question, answer);
      saveEvaluation(result);
      navigate(`/results/${result.id}`, { state: result });
    } catch (err) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Failed to run evaluation";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100 mb-2">
        Evaluate an AI medical answer
      </h1>
      <p className="text-slate-600 dark:text-slate-400 mb-6">
        Paste a question and an AI-generated answer. SourceMD will extract the
        factual claims, retrieve relevant passages from real medical guidelines,
        and return a trust score with a corrected, source-backed version.
      </p>
      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
            Question
          </label>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={3}
            required
            minLength={3}
            className="w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 p-3 focus:outline-none focus:ring-2 focus:ring-slate-400 dark:focus:ring-slate-500 placeholder:text-slate-400 dark:placeholder:text-slate-500"
            placeholder="What is the first-line drug for type 2 diabetes?"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
            AI answer
          </label>
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            rows={8}
            required
            minLength={3}
            className="w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 p-3 focus:outline-none focus:ring-2 focus:ring-slate-400 dark:focus:ring-slate-500 placeholder:text-slate-400 dark:placeholder:text-slate-500"
            placeholder="Metformin is first-line; however, insulin is always required within 6 months."
          />
        </div>
        {error && (
          <p className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded p-2">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 rounded-md bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 hover:bg-slate-700 dark:hover:bg-white disabled:opacity-60 font-medium"
        >
          {loading ? "Evaluating…" : "Run evaluation"}
        </button>
      </form>
    </div>
  );
}
