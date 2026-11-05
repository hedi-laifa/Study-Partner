import type {
  ConceptLearningProfileItem,
  CourseLearningProfile,
  RevisionRecommendationItem,
} from '../types/learningProfile';
import { apiRequest } from './apiClient';

export function fetchCourseLearningProfile(
  courseId: string,
  userId: string
): Promise<CourseLearningProfile> {
  return apiRequest<CourseLearningProfile>(
    `/courses/${encodeURIComponent(courseId)}/learning-profile`,
    { query: { user_id: userId } }
  );
}

export function fetchConceptProgress(
  courseId: string,
  conceptId: string,
  userId: string
): Promise<ConceptLearningProfileItem> {
  return apiRequest<ConceptLearningProfileItem>(
    `/courses/${encodeURIComponent(courseId)}/concepts/${encodeURIComponent(conceptId)}/progress`,
    { query: { user_id: userId } }
  );
}

export function updateRevisionTaskStatus(params: {
  taskId: string;
  userId: string;
  status: 'PENDING' | 'COMPLETED' | 'DISMISSED';
}): Promise<RevisionRecommendationItem> {
  return apiRequest<RevisionRecommendationItem>(
    `/revision-tasks/${encodeURIComponent(params.taskId)}`,
    {
      method: 'PATCH',
      query: { user_id: params.userId },
      json: { status: params.status },
    }
  );
}
