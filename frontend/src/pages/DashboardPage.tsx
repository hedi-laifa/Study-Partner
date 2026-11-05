import React, { useCallback, useMemo, useState } from 'react';
import { Link, navigate } from '../app/router';
import { AlertBanner } from '../components/ui/AlertBanner';
import { Card, StatCard, WelcomeCard } from '../components/ui/Layout';
import { EmptyState, ErrorState, LoadingState } from '../components/ui/States';
import { CourseCard, CreateCourseForm } from '../features/courses';
import {
  activityLabel,
  EVIDENCE_BADGES,
  MASTERY_BADGES,
  practicePriority,
} from '../features/learning-progress';
import { sessionPath, useStartSession } from '../features/study-session/useStartSession';
import { useAsyncData } from '../hooks/useAsyncData';
import { createCourse, deleteCourse, fetchUserCourses } from '../services/courseService';
import { fetchCourseLearningProfile } from '../services/learningProfileService';
import { fetchCourseSessions } from '../services/studySessionService';
import type { Course } from '../types/course';
import type {
  ConceptLearningProfileItem,
  CourseLearningProfile,
  RevisionRecommendationItem,
} from '../types/learningProfile';
import type { InteractiveSessionDetail } from '../types/studySession';
import { formatIsoTimestamp } from '../utils/config';

interface DashboardData {
  courses: Course[];
  profiles: Map<string, CourseLearningProfile>;
  sessions: InteractiveSessionDetail[];
  partialFailures: number;
}

async function loadDashboard(userId: string): Promise<DashboardData> {
  const courses = await fetchUserCourses(userId);
  const results = await Promise.allSettled(
    courses.map(async (course) => ({
      course,
      profile: await fetchCourseLearningProfile(course.id, userId),
      sessions: await fetchCourseSessions(course.id, userId),
    }))
  );
  const profiles = new Map<string, CourseLearningProfile>();
  const sessions: InteractiveSessionDetail[] = [];
  let partialFailures = 0;
  for (const r of results) {
    if (r.status === 'fulfilled') {
      profiles.set(r.value.course.id, r.value.profile);
      sessions.push(...r.value.sessions);
    } else {
      partialFailures += 1;
    }
  }
  return { courses, profiles, sessions, partialFailures };
}

interface PracticeItem {
  course: Course;
  concept: ConceptLearningProfileItem;
}

