import React, { useCallback, useEffect, useState } from 'react';
import {
  fetchCourseConcepts,
  fetchCourseSessions,
  startStudySession,
} from '../../services/studySessionService';
import type {
  CourseConcept,
  InteractiveSessionDetail,
} from '../../types/studySession';

interface StudySessionLauncherProps {
  courseId: string;
  userId: string;
  hasReadyDocuments: boolean;
  onLaunchSession: (session: InteractiveSessionDetail) => void;
}

export const StudySessionLauncher: React.FC<StudySessionLauncherProps> = ({
  courseId,
  userId,
  hasReadyDocuments,
  onLaunchSession,
}) => {
  const [concepts, setConcepts] = useState<CourseConcept[]>([]);
  const [pastSessions, setPastSessions] = useState<InteractiveSessionDetail[]>(
    []
  );
  const [selectedConceptId, setSelectedConceptId] = useState<string>('');
  const [learningGoal, setLearningGoal] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isStarting, setIsStarting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadWorkspaceData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [conceptList, sessionList] = await Promise.all([
        fetchCourseConcepts(courseId, userId),
        fetchCourseSessions(courseId, userId),
      ]);
      setConcepts(conceptList);
      setPastSessions(sessionList);
      if (conceptList.length > 0 && !selectedConceptId) {
        setSelectedConceptId(conceptList[0].id);
      }
      setErrorMessage(null);
    } catch (err) {
      setErrorMessage(
        err instanceof Error
          ? err.message
          : 'Failed to load study session concepts.'
      );
    } finally {
      setIsLoading(false);
    }
  }, [courseId, selectedConceptId, userId]);

  useEffect(() => {
    void loadWorkspaceData();
  }, [loadWorkspaceData, hasReadyDocuments]);

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isStarting) return;
    setIsStarting(true);
    setErrorMessage(null);
    try {
      const session = await startStudySession({
        courseId,
        userId,
        conceptId: selectedConceptId || null,
        learningGoal: learningGoal.trim() || undefined,
      });
      onLaunchSession(session);
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : 'Unable to start study session.'
      );
    } finally {
      setIsStarting(false);
    }
  };

  return (
    <section className="rounded-2xl border border-line bg-paper-surface p-6 sm:p-7 shadow-warm-sm space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
        <div>
          <span className="inline-block rounded-full bg-forest-soft px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-forest mb-1.5">
            Interactive Diagnostic Practice
          </span>
          <h3 className="font-display text-lg sm:text-xl font-semibold tracking-tight text-ink">
            Launch Guided Study Session
          </h3>
          <p className="text-xs text-ink-muted leading-relaxed mt-0.5">
            Select an extracted course concept or set a personal goal. The AI Tutor presents one diagnostic question at a time with graduated hints and rubric grading.
          </p>
        </div>
      </div>

      {errorMessage && (
        <div className="rounded-xl border border-[#f0c2b8] bg-coral-soft p-4 text-xs font-semibold text-[#85291b]">
          {errorMessage}
        </div>
      )}

      {!hasReadyDocuments && (
        <div className="rounded-xl border border-[#ead8a4] bg-[#fdf8e9] p-4 text-xs text-[#7a5407] leading-relaxed">
          Upload a course PDF in the Documents tab so the AI Tutor can ground your diagnostic questions in your actual course material.
        </div>
      )}

      <form onSubmit={(e) => void handleStart(e)} className="grid gap-4 sm:grid-cols-12">
        <div className="sm:col-span-5">
          <label
            htmlFor="concept-select"
            className="block text-xs font-bold uppercase tracking-wider text-ink-muted mb-1.5"
          >
            1. Select Course Concept
          </label>
          <select
            id="concept-select"
            value={selectedConceptId}
            onChange={(e) => setSelectedConceptId(e.target.value)}
            disabled={isLoading || isStarting}
            className="w-full rounded-xl border border-line bg-surface px-3.5 py-2.5 text-xs sm:text-sm text-ink outline-none transition-all focus:border-forest focus:ring-2 focus:ring-forest/15"
          >
            {concepts.length === 0 ? (
              <option value="">General Course Foundations (or custom goal)</option>
            ) : (
              concepts.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}{' '}
                  {c.source_pages.length > 0
                    ? `(p. ${c.source_pages.join(', ')})`
                    : ''}
                </option>
              ))
            )}
          </select>
        </div>

        <div className="sm:col-span-4">
          <label
            htmlFor="learning-goal-input"
            className="block text-xs font-bold uppercase tracking-wider text-ink-muted mb-1.5"
          >
            2. Learning Goal (optional)
          </label>
          <input
            id="learning-goal-input"
            type="text"
            value={learningGoal}
            onChange={(e) => setLearningGoal(e.target.value)}
            disabled={isStarting}
            placeholder="e.g. Master leader election timeouts"
            className="w-full rounded-xl border border-line bg-surface px-3.5 py-2.5 text-xs sm:text-sm text-ink outline-none transition-all placeholder:text-ink-subtle focus:border-forest focus:ring-2 focus:ring-forest/15"
          />
        </div>

        <div className="flex items-end sm:col-span-3">
          <button
            type="submit"
            disabled={isStarting}
            className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-forest px-4 py-2.5 text-xs sm:text-sm font-bold text-paper shadow-warm-sm transition-all hover:bg-forest-hover disabled:opacity-50"
          >
            <span>{isStarting ? 'Starting…' : 'Start Session'}</span>
            <span aria-hidden="true">→</span>
          </button>
        </div>
      </form>

      {/* Previous & Resumable Study Sessions */}
      {pastSessions.length > 0 && (
        <div className="border-t border-line/60 pt-5 space-y-3">
          <div className="text-[11px] font-bold uppercase tracking-wider text-ink-muted">
            Recent Study Sessions in this Course ({pastSessions.length})
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {pastSessions.slice(0, 6).map((sess) => {
              const isDone = sess.state === 'COMPLETED';
              return (
                <div
                  key={sess.id}
                  className="flex items-center justify-between gap-3 rounded-xl border border-line bg-paper/60 p-3.5 hover:border-forest/30 transition-colors"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-display text-xs sm:text-sm font-semibold text-ink">
                        {sess.concept_title}
                      </span>
                      <span
                        className={`rounded px-1.5 py-0.5 text-[9px] font-bold ${
                          isDone
                            ? 'bg-sage-soft text-[#2d4c30]'
                            : 'bg-forest-soft text-forest'
                        }`}
                      >
                        {sess.state}
                      </span>
                    </div>
                    <p className="truncate text-[11px] text-ink-muted mt-0.5">
                      {sess.progress.completed_activities_count} activities answered •{' '}
                      Difficulty: {sess.progress.current_difficulty}
                      {sess.progress.average_score !== null
                        ? ` • Avg: ${sess.progress.average_score}/100`
                        : ''}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onLaunchSession(sess)}
                    className="shrink-0 rounded-lg border border-line bg-paper-surface px-3 py-1.5 text-xs font-bold text-forest hover:border-forest shadow-warm-sm transition-colors"
                  >
                    {isDone ? 'View Summary' : 'Resume'}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
};
