/* eslint-disable react-refresh/only-export-components */
import React, { useCallback, useState } from 'react';
import { Link, navigate } from '../app/router';
import { AlertBanner } from '../components/ui/AlertBanner';
import { Card, Tabs } from '../components/ui/Layout';
import { ErrorState, LoadingState } from '../components/ui/States';
import { DocumentList, PDFUploader } from '../features/courses';
import {
  LearningProfileView,
  RevisionRecommendationsView,
} from '../features/learning-progress';
import type { PracticeHandler } from '../features/learning-progress';
import {
  CourseTutorChat,
  SessionHistory,
  StudySessionLauncher,
  sessionPath,
  useStartSession,
} from '../features/study-session';
import { useAsyncData } from '../hooks/useAsyncData';
import {
  deleteDocument,
  fetchCourseById,
  fetchCourseDocuments,
  fetchDocumentChunks,
  uploadCourseDocument,
} from '../services/courseService';
import {
  fetchCourseLearningProfile,
  updateRevisionTaskStatus,
} from '../services/learningProfileService';
import type { CourseDocument } from '../types/course';

export type CourseTabId =
  | 'overview'
  | 'documents'
  | 'tutor'
  | 'sessions'
  | 'profile'
  | 'revision';

const TAB_IDS: CourseTabId[] = ['overview', 'documents', 'tutor', 'sessions', 'profile', 'revision'];

export function isCourseTab(value: string | undefined): value is CourseTabId {
  return Boolean(value && (TAB_IDS as string[]).includes(value));
}

export const viewerPath = (courseId: string, documentId: string, page?: number): string =>
  `/courses/${courseId}/documents/${documentId}${page ? `?page=${page}` : ''}`;

interface TabProps {
  courseId: string;
  userId: string;
  hasReadyDocuments: boolean;
}

/** Shared loader for the Learning Profile and Revision tabs (one cached request). */
function useProfile(courseId: string, userId: string) {
  const loader = useCallback(
    () => fetchCourseLearningProfile(courseId, userId),
    [courseId, userId]
  );
  return useAsyncData(loader);
}

const LearningProfileTab: React.FC<TabProps> = ({ courseId, userId, hasReadyDocuments }) => {
  const { data, error, isLoading, reload } = useProfile(courseId, userId);
  const { start, busyKey, error: startError, clearError } = useStartSession(userId);

  const onPractice: PracticeHandler = (conceptId, conceptTitle, activity) =>
    void start({ courseId, conceptId, conceptTitle, activity });

  if (isLoading && !data) return <LoadingState label="Loading learning profile…" />;
  if (error && !data) return <ErrorState message={error} onRetry={() => void reload()} />;
  if (!data) return null;
  return (
    <div className="space-y-4">
      {startError && <AlertBanner variant="error" message={startError} onDismiss={clearError} />}
      {!hasReadyDocuments && (
        <AlertBanner variant="info" message="Upload a PDF in the Documents tab to start studying these concepts." />
      )}
      <LearningProfileView
        profile={data}
        canStartSession={hasReadyDocuments}
        busyConceptId={busyKey}
        onPractice={onPractice}
      />
    </div>
  );
};

const RevisionTab: React.FC<TabProps> = ({ courseId, userId, hasReadyDocuments }) => {
  const { data, error, isLoading, reload } = useProfile(courseId, userId);
  const { start, busyKey, error: startError, clearError } = useStartSession(userId);
  const [busyTaskId, setBusyTaskId] = useState<string | null>(null);
  const [taskError, setTaskError] = useState<string | null>(null);

  const onUpdateTask = async (taskId: string, status: 'COMPLETED' | 'DISMISSED') => {
    setBusyTaskId(taskId);
    setTaskError(null);
    try {
      await updateRevisionTaskStatus({ taskId, userId, status });
      await reload();
    } catch (err) {
      setTaskError(err instanceof Error ? err.message : 'Could not update the task.');
    } finally {
      setBusyTaskId(null);
    }
  };

  if (isLoading && !data) return <LoadingState label="Loading revision recommendations…" />;
  if (error && !data) return <ErrorState message={error} onRetry={() => void reload()} />;
  if (!data) return null;
  return (
    <div className="space-y-4">
      {(startError || taskError) && (
        <AlertBanner
          variant="error"
          message={(startError ?? taskError) as string}
          onDismiss={() => {
            clearError();
            setTaskError(null);
          }}
        />
      )}
      <RevisionRecommendationsView
        profile={data}
        canStartSession={hasReadyDocuments}
        busyConceptId={busyKey}
        busyTaskId={busyTaskId}
        onPractice={(conceptId, conceptTitle, activity) =>
          void start({ courseId, conceptId, conceptTitle, activity })
        }
        onUpdateTask={(id, status) => void onUpdateTask(id, status)}
      />
    </div>
  );
};

