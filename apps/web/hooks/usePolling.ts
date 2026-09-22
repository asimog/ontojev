"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const MAX_BACKOFF_MS = 30_000;

export function usePolling<T>(load: (signal: AbortSignal) => Promise<T>, intervalMs: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const loadRef = useRef(load);
  loadRef.current = load;
  const failures = useRef(0);

  const refresh = useCallback(async (signal: AbortSignal) => {
    try {
      const next = await loadRef.current(signal);
      failures.current = 0;
      setData(next);
      setError(null);
      setUpdatedAt(new Date().toISOString());
    } catch (reason) {
      if ((reason as Error).name !== "AbortError") {
        failures.current += 1;
        setError("API unavailable");
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let stopped = false;
    let inFlight = false;
    const loop = async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        if (document.visibilityState === "visible") await refresh(controller.signal);
      } finally {
        inFlight = false;
      }
      if (stopped) return;
      const backoff = Math.min(intervalMs * 2 ** failures.current, MAX_BACKOFF_MS);
      timer = setTimeout(loop, document.visibilityState === "visible" ? backoff : intervalMs);
    };
    const onVisibility = () => {
      if (document.visibilityState !== "visible" || stopped) return;
      clearTimeout(timer);
      void loop();
    };
    document.addEventListener("visibilitychange", onVisibility);
    void loop();
    return () => {
      stopped = true;
      controller.abort();
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [intervalMs, refresh]);

  return { data, error, updatedAt, refresh };
}
