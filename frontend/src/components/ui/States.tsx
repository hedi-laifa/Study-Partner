import React from 'react';

export const Spinner: React.FC<{ className?: string }> = ({
  className = 'h-4 w-4',
}) => (
  <svg
    className={`animate-spin text-forest ${className}`}
    viewBox="0 0 24 24"
    fill="none"
    aria-hidden="true"
  >
    <circle
      className="opacity-25"
      cx="12"
      cy="12"
      r="10"
      stroke="currentColor"
      strokeWidth="4"
    />
    <path
      className="opacity-75"
      fill="currentColor"
      d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
    />
  </svg>
);

export const LoadingState: React.FC<{ label?: string }> = ({
  label = 'Loading…',
}) => (
  <div
    role="status"
    aria-live="polite"
    className="flex items-center justify-center gap-3 rounded-xl border border-line bg-paper-surface p-8 text-xs sm:text-sm font-medium text-ink-muted shadow-warm-sm"
  >
    <Spinner className="h-5 w-5 text-forest" />
    <span>{label}</span>
  </div>
);

interface EmptyStateProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  action,
}) => (
  <div className="rounded-2xl border border-dashed border-line bg-paper-surface/60 p-10 text-center shadow-warm-sm">
    <div
      className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-forest-soft text-forest text-xl font-display"
      aria-hidden="true"
    >
      ✦
    </div>
    <h3 className="font-display text-base sm:text-lg font-semibold text-ink">
      {title}
    </h3>
    {description && (
      <p className="mx-auto mt-1 max-w-sm text-xs sm:text-sm text-ink-muted leading-relaxed">
        {description}
      </p>
    )}
    {action && <div className="mt-5 flex justify-center">{action}</div>}
  </div>
);

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
  title?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  message,
  onRetry,
  title = 'Something went wrong',
}) => (
  <div
    role="alert"
    className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-[#f0c2b8] bg-coral-soft p-4 sm:p-5 text-xs sm:text-sm text-[#85291b] shadow-warm-sm"
  >
    <div className="min-w-0">
      <p className="font-bold text-xs uppercase tracking-wide">{title}</p>
      <p className="mt-0.5 text-xs sm:text-sm opacity-90">{message}</p>
    </div>
    {onRetry && (
      <button
        type="button"
        onClick={onRetry}
        className="rounded-lg border border-[#f0c2b8] bg-paper px-3 py-1.5 text-xs font-bold text-[#85291b] hover:bg-white shadow-warm-sm transition-all"
      >
        Try again
      </button>
    )}
  </div>
);
