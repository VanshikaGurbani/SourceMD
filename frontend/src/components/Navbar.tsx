import { Link, useNavigate } from "react-router-dom";
import { clearToken, getToken } from "../api/client";

export default function Navbar() {
  const navigate = useNavigate();
  const authed = Boolean(getToken());

  function handleLogout() {
    clearToken();
    navigate("/evaluate");
  }

  return (
    <header className="bg-white border-b border-slate-200">
      <div className="container mx-auto px-4 py-3 max-w-5xl flex items-center justify-between">
        <Link to="/evaluate" className="text-xl font-semibold text-slate-900">
          SourceMD
        </Link>
        <nav className="flex items-center gap-4 text-sm">
          <Link to="/evaluate" className="text-slate-700 hover:text-slate-900">
            Evaluate
          </Link>
          {authed && (
            <Link to="/history" className="text-slate-700 hover:text-slate-900">
              History
            </Link>
          )}
          {authed ? (
            <button
              type="button"
              onClick={handleLogout}
              className="text-slate-700 hover:text-slate-900"
            >
              Logout
            </button>
          ) : (
            <>
              <Link to="/login" className="text-slate-700 hover:text-slate-900">
                Login
              </Link>
              <Link
                to="/register"
                className="px-3 py-1.5 rounded-md bg-slate-900 text-white hover:bg-slate-800"
              >
                Register
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
