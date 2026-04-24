import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { setToken } from "../api/client";
import { login } from "../api/endpoints";

export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const token = await login(email, password);
      setToken(token.access_token);
      navigate("/evaluate");
    } catch (err) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Login failed";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center px-4">
    <div className="w-full max-w-sm">
      <p className="text-center text-xl font-semibold text-slate-900 mb-6">SourceMD</p>
      <h1 className="text-2xl font-semibold text-slate-900 mb-4">Log in</h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="email"
          className="w-full rounded-md border border-slate-300 p-2"
        />
        <input
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="password"
          className="w-full rounded-md border border-slate-300 p-2"
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full px-4 py-2 rounded-md bg-slate-900 text-white hover:bg-slate-800 disabled:opacity-60"
        >
          {loading ? "Logging in..." : "Log in"}
        </button>
      </form>
      <p className="mt-4 text-center text-sm text-slate-500">
        No account?{" "}
        <a href="/register" className="text-slate-900 underline">Register</a>
      </p>
    </div>
    </div>
  );
}
