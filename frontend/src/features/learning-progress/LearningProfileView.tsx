import React from 'react';
import { EmptyState } from '../../components/ui/States';
import type {
  CoachActivityType,
  CourseLearningProfile,
} from '../../types/learningProfile';
import { formatIsoTimestamp } from '../../utils/config';
import { ACTIVITY_LABELS, EVIDENCE_BADGES, MASTERY_BADGES } from './labels';

export interface PracticeHandler {
  (
    conceptId: string,
    conceptTitle: string,
    activity: CoachActivityType
  ): void;
}

interface ProfileViewProps {
  profile: CourseLearningProfile;
  canStartSession: boolean;
  busyConceptId: string | null;
  onPractice: PracticeHandler;
}

const Stat: React.FC<{ label: string; value: React.ReactNode; color?: string }> = ({
  label,
  value,
  color = 'bg-paper border-line text-ink',
}) => (
  <div className={`rounded-xl border p-4 shadow-warm-sm ${color}`}>
    <div className="text-[10px] font-bold uppercase tracking-wider text-ink-muted">{label}</div>
    <div className="mt-1 font-display text-xl sm:text-2xl font-bold tracking-tight text-ink">{value}</div>
  </div>
);

export const LearningProfileView: React.FC<ProfileViewProps> = ({
  profile,
  canStartSession,
  busyConceptId,
  onPractice,
}) => {
  const uncertaintyPct = Math.round(profile.overall_uncertainty_score * 100);

  return (
    <div data-testid="learning-profile-view" className="space-y-6">
      {/* 5-stat overview row */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Stat label="Overall mastery" value={`${profile.overall_mastery_score}/100`} />
        <Stat
          label="Mastered"
          value={`${profile.mastered_concepts_count}/${profile.total_concepts}`}
        />
        <Stat label="Learning" value={profile.learning_concepts_count} />
        <Stat label="Needs review" value={profile.needs_review_concepts_count} />
        <Stat label="Uncertainty" value={`${uncertaintyPct}%`} />
      </div>

      <p className="text-xs text-ink-muted leading-relaxed">
        Mastery is computed by deterministic cognitive rules using grounded student evidence. A single answer never assigns mastery directly, and hint-assisted successes count less than independent reasoning.
      </p>

      {/* Strengths & Weaknesses Grids */}
      <div className="grid gap-4 md:grid-cols-2">
        <section
          data-testid="learning-profile-strengths"
          className="rounded-2xl border border-sage/40 bg-sage-soft/60 p-5 shadow-warm-sm"
          aria-labelledby="lp-strengths"
        >
          <div className="flex items-center gap-2 mb-2">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-sage text-white text-xs font-bold">✓</span>
            <h3 id="lp-strengths" className="font-display text-sm sm:text-base font-semibold text-[#244227]">
              Demonstrated Strengths
            </h3>
          </div>
          {profile.observed_strengths.length > 0 ? (
            <ul className="list-inside list-disc space-y-1.5 text-xs text-ink">
              {profile.observed_strengths.map((s) => (
                <li key={s} className="leading-relaxed">{s}</li>
              ))}
            </ul>
          ) : (
            <p className="text-xs italic text-ink-muted">
              Answer questions in a study session to log evidence of strengths.
            </p>
          )}
        </section>

        <section
          data-testid="learning-profile-gaps"
          className="rounded-2xl border border-coral/30 bg-coral-soft/50 p-5 shadow-warm-sm"
          aria-labelledby="lp-gaps"
        >
          <div className="flex items-center gap-2 mb-2">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-coral text-white text-xs font-bold">!</span>
            <h3 id="lp-gaps" className="font-display text-sm sm:text-base font-semibold text-[#85291b]">
              Areas Needing Practice
            </h3>
          </div>
          {profile.areas_needing_practice.length > 0 ? (
            <ul className="list-inside list-disc space-y-1.5 text-xs text-ink">
              {profile.areas_needing_practice.map((g) => (
                <li key={g} className="leading-relaxed">{g}</li>
              ))}
            </ul>
          ) : (
            <p className="text-xs italic text-ink-muted">
              No unresolved reasoning gaps or misconceptions flagged.
            </p>
          )}
        </section>
      </div>

      {/* Concept Mastery List */}
      <section aria-labelledby="lp-concepts" className="space-y-4">
        <h3 id="lp-concepts" className="font-display text-lg font-semibold tracking-tight text-ink">
          Extracted Course Concepts ({profile.concepts.length})
        </h3>
        {profile.concepts.length === 0 ? (
          <EmptyState
            title="No concepts extracted yet"
            description="Upload a course PDF in the Documents tab so PyMuPDF can extract text and index concepts."
          />
        ) : (
          <ul className="grid gap-3.5">
            {profile.concepts.map((concept) => {
              const m = MASTERY_BADGES[concept.mastery_status];
              const ev = EVIDENCE_BADGES[concept.evidence_status];
              const rec = concept.recommended_next_action;
              const busy = busyConceptId === concept.concept_id;
              return (
                <li
                  key={concept.concept_id}
                  data-testid={`concept-progress-card-${concept.concept_id}`}
                  className="space-y-3.5 rounded-2xl border border-line bg-paper-surface p-5 shadow-warm-sm transition-all hover:border-forest/30"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-display text-base font-semibold text-ink">
                          {concept.title}
                        </span>
                        <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${m.className}`}>
                          {m.label} · {concept.mastery_score}%
                        </span>
                        <span className={`rounded border px-2 py-0.5 text-[10px] font-semibold ${ev.className}`}>
                          {ev.label}
                        </span>
                      </div>
                      {concept.summary && (
                        <p className="line-clamp-2 text-xs text-ink-muted leading-relaxed">{concept.summary}</p>
                      )}
                    </div>
                    <button
                      type="button"
                      disabled={!canStartSession || busy}
                      onClick={() =>
                        onPractice(concept.concept_id, concept.title, rec.recommended_activity)
                      }
                      className="inline-flex items-center gap-1.5 rounded-lg bg-forest px-3.5 py-2 text-xs font-bold text-paper shadow-warm-sm hover:bg-forest-hover transition-all disabled:opacity-50"
                    >
                      {busy
                        ? 'Starting…'
                        : `Practice: ${ACTIVITY_LABELS[rec.recommended_activity]}`}
                    </button>
                  </div>

                  {/* StudyMate-style Progress Track */}
                  <div
                    className="h-2 w-full overflow-hidden rounded-full bg-paper-deep"
                    role="progressbar"
                    aria-label={`Mastery of ${concept.title}`}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={Math.round(concept.mastery_score)}
                  >
                    <div
                      className={`h-full rounded-full transition-all duration-300 ${
                        concept.mastery_status === 'MASTERED'
                          ? 'bg-[#365c3b]'
                          : concept.mastery_status === 'NEEDS_REVIEW'
                            ? 'bg-coral'
                            : 'bg-forest'
                      }`}
                      style={{ width: `${Math.min(100, Math.max(0, concept.mastery_score))}%` }}
                    />
                  </div>

                  <dl className="flex flex-wrap gap-x-5 gap-y-1 text-[11px] text-ink-muted">
                    <div><dt className="inline">Attempts: </dt><dd className="inline font-bold text-ink">{concept.attempts_count}</dd></div>
                    <div><dt className="inline">Independent successes: </dt><dd className="inline font-bold text-ink">{concept.independent_success_count}</dd></div>
                    <div><dt className="inline">Hint-assisted: </dt><dd className="inline font-bold text-ink">{concept.assisted_success_count}</dd></div>
                    <div><dt className="inline">Uncertainty: </dt><dd className="inline font-bold text-ink">{Math.round(concept.uncertainty_score * 100)}%</dd></div>
                    {concept.next_review_at && (
                      <div><dt className="inline">Next review: </dt><dd className="inline font-bold text-ink">{formatIsoTimestamp(concept.next_review_at)}</dd></div>
                    )}
                  </dl>
                  <p className="text-xs text-forest bg-forest-soft/60 rounded-lg p-2.5">
                    <strong>Learning Coach Policy:</strong> {rec.reason}
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* Recent evidence log */}
      <section aria-labelledby="lp-evidence" className="space-y-3">
        <h3 id="lp-evidence" className="font-display text-base font-semibold tracking-tight text-ink">
          Evidence Trail ({profile.recent_activity.length})
        </h3>
        {profile.recent_activity.length === 0 ? (
          <p className="text-xs text-ink-muted">
            No evidence recorded yet. Submit an answer in a study session to log your learning evidence.
          </p>
        ) : (
          <ul className="space-y-2">
            {profile.recent_activity.slice(0, 8).map((item) => (
              <li
                key={item.evidence_id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-paper-surface p-3.5 text-xs shadow-warm-sm"
              >
                <div className="min-w-0 space-y-0.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-display font-semibold text-ink">{item.concept_title}</span>
                    <span className="rounded bg-paper-deep px-2 py-0.5 text-[10px] font-bold text-ink-muted">
                      {item.evidence_type.replace(/_/g, ' ')}
                    </span>
                    {item.hints_used > 0 && (
                      <span className="rounded bg-coral-soft px-2 py-0.5 text-[10px] font-bold text-coral">
                        {item.hints_used} hint(s)
                      </span>
                    )}
                  </div>
                  <p className="text-ink-muted">{item.summary}</p>
                </div>
                <div className="text-right">
                  <div className="font-bold text-ink">{item.observed_score}/100</div>
                  <div className={`text-[10px] font-bold ${item.score_delta >= 0 ? 'text-[#325235]' : 'text-coral'}`}>
                    {item.score_delta >= 0 ? '+' : ''}
                    {item.score_delta} delta
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
};
