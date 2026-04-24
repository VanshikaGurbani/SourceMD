import type { Verdict } from "../api/types";

const STYLES: Record<Verdict, string> = {
  SUPPORTED:    "bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-300 border-emerald-300 dark:border-emerald-700",
  UNSUPPORTED:  "bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300 border-amber-300 dark:border-amber-700",
  CONTRADICTED: "bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300 border-red-300 dark:border-red-700",
};

export default function VerdictChip({ verdict }: { verdict: Verdict }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md border text-xs font-medium ${STYLES[verdict]}`}>
      {verdict}
    </span>
  );
}
