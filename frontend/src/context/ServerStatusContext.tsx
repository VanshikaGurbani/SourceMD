import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { apiClient } from "../api/client";

/**
 * "ready"       backend answered /health
 * "waking"      no answer yet; free-tier hosts sleep when idle and take ~30 s to wake
 * "unreachable" still no answer after GIVE_UP_MS; the UI stops blocking and lets the user try
 */
export type ServerStatus = "checking" | "waking" | "ready" | "unreachable";

interface ServerStatusValue {
  status: ServerStatus;
  elapsedSeconds: number;
}

const WAKING_AFTER_MS = 2500; // a warm server answers well before this
const RETRY_EVERY_MS = 3000;
const PER_REQUEST_TIMEOUT_MS = 8000;
const GIVE_UP_MS = 120_000;

const ServerStatusContext = createContext<ServerStatusValue>({ status: "checking", elapsedSeconds: 0 });

export function ServerStatusProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<ServerStatus>("checking");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const started = Date.now();

    const tick = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - started) / 1000));
    }, 1000);
    const wakingTimer = window.setTimeout(() => {
      if (!cancelled) setStatus((s) => (s === "checking" ? "waking" : s));
    }, WAKING_AFTER_MS);

    async function ping() {
      while (!cancelled) {
        try {
          await apiClient.get("/health", { timeout: PER_REQUEST_TIMEOUT_MS });
          if (!cancelled) setStatus("ready");
          return;
        } catch {
          if (Date.now() - started > GIVE_UP_MS) {
            if (!cancelled) setStatus("unreachable");
            return;
          }
          await new Promise((r) => setTimeout(r, RETRY_EVERY_MS));
        }
      }
    }
    void ping();

    return () => {
      cancelled = true;
      window.clearInterval(tick);
      window.clearTimeout(wakingTimer);
    };
  }, []);

  return (
    <ServerStatusContext.Provider value={{ status, elapsedSeconds }}>{children}</ServerStatusContext.Provider>
  );
}

export function useServerStatus(): ServerStatusValue {
  return useContext(ServerStatusContext);
}
