import type { ConversationTurn, TutorAskResponse } from '../types/tutor';
import { apiRequest } from './apiClient';

export interface AskCourseTutorInput {
  courseId: string;
  userId: string;
  question: string;
  topK?: number;
  conversationHistory?: ConversationTurn[];
}

export function askCourseTutor({
  courseId,
  userId,
  question,
  topK = 5,
  conversationHistory = [],
}: AskCourseTutorInput): Promise<TutorAskResponse> {
  return apiRequest<TutorAskResponse>(
    `/courses/${encodeURIComponent(courseId)}/ask`,
    {
      method: 'POST',
      query: { user_id: userId },
      json: {
        question,
        user_id: userId,
        top_k: topK,
        conversation_history: conversationHistory,
      },
    }
  );
}
