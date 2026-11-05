import { useCallback, useEffect, useState } from 'react';
import { fetchBackendHealth } from '../services/healthService';
import type { HealthStatusResponse } from '../types/health';

export interface UseBackendHealthResult {
  data: HealthStatusResponse | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useBackendHealth(): UseBackendHealthResult {
  const [data, setData] = useState<HealthStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await fetchBackendHealth();
      setData(result);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Unable to reach backend API';
      setError(message);
      setData(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { data, isLoading, error, refresh };
}
