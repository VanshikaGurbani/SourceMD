import { KeyboardEvent, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTheme } from "../context/ThemeContext";
import { deleteEvaluationById, getHistoryIndex, renameEvaluation } from "../pages/EvaluatePage";
import type { EvaluationListItem } from "../api/types";

// ── date grouping ─────────────────────────────────────────────────────────────

function isSameDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function groupByDate(items: EvaluationListItem[]) {
  const now = new Date();
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const today: EvaluationListItem[] = [];
  const yest: EvaluationListItem[] = [];
  const older: EvaluationListItem[] = [];
  for (const item of items) {
    const d = new Date(item.created_at);
    if (isSameDay(d, now)) today.push(item);
    else if (isSameDay(d, yesterday)) yest.push(item);
    else older.push(item);
  }
  return [
    ...(today.length ? [{ label: "Today", items: today }] : []),
    ...(yest.length ? [{ label: "Yesterday", items: yest }] : []),
    ...(older.length ? [{ label: "Older", items: older }] : []),
  ];
}

function trustDot(score: number) {
  if (score >= 70) return "bg-emerald-400";
  if (score >= 40) return "bg-amber-400";
  return "bg-red-400";
}

// ── icons ─────────────────────────────────────────────────────────────────────

function PencilIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
    </svg>
  );
}
function TrashIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
    </svg>
  );
}
function SunIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707M17.657 17.657l-.707-.707M6.343 6.343l-.707-.707M12 8a4 4 0 100 8 4 4 0 000-8z" />
    </svg>
  );
}
function MoonIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
    </svg>
  );
}

// ── component ─────────────────────────────────────────────────────────────────

export default function EvalSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const [history, setHistory] = useState<EvaluationListItem[]>([]);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);

  const location = useLocation();
  const navigate = useNavigate();
  const { theme, toggle: toggleTheme } = useTheme();

  const match = location.pathname.match(/^\/results\/(.+)$/);
  const activeId = match ? match[1] : null;

  // Reload history from localStorage whenever route changes
  useEffect(() => {
    setHistory(getHistoryIndex());
  }, [location.pathname]);

  useEffect(() => {
    if (renamingId !== null) renameInputRef.current?.focus();
  }, [renamingId]);

  function startRename(item: EvaluationListItem) {
    setRenamingId(item.id);
    setRenameValue(item.question);
    setDeletingId(null);
  }

  function commitRename(id: string) {
    const trimmed = renameValue.trim();
    if (trimmed) {
      renameEvaluation(id, trimmed);
      setHistory(getHistoryIndex());
    }
    setRenamingId(null);
  }

  function handleRenameKey(e: KeyboardEvent, id: string) {
    if (e.key === "Enter") commitRename(id);
    if (e.key === "Escape") setRenamingId(null);
  }

  function confirmDelete(id: string) {
    deleteEvaluationById(id);
    setHistory(getHistoryIndex());
    setDeletingId(null);
    if (activeId === id) navigate("/evaluate");
  }

  const groups = groupByDate(history);

  return (
    <aside className="w-64 shrink-0 h-screen bg-slate-900 flex flex-col border-r border-slate-700/60">
      {/* Header */}
      <div className="p-4 border-b border-slate-700/60">
        <Link to="/evaluate" onClick={onNavigate} className="text-base font-semibold text-white block mb-3 tracking-tight">
          SourceMD
        </Link>
        <Link
          to="/evaluate"
          onClick={onNavigate}
          className="flex items-center gap-2 w-full px-3 py-2 rounded-md bg-slate-800 hover:bg-slate-700 text-sm text-slate-200 transition-colors"
        >
          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New evaluation
        </Link>
      </div>

      {/* History list */}
      <nav className="flex-1 overflow-y-auto py-2">
        {groups.length === 0 ? (
          <p className="px-4 py-8 text-slate-500 text-xs text-center">No evaluations yet.</p>
        ) : (
          groups.map((group) => (
            <div key={group.label}>
              <p className="px-4 pt-4 pb-1.5 text-xs font-medium text-slate-500 uppercase tracking-wider">
                {group.label}
              </p>
              {group.items.map((item) => {
                const isActive = activeId === item.id;
                const isDeleting = deletingId === item.id;
                const isRenaming = renamingId === item.id;

                return (
                  <div key={item.id} className="group mx-2 mb-0.5">
                    {isDeleting ? (
                      <div className="flex items-center gap-1.5 px-3 py-2 rounded-md bg-red-900/40 border border-red-700/50 text-xs text-red-300">
                        <span className="flex-1">Delete this?</span>
                        <button onClick={() => confirmDelete(item.id)} className="text-red-300 hover:text-white font-medium">Yes</button>
                        <span className="text-red-600">·</span>
                        <button onClick={() => setDeletingId(null)} className="text-slate-400 hover:text-white">No</button>
                      </div>
                    ) : isRenaming ? (
                      <div className="px-2 py-1">
                        <input
                          ref={renameInputRef}
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          onBlur={() => commitRename(item.id)}
                          onKeyDown={(e) => handleRenameKey(e, item.id)}
                          className="w-full rounded px-2 py-1.5 text-xs bg-slate-700 text-white border border-slate-500 focus:outline-none focus:border-slate-400"
                          placeholder="Rename…"
                        />
                        <p className="text-slate-500 text-xs mt-0.5 px-1">Enter to save · Esc to cancel</p>
                      </div>
                    ) : (
                      <div className={`flex items-start rounded-md transition-colors ${isActive ? "bg-slate-700" : "hover:bg-slate-800"}`}>
                        <Link
                          to={`/results/${item.id}`}
                          onClick={onNavigate}
                          className="flex items-start gap-2.5 flex-1 min-w-0 px-3 py-2 text-sm"
                        >
                          <span className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${trustDot(item.trust_score)}`} />
                          <span className={`truncate leading-snug ${isActive ? "text-white" : "text-slate-300 group-hover:text-white"}`}>
                            {item.question.length > 52 ? `${item.question.slice(0, 52)}…` : item.question}
                          </span>
                        </Link>
                        <div className="flex items-center gap-0.5 pr-1.5 pt-2 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                          <button
                            type="button"
                            onClick={() => startRename(item)}
                            title="Rename"
                            className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-600 transition-colors"
                          >
                            <PencilIcon />
                          </button>
                          <button
                            type="button"
                            onClick={() => { setDeletingId(item.id); setRenamingId(null); }}
                            title="Delete"
                            className="p-1 rounded text-slate-400 hover:text-red-400 hover:bg-slate-600 transition-colors"
                          >
                            <TrashIcon />
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))
        )}
      </nav>

      {/* Footer — theme toggle only */}
      <div className="p-3 border-t border-slate-700/60">
        <button
          type="button"
          onClick={toggleTheme}
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          className="p-2 rounded-md text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
        >
          {theme === "dark" ? <SunIcon /> : <MoonIcon />}
        </button>
      </div>
    </aside>
  );
}
