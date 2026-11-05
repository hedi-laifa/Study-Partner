import React, { useState } from 'react';
import { Link } from '../../app/router';
import type { UserProfile } from '../../types/course';

export type NavId = 'dashboard' | 'system';

interface AppShellProps {
  children: React.ReactNode;
  user?: UserProfile | null;
  activeNav?: NavId | null;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  onLogout?: () => void;
}

const NAV_ITEMS: {
  id: NavId;
  label: string;
  to: string;
  icon: (active: boolean) => React.ReactNode;
}[] = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    to: '/',
    icon: (active) => (
      <svg
        className={`h-4 w-4 ${active ? 'text-coral' : 'text-[#9ab0a5]'}`}
        fill="none"
        viewBox="0 0 24 24"
        strokeWidth="2"
        stroke="currentColor"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z"
        />
      </svg>
    ),
  },
  {
    id: 'system',
    label: 'System Status',
    to: '/system',
    icon: (active) => (
      <svg
        className={`h-4 w-4 ${active ? 'text-coral' : 'text-[#9ab0a5]'}`}
        fill="none"
        viewBox="0 0 24 24"
        strokeWidth="2"
        stroke="currentColor"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
    ),
  },
];

export const AppShell: React.FC<AppShellProps> = ({
  children,
  user,
  activeNav,
  theme,
  onToggleTheme,
  onLogout,
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const getInitials = (name?: string) => {
    if (!name) return 'SP';
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    return name.slice(0, 2).toUpperCase();
  };

  return (
    <div className="flex min-h-screen bg-paper text-ink font-sans">
      {/* Keyboard navigation skip link */}
      <a
        href="#main-content"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById('main-content')?.focus();
        }}
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-forest focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-paper shadow-warm-md"
      >
        Skip to main content
      </a>

      {/* ------------------------------------------------------------ */}
      {/* StudyMate-inspired Forest Sidebar (Desktop)                  */}
      {/* ------------------------------------------------------------ */}
      <aside className="hidden md:flex flex-col flex-shrink-0 w-64 bg-forest text-paper border-r border-forest-dark selection:bg-coral selection:text-white">
        {/* Brand Header */}
        <div className="flex items-center gap-3 px-6 pt-7 pb-8 border-b border-white/10">
          <Link to="/" className="flex items-center gap-2.5 text-decoration-none">
            <span
              aria-hidden="true"
              className="flex h-8 w-8 items-center justify-center rounded-md bg-coral font-display text-sm font-bold text-white shadow-sm"
            >
              SP
            </span>
            <div className="flex flex-col">
              <span className="font-display text-lg font-semibold tracking-tight text-white leading-tight">
                Study Partner <span className="text-coral">AI</span>
              </span>
              <span className="text-[10px] uppercase tracking-wider text-[#9ab0a5] font-semibold">
                Adaptive Learning
              </span>
            </div>
          </Link>
        </div>

        {/* Navigation items */}
        <div className="flex-1 px-4 py-6">
          <p className="px-3 mb-3 text-[10px] font-bold uppercase tracking-widest text-[#9ab0a5]">
            Academic Platform
          </p>
          <nav aria-label="Main" className="space-y-1">
            {NAV_ITEMS.map((item) => {
              const active = activeNav === item.id;
              return (
                <Link
                  key={item.id}
                  to={item.to}
                  aria-current={active ? 'page' : undefined}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-md text-xs font-medium transition-all ${
                    active
                      ? 'bg-white/10 text-white font-semibold shadow-[inset_3px_0_0_0_#d96552]'
                      : 'text-[#b3c2b9] hover:bg-white/5 hover:text-white'
                  }`}
                >
                  {item.icon(active)}
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Bottom User Profile Section */}
        {user && (
          <div className="p-4 border-t border-white/10 bg-black/10">
            <div className="flex items-center gap-3">
              <div
                className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-coral-soft text-forest text-xs font-bold"
                aria-hidden="true"
              >
                {getInitials(user.full_name)}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-semibold text-white leading-tight">
                  {user.full_name}
                </p>
                <p className="truncate text-[10px] text-[#9ab0a5]" title={user.email}>
                  {user.email}
                </p>
              </div>
              {onLogout && (
                <button
                  type="button"
                  onClick={onLogout}
                  aria-label="Sign out"
                  title="Sign out"
                  className="rounded p-1.5 text-[#9ab0a5] hover:bg-white/10 hover:text-white transition-colors"
                >
                  <svg
                    className="h-4 w-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth="2"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M12 9l-3 3m0 0l3 3m-3-3h12.75"
                    />
                  </svg>
                </button>
              )}
            </div>
          </div>
        )}
      </aside>

      {/* ------------------------------------------------------------ */}
      {/* Mobile Drawer Menu (Visible when toggled on smaller screens) */}
      {/* ------------------------------------------------------------ */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setMobileMenuOpen(false)}
        >
          <div
            className="w-64 max-w-[80vw] h-full bg-forest text-paper p-6 flex flex-col shadow-warm-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between pb-6 border-b border-white/10">
              <span className="font-display text-lg font-bold text-white">
                Study Partner <span className="text-coral">AI</span>
              </span>
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                className="text-white/70 hover:text-white text-lg p-1"
                aria-label="Close menu"
              >
                ✕
              </button>
            </div>
            <nav className="mt-6 space-y-1 flex-1">
              {NAV_ITEMS.map((item) => (
                <Link
                  key={item.id}
                  to={item.to}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-md text-xs font-medium ${
                    activeNav === item.id
                      ? 'bg-white/10 text-white font-semibold shadow-[inset_3px_0_0_0_#d96552]'
                      : 'text-[#b3c2b9] hover:bg-white/5 hover:text-white'
                  }`}
                >
                  {item.icon(activeNav === item.id)}
                  <span>{item.label}</span>
                </Link>
              ))}
            </nav>
            {user && onLogout && (
              <div className="pt-4 border-t border-white/10">
                <button
                  type="button"
                  onClick={() => {
                    setMobileMenuOpen(false);
                    onLogout();
                  }}
                  className="w-full flex items-center justify-center gap-2 py-2 rounded bg-white/10 text-xs font-semibold text-white hover:bg-coral transition-colors"
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------ */}
      {/* Main Content Area + StudyMate Topbar                         */}
      {/* ------------------------------------------------------------ */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Topbar */}
        <header className="sticky top-0 z-30 flex h-20 items-center justify-between border-b border-line bg-paper-surface/95 backdrop-blur px-5 sm:px-8">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileMenuOpen((o) => !o)}
              className="md:hidden rounded p-2 text-ink hover:bg-paper-deep transition-colors"
              aria-label="Toggle navigation menu"
              aria-expanded={mobileMenuOpen}
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>

            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
                {activeNav === 'system' ? 'System Infrastructure' : 'Academic Companion'}
              </p>
              <h1 className="font-display text-lg sm:text-xl font-semibold tracking-tight text-ink leading-tight">
                {activeNav === 'system' ? 'Platform Health & Models' : 'Student Learning Hub'}
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onToggleTheme}
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
              className="inline-flex items-center gap-1.5 rounded-full border border-line bg-paper px-3 py-1.5 text-xs font-medium text-ink hover:border-forest transition-colors shadow-warm-sm"
            >
              <span aria-hidden="true">{theme === 'dark' ? '☀️' : '🌙'}</span>
              <span className="hidden sm:inline">
                {theme === 'dark' ? 'Light mode' : 'Dark mode'}
              </span>
            </button>

            {user && (
              <div className="hidden sm:flex items-center gap-2 pl-3 border-l border-line text-xs">
                <span className="font-semibold text-ink">{user.full_name}</span>
              </div>
            )}
          </div>
        </header>

        {/* Page Container */}
        <main
          id="main-content"
          tabIndex={-1}
          className="flex-1 px-5 py-8 sm:px-8 max-w-6xl w-full mx-auto outline-none"
        >
          {children}
        </main>
      </div>
    </div>
  );
};
