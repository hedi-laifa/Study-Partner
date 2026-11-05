import React, { useState } from 'react';
import { AlertBanner } from '../../components/ui/AlertBanner';
import { Spinner } from '../../components/ui/States';
import { Link, navigate } from '../../app/router';
import { useAuth } from './AuthContext';

const inputClass =
  'mt-1 w-full rounded-xl border border-line bg-surface px-3.5 py-2.5 text-sm text-ink placeholder-ink/40 shadow-warm-sm transition-all focus:border-forest focus:outline-none focus:ring-2 focus:ring-forest/20';

const inputErrorClass =
  'mt-1 w-full rounded-xl border border-coral bg-surface px-3.5 py-2.5 text-sm text-ink shadow-warm-sm transition-all focus:border-coral focus:outline-none focus:ring-2 focus:ring-coral/20';

const AuthFrame: React.FC<{
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer: React.ReactNode;
}> = ({ title, subtitle, children, footer }) => (
  <div className="mx-auto w-full max-w-md py-8">
    <div className="mb-6 flex items-center justify-center gap-2.5">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-forest text-paper shadow-warm-sm">
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M22 10v6M2 10l10-5 10 5-10 5z" />
          <path d="M6 12v5c3 3 9 3 12 0v-5" />
        </svg>
      </div>
      <div>
        <span className="font-display text-lg font-bold tracking-tight text-ink">Study Partner</span>
        <span className="ml-1 rounded bg-coral/10 px-1.5 py-0.5 font-sans text-[10px] font-bold text-coral">AI</span>
      </div>
    </div>
    <div className="rounded-2xl border border-line bg-surface p-6 shadow-warm-md sm:p-8">
      <h1 className="font-display text-2xl font-bold tracking-tight text-ink">{title}</h1>
      <p className="mt-1 text-sm text-ink/70">{subtitle}</p>
      <div className="mt-6">{children}</div>
    </div>
    <p className="mt-4 text-center text-sm text-ink/70">{footer}</p>
  </div>
);

export const LoginPage: React.FC = () => {
  const { login, notice, clearNotice } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setError(null);
    clearNotice();

    const cleanEmail = email.trim();
    if (!cleanEmail || !password) {
      setError('Please enter both your email and password.');
      return;
    }

    setBusy(true);
    try {
      await login(cleanEmail, password);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to sign in.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthFrame
      title="Sign in"
      subtitle="Continue your studies where you left off."
      footer={
        <>
          New to Study Partner?{' '}
          <Link to="/register" className="font-semibold text-coral hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={(e) => void submit(e)} className="space-y-4" noValidate>
        {notice && <AlertBanner variant="warning" message={notice} />}
        {error && <AlertBanner variant="error" message={error} />}
        <div>
          <label htmlFor="login-email" className="block text-xs font-semibold uppercase tracking-wider text-ink/70">
            Email
          </label>
          <input
            id="login-email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              if (error) setError(null);
            }}
            className={inputClass}
            placeholder="student@university.edu"
          />
        </div>
        <div>
          <label htmlFor="login-password" className="block text-xs font-semibold uppercase tracking-wider text-ink/70">
            Password
          </label>
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (error) setError(null);
            }}
            className={inputClass}
          />
        </div>
        <button
          type="submit"
          disabled={busy}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-forest px-4 py-2.5 text-sm font-semibold text-paper shadow-warm-sm transition-all hover:bg-forest/90 disabled:opacity-60"
        >
          {busy && <Spinner className="h-4 w-4 text-paper" />}
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </AuthFrame>
  );
};

export const RegisterPage: React.FC = () => {
  const { register } = useAuth();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isExistingAccount, setIsExistingAccount] = useState(false);
  const [busy, setBusy] = useState(false);

  const cleanEmail = email.trim();
  const cleanName = fullName.trim();
  const emailRegex = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setError(null);
    setIsExistingAccount(false);

    // Explicit validation with actionable user-facing messages
    if (!cleanName) {
      setError('Please enter your full name.');
      return;
    }
    if (!cleanEmail) {
      setError('Please enter your university email.');
      return;
    }
    if (!emailRegex.test(cleanEmail)) {
      setError('Please enter a valid email address (e.g. student@university.edu).');
      return;
    }
    if (!password) {
      setError('Please enter a password.');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }
    if (!confirm) {
      setError('Please confirm your password.');
      return;
    }
    if (confirm !== password) {
      setError('Passwords do not match. Please re-enter.');
      return;
    }

    setBusy(true);
    try {
      await register({ email: cleanEmail, fullName: cleanName, password });
      navigate('/', { replace: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to create account.';
      if (message.toLowerCase().includes('already exists')) {
        setIsExistingAccount(true);
        setError(`${message} You can sign in directly.`);
      } else {
        setError(message);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthFrame
      title="Create your account"
      subtitle="Upload course PDFs and study with an AI tutor that cites your own material."
      footer={
        <>
          Already registered?{' '}
          <Link to="/login" className="font-semibold text-coral hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={(e) => void submit(e)} className="space-y-4" noValidate>
        {error && (
          <div className="space-y-2">
            <AlertBanner variant="error" message={error} />
            {isExistingAccount && (
              <div className="text-center">
                <Link
                  to="/login"
                  className="inline-flex items-center text-sm font-semibold text-coral underline hover:opacity-80"
                >
                  Go to Sign in page →
                </Link>
              </div>
            )}
          </div>
        )}

        <div>
          <label htmlFor="reg-name" className="block text-xs font-semibold uppercase tracking-wider text-ink/70">
            Full name
          </label>
          <input
            id="reg-name"
            autoComplete="name"
            required
            value={fullName}
            onChange={(e) => {
              setFullName(e.target.value);
              if (error) setError(null);
            }}
            className={inputClass}
            placeholder="Ada Lovelace"
          />
        </div>

        <div>
          <label htmlFor="reg-email" className="block text-xs font-semibold uppercase tracking-wider text-ink/70">
            University email
          </label>
          <input
            id="reg-email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              if (error) setError(null);
            }}
            className={inputClass}
            placeholder="student@university.edu"
          />
        </div>

        <div>
          <label htmlFor="reg-password" className="block text-xs font-semibold uppercase tracking-wider text-ink/70">
            Password
          </label>
          <input
            id="reg-password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            aria-describedby="reg-password-hint"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (error) setError(null);
            }}
            className={password && password.length < 8 ? inputErrorClass : inputClass}
            placeholder="At least 8 characters"
          />
          <p id="reg-password-hint" className="mt-1 text-xs text-ink/50">
            Must be at least 8 characters.
          </p>
        </div>

        <div>
          <label htmlFor="reg-confirm" className="block text-xs font-semibold uppercase tracking-wider text-ink/70">
            Confirm password
          </label>
          <input
            id="reg-confirm"
            type="password"
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(e) => {
              setConfirm(e.target.value);
              if (error) setError(null);
            }}
            className={confirm && confirm !== password ? inputErrorClass : inputClass}
            placeholder="Re-enter your password"
          />
          {confirm && confirm !== password && (
            <p role="alert" className="mt-1 text-xs font-medium text-coral">
              Passwords do not match.
            </p>
          )}
        </div>

        <button
          type="submit"
          disabled={busy}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-forest px-4 py-2.5 text-sm font-semibold text-paper shadow-warm-sm transition-all hover:bg-forest/90 disabled:opacity-60"
        >
          {busy && <Spinner className="h-4 w-4 text-paper" />}
          {busy ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </AuthFrame>
  );
};
