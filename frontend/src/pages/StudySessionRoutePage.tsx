import React, { useCallback } from 'react';
import { Link, navigate } from '../app/router';
import { ErrorState, LoadingState } from '../components/ui/States';
import { useAsyncData } from '../hooks/useAsyncData';
import { getStudySession } from '../services/studySessionService';
import { viewerPath } from './CourseWorkspacePage';
import { StudySessionPage } from './StudySessionPage';

interface Props {
  courseId: string;
  sessionId: string;
  userId: string;
}

/** Route wrapper: loads a session by id (resuming interrupted ones) then renders the study UI. */
export const StudySessionRoutePage: React.FC<Props> = ({ courseId, sessionId, userId }) => {
  const loader = useCallback(() => getStudySession(sessionId, userId), [sessionId, userId]);
  const { data, error, isLoading, reload } = useAsyncData(loader);

  const exit = () => navigate(`/courses/${courseId}/sessions`);

  if (isLoading && !data) return <LoadingState label="Loading study session…" />;
  if (error || !data) {
    return (
      <div className="space-y-4">
        <Link to={`/courses/${courseId}`} className="text-xs font-semibold text-indigo-600 hover:underline">
          ← Back to course
        </Link>
        <ErrorState
          message={error ?? 'Session not found.'}
          onRetry={() => void reload()}
          title="Could not open this study session"
        />
      </div>
    );
  }

  return (
    <StudySessionPage
      key={data.id}
      initialSession={data}
      userId={userId}
      onExitSession={exit}
      onOpenSource={(documentId, page) => navigate(viewerPath(data.course_id, documentId, page))}
    />
  );
};
