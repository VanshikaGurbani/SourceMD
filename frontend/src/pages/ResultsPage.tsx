import { FormEvent, useEffect, useRef, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import { getEvaluation, sendFollowUp } from "../api/endpoints";
import type { EvaluationOut } from "../api/types";
import ClaimRow from "../components/ClaimRow";
import TrustGauge from "../components/TrustGauge";

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
}

const chatKey = (id: string | number) => `sourcemd_chat_${id}`;

const accentColors = {
  green: "text-emerald-600 dark:text-emerald-400",
  amber: "text-amber-500 dark:text-amber-400",
  red: "text-red-500 dark:text-red-400",
  neutral: "text-slate-900 dark:text-slate-100",
};

function hallucinationAccent(rate: number) {
  if (rate <= 0.2) return "green" as const;
  if (rate <= 0.5) return "amber" as const;
  return "red" as const;
}
function coverageAccent(cov: number) {
  if (cov >= 0.7) return "green" as const;
  if (cov >= 0.4) return "amber" as const;
  return "red" as const;
}

export default function ResultsPage() {
  const { id } = useParams();
  const location = useLocation();
  const prefetched = (location.state as EvaluationOut | null) || null;
  const [data, setData] = useState<EvaluationOut | null>(prefetched);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (prefetched || !id) return;
    getEvaluation(Number(id))
      .then(setData)
      .catch(() => setError("Unable to load this evaluation. Login may be required."));
  }, [id, prefetched]);

  // Restore persisted chat
  useEffect(() => {
    if (!id) return;
    try {
      const saved = localStorage.getItem(chatKey(id));
      if (saved) setMessages(JSON.parse(saved));
    } catch { /* ignore */ }
  }, [id]);

  // Persist chat on change
  useEffect(() => {
    if (!id || messages.length === 0) return;
    localStorage.setItem(chatKey(id), JSON.stringify(messages));
  }, [messages, id]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleFollowUp(question: string) {
    if (!data || !question.trim()) return;
    const q = question.trim();
    setChatInput("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setChatLoading(true);
    try {
      const res = await sendFollowUp(data.id, q);
      setMessages((m) => [...m, { role: "assistant", text: res.answer }]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", text: "Sorry, could not get an answer. Please try again." }]);
    } finally {
      setChatLoading(false);
    }
  }

  function handleChatSubmit(e: FormEvent) {
    e.preventDefault();
    handleFollowUp(chatInput);
  }

  function handleShare() {
    navigator.clipboard.writeText(window.location.href).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  if (error) return <p className="text-red-600 dark:text-red-400">{error}</p>;
  if (!data) return <p className="text-slate-600 dark:text-slate-400">Loading report…</p>;

  const hallucinationRate = data.ragas_faithfulness;
  const sourceCoverage = data.ragas_context_precision;
  const followUps = data.follow_up_questions ?? [];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Trust report</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1 text-sm">
            Evaluated {new Date(data.created_at).toLocaleString()}
          </p>
        </div>
        <button
          type="button"
          onClick={handleShare}
          title="Copy link to clipboard"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors shrink-0"
        >
          {copied ? (
            <>
              <svg className="w-4 h-4 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Copied!
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
              </svg>
              Share
            </>
          )}
        </button>
      </div>

      {/* Score row */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-1 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
          <TrustGauge score={data.trust_score} />
        </div>
        <div className="md:col-span-2 grid grid-cols-2 gap-4">
          <StatCard
            label="Hallucination Rate"
            value={hallucinationRate === null ? "n/a" : `${Math.round(hallucinationRate * 100)}%`}
            subtitle="lower is better"
            accent={hallucinationRate === null ? "neutral" : hallucinationAccent(hallucinationRate)}
          />
          <StatCard
            label="Source Coverage"
            value={sourceCoverage === null ? "n/a" : `${Math.round(sourceCoverage * 100)}%`}
            subtitle="higher is better"
            accent={sourceCoverage === null ? "neutral" : coverageAccent(sourceCoverage)}
          />
          <div className="col-span-2 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
            <h3 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase mb-1">Question</h3>
            <p className="text-slate-900 dark:text-slate-100">{data.question}</p>
          </div>
        </div>
      </section>

      {/* Claim breakdown */}
      <section>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-3">
          Claim breakdown ({data.claims.length})
        </h2>
        <div className="space-y-3">
          {data.claims.map((c) => (
            <ClaimRow key={c.id} claim={c} />
          ))}
        </div>
      </section>

      {/* Corrected answer */}
      <section>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-3">
          Corrected, source-backed answer
        </h2>
        <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-4 space-y-4">
          <p className="whitespace-pre-wrap text-slate-800 dark:text-slate-200 leading-relaxed">
            {/* Strip any trailing "Sources: …" line the LLM appends — we render sources properly below */}
            {data.corrected_answer.replace(/\n*Sources:[\s\S]*$/i, "").trim()}
          </p>
          {/* Deduplicated sources from all claims */}
          {(() => {
            const seen = new Set<string>();
            const sources = data.claims.flatMap((c) => c.sources).filter((s) => {
              const key = `${s.doc}-${s.page}-${s.chunk}`;
              if (seen.has(key)) return false;
              seen.add(key);
              return true;
            });
            if (sources.length === 0) return null;
            return (
              <div className="border-t border-slate-200 dark:border-slate-700 pt-3">
                <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">
                  Sources
                </p>
                <ul className="space-y-1.5">
                  {sources.map((s, i) => {
                    const isWeb = s.chunk === -1;
                    const link = s.web_url || s.source_url || "";
                    return (
                      <li key={i} className="flex items-center gap-2 text-sm flex-wrap">
                        {link ? (
                          <a href={link} target="_blank" rel="noopener noreferrer"
                            className="font-medium text-blue-700 dark:text-blue-400 hover:underline">
                            {s.doc}
                          </a>
                        ) : (
                          <span className="font-medium text-slate-800 dark:text-slate-200">{s.doc}</span>
                        )}
                        {!isWeb && s.page > 0 && (
                          <span className="text-xs text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-700 px-1.5 py-0.5 rounded">
                            p.{s.page}
                          </span>
                        )}
                        {isWeb && (
                          <span className="text-xs text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/30 border border-emerald-200 dark:border-emerald-700 px-1.5 py-0.5 rounded font-medium">
                            ● live web
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })()}
        </div>
      </section>

      {/* Original answer */}
      <section>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-3">Original AI answer</h2>
        <div className="bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg p-4 whitespace-pre-wrap text-slate-700 dark:text-slate-300 text-sm">
          {data.ai_answer}
        </div>
      </section>

      {/* Follow-up chat */}
      <section>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-1">Ask a follow-up</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
          Chat about this evaluation — answers are grounded in the retrieved guideline context.
        </p>

        {followUps.length > 0 && messages.length === 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            {followUps.map((q, i) => (
              <button
                key={i}
                type="button"
                onClick={() => handleFollowUp(q)}
                className="text-sm px-3 py-1.5 rounded-full border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors text-left"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {messages.length > 0 && (
          <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-4 space-y-4 mb-4 max-h-96 overflow-y-auto">
            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-2.5 text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900"
                      : "bg-slate-100 dark:bg-slate-700 text-slate-800 dark:text-slate-200"
                  }`}
                >
                  {msg.text}
                </div>
              </div>
            ))}
            {chatLoading && (
              <div className="flex justify-start">
                <div className="bg-slate-100 dark:bg-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-500 dark:text-slate-400">
                  Thinking…
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
        )}

        <form onSubmit={handleChatSubmit} className="flex gap-2">
          <input
            type="text"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            placeholder="Ask about the sources, a specific claim, treatment details…"
            className="flex-1 rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400 dark:focus:ring-slate-500 placeholder:text-slate-400 dark:placeholder:text-slate-500"
            disabled={chatLoading}
          />
          <button
            type="submit"
            disabled={chatLoading || !chatInput.trim()}
            className="px-4 py-2 rounded-md bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 text-sm hover:bg-slate-700 dark:hover:bg-white disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </section>
    </div>
  );
}

function StatCard({
  label, value, subtitle, accent = "neutral",
}: {
  label: string;
  value: string;
  subtitle?: string;
  accent?: keyof typeof accentColors;
}) {
  return (
    <div className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
      <div className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">{label}</div>
      <div className={`text-2xl font-semibold mt-1 ${accentColors[accent]}`}>{value}</div>
      {subtitle && <div className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">{subtitle}</div>}
    </div>
  );
}