interface Props {
  courseId: string;
  tab: CourseTabId;
  userId: string;
}

export const CourseWorkspacePage: React.FC<Props> = ({ courseId, tab, userId }) => {
  const courseLoader = useCallback(() => fetchCourseById(courseId, userId), [courseId, userId]);
  const docsLoader = useCallback(() => fetchCourseDocuments(courseId, userId), [courseId, userId]);
  const course = useAsyncData(courseLoader);
  const docs = useAsyncData(docsLoader);

  const [isUploading, setIsUploading] = useState(false);
  const [notice, setNotice] = useState<{ kind: 'error' | 'success'; text: string } | null>(null);

  const documents: CourseDocument[] = docs.data ?? [];
  const hasReadyDocuments = documents.some((d) => d.status === 'READY' && d.chunk_count > 0);

  const handleUpload = async (file: File) => {
    setIsUploading(true);
    setNotice(null);
    try {
      const uploaded = await uploadCourseDocument(courseId, userId, file);
      const warn = uploaded.extraction_warnings.length
        ? ` (${uploaded.extraction_warnings.length} extraction warning(s) below)`
        : '';
      setNotice({
        kind: 'success',
        text: `Processed "${uploaded.filename}": ${uploaded.page_count ?? 0} page(s), ${uploaded.chunk_count} chunk(s)${warn}.`,
      });
    } catch (err) {
      setNotice({ kind: 'error', text: err instanceof Error ? err.message : 'PDF upload failed.' });
    } finally {
      setIsUploading(false);
      await docs.reload();
    }
  };

  const handleDelete = async (documentId: string) => {
    setNotice(null);
    try {
      await deleteDocument(documentId, userId);
      setNotice({ kind: 'success', text: 'Document and its indexed passages were deleted.' });
      await docs.reload();
    } catch (err) {
      setNotice({ kind: 'error', text: err instanceof Error ? err.message : 'Failed to delete document.' });
    }
  };

  if (course.isLoading && !course.data) return <LoadingState label="Loading course workspace…" />;
  if (course.error && !course.data) {
    return (
      <div className="space-y-4">
        <Link to="/" className="inline-flex items-center gap-1.5 text-xs font-bold text-forest hover:underline">
          ← Back to dashboard
        </Link>
        <ErrorState message={course.error} onRetry={() => void course.reload()} title="Could not open this course" />
      </div>
    );
  }
  if (!course.data) return null;
  const c = course.data;

  return (
    <div className="space-y-6">
      {/* Back navigation */}
      <div>
        <Link to="/" className="inline-flex items-center gap-1.5 text-xs font-bold text-ink-muted hover:text-forest transition-colors">
          <span>←</span>
          <span>Back to Dashboard</span>
        </Link>
      </div>

      {/* StudyMate Course Detail Hero Banner */}
      <div className="welcome-hero-banner rounded-2xl p-6 sm:p-8 shadow-warm-md flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="flex items-start sm:items-center gap-4 z-10 min-w-0">
          <div className="flex h-16 w-16 sm:h-20 sm:w-20 flex-shrink-0 items-center justify-center rounded-xl bg-white/10 border border-white/20 font-display text-2xl sm:text-3xl font-bold text-white shadow-sm">
            {c.code ? c.code.slice(0, 3) : 'CS'}
          </div>
          <div className="min-w-0">
            {c.code && (
              <span className="inline-block rounded bg-coral text-white font-mono text-[10px] sm:text-xs font-bold px-2 py-0.5 tracking-wider uppercase mb-1.5 shadow-sm">
                {c.code}
              </span>
            )}
            <h1 className="font-display text-xl sm:text-3xl font-bold text-white tracking-tight leading-tight">
              {c.title}
            </h1>
            {c.description && (
              <p className="mt-1 text-xs sm:text-sm text-[#e8f0ea] max-w-xl line-clamp-2 leading-relaxed">
                {c.description}
              </p>
            )}
          </div>
        </div>

        {/* Hero Actions / Status Pill */}
        <div className="flex flex-wrap items-center gap-3 z-10 self-stretch sm:self-auto justify-end">
          <span className="flex items-center gap-1.5 rounded-full bg-white/10 px-3.5 py-1.5 text-xs font-bold text-white border border-white/15">
            <span>📄</span>
            <span>
              {documents.length} {documents.length === 1 ? 'Document' : 'Documents'}
            </span>
          </span>
          <button
            type="button"
            onClick={() => navigate(`/courses/${courseId}/tutor`)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-paper px-4 py-2 text-xs sm:text-sm font-bold text-forest shadow-sm hover:bg-white transition-all transform hover:-translate-y-0.5"
          >
            <span>Open Tutor</span>
            <span aria-hidden="true">✦</span>
          </button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs
        label="Course sections"
        activeId={tab}
        onSelect={(id) => navigate(id === 'overview' ? `/courses/${courseId}` : `/courses/${courseId}/${id}`)}
        tabs={[
          { id: 'overview', label: 'Overview' },
          { id: 'documents', label: 'Documents', count: documents.length },
          { id: 'tutor', label: 'AI Tutor' },
          { id: 'sessions', label: 'Session history' },
          { id: 'profile', label: 'Learning profile' },
          { id: 'revision', label: 'Revision' },
        ]}
      />

      {/* Tab Panels */}
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="space-y-6">
        {notice && (
          <AlertBanner variant={notice.kind} message={notice.text} onDismiss={() => setNotice(null)} />
        )}
        {docs.error && !docs.data && (
          <ErrorState message={docs.error} onRetry={() => void docs.reload()} title="Could not load documents" />
        )}

        {tab === 'overview' && (
          <StudySessionLauncher
            courseId={courseId}
            userId={userId}
            hasReadyDocuments={hasReadyDocuments}
            onLaunchSession={(session) => navigate(sessionPath(courseId, session.id))}
          />
        )}

        {tab === 'documents' && (
          <div className="space-y-6">
            <PDFUploader isUploading={isUploading} onUpload={handleUpload} />
            <Card
              title={`Course Documents (${documents.length})`}
              actions={
                <button
                  type="button"
                  onClick={() => void docs.reload()}
                  className="rounded-lg border border-line bg-paper px-3 py-1.5 text-xs font-bold text-forest hover:border-forest shadow-warm-sm transition-colors"
                >
                  Refresh Documents
                </button>
              }
            >
              {docs.isLoading && !docs.data ? (
                <LoadingState label="Loading documents…" />
              ) : (
                <DocumentList
                  documents={documents}
                  onDeleteDocument={handleDelete}
                  onInspectChunks={(id) => fetchDocumentChunks(id, userId)}
                  onPreviewDocument={(id) => navigate(viewerPath(courseId, id))}
                />
              )}
            </Card>
          </div>
        )}

        {tab === 'tutor' && (
          <CourseTutorChat
            courseId={courseId}
            courseTitle={c.title}
            userId={userId}
            hasReadyDocuments={hasReadyDocuments}
            onOpenSource={(documentId, page) => navigate(viewerPath(courseId, documentId, page))}
          />
        )}

        {tab === 'sessions' && <SessionHistory courseId={courseId} userId={userId} />}

        {tab === 'profile' && (
          <LearningProfileTab courseId={courseId} userId={userId} hasReadyDocuments={hasReadyDocuments} />
        )}

        {tab === 'revision' && (
          <RevisionTab courseId={courseId} userId={userId} hasReadyDocuments={hasReadyDocuments} />
        )}
      </div>
    </div>
  );
};
