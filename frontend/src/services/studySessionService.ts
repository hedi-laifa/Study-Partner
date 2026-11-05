import type { CoachActivityType } from '../types/learningProfile';
import type {
  AnswerSubmissionResponse,
  CourseConcept,
  ExplanationResponse,
  HintResponse,
  InteractiveSessionDetail,
} from '../types/studySession';
import { apiRequest } from './apiClient';

const sessionPath = (sessionId: string, suffix = '') =>
  `/sessions/${encodeURIComponent(sessionId)}${suffix}`;

export function fetchCourseConcepts(
  courseId: string,
  userId: string
): Promise<CourseConcept[]> {
  return apiRequest<CourseConcept[]>(
    `/courses/${encodeURIComponent(courseId)}/concepts`,
    { query: { user_id: userId } }
  );
}

export function fetchCourseSessions(
  courseId: string,
  userId: string
): Promise<InteractiveSessionDetail[]> {
  return apiRequest<InteractiveSessionDetail[]>(
    `/courses/${encodeURIComponent(courseId)}/sessions`,
    { query: { user_id: userId } }
  );
}

export function startStudySession(params: {
  courseId: string;
  userId: string;
  conceptId?: string | null;
  learningGoal?: string;
}): Promise<InteractiveSessionDetail> {
  return apiRequest<InteractiveSessionDetail>('/sessions', {
    method: 'POST',
    query: { user_id: params.userId },
    json: {
      course_id: params.courseId,
      user_id: params.userId,
      concept_id: params.conceptId || null,
      learning_goal: params.learningGoal || null,
    },
  });
}

export function getStudySession(
  sessionId: string,
  userId: string
): Promise<InteractiveSessionDetail> {
  return apiRequest<InteractiveSessionDetail>(sessionPath(sessionId), {
    query: { user_id: userId },
  });
}

export function submitSessionAnswer(params: {
  sessionId: string;
  userId: string;
  activityId?: string;
  responseText: string;
  idempotencyKey?: string;
}): Promise<AnswerSubmissionResponse> {
  return apiRequest<AnswerSubmissionResponse>(
    sessionPath(params.sessionId, '/submit-answer'),
    {
      method: 'POST',
      query: { user_id: params.userId },
      json: {
        user_id: params.userId,
        activity_id: params.activityId || null,
        response_text: params.responseText,
        idempotency_key: params.idempotencyKey || null,
      },
    }
  );
}

export function requestSessionHint(params: {
  sessionId: string;
  userId: string;
  activityId?: string;
}): Promise<HintResponse> {
  return apiRequest<HintResponse>(sessionPath(params.sessionId, '/hint'), {
    method: 'POST',
    query: { user_id: params.userId },
    json: { user_id: params.userId, activity_id: params.activityId || null },
  });
}

export function requestSessionExplanation(params: {
  sessionId: string;
  userId: string;
  activityId?: string;
  focusQuestion?: string;
}): Promise<ExplanationResponse> {
  return apiRequest<ExplanationResponse>(
    sessionPath(params.sessionId, '/explain'),
    {
      method: 'POST',
      query: { user_id: params.userId },
      json: {
        user_id: params.userId,
        activity_id: params.activityId || null,
        focus_question: params.focusQuestion || null,
      },
    }
  );
}

export function generateNextSessionActivity(params: {
  sessionId: string;
  userId: string;
  requestedActivityType?: CoachActivityType | null;
  targetConceptId?: string | null;
  studentConfirmed?: boolean;
}): Promise<InteractiveSessionDetail> {
  return apiRequest<InteractiveSessionDetail>(
    sessionPath(params.sessionId, '/next-activity'),
    {
      method: 'POST',
      query: { user_id: params.userId },
      json: {
        user_id: params.userId,
        requested_activity_type: params.requestedActivityType || null,
        target_concept_id: params.targetConceptId || null,
        student_confirmed: params.studentConfirmed ?? true,
      },
    }
  );
}

export function endStudySession(params: {
  sessionId: string;
  userId: string;
}): Promise<InteractiveSessionDetail> {
  return apiRequest<InteractiveSessionDetail>(
    sessionPath(params.sessionId, '/end'),
    {
      method: 'POST',
      query: { user_id: params.userId },
      json: { user_id: params.userId },
    }
  );
}
