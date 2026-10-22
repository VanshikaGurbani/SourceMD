import { useServerStatus } from "../context/ServerStatusContext";

/** Shown only while the free-tier backend is asleep/waking or unreachable. */
export default function ServerStatusBanner() {
  const { status, elapsedSeconds } = useServerStatus();

  if (status === "checking" || status === "ready") return null;

  if (status === "unreachable") {
    return (
      <div
        role="alert"
        className="mb-4 rounded-md border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-3 text-sm text-red-700 dark:text-red-300"
      >
        The server is not responding. You can still try to submit, but it may fail. Please retry in a minute.
      </div>
    );
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className="mb-4 flex items-start gap-3 rounded-md border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/20 p-3 text-sm text-amber-800 dark:text-amber-200"
    >
      <span
        aria-hidden="true"
        className="mt-0.5 h-4 w-4 flex-none animate-spin rounded-full border-2 border-amber-500 border-t-transparent"
      />
      <div>
        <p className="font-medium">Server waking up ({elapsedSeconds}s)</p>
        <p>
          The free-tier backend sleeps when idle and usually takes about 30 seconds to start. You can type your
          question now; submitting is enabled as soon as the server responds.
        </p>
      </div>
    </div>
  );
}