export const DashboardPage: React.FC<{ userId: string; userName: string }> = ({
  userId,
  userName,
}) => {
  const loader = useCallback(() => loadDashboard(userId), [userId]);
  const { data, error, isLoading, reload, setData } = useAsyncData(loader);
  const { start, busyKey, error: startError, clearError } = useStartSession(userId);
  const [showCreate, setShowCreate] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [message, setMessage] = useState<{ kind: 'error' | 'success'; text: string } | null>(null);

  const derived = useMemo(() => {
    if (!data) return null;
    const courseById = new Map(data.courses.map((c) => [c.id, c]));

    const recentSessions = [...data.sessions]
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
      .slice(0, 5);

    const recentConcepts: {
      key: string;
      conceptTitle: string;
      course: Course;
      score: number;
      verdict: string | null;
      at: string;
    }[] = [];
    const seen = new Set<string>();
    const allEvidence = [...data.profiles.entries()].flatMap(([courseId, p]) =>
      p.recent_activity.map((a) => ({ courseId, a }))
    );
    allEvidence.sort((x, y) => y.a.created_at.localeCompare(x.a.created_at));
    for (const { courseId, a } of allEvidence) {
      const course = courseById.get(courseId);
      if (!course || seen.has(a.concept_id)) continue;
      seen.add(a.concept_id);
      recentConcepts.push({
        key: a.concept_id,
        conceptTitle: a.concept_title,
        course,
        score: a.observed_score,
        verdict: a.verdict,
        at: a.created_at,
      });
      if (recentConcepts.length === 5) break;
    }

    const practice: PracticeItem[] = [];
    let notStarted: PracticeItem | null = null;
    let totalMastered = 0;

    for (const course of data.courses) {
      const profile = data.profiles.get(course.id);
      if (!profile) continue;
      for (const concept of profile.concepts) {
        if (concept.mastery_status === 'MASTERED') {
          totalMastered += 1;
        }
        if (concept.attempts_count > 0 && concept.mastery_status !== 'MASTERED') {
          practice.push({ course, concept });
        } else if (concept.attempts_count === 0 && !notStarted) {
          notStarted = { course, concept };
        }
      }
    }
    practice.sort(
      (a, b) =>
        practicePriority(a.concept.mastery_status, a.concept.mastery_score) -
        practicePriority(b.concept.mastery_status, b.concept.mastery_score)
    );

    const rank: Record<string, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
    const revisions: { course: Course; task: RevisionRecommendationItem }[] = [];
    for (const course of data.courses) {
      for (const task of data.profiles.get(course.id)?.revision_recommendations ?? []) {
        if (task.status === 'PENDING') revisions.push({ course, task });
      }
    }
    revisions.sort((a, b) => (rank[a.task.priority] ?? 9) - (rank[b.task.priority] ?? 9));

    let suggestion: {
      course: Course;
      conceptId: string;
      conceptTitle: string;
      activity: ConceptLearningProfileItem['recommended_next_action']['recommended_activity'];
      reason: string;
    } | null = null;
    if (revisions[0]) {
      const { course, task } = revisions[0];
      suggestion = {
        course,
        conceptId: task.concept_id,
        conceptTitle: task.concept_title,
        activity: task.recommended_activity,
        reason: task.reason,
      };
    } else if (practice[0]) {
      const { course, concept } = practice[0];
      suggestion = {
        course,
        conceptId: concept.concept_id,
        conceptTitle: concept.title,
        activity: concept.recommended_next_action.recommended_activity,
        reason: concept.recommended_next_action.reason,
      };
    } else if (notStarted) {
      suggestion = {
        course: notStarted.course,
        conceptId: notStarted.concept.concept_id,
        conceptTitle: notStarted.concept.title,
        activity: 'DIAGNOSTIC_QUESTION',
        reason: 'You have not studied this concept yet. A short diagnostic question will establish your starting point.',
      };
    }

    const totalDocs = data.courses.reduce((acc, c) => acc + (c.document_count || 0), 0);

    return {
      recentSessions,
      recentConcepts,
      practice: practice.slice(0, 5),
      suggestion,
      courseById,
      totalDocs,
      totalMastered,
    };
  }, [data]);

  const handleCreate = async (form: { title: string; code?: string; description?: string }) => {
    setIsCreating(true);
    setMessage(null);
    try {
      const created = await createCourse({ user_id: userId, ...form });
      setMessage({ kind: 'success', text: `Course "${created.title}" created.` });
      setShowCreate(false);
      navigate(`/courses/${created.id}/documents`);
    } catch (err) {
      setMessage({ kind: 'error', text: err instanceof Error ? err.message : 'Failed to create course.' });
    } finally {
      setIsCreating(false);
    }
  };

  const handleDelete = async (courseId: string) => {
    setMessage(null);
    try {
      await deleteCourse(courseId, userId);
      setData((prev) =>
        prev ? { ...prev, courses: prev.courses.filter((c) => c.id !== courseId) } : prev
      );
      setMessage({ kind: 'success', text: 'Course deleted.' });
      void reload();
    } catch (err) {
      setMessage({ kind: 'error', text: err instanceof Error ? err.message : 'Failed to delete course.' });
    }
  };

  const hasCourses = (data?.courses.length ?? 0) > 0;

  return (
    <div className="space-y-7">
      {/* StudyMate-inspired Welcome Hero Banner */}
      <WelcomeCard
        userName={userName}
        coursesCount={data?.courses.length ?? 0}
        conceptsMasteredCount={derived?.totalMastered ?? 0}
        onStartStudy={
          derived?.suggestion
            ? () =>
                void start({
                  courseId: derived.suggestion!.course.id,
                  conceptId: derived.suggestion!.conceptId,
                  conceptTitle: derived.suggestion!.conceptTitle,
                  activity: derived.suggestion!.activity,
                })
            : undefined
        }
      />

      {/* 4 Stat Cards Row */}
      {data && derived && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            color="coral"
            icon="📚"
            label="Enrolled Courses"
            value={data.courses.length}
            detail={`${derived.totalDocs} PDFs uploaded`}
          />
          <StatCard
            color="sage"
            icon="📄"
            label="Ingested Docs"
            value={derived.totalDocs}
            detail="Indexed for RAG"
          />
          <StatCard
            color="lilac"
            icon="⏱️"
            label="Study Sessions"
            value={data.sessions.length}
            detail="Interactive practice"
          />
          <StatCard
            color="forest"
            icon="✦"
            label="Concepts Mastered"
            value={derived.totalMastered}
            detail="Evidence-proven"
          />
        </div>
      )}

      {message && (
        <AlertBanner variant={message.kind} message={message.text} onDismiss={() => setMessage(null)} />
      )}
      {startError && <AlertBanner variant="error" message={startError} onDismiss={clearError} />}
      {data && data.partialFailures > 0 && (
        <AlertBanner
          variant="warning"
          message={`Progress data could not be loaded for ${data.partialFailures} course(s). Other sections may be incomplete.`}
        />
      )}

      {/* Suggested Next Activity */}
      {data && derived && (
        <Card
          title="Suggested Next Study Activity"
          description="Prescribed by the Learning Coach based on your cognitive evidence and spaced revision tasks."
        >
          {derived.suggestion ? (
            <div data-testid="suggested-activity" className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-forest-soft/60 border border-forest/20">
              <div className="min-w-0 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-forest px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-paper">
                    {activityLabel(derived.suggestion.activity)}
                  </span>
                  <span className="text-xs font-semibold text-forest">
                    {derived.suggestion.course.title}
                  </span>
                </div>
                <h4 className="font-display text-base sm:text-lg font-semibold text-ink">
                  {derived.suggestion.conceptTitle}
                </h4>
                <p className="text-xs text-ink-muted leading-relaxed max-w-2xl">
                  {derived.suggestion.reason}
                </p>
              </div>
              <button
                type="button"
                disabled={busyKey !== null}
                onClick={() =>
                  void start({
                    courseId: derived.suggestion!.course.id,
                    conceptId: derived.suggestion!.conceptId,
                    conceptTitle: derived.suggestion!.conceptTitle,
                    activity: derived.suggestion!.activity,
                  })
                }
                className="inline-flex items-center gap-2 rounded-lg bg-forest px-4 py-2.5 text-xs sm:text-sm font-bold text-paper shadow-warm-sm hover:bg-forest-hover disabled:opacity-50 transition-all transform hover:-translate-y-0.5"
              >
                <span>{busyKey === derived.suggestion.conceptId ? 'Starting…' : 'Start now'}</span>
                <span aria-hidden="true">→</span>
              </button>
            </div>
          ) : (
            <p className="text-xs sm:text-sm text-ink-muted">
              {hasCourses
                ? 'Upload a PDF to a course so concepts can be extracted, then your first suggestion will appear here.'
                : 'Create a course and upload your lecture PDFs to get personalized suggestions.'}
            </p>
          )}
        </Card>
      )}

      {/* Create Course Form Toggle */}
      {(showCreate || (!isLoading && !error && !hasCourses)) && (
        <CreateCourseForm isSubmitting={isCreating} onCreate={handleCreate} />
      )}

      {/* Courses Section */}
      <section aria-labelledby="dash-courses" className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-ink-muted">
              Academic Modules
            </span>
            <h2 id="dash-courses" className="font-display text-xl sm:text-2xl font-semibold tracking-tight text-ink">
              Your Courses ({data?.courses.length ?? 0})
            </h2>
          </div>
          <button
            type="button"
            onClick={() => setShowCreate((s) => !s)}
            aria-expanded={showCreate}
            className="inline-flex items-center gap-1.5 rounded-lg bg-forest px-4 py-2 text-xs sm:text-sm font-bold text-paper hover:bg-forest-hover shadow-warm-sm transition-all"
          >
            <span>{showCreate ? 'Close Form' : 'New course'}</span>
            {!showCreate && <span aria-hidden="true">+</span>}
          </button>
        </div>

        {isLoading && !data ? (
          <LoadingState label="Loading your courses and progress…" />
        ) : error && !data ? (
          <ErrorState message={error} onRetry={() => void reload()} title="Could not load your dashboard" />
        ) : hasCourses && data ? (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {data.courses.map((course, idx) => (
              <CourseCard
                key={course.id}
                course={course}
                index={idx}
                onSelect={(c) => navigate(`/courses/${c.id}`)}
                onDelete={handleDelete}
              />
            ))}
          </div>
        ) : (
          <EmptyState
            title="No courses enrolled yet"
            description="Create your first course to upload syllabus or lecture readings and begin studying with your personal AI partner."
            action={
              <button
                type="button"
                onClick={() => setShowCreate(true)}
                className="inline-flex items-center gap-2 rounded-lg bg-forest px-5 py-2.5 text-xs sm:text-sm font-bold text-paper shadow-warm-sm hover:bg-forest-hover transition-all"
              >
                <span>Create a course</span>
                <span aria-hidden="true">+</span>
              </button>
            }
          />
        )}
      </section>

      {/* Concepts requiring practice & Recent studied concepts */}
      {data && derived && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Practice List */}
          <Card
            title="Concepts Requiring Practice"
            description="Concepts where your demonstrated mastery is still emerging or developing."
          >
            {derived.practice.length === 0 ? (
              <p className="text-xs sm:text-sm text-ink-muted">
                Nothing needs practice yet. Answer questions in a study session and concepts that need work will show up here.
              </p>
            ) : (
              <ul className="space-y-3" data-testid="practice-list">
                {derived.practice.map(({ course, concept }) => {
                  const m = MASTERY_BADGES[concept.mastery_status];
                  const ev = EVIDENCE_BADGES[concept.evidence_status];
                  return (
                    <li
                      key={concept.concept_id}
                      className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl border border-line bg-paper/50 hover:bg-paper transition-colors"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-display text-sm font-semibold text-ink">
                          {concept.title}
                        </p>
                        <p className="text-xs text-ink-muted">{course.title}</p>
                        <div className="mt-1.5 flex flex-wrap items-center gap-2">
                          <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${m.className}`}>
                            {m.label} · {concept.mastery_score}%
                          </span>
                          <span className={`rounded px-2 py-0.5 text-[10px] font-medium border ${ev.className}`}>
                            {ev.label}
                          </span>
                        </div>
                      </div>
                      <button
                        type="button"
                        disabled={busyKey !== null}
                        onClick={() =>
                          void start({
                            courseId: course.id,
                            conceptId: concept.concept_id,
                            conceptTitle: concept.title,
                            activity: concept.recommended_next_action.recommended_activity,
                          })
                        }
                        className="rounded-lg border border-line bg-paper px-3 py-1.5 text-xs font-bold text-forest hover:border-forest transition-colors shadow-warm-sm disabled:opacity-50"
                      >
                        {busyKey === concept.concept_id ? 'Starting…' : 'Practice'}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </Card>

          {/* Recent Studied Concepts */}
          <Card
            title="Recently Studied Concepts"
            description="Your latest diagnostic and practice activities across enrolled courses."
          >
            {derived.recentConcepts.length === 0 ? (
              <p className="text-xs sm:text-sm text-ink-muted">No studied concepts yet.</p>
            ) : (
              <ul className="space-y-3" data-testid="recent-concepts">
                {derived.recentConcepts.map((item) => (
                  <li
                    key={item.key}
                    className="flex items-center justify-between gap-3 p-3 rounded-xl border border-line bg-paper/50"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-display text-sm font-semibold text-ink">
                        {item.conceptTitle}
                      </p>
                      <p className="text-xs text-ink-muted">
                        {item.course.title} • {formatIsoTimestamp(item.at)}
                      </p>
                    </div>
                    <span className="flex-shrink-0 rounded-md bg-forest-soft px-2.5 py-1 text-xs font-bold text-forest">
                      {item.score}/100
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}

      {/* Recent Sessions List */}
      {data && derived && (
        <Card
          title="Recent Study Sessions"
          description="Past interactive practice and diagnostic sessions with adaptive activity trails."
        >
          {derived.recentSessions.length === 0 ? (
            <p className="text-xs sm:text-sm text-ink-muted">
              You have not started a study session yet.
            </p>
          ) : (
            <ul className="divide-y divide-line" data-testid="recent-sessions">
              {derived.recentSessions.map((s) => (
                <li
                  key={s.id}
                  className="flex flex-wrap items-center justify-between gap-3 py-3.5 first:pt-0 last:pb-0"
                >
                  <div className="min-w-0">
                    <p className="truncate font-display text-sm font-semibold text-ink">
                      {s.concept_title}
                    </p>
                    <p className="text-xs text-ink-muted mt-0.5">
                      {s.course_title} • {s.progress.completed_activities_count} activities answered
                      {s.progress.average_score !== null ? ` • avg score ${s.progress.average_score}/100` : ''} •{' '}
                      {formatIsoTimestamp(s.updated_at)}
                    </p>
                  </div>
                  <Link
                    to={sessionPath(s.course_id, s.id)}
                    className="inline-flex items-center gap-1 rounded-lg border border-line bg-paper px-3 py-1.5 text-xs font-bold text-forest hover:border-forest transition-colors shadow-warm-sm"
                  >
                    <span>{s.state === 'COMPLETED' ? 'View summary' : 'Resume'}</span>
                    <span aria-hidden="true">→</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
};
