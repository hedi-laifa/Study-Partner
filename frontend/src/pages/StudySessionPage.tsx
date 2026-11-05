import React from 'react';
import { AlertBanner } from '../components/ui/AlertBanner';
import { AssessmentFeedbackCard } from '../features/assessment';
import { useStudySession } from '../hooks/useStudySession';
import type { InteractiveSessionDetail } from '../types/studySession';

interface StudySessionPageProps {
  initialSession: InteractiveSessionDetail;
  userId: string;
  onExitSession: () => void;
  onOpenSource?: (documentId: string, page: number) => void;
}

export const StudySessionPage: React.FC<StudySessionPageProps> = ({
  initialSession,
  userId,
  onExitSession,
  onOpenSource,
}) => {
  const {
    session,
    answerDraft,
    setAnswerDraft,
    latestEvaluation,
    explanationTakeaways,
    isSubmitting,
    isRequestingHint,
    isRequestingExplanation,
    isAdvancing,
    isEnding,
    errorMessage,
    clearError,
    handleSubmitAnswer,
    handleRequestHint,
    handleRequestExplanation,
    handleNextActivity,
    handleEndSession,
  } = useStudySession({ initialSession, userId });

  const currentActivity = session.current_activity;
  const isCompleted = session.state === 'COMPLETED';
  const isFeedbackReady =
    session.state === 'FEEDBACK_READY' ||
    (currentActivity?.status === 'COMPLETED' && !isCompleted);

  const hintsUsedCount = currentActivity?.hints_used.length ?? 0;
  const maxHints = currentActivity?.total_hints_available ?? 3;
  const previousActivities = session.activity_history.filter(
    (item) => item.id !== currentActivity?.id || isCompleted
  );

  const difficultyBadgeColor = (diff: string) => {
    switch (diff.toUpperCase()) {
      case 'BASIC':
        return 'bg-sage-soft text-[#2d4c30] border-[#bed3c1]';
      case 'ADVANCED':
        return 'bg-coral-soft text-[#85291b] border-[#f0c2b8]';
      default:
        return 'bg-[#fdf8e9] text-[#7a5407] border-[#ead8a4]';
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header: Course & Concept Info, Session Goal, Exit & End Actions */}
      <div className="rounded-2xl border border-line bg-paper-surface p-6 sm:p-7 shadow-warm-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1.5 max-w-2xl">
            <div className="flex flex-wrap items-center gap-2 text-xs font-bold uppercase tracking-wider text-forest">
              <span>{session.course_title}</span>
              <span>•</span>
              <span>Interactive Study Session</span>
              <span
                className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${
                  isCompleted
                    ? 'border-sage/40 bg-sage-soft text-[#2d4c30]'
                    : 'border-forest/20 bg-forest-soft text-forest'
                }`}
              >
                {session.state}
              </span>
            </div>
            <h2 className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-ink">
              {session.concept_title}
            </h2>
            <p className="text-xs sm:text-sm text-ink-muted leading-relaxed">
              <span className="font-bold text-ink">Session Goal: </span>
              {session.learning_goal}
            </p>
            {session.concept_summary && (
              <p className="text-xs text-ink-muted leading-relaxed">{session.concept_summary}</p>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              type="button"
              onClick={onExitSession}
              className="rounded-lg border border-line bg-paper px-4 py-2 text-xs font-bold text-ink hover:border-forest transition-colors shadow-warm-sm"
            >
              {isCompleted ? 'Back to Course' : 'Save & Exit Session'}
            </button>
            {!isCompleted && (
              <button
                type="button"
                onClick={() => void handleEndSession()}
                disabled={isEnding}
                className="rounded-lg bg-coral px-4 py-2 text-xs font-bold text-white shadow-warm-sm hover:bg-coral-hover disabled:opacity-50 transition-all"
              >
                {isEnding ? 'Ending Session…' : 'End Session & View Summary'}
              </button>
            )}
          </div>
        </div>

        {/* Session Progress Strip */}
        <div className="mt-6 grid grid-cols-2 gap-3 border-t border-line/60 pt-4 sm:grid-cols-5">
          <div className="rounded-xl border border-line/70 bg-paper/60 px-3.5 py-2.5">
            <div className="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
              Current Activity
            </div>
            <div className="mt-0.5 font-display text-sm sm:text-base font-semibold text-ink">
              #{session.progress.current_activity_index} of{' '}
              {session.progress.total_activities_generated}
            </div>
          </div>

          <div className="rounded-xl border border-line/70 bg-paper/60 px-3.5 py-2.5">
            <div className="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
              Completed Questions
            </div>
            <div className="mt-0.5 font-display text-sm sm:text-base font-semibold text-ink">
              {session.progress.completed_activities_count} answered
            </div>
          </div>

          <div className="rounded-xl border border-line/70 bg-paper/60 px-3.5 py-2.5">
            <div className="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
              Adaptive Difficulty
            </div>
            <div className="mt-0.5">
              <span
                className={`inline-block rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${difficultyBadgeColor(
                  session.progress.current_difficulty
                )}`}
              >
                {session.progress.current_difficulty}
              </span>
            </div>
          </div>

          <div className="rounded-xl border border-line/70 bg-paper/60 px-3.5 py-2.5">
            <div className="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
              Hints &amp; Explanations
            </div>
            <div className="mt-0.5 text-xs font-semibold text-ink">
              {session.progress.hints_used_count} hint(s) •{' '}
              {session.progress.explanations_requested_count} expl.
            </div>
          </div>

          <div className="rounded-xl border border-line/70 bg-paper/60 px-3.5 py-2.5">
            <div className="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
              Average Score
            </div>
            <div className="mt-0.5 font-display text-sm sm:text-base font-bold text-forest">
              {session.progress.average_score !== null
                ? `${session.progress.average_score} / 100`
                : 'Not graded yet'}
            </div>
          </div>
        </div>
      </div>

      {errorMessage && (
        <AlertBanner
          variant="error"
          title="Study Session Notice"
          message={errorMessage}
          onDismiss={clearError}
        />
      )}

      {/* Session Summary View (when COMPLETED) */}
      {isCompleted && session.summary && (
        <div className="rounded-2xl border-2 border-sage/60 bg-paper-surface p-6 sm:p-8 shadow-warm-md space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line/60 pb-5">
            <div>
              <span className="inline-block rounded-full bg-sage-soft px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-[#2d4c30]">
                Session Complete
              </span>
              <h3 className="font-display text-xl sm:text-2xl font-bold text-ink mt-1.5">
                Learning Session Summary: {session.summary.concept_title}
              </h3>
              <p className="text-xs text-ink-muted mt-0.5">
                Goal: {session.summary.learning_goal}
              </p>
            </div>
            <div className="rounded-2xl bg-forest-soft border border-forest/20 px-6 py-4 text-center shadow-warm-sm">
              <div className="text-[10px] font-bold uppercase tracking-wider text-forest">
                Overall Session Score
              </div>
              <div className="font-display text-3xl font-extrabold text-forest mt-0.5">
                {session.summary.average_score} / 100
              </div>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-xl border border-sage/40 bg-sage-soft/60 p-5">
              <h4 className="text-xs font-bold uppercase tracking-wider text-[#244227] mb-2 flex items-center gap-1.5">
                <span>✓</span>
                <span>Demonstrated Strengths</span>
              </h4>
              <ul className="list-inside list-disc space-y-1.5 text-xs text-ink">
                {session.summary.strengths.map((s, idx) => (
                  <li key={idx} className="leading-relaxed">{s}</li>
                ))}
              </ul>
            </div>

            <div className="rounded-xl border border-coral/30 bg-coral-soft/50 p-5">
              <h4 className="text-xs font-bold uppercase tracking-wider text-[#85291b] mb-2 flex items-center gap-1.5">
                <span>!</span>
                <span>Areas for Review</span>
              </h4>
              <ul className="list-inside list-disc space-y-1.5 text-xs text-ink">
                {session.summary.areas_for_improvement.map((g, idx) => (
                  <li key={idx} className="leading-relaxed">{g}</li>
                ))}
              </ul>
            </div>
          </div>

          <div className="rounded-xl border border-line bg-paper p-5 space-y-2.5">
            <h4 className="text-[11px] font-bold uppercase tracking-wider text-ink-muted">
              Key Takeaways &amp; Recommended Next Steps
            </h4>
            <ul className="list-inside list-disc space-y-1 text-xs text-ink">
              {session.summary.key_takeaways.map((t, idx) => (
                <li key={idx} className="leading-relaxed">{t}</li>
              ))}
            </ul>
            <p className="pt-2 text-xs font-bold text-forest">
              Next Step: {session.summary.recommended_next_steps}
            </p>
          </div>
        </div>
      )}

      {/* Active Question Workspace (when session is NOT completed) */}
      {!isCompleted && currentActivity && (
        <div className="rounded-2xl border border-line bg-paper-surface p-6 sm:p-7 shadow-warm-sm space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line/60 pb-4">
            <div className="flex items-center gap-2">
              <span className="rounded-md bg-forest-soft px-3 py-1 text-xs font-bold text-forest">
                {currentActivity.activity_type === 'DIAGNOSTIC_QUESTION'
                  ? 'Diagnostic Question'
                  : currentActivity.activity_type.replace(/_/g, ' ')}
              </span>
              <span
                className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${difficultyBadgeColor(
                  currentActivity.difficulty
                )}`}
              >
                {currentActivity.difficulty}
              </span>
            </div>

            {currentActivity.relevant_pages.length > 0 && (
              <span className="text-xs font-medium text-ink-muted">
                Grounded in PDF Page(s):{' '}
                <strong className="text-forest">
                  {currentActivity.relevant_pages.join(', ')}
                </strong>
              </span>
            )}
          </div>

          {/* Question Prompt */}
          <div className="rounded-2xl border border-forest/20 bg-forest-soft/50 p-5 sm:p-6 shadow-warm-sm">
            <p className="font-display text-base sm:text-lg font-semibold leading-relaxed text-ink">
              {currentActivity.prompt_text}
            </p>
          </div>

          {/* Source references grounding this question */}
          {currentActivity.source_excerpts.length > 0 && (
            <section
              data-testid="session-sources"
              aria-label="Source references"
              className="space-y-2 rounded-xl border border-line bg-paper p-4"
            >
              <h4 className="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
                Grounded Source Passages
              </h4>
              <ul className="space-y-2.5">
                {currentActivity.source_excerpts.map((src, idx) => (
                  <li key={`${src.document_id}-${idx}`} className="text-xs text-ink leading-relaxed">
                    <div className="flex flex-wrap items-center gap-2 font-medium">
                      <span className="font-bold text-forest">{src.filename}</span>
                      <span className="rounded bg-paper-deep px-1.5 py-0.5 font-mono text-[11px] text-ink-muted">
                        {src.page_start === src.page_end
                          ? `p. ${src.page_start}`
                          : `pp. ${src.page_start}-${src.page_end}`}
                      </span>
                      {onOpenSource && (
                        <button
                          type="button"
                          onClick={() => onOpenSource(src.document_id, src.page_start)}
                          className="font-bold text-forest hover:underline"
                        >
                          Open in PDF →
                        </button>
                      )}
                    </div>
                    <p className="mt-1 italic text-ink-muted">{src.excerpt}</p>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Support Toolbar: Graduated Hint Button & Request Explanation Button */}
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => void handleRequestHint()}
              disabled={
                isRequestingHint ||
                isFeedbackReady ||
                hintsUsedCount >= maxHints
              }
              className="inline-flex items-center gap-1.5 rounded-xl border border-coral/30 bg-coral-soft px-4 py-2 text-xs font-bold text-[#85291b] hover:bg-coral-soft/80 transition-colors disabled:opacity-50 shadow-warm-sm"
            >
              <span>
                {isRequestingHint
                  ? 'Loading Hint…'
                  : hintsUsedCount >= maxHints
                    ? `All Hints Used (${hintsUsedCount}/${maxHints})`
                    : `Get Graduated Hint (${hintsUsedCount}/${maxHints})`}
              </span>
            </button>

            <button
              type="button"
              onClick={() => void handleRequestExplanation()}
              disabled={isRequestingExplanation}
              className="inline-flex items-center gap-1.5 rounded-xl border border-line bg-paper px-4 py-2 text-xs font-bold text-forest hover:border-forest transition-colors disabled:opacity-50 shadow-warm-sm"
            >
              <span>
                {isRequestingExplanation
                  ? 'Generating Explanation…'
                  : 'Request Concept Explanation'}
              </span>
            </button>
          </div>

          {/* Revealed Graduated Hints */}
          {currentActivity.hints_used.length > 0 && (
            <div className="rounded-xl border border-coral/30 bg-coral-soft/60 p-4 space-y-2">
              <div className="text-[10px] font-bold uppercase tracking-wider text-[#85291b]">
                Graduated Reasoning Hints ({currentActivity.hints_used.length} of{' '}
                {maxHints})
              </div>
              <ol className="list-decimal space-y-1.5 pl-4 text-xs text-[#85291b]">
                {currentActivity.hints_used.map((hint, idx) => (
                  <li key={idx} className="leading-relaxed font-medium">
                    {hint}
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* Requested Concise Explanation */}
          {currentActivity.explanation_requested && (
            <div className="rounded-xl border border-lilac/30 bg-lilac-soft/60 p-4 space-y-2">
              <div className="text-[10px] font-bold uppercase tracking-wider text-[#524474]">
                Grounded Concept Explanation
              </div>
              <p className="text-xs sm:text-sm leading-relaxed text-ink">
                {currentActivity.explanation_requested}
              </p>
              {explanationTakeaways.length > 0 && (
                <ul className="list-inside list-disc space-y-1 text-xs text-ink">
                  {explanationTakeaways.map((takeaway, idx) => (
                    <li key={idx}>{takeaway}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* Student Answer Input & Submit Button */}
          <div className="space-y-3">
            <label
              htmlFor="student-session-answer"
              className="block text-xs font-bold uppercase tracking-wider text-ink-muted"
            >
              Your Reasoning &amp; Answer
            </label>
            <textarea
              id="student-session-answer"
              rows={4}
              value={answerDraft}
              disabled={isSubmitting || isFeedbackReady}
              onChange={(e) => setAnswerDraft(e.target.value)}
              placeholder="Explain your conceptual reasoning step by step based on your course readings…"
              className="w-full rounded-xl border border-line bg-surface p-4 text-xs sm:text-sm text-ink outline-none transition-all placeholder:text-ink-subtle focus:border-forest focus:ring-2 focus:ring-forest/15 disabled:bg-paper-deep"
            />

            {!isFeedbackReady && (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span className="text-xs text-ink-muted">
                  Tip: Explain both the core mechanism and why it behaves that way.
                </span>
                <button
                  type="button"
                  onClick={() => void handleSubmitAnswer()}
                  disabled={isSubmitting || !answerDraft.trim()}
                  className="inline-flex items-center gap-2 rounded-xl bg-forest px-6 py-2.5 text-xs sm:text-sm font-bold text-paper shadow-warm-sm hover:bg-forest-hover disabled:opacity-50 transition-all transform hover:-translate-y-0.5"
                >
                  <span>{isSubmitting ? 'Evaluating Answer…' : 'Submit Answer'}</span>
                  <span aria-hidden="true">→</span>
                </button>
              </div>
            )}
          </div>

          {/* Rubric Feedback & Next Activity Card */}
          {isFeedbackReady &&
            (latestEvaluation ||
              currentActivity.attempts[currentActivity.attempts.length - 1]
                ?.evaluation) &&
            (() => {
              const evalItem =
                latestEvaluation ||
                currentActivity.attempts[currentActivity.attempts.length - 1]
                  ?.evaluation;
              if (!evalItem) return null;
              return (
                <AssessmentFeedbackCard
                  evaluation={evalItem}
                  coachRecommendation={session.coach_recommendation}
                  isEnding={isEnding}
                  isAdvancing={isAdvancing}
                  onEndSession={() => void handleEndSession()}
                  onNextActivity={(requestedOverride) =>
                    void handleNextActivity(requestedOverride)
                  }
                />
              );
            })()}
        </div>
      )}

      {/* Previous Activity History */}
      <section className="rounded-2xl border border-line bg-paper-surface p-6 sm:p-7 shadow-warm-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line/60 pb-3">
          <h3 className="font-display text-base sm:text-lg font-semibold text-ink">
            Session Activity History ({previousActivities.length})
          </h3>
          <span className="text-xs text-ink-muted">
            Chronological record of attempts, hints, and rubric evaluations
          </span>
        </div>

        {previousActivities.length === 0 ? (
          <p className="text-xs text-ink-muted">
            Complete your current question to see your activity history recorded here.
          </p>
        ) : (
          <div className="space-y-3">
            {previousActivities.map((act) => {
              const latestAtt = act.attempts[act.attempts.length - 1];
              return (
                <div
                  key={act.id}
                  className="rounded-xl border border-line bg-paper p-4 space-y-2.5 shadow-warm-sm"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-display text-xs font-bold text-ink">
                        Activity #{act.order_index + 1}
                      </span>
                      <span className="rounded bg-paper-deep px-2 py-0.5 text-[10px] font-bold text-ink-muted">
                        {act.activity_type}
                      </span>
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${difficultyBadgeColor(
                          act.difficulty
                        )}`}
                      >
                        {act.difficulty}
                      </span>
                    </div>
                    {latestAtt?.evaluation && (
                      <div className="flex items-center gap-2">
                        <span className="rounded-full bg-forest-soft px-2.5 py-0.5 text-[10px] font-bold text-forest">
                          {latestAtt.evaluation.verdict}
                        </span>
                        <span className="text-xs font-bold text-forest">
                          Score: {latestAtt.evaluation.total_score} / 100
                        </span>
                      </div>
                    )}
                  </div>

                  <p className="text-xs font-semibold text-ink leading-relaxed">
                    Q: {act.prompt_text}
                  </p>

                  {latestAtt ? (
                    <div className="space-y-1.5 border-t border-line/60 pt-2 text-xs">
                      <p className="text-ink-muted leading-relaxed">
                        <strong className="text-ink">Your Answer: </strong>
                        {latestAtt.attempt.response_text}
                      </p>
                      {latestAtt.evaluation && (
                        <>
                          <p className="text-forest leading-relaxed">
                            <strong>Feedback: </strong>
                            {latestAtt.evaluation.overall_feedback}
                          </p>
                          {latestAtt.evaluation.misconception && (
                            <p className="text-coral leading-relaxed">
                              <strong>Supported Misconception: </strong>
                              {latestAtt.evaluation.misconception}
                            </p>
                          )}
                        </>
                      )}
                    </div>
                  ) : (
                    <p className="text-xs italic text-ink-muted">
                      Status: {act.status}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
};
