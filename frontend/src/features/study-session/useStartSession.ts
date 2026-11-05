import { useCallback, useState } from 'react';
import { navigate } from '../../app/router';
import { startStudySession } from '../../services/studySessionService';
import type { CoachActivityType } from '../../types/learningProfile';
import { activityLabel } from '../learning-progress/labels';

export const sessionPath = (courseId: string, sessionId: string): string =>
  `/courses/${courseId}/sessions/${sessionId}`;

/** Start a study session for a concept and navigate to it; tracks busy/error state. */
export function useStartSession(userId: string) {
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const start = useCallback(
    async (params: {
      courseId: string;
      conceptId?: string | null;
      conceptTitle?: string;
      activity?: CoachActivityType;
    }) => {
      const key = params.conceptId ?? params.courseId;
      if (busyKey) return;
      setBusyKey(key);
      setError(null);
      try {
        const goal =
          params.conceptTitle && params.activity
            ? `${activityLabel(params.activity)}: master ${params.conceptTitle}.`
            : undefined;
        const session = await startStudySession({
          courseId: params.courseId,
          userId,
          conceptId: params.conceptId,
          learningGoal: goal,
        });
        navigate(sessionPath(params.courseId, session.id));
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Unable to start the study session.'
        );
      } finally {
        setBusyKey(null);
      }
    },
    [busyKey, userId]
  );

  return { start, busyKey, error, clearError: () => setError(null) };
}
