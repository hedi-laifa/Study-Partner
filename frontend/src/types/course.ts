export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Course {
  id: string;
  user_id: string;
  title: string;
  code: string | null;
  description: string | null;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export interface CreateCoursePayload {
  user_id: string;
  title: string;
  code?: string;
  description?: string;
}

export type DocumentProcessingStatus =
  | 'UPLOADED'
  | 'PROCESSING'
  | 'READY'
  | 'FAILED';

export interface CourseDocument {
  id: string;
  user_id: string;
  course_id: string;
  filename: string;
  file_path: string;
  file_size_bytes: number;
  mime_type: string;
  page_count: number | null;
  chunk_count: number;
  status: DocumentProcessingStatus;
  error_message: string | null;
  extraction_warnings: string[];
  created_at: string;
  updated_at: string;
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  course_id: string;
  chroma_vector_id: string;
  chunk_index: number;
  page_start: number | null;
  page_end: number | null;
  page_number: number | null;
  section_title: string | null;
  chunk_text: string;
  char_count: number;
  created_at: string;
}
