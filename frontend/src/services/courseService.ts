import type {
  Course,
  CourseDocument,
  CreateCoursePayload,
  DocumentChunk,
} from '../types/course';
import { apiBlob, apiRequest } from './apiClient';

export function fetchUserCourses(userId: string): Promise<Course[]> {
  return apiRequest<Course[]>('/courses', { query: { user_id: userId } });
}

export function fetchCourseById(
  courseId: string,
  userId: string
): Promise<Course> {
  return apiRequest<Course>(`/courses/${encodeURIComponent(courseId)}`, {
    query: { user_id: userId },
  });
}

export function createCourse(payload: CreateCoursePayload): Promise<Course> {
  return apiRequest<Course>('/courses', { method: 'POST', json: payload });
}

export function deleteCourse(courseId: string, userId: string): Promise<void> {
  return apiRequest<void>(`/courses/${encodeURIComponent(courseId)}`, {
    method: 'DELETE',
    query: { user_id: userId },
  });
}

export function fetchCourseDocuments(
  courseId: string,
  userId: string
): Promise<CourseDocument[]> {
  return apiRequest<CourseDocument[]>(
    `/courses/${encodeURIComponent(courseId)}/documents`,
    { query: { user_id: userId } }
  );
}

export function uploadCourseDocument(
  courseId: string,
  userId: string,
  file: File
): Promise<CourseDocument> {
  const form = new FormData();
  form.append('file', file);
  return apiRequest<CourseDocument>(
    `/courses/${encodeURIComponent(courseId)}/documents`,
    { method: 'POST', form, query: { user_id: userId } }
  );
}

export function fetchDocument(
  documentId: string,
  userId: string
): Promise<CourseDocument> {
  return apiRequest<CourseDocument>(
    `/documents/${encodeURIComponent(documentId)}`,
    { query: { user_id: userId } }
  );
}

export function deleteDocument(
  documentId: string,
  userId: string
): Promise<void> {
  return apiRequest<void>(`/documents/${encodeURIComponent(documentId)}`, {
    method: 'DELETE',
    query: { user_id: userId },
  });
}

export function fetchDocumentChunks(
  documentId: string,
  userId: string
): Promise<DocumentChunk[]> {
  return apiRequest<DocumentChunk[]>(
    `/documents/${encodeURIComponent(documentId)}/chunks`,
    { query: { user_id: userId } }
  );
}

/** Download the original PDF as a Blob (authenticated; used for in-app preview). */
export function fetchDocumentFile(
  documentId: string,
  userId: string
): Promise<Blob> {
  return apiBlob(`/documents/${encodeURIComponent(documentId)}/file`, {
    user_id: userId,
  });
}
