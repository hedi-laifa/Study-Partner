import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { configureApiAuth, invalidateApiCache } from '../../services/apiClient';
import {
  fetchCurrentUser,
  loginRequest,
  registerRequest,
  type AuthResult,
} from '../../services/authService';
import type { UserProfile } from '../../types/course';

const STORAGE_KEY = 'study-partner.auth.v1';

interface StoredAuth {
  token: string;
  expiresAt: number;
}

function readStored(): StoredAuth | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredAuth;
    if (!parsed.token || parsed.expiresAt * 1000 <= Date.now()) {
      window.localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous';

interface AuthContextValue {
  status: AuthStatus;
  user: UserProfile | null;
  /** Message explaining why the user was signed out (e.g. expired session). */
  notice: string | null;
  clearNotice: () => void;
  login: (email: string, password: string) => Promise<void>;
  register: (params: {
    email: string;
    fullName: string;
    password: string;
  }) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [stored, setStored] = useState<StoredAuth | null>(readStored);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [status, setStatus] = useState<AuthStatus>(
    stored ? 'loading' : 'anonymous'
  );
  const [notice, setNotice] = useState<string | null>(null);
  const tokenRef = useRef<string | null>(stored?.token ?? null);

  const clearSession = useCallback((message: string | null) => {
    tokenRef.current = null;
    window.localStorage.removeItem(STORAGE_KEY);
    invalidateApiCache();
    setStored(null);
    setUser(null);
    setStatus('anonymous');
    setNotice(message);
  }, []);

  // Register API auth hooks synchronously so the very first request is signed.
  configureApiAuth({
    getToken: () => tokenRef.current,
    onUnauthorized: (reason) =>
      clearSession(
        reason === 'expired'
          ? 'Your session has expired. Please sign in again.'
          : 'Your session is no longer valid. Please sign in again.'
      ),
  });

  const applyAuth = useCallback((result: AuthResult) => {
    const next: StoredAuth = {
      token: result.access_token,
      expiresAt: result.expires_at,
    };
    tokenRef.current = next.token;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    invalidateApiCache();
    setStored(next);
    setUser(result.user);
    setStatus('authenticated');
    setNotice(null);
  }, []);

  // Validate a persisted token once on startup.
  useEffect(() => {
    if (!stored || user) return;
    let cancelled = false;
    fetchCurrentUser()
      .then((profile) => {
        if (cancelled) return;
        setUser(profile);
        setStatus('authenticated');
      })
      .catch(() => {
        if (!cancelled && tokenRef.current) {
          // Network failure or invalid token: fall back to the sign-in screen.
          clearSession('Please sign in to continue.');
        }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Proactively sign out when the token's lifetime elapses.
  useEffect(() => {
    if (!stored) return undefined;
    const ms = stored.expiresAt * 1000 - Date.now();
    const timer = window.setTimeout(
      () => clearSession('Your session has expired. Please sign in again.'),
      Math.max(0, Math.min(ms, 2_147_000_000))
    );
    return () => window.clearTimeout(timer);
  }, [stored, clearSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      notice,
      clearNotice: () => setNotice(null),
      login: async (email, password) => {
        applyAuth(await loginRequest(email, password));
      },
      register: async (params) => {
        applyAuth(await registerRequest(params));
      },
      logout: () => clearSession(null),
    }),
    [status, user, notice, applyAuth, clearSession]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
