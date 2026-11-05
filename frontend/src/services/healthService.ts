import type { HealthStatusResponse } from '../types/health';
import { apiRequest } from './apiClient';

export function fetchBackendHealth(): Promise<HealthStatusResponse> {
  return apiRequest<HealthStatusResponse>('/health', {
    anonymous: true,
    fresh: true,
  });
}
