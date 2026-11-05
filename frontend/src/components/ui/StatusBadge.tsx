import React from 'react';
import type { DocumentProcessingStatus } from '../../types/course';

interface StatusBadgeProps {
  label: string;
  variant: 'healthy' | 'warning' | 'offline';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ label, variant }) => {
  const styles: Record<StatusBadgeProps['variant'], string> = {
    healthy: 'bg-sage-soft text-[#2d4c30] border-[#bed3c1]',
    warning: 'bg-[#fbf3db] text-[#855e0c] border-[#ead8a4]',
    offline: 'bg-coral-soft text-[#943122] border-[#f1c1b7]',
  };

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${styles[variant]}`}
    >
      {label}
    </span>
  );
};

interface DocumentStatusBadgeProps {
  status: DocumentProcessingStatus;
}

export const DocumentStatusBadge: React.FC<DocumentStatusBadgeProps> = ({
  status,
}) => {
  switch (status) {
    case 'READY':
      return <StatusBadge label="Ready" variant="healthy" />;
    case 'PROCESSING':
    case 'UPLOADED':
      return <StatusBadge label="Processing" variant="warning" />;
    case 'FAILED':
      return <StatusBadge label="Extraction Failed" variant="offline" />;
    default:
      return <StatusBadge label={status} variant="warning" />;
  }
};
