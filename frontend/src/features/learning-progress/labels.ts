import type {
  CoachActivityType,
  EvidenceStatus,
  MasteryStatus,
} from '../../types/learningProfile';

export const MASTERY_BADGES: Record<
  MasteryStatus,
  { label: string; className: string }
> = {
  MASTERED: {
    label: 'Mastered',
    className: 'bg-emerald-100 text-emerald-900 border-emerald-300',
  },
  LEARNING: {
    label: 'Learning',
    className: 'bg-indigo-100 text-indigo-900 border-indigo-300',
  },
  NEEDS_REVIEW: {
    label: 'Needs review',
    className: 'bg-amber-100 text-amber-900 border-amber-300',
  },
  NOT_STARTED: {
    label: 'Not started',
    className: 'bg-slate-100 text-slate-700 border-slate-300',
  },
};

export const EVIDENCE_BADGES: Record<
  EvidenceStatus,
  { label: string; className: string }
> = {
  NO_EVIDENCE: {
    label: 'No evidence yet',
    className: 'bg-slate-100 text-slate-700 border-slate-200',
  },
  MISCONCEPTION_DETECTED: {
    label: 'Misconception flagged',
    className: 'bg-rose-100 text-rose-900 border-rose-300',
  },
  NEEDS_FOUNDATION: {
    label: 'Needs foundation',
    className: 'bg-rose-50 text-rose-800 border-rose-200',
  },
  PARTIAL_EVIDENCE: {
    label: 'Partial evidence',
    className: 'bg-amber-100 text-amber-900 border-amber-300',
  },
  ASSISTED_PROFICIENCY: {
    label: 'Hint-assisted',
    className: 'bg-purple-100 text-purple-900 border-purple-300',
  },
  EMERGING_EVIDENCE: {
    label: 'Emerging independent evidence',
    className: 'bg-blue-100 text-blue-900 border-blue-300',
  },
  STRONG_INDEPENDENT_EVIDENCE: {
    label: 'Strong independent evidence',
    className: 'bg-emerald-100 text-emerald-900 border-emerald-300',
  },
  DUE_FOR_REVIEW: {
    label: 'Due for review',
    className: 'bg-amber-100 text-amber-900 border-amber-300',
  },
};

export const ACTIVITY_LABELS: Record<CoachActivityType, string> = {
  EXPLANATION: 'Guided explanation',
  DIAGNOSTIC_QUESTION: 'Diagnostic question',
  EASIER_PRACTICE: 'Easier practice',
  TARGETED_PRACTICE: 'Targeted practice',
  HINT_AND_RETRY: 'Hint & retry',
  HARDER_PRACTICE: 'Harder practice',
  TRANSFER_QUESTION: 'Transfer question',
  REVIEW: 'Spaced review',
};

export function activityLabel(type: string): string {
  return (
    (ACTIVITY_LABELS as Record<string, string>)[type] ??
    type.replace(/_/g, ' ').toLowerCase()
  );
}

/** Concepts that most need attention first. */
export function practicePriority(status: MasteryStatus, score: number): number {
  const base: Record<MasteryStatus, number> = {
    NEEDS_REVIEW: 0,
    LEARNING: 1,
    NOT_STARTED: 2,
    MASTERED: 3,
  };
  return base[status] * 1000 + score;
}
