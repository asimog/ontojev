"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export function usePolling<T>(load: (signal: AbortSignal) => Promise<T>, intervalMs: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const loadRef = useRef(load);
  loadRef.current = load;

  const refresh = useCallback(async (signal: AbortSignal) => {
    try {
      const next = await loadRef.current(signal);
      setData(next);
      setError(null);
      setUpdatedAt(new Date().toISOString());
    } catch (reason) {
      if ((reason as Error).name !== "AbortError") setError("API unavailable");
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let stopped = false;
    const loop = async () => {
      await refresh(controller.signal);
      if (!stopped) timer = setTimeout(loop, intervalMs);
    };
    void loop();
    return () => {
      stopped = true;
      controller.abort();
      clearTimeout(timer);
    };
  }, [intervalMs, refresh]);

  return { data, error, updatedAt, refresh };
}

