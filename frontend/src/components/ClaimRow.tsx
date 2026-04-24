import { useState } from "react";
import type { ClaimOut, SourceCitation } from "../api/types";
import VerdictChip from "./VerdictChip";

function SourceTag({ src }: { src: SourceCitation }) {
  const link = src.web_url || src.source_url || "";
  const isWeb = src.chunk === -1;

  return (
    <li className="text-sm bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded p-3">
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2 flex-wrap">
          {link ? (
            <a href={link} target="_blank" rel="noopener noreferrer"
              className="font-semibold text-blue-700 dark:text-blue-400 hover:underline transition-colors">
              {src.doc}
            </a>
          ) : (
            <span className="font-semibold text-slate-800 dark:text-slate-200">{src.doc}</span>
          )}

          {!isWeb && src.page > 0 && (
            <span className="text-xs text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-700 px-1.5 py-0.5 rounded">
              p.{src.page}
            </span>
          )}

          {isWeb && (
            <span className="text-xs text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/30 border border-emerald-200 dark:border-emerald-700 px-1.5 py-0.5 rounded font-medium">
              ● live web
            </span>
          )}

          {link && (
            <a href={link} target="_blank" rel="noopener noreferrer"
              className="text-xs text-blue-500 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 flex items-center gap-0.5">
              ↗ {isWeb ? "Open article" : "View guideline"}
            </a>
          )}
        </div>
        <span className="text-xs text-slate-400 dark:text-slate-500 ml-2 shrink-0">
          {(src.score * 100).toFixed(0)}% match
        </span>
      </div>
      <p className="text-slate-600 dark:text-slate-400 text-xs leading-relaxed line-clamp-5">{src.text}</p>
    </li>
  );
}

export default function ClaimRow({ claim }: { claim: ClaimOut }) {
  const [open, setOpen] = useState(false);
  const pct = Math.round(claim.confidence * 100);

  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-lg bg-white dark:bg-slate-800">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full text-left p-4 flex items-start gap-4 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors"
      >
        <div className="flex-1">
          <p className="text-slate-900 dark:text-slate-100">{claim.text}</p>
          <div className="mt-2 flex items-center gap-3 flex-wrap">
            <VerdictChip verdict={claim.verdict} />
            <div className="flex items-center gap-2">
              <div className="w-24 h-1.5 bg-slate-200 dark:bg-slate-600 rounded-full overflow-hidden">
                <div className="h-full bg-slate-700 dark:bg-slate-300" style={{ width: `${pct}%` }} />
              </div>
              <span className="text-xs text-slate-500 dark:text-slate-400">{pct}% confidence</span>
            </div>
            {claim.sources.length > 0 && (
              <span className="text-xs text-slate-400 dark:text-slate-500">
                {claim.sources.length} source{claim.sources.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>
        </div>
        <span className="text-slate-400 dark:text-slate-500 text-sm mt-1 shrink-0">
          {open ? "hide ▲" : "details ▼"}
        </span>
      </button>

      {open && (
        <div className="border-t border-slate-200 dark:border-slate-700 p-4 bg-slate-50 dark:bg-slate-900/50 space-y-4">
          {claim.rationale && (
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-1">
                Rationale
              </p>
              <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">{claim.rationale}</p>
            </div>
          )}
          <div>
            <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">
              Evidence sources
            </p>
            {claim.sources.length === 0 ? (
              <p className="text-sm text-slate-500 dark:text-slate-400 italic">No passages retrieved.</p>
            ) : (
              <ul className="space-y-2">
                {claim.sources.map((src, i) => (
                  <SourceTag key={`${src.doc}-${src.page}-${src.chunk}-${i}`} src={src} />
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
