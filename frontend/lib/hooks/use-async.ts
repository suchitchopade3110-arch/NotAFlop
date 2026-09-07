"use client";

import { useCallback, useEffect, useState } from "react";

interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: unknown;
}

/** Small fetch-on-mount hook shared by the log/idea-detail surfaces
 * (C1-C4) — every one of them needs the same loading/error/data/refetch
 * shape, so it's factored out once rather than repeated per component. */
export function useAsync<T>(fn: () => Promise<T>, deps: React.DependencyList): AsyncState<T> & { refetch: () => void } {
  const [state, setState] = useState<AsyncState<T>>({ data: null, loading: true, error: null });
  const [tick, setTick] = useState(0);

  const run = useCallback(() => {
    let cancelled = false;
    setState((prev) => ({ ...prev, loading: true, error: null }));
    fn()
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: null });
      })
      .catch((error) => {
        if (!cancelled) setState({ data: null, loading: false, error });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  useEffect(() => run(), [run]);

  return { ...state, refetch: () => setTick((t) => t + 1) };
}
