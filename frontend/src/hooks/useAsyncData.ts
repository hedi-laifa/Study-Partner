import { useCallback, useEffect, useRef, useState } from 'react';

export interface AsyncState<T> {
  data: T | null;
  error: string | null;
  isLoading: boolean;
  reload: () => Promise<void>;
  setData: (updater: (prev: T | null) => T | null) => void;
}

/**
 * Loads data with loading/error state and ignores stale responses.
 * `loader` should be memoized (useCallback) – it re-runs when its identity changes.
 */
export function useAsyncData<T>(loader: () => Promise<T>): AsyncState<T> {
  const [data, setDataState] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const requestId = useRef(0);

  const run = useCallback(async () => {
    const id = ++requestId.current;
    setIsLoading(true);
    try {
      const result = await loader();
      if (id !== requestId.current) return;
      setDataState(result);
      setError(null);
    } catch (err) {
      if (id !== requestId.current) return;
      setError(err instanceof Error ? err.message : 'Something went wrong.');
    } finally {
      if (id === requestId.current) setIsLoading(false);
    }
  }, [loader]);

  useEffect(() => {
    void run();
    return () => {
      requestId.current += 1;
    };
  }, [run]);

  return { data, error, isLoading, reload: run, setData: setDataState };
}
