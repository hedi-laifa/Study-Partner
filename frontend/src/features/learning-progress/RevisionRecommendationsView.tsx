import React from 'react';
import { EmptyState } from '../../components/ui/States';
import type { CourseLearningProfile } from '../../types/learningProfile';
import { formatIsoTimestamp } from '../../utils/config';
import { activityLabel } from './labels';
import type { PracticeHandler } from './LearningProfileView';

interface RevisionViewProps {
  profile: CourseLearningProfile;
  canStartSession: boolean;
  busyConceptId: string | null;
  busyTaskId: string | null;
  onPractice: PracticeHandler;
  onUpdateTask: (taskId: string, status: 'COMPLETED' | 'DISMISSED') => void;
}

const PRIORITY_STYLE: Record<string, string> = {
  CRITICAL: 'bg-coral-soft text-[#85291b] border-[#f0c2b8]',
  HIGH: 'bg-coral-soft text-[#85291b] border-[#f0c2b8]',
  MEDIUM: 'bg-[#fdf8e9] text-[#7a5407] border-[#ead8a4]',
  LOW: 'bg-sage-soft text-[#244227] border-[#bed3c1]',
};

export const RevisionRecommendationsView: React.FC<RevisionViewProps> = ({
  profile,
  canStartSession,
  busyConceptId,
  busyTaskId,
  onPractice,
  onUpdateTask,
}) => {
  const pending = profile.revision_recommendations.filter((r) => r.status === 'PENDING');
  const done = profile.revision_recommendations.filter((r) => r.status !== 'PENDING');

  return (
    <div data-testid="revision-recommendations-view" className="space-y-6">
      {pending.length === 0 ? (
        <EmptyState
          title="No revision tasks due right now"
          description="Recommendations appear automatically based on spaced learning: remediation after mistakes, verification after hint usage, and spaced reviews after high scores."
        />
      ) : (
        <ul className="grid gap-4 md:grid-cols-2">
          {pending.map((task) => (
            <li
              key={task.id}
              className="flex flex-col justify-between gap-4 rounded-2xl border border-line bg-paper-surface p-5 sm:p-6 shadow-warm-sm transition-all hover:border-forest/30"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span
                    className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${PRIORITY_STYLE[task.priority] ?? PRIORITY_STYLE.LOW}`}
                  >
                    {task.priority} priority
                  </span>
                  <span className="text-xs font-bold text-forest">
                    {activityLabel(task.recommended_activity)}
                  </span>
                </div>
                <h3 className="font-display text-base font-semibold text-ink leading-snug">{task.title}</h3>
                <p className="text-xs text-ink-muted leading-relaxed">{task.reason}</p>
                {task.due_at && (
                  <p className="text-[11px] text-ink-muted">Due {formatIsoTimestamp(task.due_at)}</p>
                )}
              </div>
              <div className="flex flex-wrap items-center justify-end gap-2 border-t border-line/60 pt-3">
                <button
                  type="button"
                  disabled={busyTaskId === task.id}
                  onClick={() => onUpdateTask(task.id, 'DISMISSED')}
                  className="rounded-lg border border-line bg-paper px-3 py-1.5 text-xs font-semibold text-ink-muted hover:border-forest hover:text-ink disabled:opacity-50"
                >
                  Dismiss
                </button>
                <button
                  type="button"
                  disabled={busyTaskId === task.id}
                  onClick={() => onUpdateTask(task.id, 'COMPLETED')}
                  className="rounded-lg border border-line bg-paper px-3 py-1.5 text-xs font-semibold text-ink hover:border-forest disabled:opacity-50"
                >
                  {busyTaskId === task.id ? 'Saving…' : 'Mark complete'}
                </button>
                <button
                  type="button"
                  disabled={!canStartSession || busyConceptId === task.concept_id}
                  onClick={() => onPractice(task.concept_id, task.concept_title, task.recommended_activity)}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-forest px-3.5 py-1.5 text-xs font-bold text-paper shadow-warm-sm hover:bg-forest-hover disabled:opacity-50 transition-all"
                >
                  <span>{busyConceptId === task.concept_id ? 'Starting…' : 'Start activity'}</span>
                  <span aria-hidden="true">→</span>
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {done.length > 0 && (
        <section aria-labelledby="rev-done" className="space-y-3">
          <h3 id="rev-done" className="font-display text-base font-semibold text-ink">
            Completed or Dismissed ({done.length})
          </h3>
          <ul className="space-y-2">
            {done.map((task) => (
              <li
                key={task.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line bg-paper-surface px-4 py-2.5 text-xs text-ink-muted shadow-warm-sm"
              >
                <span>{task.title}</span>
                <span className="font-bold text-forest capitalize">{task.status.toLowerCase()}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
};
