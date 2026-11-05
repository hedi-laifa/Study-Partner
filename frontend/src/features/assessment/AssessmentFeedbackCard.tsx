import React, { useState } from 'react';
import type {
  CoachActivityType,
  CoachRecommendation,
} from '../../types/learningProfile';
import type { EvaluationRecord } from '../../types/studySession';

interface AssessmentFeedbackCardProps {
  evaluation: EvaluationRecord;
  coachRecommendation?: CoachRecommendation | null;
  isEnding?: boolean;
  isAdvancing?: boolean;
  onEndSession?: () => void;
  onNextActivity?: (requestedActivityType?: CoachActivityType | null) => void;
}

const VERDICT_CONFIG: Record<
  string,
  { label: string; badgeClass: string; borderClass: string }
> = {
  CORRECT: {
    label: 'Correct',
    badgeClass: 'bg-sage-soft text-[#2d4c30] border-[#bed3c1]',
    borderClass: 'border-[#bed3c1] bg-sage-soft/30',
  },
  PARTIALLY_CORRECT: {
    label: 'Partially Correct',
    badgeClass: 'bg-[#fbf3db] text-[#855e0c] border-[#ead8a4]',
    borderClass: 'border-[#ead8a4] bg-[#fdf8e9]/40',
  },
  INCORRECT: {
    label: 'Incorrect',
    badgeClass: 'bg-coral-soft text-[#943122] border-[#f1c1b7]',
    borderClass: 'border-[#f1c1b7] bg-coral-soft/30',
  },
  OFF_TOPIC: {
    label: 'Off-Topic',
    badgeClass: 'bg-paper-deep text-ink-muted border-line',
    borderClass: 'border-line bg-paper-deep/50',
  },
  INSUFFICIENT_EVIDENCE: {
    label: 'Insufficient Evidence',
    badgeClass: 'bg-lilac-soft text-[#5c4e7c] border-[#d6cce8]',
    borderClass: 'border-[#d6cce8] bg-lilac-soft/30',
  },
};

const ERROR_TYPE_LABELS: Record<string, string> = {
  NONE: 'Full Conceptual Alignment',
  INCOMPLETE_REASONING: 'Incomplete Reasoning (Missing Steps)',
  FACTUAL_MISTAKE: 'Factual Mistake Detected',
  CALCULATION_ERROR: 'Deterministic Calculation Error',
  AMBIGUOUS_OR_VAGUE: 'Ambiguous or Vague Response',
  OFF_TOPIC: 'Unrelated to Course Concept',
};

const NEXT_ACTIVITY_LABELS: Record<string, string> = {
  EXPLANATION: 'Guided Explanation & Check',
  DIAGNOSTIC_QUESTION: 'Diagnostic Question',
  EASIER_PRACTICE: 'Easier Practice',
  TARGETED_PRACTICE: 'Targeted Practice',
  HINT_AND_RETRY: 'Hint & Retry',
  HARDER_PRACTICE: 'Harder Practice',
  TRANSFER_QUESTION: 'Transfer Question',
  REVIEW: 'Spaced Review',
  ADVANCE_DIFFICULTY: 'Advance to Higher-Difficulty Activity',
  PRACTICE_SAME_CONCEPT: 'Practice Another Question on This Concept',
  REMEDIATION_EXPLANATION: 'Review Concept Explanation & Remediate',
  CLARIFY_AMBIGUOUS_ANSWER: 'Clarify Reasoning with Specific Mechanisms',
  REFOCUS_ON_COURSE_CONCEPT: 'Refocus on Target Course Concept',
};

