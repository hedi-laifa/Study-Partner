import { useCallback, useEffect, useState } from 'react';
import {
  endStudySession,
  generateNextSessionActivity,
  getStudySession,
  requestSessionExplanation,
  requestSessionHint,
  submitSessionAnswer,
} from '../services/studySessionService';
import type { CoachActivityType } from '../types/learningProfile';
import type {
  EvaluationRecord,
  InteractiveSessionDetail,
} from '../types/studySession';

export interface UseStudySessionOptions {
  initialSession: InteractiveSessionDetail;
  userId: string;
}

export function useStudySession({
  initialSession,
  userId,
}: UseStudySessionOptions) {
  const [session, setSession] =
    useState<InteractiveSessionDetail>(initialSession);
  const [answerDraft, setAnswerDraft] = useState<string>('');
  const [latestEvaluation, setLatestEvaluation] =
    useState<EvaluationRecord | null>(null);
  const [explanationTakeaways, setExplanationTakeaways] = useState<string[]>(
    []
  );
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isRequestingHint, setIsRequestingHint] = useState<boolean>(false);
  const [isRequestingExplanation, setIsRequestingExplanation] =
    useState<boolean>(false);
  const [isAdvancing, setIsAdvancing] = useState<boolean>(false);
  const [isEnding, setIsEnding] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    setSession(initialSession);
    const currentAct = initialSession.current_activity;
    if (
      currentAct &&
      currentAct.attempts.length > 0 &&
      initialSession.state === 'FEEDBACK_READY'
    ) {
      const lastAttempt = currentAct.attempts[currentAct.attempts.length - 1];
      setLatestEvaluation(lastAttempt.evaluation);
      setAnswerDraft(lastAttempt.attempt.response_text);
    } else {
      setLatestEvaluation(null);
      setAnswerDraft('');
    }
  }, [initialSession]);

  const refreshSession = useCallback(async () => {
    try {
      const updated = await getStudySession(session.id, userId);
      setSession(updated);
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : 'Unable to refresh study session.'
      );
    }
  }, [session.id, userId]);

  const handleSubmitAnswer = useCallback(async () => {
    const trimmed = answerDraft.trim();
    if (!trimmed || isSubmitting) {
      return;
    }
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      const currentActId = session.current_activity?.id;
      const idempotencyKey = `${session.id}:${currentActId ?? 'act'}:${trimmed.length}`;
      const result = await submitSessionAnswer({
        sessionId: session.id,
        userId,
        activityId: currentActId,
        responseText: trimmed,
        idempotencyKey,
      });
      setSession(result.session);
      setLatestEvaluation(result.evaluation);
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : 'Failed to submit your answer.'
      );
    } finally {
      setIsSubmitting(false);
    }
  }, [answerDraft, isSubmitting, session.current_activity?.id, session.id, userId]);

  const handleRequestHint = useCallback(async () => {
    if (isRequestingHint) {
      return;
    }
    setIsRequestingHint(true);
    setErrorMessage(null);
    try {
      await requestSessionHint({
        sessionId: session.id,
        userId,
        activityId: session.current_activity?.id,
      });
      await refreshSession();
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : 'Failed to request hint.'
      );
    } finally {
      setIsRequestingHint(false);
    }
  }, [isRequestingHint, refreshSession, session.current_activity?.id, session.id, userId]);

  const handleRequestExplanation = useCallback(async () => {
    if (isRequestingExplanation) {
      return;
    }
    setIsRequestingExplanation(true);
    setErrorMessage(null);
    try {
      const response = await requestSessionExplanation({
        sessionId: session.id,
        userId,
        activityId: session.current_activity?.id,
      });
      setExplanationTakeaways(response.key_takeaways);
      await refreshSession();
    } catch (err) {
      setErrorMessage(
        err instanceof Error
          ? err.message
          : 'Failed to request concept explanation.'
      );
    } finally {
      setIsRequestingExplanation(false);
    }
  }, [
    isRequestingExplanation,
    refreshSession,
    session.current_activity?.id,
    session.id,
    userId,
  ]);

  const handleNextActivity = useCallback(
    async (requestedActivityType?: CoachActivityType | null) => {
      if (isAdvancing) {
        return;
      }
      setIsAdvancing(true);
      setErrorMessage(null);
      try {
        const updated = await generateNextSessionActivity({
          sessionId: session.id,
          userId,
          requestedActivityType: requestedActivityType || null,
          studentConfirmed: true,
        });
        setSession(updated);
        setLatestEvaluation(null);
        setAnswerDraft('');
        setExplanationTakeaways([]);
      } catch (err) {
        setErrorMessage(
          err instanceof Error
            ? err.message
            : 'Failed to generate next study activity.'
        );
      } finally {
        setIsAdvancing(false);
      }
    },
    [isAdvancing, session.id, userId]
  );

  const handleEndSession = useCallback(async () => {
    if (isEnding) {
      return;
    }
    setIsEnding(true);
    setErrorMessage(null);
    try {
      const completed = await endStudySession({
        sessionId: session.id,
        userId,
      });
      setSession(completed);
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : 'Failed to end study session.'
      );
    } finally {
      setIsEnding(false);
    }
  }, [isEnding, session.id, userId]);

  return {
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
    clearError: () => setErrorMessage(null),
    handleSubmitAnswer,
    handleRequestHint,
    handleRequestExplanation,
    handleNextActivity,
    handleEndSession,
  };
}
