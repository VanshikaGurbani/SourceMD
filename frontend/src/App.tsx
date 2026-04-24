import { Navigate, Route, Routes } from "react-router-dom";
import EvalSidebar from "./components/EvalSidebar";
import ProtectedRoute from "./components/ProtectedRoute";
import EvaluatePage from "./pages/EvaluatePage";
import HistoryPage from "./pages/HistoryPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import ResultsPage from "./pages/ResultsPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="*" element={<AppLayout />} />
    </Routes>
  );
}

function AppLayout() {
  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 dark:bg-slate-950">
      <EvalSidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-6 py-8">
          <Routes>
            <Route path="/" element={<Navigate to="/evaluate" replace />} />
            <Route path="/evaluate" element={<EvaluatePage />} />
            <Route path="/results/:id" element={<ResultsPage />} />
            <Route
              path="/history"
              element={
                <ProtectedRoute>
                  <HistoryPage />
                </ProtectedRoute>
              }
            />
            <Route path="*" element={<Navigate to="/evaluate" replace />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}
