import type { UserProfile } from '../types/course';
import { apiRequest } from './apiClient';

export interface AuthResult {
  access_token: string;
  token_type: string;
  expires_at: number;
  user: UserProfile;
}

export function loginRequest(
  email: string,
  password: string
): Promise<AuthResult> {
  return apiRequest<AuthResult>('/auth/login', {
    method: 'POST',
    json: { email, password },
    anonymous: true,
  });
}

export function registerRequest(params: {
  email: string;
  fullName: string;
  password: string;
}): Promise<AuthResult> {
  return apiRequest<AuthResult>('/auth/register', {
    method: 'POST',
    json: {
      email: params.email,
      full_name: params.fullName,
      password: params.password,
    },
    anonymous: true,
  });
}

export function fetchCurrentUser(): Promise<UserProfile> {
  return apiRequest<UserProfile>('/auth/me', { fresh: true });
}