export const AssessmentFeedbackCard: React.FC<AssessmentFeedbackCardProps> = ({
  evaluation,
  coachRecommendation,
  isEnding = false,
  isAdvancing = false,
  onEndSession,
  onNextActivity,
}) => {
  const [selectedOverride, setSelectedOverride] =
    useState<CoachActivityType | null>(null);

  const verdictKey = (evaluation.verdict || 'INCORRECT').toUpperCase();
  const verdictMeta = VERDICT_CONFIG[verdictKey] || VERDICT_CONFIG.INCORRECT;

  const strengths =
    evaluation.strengths?.length > 0
      ? evaluation.strengths
      : evaluation.strengths_json || [];
  const missingIdeas =
    evaluation.gaps?.length > 0 ? evaluation.gaps : evaluation.gaps_json || [];
  const evidenceItems =
    evaluation.evidence?.length > 0
      ? evaluation.evidence
      : evaluation.evidence_json || [];
  const scoreValue =
    typeof evaluation.rubric_score === 'number'
      ? evaluation.rubric_score
      : evaluation.total_score;
  const confidencePct = Math.round((evaluation.confidence ?? 0.85) * 100);
  const errorLabel =
    ERROR_TYPE_LABELS[evaluation.error_classification || 'NONE'] ||
    evaluation.error_classification;

  const activeActivityType: CoachActivityType | undefined =
    selectedOverride ?? coachRecommendation?.recommended_activity;
  const suggestedNextActivityLabel = activeActivityType
    ? NEXT_ACTIVITY_LABELS[activeActivityType] ||
      activeActivityType.replace(/_/g, ' ')
    : evaluation.next_activity
      ? NEXT_ACTIVITY_LABELS[evaluation.next_activity] ||
        evaluation.next_activity.replace(/_/g, ' ')
      : 'Continue Guided Practice';

  return (
    <div
      data-testid="assessment-feedback-card"
      className={`rounded-2xl border-2 p-6 sm:p-7 space-y-5 shadow-warm-sm ${verdictMeta.borderClass}`}
    >
      {/* Header: Verdict Badge, Confidence & Rubric Score */}
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line/60 pb-4">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span
              data-testid="assessment-verdict-badge"
              className={`inline-block rounded-full border px-3.5 py-1 text-xs font-bold uppercase tracking-wider ${verdictMeta.badgeClass}`}
            >
              Verdict: {verdictMeta.label}
            </span>

            {evaluation.error_classification &&
              evaluation.error_classification !== 'NONE' && (
                <span className="inline-block rounded-md border border-line bg-paper-surface px-2.5 py-0.5 text-xs font-semibold text-ink-muted">
                  {errorLabel}
                </span>
              )}

            <span
              className={`inline-block rounded-md border px-2.5 py-0.5 text-[11px] font-semibold ${
                evaluation.uncertain_evaluation
                  ? 'border-lilac/40 bg-lilac-soft text-[#5c4e7c]'
                  : 'border-line bg-paper-surface text-ink-muted'
              }`}
            >
              Confidence: {confidencePct}%
              {evaluation.uncertain_evaluation ? ' (Uncertain Evaluation)' : ''}
            </span>
          </div>

          <h4 className="font-display text-lg font-semibold tracking-tight text-ink">
            Assessment Agent Rubric Evaluation
          </h4>
        </div>

        <div className="rounded-xl border border-line bg-paper-surface px-5 py-3 text-right shadow-warm-sm">
          <div className="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
            Rubric Score
          </div>
          <div className="font-display text-2xl font-bold text-forest">
            {scoreValue} / {evaluation.max_score}
          </div>
        </div>
      </div>

      {/* Feedback Explanation */}
      <div className="rounded-xl border border-line bg-paper-surface p-4 shadow-warm-sm">
        <div className="text-[10px] font-bold uppercase tracking-wider text-ink-muted mb-1">
          Detailed Evaluator Feedback
        </div>
        <p
          data-testid="assessment-feedback-text"
          className="text-xs sm:text-sm leading-relaxed text-ink"
        >
          {evaluation.overall_feedback}
        </p>
      </div>

      {/* Supported Misconception Alert (Rendered ONLY when supported by evidence) */}
      {evaluation.misconception && (
        <div
          data-testid="assessment-misconception-box"
          className="rounded-xl border-2 border-coral/50 bg-coral-soft p-4 space-y-1.5 shadow-warm-sm"
        >
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#85291b]">
            <span>Supported Misconception Detected</span>
          </div>
          <p className="text-xs font-semibold text-[#85291b]">
            {evaluation.misconception}
          </p>
          {evidenceItems.length > 0 && (
            <div className="pt-1 text-[11px] text-[#85291b]/90">
              <span className="font-bold">Supporting Evidence: </span>
              {evidenceItems[0]}
            </div>
          )}
        </div>
      )}

      {/* Strengths (Correct Concepts) & Missing Ideas (Gaps) */}
      <div className="grid gap-4 sm:grid-cols-2">
        <div
          data-testid="assessment-strengths-box"
          className="rounded-xl border border-sage/40 bg-sage-soft/70 p-4"
        >
          <h5 className="text-xs font-bold uppercase tracking-wider text-[#244227] mb-2 flex items-center gap-1.5">
            <span>✓</span>
            <span>Strengths (Verified Concepts)</span>
          </h5>
          {strengths.length > 0 ? (
            <ul className="list-inside list-disc space-y-1 text-xs text-ink">
              {strengths.map((s, idx) => (
                <li key={idx} className="leading-relaxed">{s}</li>
              ))}
            </ul>
          ) : (
            <p className="text-xs italic text-ink-muted">
              No specific required concepts verified yet.
            </p>
          )}
        </div>

        <div
          data-testid="assessment-gaps-box"
          className="rounded-xl border border-coral/30 bg-coral-soft/50 p-4"
        >
          <h5 className="text-xs font-bold uppercase tracking-wider text-[#85291b] mb-2 flex items-center gap-1.5">
            <span>!</span>
            <span>Missing Ideas &amp; Gaps</span>
          </h5>
          {missingIdeas.length > 0 ? (
            <ul className="list-inside list-disc space-y-1 text-xs text-ink">
              {missingIdeas.map((g, idx) => (
                <li key={idx} className="leading-relaxed">{g}</li>
              ))}
            </ul>
          ) : (
            <p className="text-xs italic text-ink-muted">
              All required rubric concepts were addressed!
            </p>
          )}
        </div>
      </div>

      {/* Rubric Criterion Breakdown */}
      {evaluation.criteria_scores_json.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {evaluation.criteria_scores_json.map((crit, idx) => (
            <div
              key={idx}
              className="rounded-xl border border-line bg-paper-surface p-3.5 shadow-warm-sm"
            >
              <div className="flex items-center justify-between text-xs font-bold text-ink">
                <span>{crit.name}</span>
                <span className="font-display text-forest font-bold">
                  {crit.awarded_points} / {crit.max_points}
                </span>
              </div>
              <p className="mt-1 text-xs text-ink-muted leading-relaxed">{crit.feedback}</p>
            </div>
          ))}
        </div>
      )}

      {/* Learning Coach Adaptive Recommendation & Activity Selector */}
      {coachRecommendation && (
        <div
          data-testid="learning-coach-recommendation-box"
          className="rounded-2xl border border-forest/30 bg-forest-soft/60 p-5 space-y-3.5 shadow-warm-sm"
        >
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-forest/15 pb-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-md bg-forest px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-paper">
                Learning Coach
              </span>
              <span className="text-xs font-bold text-ink">
                Recommended:{' '}
                {NEXT_ACTIVITY_LABELS[coachRecommendation.recommended_activity] ||
                  coachRecommendation.recommended_activity}
              </span>
              <span className="rounded border border-forest/20 bg-paper-surface px-2 py-0.5 text-[11px] font-semibold text-forest">
                Difficulty: {coachRecommendation.difficulty}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="rounded border border-line bg-paper-surface px-2 py-0.5 text-[11px] font-semibold text-ink-muted">
                Evidence: {coachRecommendation.evidence_status.replace(/_/g, ' ')}
              </span>
              {coachRecommendation.requires_student_confirmation && (
                <span className="rounded bg-coral-soft px-2 py-0.5 text-[11px] font-bold text-[#85291b]">
                  Confirmation Requested
                </span>
              )}
            </div>
          </div>

          <p className="text-xs sm:text-sm leading-relaxed text-ink">
            <strong className="text-forest">Pedagogical Reason: </strong>
            {coachRecommendation.reason}
          </p>

          {coachRecommendation.alternative_activities.length > 0 && (
            <div className="space-y-2 pt-1">
              <div className="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
                Or Select an Alternative Activity:
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedOverride(null)}
                  className={`rounded-lg border px-3 py-1.5 text-xs font-bold transition-all ${
                    selectedOverride === null
                      ? 'border-forest bg-forest text-paper shadow-warm-sm'
                      : 'border-line bg-paper-surface text-ink hover:border-forest'
                  }`}
                >
                  Coach Pick:{' '}
                  {NEXT_ACTIVITY_LABELS[
                    coachRecommendation.recommended_activity
                  ] || coachRecommendation.recommended_activity}
                </button>

                {coachRecommendation.alternative_activities.map((alt) => (
                  <button
                    key={alt.activity_type}
                    type="button"
                    title={alt.description}
                    onClick={() => setSelectedOverride(alt.activity_type)}
                    className={`rounded-lg border px-3 py-1.5 text-xs font-bold transition-all ${
                      selectedOverride === alt.activity_type
                        ? 'border-forest bg-forest text-paper shadow-warm-sm'
                        : 'border-line bg-paper-surface text-ink hover:border-forest'
                    }`}
                  >
                    {alt.label} ({alt.difficulty})
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Suggested Next Activity Banner & Action Buttons */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line/60 pt-4">
        <div
          data-testid="assessment-next-activity"
          className="flex items-center gap-2 text-xs"
        >
          <span className="font-bold uppercase tracking-wider text-ink-muted text-[10px]">
            Selected Next Activity:
          </span>
          <span className="rounded-md bg-forest-soft px-2.5 py-1 font-bold text-forest">
            {suggestedNextActivityLabel}
          </span>
        </div>

        {(onEndSession || onNextActivity) && (
          <div className="flex flex-wrap items-center gap-2.5">
            {onEndSession && (
              <button
                type="button"
                onClick={onEndSession}
                disabled={isEnding}
                className="rounded-lg border border-line bg-paper px-4 py-2 text-xs font-bold text-ink hover:border-forest disabled:opacity-50 transition-colors"
              >
                {isEnding ? 'Ending…' : 'End Session & View Summary'}
              </button>
            )}
            {onNextActivity && (
              <button
                type="button"
                onClick={() => onNextActivity(selectedOverride)}
                disabled={isAdvancing}
                className="inline-flex items-center gap-2 rounded-lg bg-forest px-5 py-2.5 text-xs sm:text-sm font-bold text-paper shadow-warm-sm hover:bg-forest-hover disabled:opacity-50 transition-all transform hover:-translate-y-0.5"
              >
                <span>
                  {isAdvancing
                    ? 'Generating Next Activity…'
                    : `Continue: ${suggestedNextActivityLabel}`}
                </span>
                <span aria-hidden="true">→</span>
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
