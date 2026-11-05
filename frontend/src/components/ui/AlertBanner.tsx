import React from 'react';

interface AlertBannerProps {
  variant: 'error' | 'warning' | 'success' | 'info';
  title?: string;
  message: string;
  onDismiss?: () => void;
}

export const AlertBanner: React.FC<AlertBannerProps> = ({
  variant,
  title,
  message,
  onDismiss,
}) => {
  const styles: Record<AlertBannerProps['variant'], string> = {
    error: 'border-[#f0c2b8] bg-coral-soft text-[#85291b]',
    warning: 'border-[#ead8a4] bg-[#fdf8e9] text-[#7a5407]',
    success: 'border-[#bed3c1] bg-sage-soft text-[#244227]',
    info: 'border-[#d6cce8] bg-lilac-soft text-[#524474]',
  };

  return (
    <div
      role="alert"
      className={`flex items-start justify-between gap-4 rounded-xl border p-4 text-xs sm:text-sm shadow-warm-sm ${styles[variant]}`}
    >
      <div className="min-w-0">
        {title && <p className="font-bold text-xs uppercase tracking-wide">{title}</p>}
        <p className={title ? 'mt-1' : ''}>{message}</p>
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="rounded px-2 py-0.5 text-xs font-semibold opacity-75 hover:opacity-100 hover:bg-black/5"
        >
          Dismiss
        </button>
      )}
    </div>
  );
};
