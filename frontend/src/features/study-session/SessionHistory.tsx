import React, { useCallback, useState } from 'react';
import { Link } from '../../app/router';
import { EmptyState, ErrorState, LoadingState } from '../../components/ui/States';
import { useAsyncData } from '../../hooks/useAsyncData';
import { fetchCourseSessions } from '../../services/studySessionService';
import { formatIsoTimestamp } from '../../utils/config';
import { sessionPath } from './useStartSession';

/** Session history for a course: every past and in-progress session with outcome metrics. */
export const SessionHistory: React.FC<{ courseId: string; userId: string }> = ({
  courseId,
  userId,
}) => {
  const loader = useCallback(
    () => fetchCourseSessions(courseId, userId),
    [courseId, userId]
  );
  const { data, error, isLoading, reload } = useAsyncData(loader);
  const [filter, setFilter] = useState<'ALL' | 'ACTIVE' | 'COMPLETED'>('ALL');

  if (isLoading && !data) return <LoadingState label="Loading session history…" />;
  if (error && !data) return <ErrorState message={error} onRetry={() => void reload()} />;
  const sessions = (data ?? [])
    .filter((s) =>
      filter === 'ALL' ? true : filter === 'COMPLETED' ? s.state === 'COMPLETED' : s.state !== 'COMPLETED'
    )
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at));

  if ((data ?? []).length === 0) {
    return (
      <EmptyState
        title="No study sessions yet"
        description="Start a session from the Overview tab. Every session you run will be listed here with its score and adaptive evaluation summary."
      />
    );
  }

  return (
    <div data-testid="session-history" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="group" aria-label="Filter sessions" className="flex gap-1.5">
          {(['ALL', 'ACTIVE', 'COMPLETED'] as const).map((f) => (
            <button
              key={f}
              type="button"
              aria-pressed={filter === f}
              onClick={() => setFilter(f)}
              className={`rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
                filter === f
                  ? 'bg-forest text-paper shadow-warm-sm'
                  : 'border border-line bg-paper text-ink-muted hover:border-forest hover:text-ink'
              }`}
            >
              {f === 'ALL' ? 'All' : f === 'ACTIVE' ? 'In progress' : 'Completed'}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={() => void reload()}
          className="text-xs font-bold text-forest hover:underline"
        >
          Refresh Sessions
        </button>
      </div>

      {sessions.length === 0 ? (
        <p className="text-xs text-ink-muted">No sessions match this filter.</p>
      ) : (
        <ul className="space-y-3">
          {sessions.map((s) => {
            const done = s.state === 'COMPLETED';
            return (
              <li
                key={s.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-paper-surface p-5 shadow-warm-sm transition-all hover:border-forest/30"
              >
                <div className="min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-display text-sm sm:text-base font-semibold text-ink">
                      {s.concept_title}
                    </span>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                        done ? 'bg-sage-soft text-[#2d4c30]' : 'bg-forest-soft text-forest'
                      }`}
                    >
                      {done ? 'Completed' : 'In progress'}
                    </span>
                  </div>
                  <p className="text-xs text-ink-muted">
                    Started {formatIsoTimestamp(s.started_at)} • {s.progress.completed_activities_count} of{' '}
                    {s.progress.total_activities_generated} activities answered •{' '}
                    {s.progress.hints_used_count} hint(s)
                    {s.progress.average_score !== null ? ` • average score ${s.progress.average_score}/100` : ''}
                  </p>
                  {done && s.summary && (
                    <p className="text-xs text-ink-muted italic border-l-2 border-forest/30 pl-2 mt-1">
                      {s.summary.recommended_next_steps}
                    </p>
                  )}
                </div>
                <Link
                  to={sessionPath(s.course_id, s.id)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-paper px-3.5 py-1.5 text-xs font-bold text-forest hover:border-forest transition-colors shadow-warm-sm"
                >
                  <span>{done ? 'View summary' : 'Resume'}</span>
                  <span aria-hidden="true">→</span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};
