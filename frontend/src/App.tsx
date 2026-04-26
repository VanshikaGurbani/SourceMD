import { useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import EvalSidebar from "./components/EvalSidebar";
import EvaluatePage from "./pages/EvaluatePage";
import HistoryPage from "./pages/HistoryPage";
import ResultsPage from "./pages/ResultsPage";

export default function App() {
  return (
    <Routes>
      <Route path="*" element={<AppLayout />} />
    </Routes>
  );
}

function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const handleNavClose = () => setSidebarOpen(false);

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 dark:bg-slate-950">
      {/* Mobile overlay backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div className={`
        fixed inset-y-0 left-0 z-40 md:static md:z-auto
        transition-transform duration-200 ease-in-out
        ${sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
      `}>
        <EvalSidebar onNavigate={handleNavClose} />
      </div>

      <main className="flex-1 overflow-y-auto min-w-0">
        {/* Mobile top bar */}
        <div className="md:hidden flex items-center gap-3 px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 sticky top-0 z-20">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="p-1.5 rounded-md text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">SourceMD</span>
        </div>

        <div className="max-w-4xl mx-auto px-4 md:px-6 py-6 md:py-8">
          <Routes>
            <Route path="/" element={<Navigate to="/evaluate" replace />} />
            <Route path="/evaluate" element={<EvaluatePage />} />
            <Route path="/results/:id" element={<ResultsPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="*" element={<Navigate to="/evaluate" replace />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}
