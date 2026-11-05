import { API_BASE_URL } from '../utils/config';

/** Error thrown for every failed API call, carrying HTTP status and backend error code. */
export class ApiError extends Error {
  readonly status: number;
  readonly errorCode: string | null;

  constructor(message: string, status: number, errorCode: string | null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.errorCode = errorCode;
  }
}

const SESSION_ERROR_CODES = new Set([
  'TOKEN_EXPIRED',
  'INVALID_TOKEN',
  'AUTH_REQUIRED',
]);

type TokenProvider = () => string | null;
type UnauthorizedHandler = (reason: 'expired' | 'invalid') => void;

let tokenProvider: TokenProvider = () => null;
let unauthorizedHandler: UnauthorizedHandler | null = null;

/** Registered once by the AuthProvider. */
export function configureApiAuth(config: {
  getToken: TokenProvider;
  onUnauthorized: UnauthorizedHandler;
}): void {
  tokenProvider = config.getToken;
  unauthorizedHandler = config.onUnauthorized;
}

// --- GET de-duplication + short-lived cache -------------------------------
// Identical GETs issued within the TTL (or while in flight) share one request.
// Any successful mutation clears the cache so screens never show stale data.
const CACHE_TTL_MS = 8_000;
const getCache = new Map<string, { at: number; promise: Promise<unknown> }>();

export function invalidateApiCache(): void {
  getCache.clear();
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  query?: Record<string, string | number | boolean | null | undefined>;
  json?: unknown;
  form?: FormData;
  /** Skip authorization header and session-expiry handling (login/register). */
  anonymous?: boolean;
  /** Bypass the GET cache. */
  fresh?: boolean;
  /** Request timeout in milliseconds (default 45_000). */
  timeoutMs?: number;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const url = new URL(
    `${API_BASE_URL.replace(/\/$/, '')}${path}`,
    window.location.origin
  );
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== null && value !== undefined && value !== '') {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

async function toApiError(response: Response): Promise<ApiError> {
  let message = `Request failed (HTTP ${response.status})`;
  let code: string | null = null;
  try {
    const body = (await response.json()) as {
      detail?: unknown;
      error_code?: string;
    };
    code = body.error_code ?? null;
    if (typeof body.detail === 'string') {
      message = body.detail;
    } else if (response.status === 422) {
      message = 'Some of the submitted values are invalid.';
    }
  } catch {
    // non-JSON error body
  }
  return new ApiError(message, response.status, code);
}

async function execute(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  const token = options.anonymous ? null : tokenProvider();
  if (token) headers.Authorization = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (options.form) {
    body = options.form;
  } else if (options.json !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(options.json);
  }

  let response: Response;
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? 45_000;
  let timedOut = false;
  const timer = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  if (options.signal) {
    options.signal.addEventListener('abort', () => controller.abort(), { once: true });
  }
  try {
    response = await fetch(buildUrl(path, options.query), {
      method: options.method ?? 'GET',
      headers,
      body,
      signal: controller.signal,
    });
  } catch (err) {
    if (timedOut) {
      throw new ApiError(
        'The request timed out. Please try again.',
        504,
        'REQUEST_TIMEOUT'
      );
    }
    if (err instanceof DOMException && err.name === 'AbortError') throw err;
    throw new ApiError(
      'Cannot reach the Study Partner server. Check that the backend is running.',
      0,
      'NETWORK_ERROR'
    );
  } finally {
    window.clearTimeout(timer);
  }

  if (!response.ok) {
    const error = await toApiError(response);
    if (
      !options.anonymous &&
      response.status === 401 &&
      error.errorCode &&
      SESSION_ERROR_CODES.has(error.errorCode)
    ) {
      unauthorizedHandler?.(
        error.errorCode === 'TOKEN_EXPIRED' ? 'expired' : 'invalid'
      );
    }
    throw error;
  }
  return response;
}

/** Typed JSON request. 204 responses resolve to `undefined`. */
export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const method = options.method ?? 'GET';

  if (method === 'GET' && !options.fresh && !options.anonymous) {
    const key = `${tokenProvider() ?? ''}|${buildUrl(path, options.query)}`;
    const hit = getCache.get(key);
    if (hit && Date.now() - hit.at < CACHE_TTL_MS) {
      return hit.promise as Promise<T>;
    }
    const promise = execute(path, options)
      .then((r) => r.json() as Promise<T>)
      .catch((err) => {
        getCache.delete(key);
        throw err;
      });
    getCache.set(key, { at: Date.now(), promise });
    return promise;
  }

  const response = await execute(path, options);
  if (method !== 'GET') invalidateApiCache();
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Authenticated binary download (e.g. PDF preview) returned as a Blob. */
export async function apiBlob(
  path: string,
  query?: RequestOptions['query']
): Promise<Blob> {
  const response = await execute(path, { query });
  return response.blob();
}
