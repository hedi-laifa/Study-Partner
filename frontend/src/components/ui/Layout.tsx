import React from 'react';

interface PageHeaderProps {
  title: string;
  description?: string;
  eyebrow?: React.ReactNode;
  actions?: React.ReactNode;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  eyebrow,
  actions,
}) => (
  <div className="flex flex-wrap items-start justify-between gap-4">
    <div className="min-w-0">
      {eyebrow && (
        <div className="mb-1 text-xs font-bold uppercase tracking-wider text-ink-muted">
          {eyebrow}
        </div>
      )}
      <h1 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-ink">
        {title}
      </h1>
      {description && (
        <p className="mt-1 max-w-2xl text-xs sm:text-sm text-ink-muted leading-relaxed">
          {description}
        </p>
      )}
    </div>
    {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
  </div>
);

export interface TabItem {
  id: string;
  label: string;
  count?: number;
}

interface TabsProps {
  tabs: TabItem[];
  activeId: string;
  onSelect: (id: string) => void;
  label: string;
}

/** Accessible tab list (arrow-key navigation, roving tabindex). */
export const Tabs: React.FC<TabsProps> = ({
  tabs,
  activeId,
  onSelect,
  label,
}) => {
  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    const idx = tabs.findIndex((t) => t.id === activeId);
    let next = idx;
    if (e.key === 'ArrowRight') next = (idx + 1) % tabs.length;
    else if (e.key === 'ArrowLeft') next = (idx - 1 + tabs.length) % tabs.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = tabs.length - 1;
    else return;
    e.preventDefault();
    onSelect(tabs[next].id);
    document.getElementById(`tab-${tabs[next].id}`)?.focus();
  };

  return (
    <div
      role="tablist"
      aria-label={label}
      onKeyDown={onKeyDown}
      className="flex gap-2 overflow-x-auto border-b border-line pb-px"
    >
      {tabs.map((tab) => {
        const active = tab.id === activeId;
        return (
          <button
            key={tab.id}
            id={`tab-${tab.id}`}
            type="button"
            role="tab"
            aria-selected={active}
            aria-controls={`panel-${tab.id}`}
            tabIndex={active ? 0 : -1}
            onClick={() => onSelect(tab.id)}
            className={`-mb-px shrink-0 whitespace-nowrap border-b-2 px-4 py-2.5 text-xs sm:text-sm font-semibold transition-all ${
              active
                ? 'border-coral text-forest font-bold'
                : 'border-transparent text-ink-muted hover:border-line hover:text-ink'
            }`}
          >
            {tab.label}
            {typeof tab.count === 'number' && (
              <span
                className={`ml-2 rounded-full px-2 py-0.5 text-[10px] font-bold ${
                  active
                    ? 'bg-coral-soft text-coral'
                    : 'bg-paper-deep text-ink-muted'
                }`}
              >
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};

export const Card: React.FC<{
  title?: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}> = ({ title, description, actions, children, className = '' }) => (
  <section
    className={`rounded-xl border border-line bg-paper-surface p-5 sm:p-6 shadow-warm-sm transition-all ${className}`}
  >
    {(title || actions) && (
      <div className="mb-4 flex flex-wrap items-start justify-between gap-2 border-b border-line/60 pb-3">
        <div>
          {title && (
            <h2 className="font-display text-base sm:text-lg font-semibold text-ink">
              {title}
            </h2>
          )}
          {description && (
            <p className="mt-0.5 text-xs text-ink-muted">{description}</p>
          )}
        </div>
        {actions}
      </div>
    )}
    {children}
  </section>
);

/** StudyMate-inspired StatCard with tinted icon box, display number, and detail text */
export const StatCard: React.FC<{
  icon: React.ReactNode;
  color: 'coral' | 'lilac' | 'sage' | 'forest';
  label: string;
  value: string | number;
  detail?: string;
}> = ({ icon, color, label, value, detail }) => {
  const colorMap = {
    coral: 'bg-coral-soft text-coral',
    lilac: 'bg-lilac-soft text-[#68598a]',
    sage: 'bg-sage-soft text-[#4f6f52]',
    forest: 'bg-forest-soft text-forest',
  };

  return (
    <div className="flex items-center gap-3.5 rounded-xl border border-line bg-paper-surface p-4 sm:p-5 shadow-warm-sm hover:border-forest/30 transition-all">
      <div
        className={`flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-lg text-lg font-bold ${colorMap[color]}`}
        aria-hidden="true"
      >
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <span className="block text-[11px] font-bold uppercase tracking-wider text-ink-muted truncate">
          {label}
        </span>
        <strong className="block font-display text-xl sm:text-2xl font-semibold tracking-tight text-ink">
          {value}
        </strong>
        {detail && <span className="block text-[11px] text-ink-muted truncate">{detail}</span>}
      </div>
    </div>
  );
};

/** StudyMate-inspired Editorial Welcome Banner with concentric rings and streak counter */
export const WelcomeCard: React.FC<{
  userName: string;
  coursesCount: number;
  conceptsMasteredCount?: number;
  onStartStudy?: () => void;
}> = ({ userName, coursesCount, conceptsMasteredCount = 0, onStartStudy }) => (
  <div className="welcome-hero-banner rounded-2xl p-6 sm:p-8 shadow-warm-md flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
    <div className="max-w-xl z-10">
      <span className="text-[11px] font-bold uppercase tracking-widest text-[#d7ceff]">
        Personal Academic Companion
      </span>
      <h2 className="font-display text-2xl sm:text-3xl font-semibold text-white tracking-tight mt-1 mb-2">
        Welcome back, {userName}
      </h2>
      <p className="text-xs sm:text-sm text-[#e8f0ea] leading-relaxed mb-5">
        You have <strong className="text-white font-semibold">{coursesCount}</strong> active {coursesCount === 1 ? 'course' : 'courses'} enrolled with grounded AI tutoring and adaptive sessions.
      </p>
      {onStartStudy && (
        <button
          type="button"
          onClick={onStartStudy}
          className="inline-flex items-center gap-2 rounded-lg bg-paper px-4 py-2.5 text-xs sm:text-sm font-bold text-forest shadow-sm hover:bg-white transition-all transform hover:-translate-y-0.5"
        >
          <span>Continue Learning</span>
          <span aria-hidden="true">→</span>
        </button>
      )}
    </div>

    {/* Concentric Streak / Mastery Orbit Ring */}
    <div className="streak-orbit-circle h-28 w-28 flex-shrink-0 self-center md:self-auto text-center border-white/20">
      <span className="text-[10px] font-bold uppercase tracking-wider text-[#d7ceff]">
        Mastered
      </span>
      <strong className="font-display text-3xl font-bold text-white leading-none my-0.5">
        {conceptsMasteredCount}
      </strong>
      <span className="text-[9px] text-[#e8f0ea]">
        Concepts
      </span>
    </div>
  </div>
);
