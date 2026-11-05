export interface ConversationTurn {
  role: 'student' | 'tutor';
  content: string;
}

export interface SourceReference {
  source_index: number;
  document_id: string;
  filename: string;
  chunk_index: number;
  page_start: number;
  page_end: number;
  section_title: string | null;
  excerpt: string;
  relevance_score: number;
}

export interface RetrievalMetadata {
  top_k_requested: number;
  passages_retrieved: number;
  total_candidates_indexed: number;
  retrieval_latency_ms: number;
  embedding_model: string;
  llm_model: string;
  max_relevance_score: number;
}

export interface TutorAskResponse {
  answer: string;
  comprehension_questions: string[];
  hints: string[];
  source_references: SourceReference[];
  relevant_pages: number[];
  relevant_page_numbers: number[];
  retrieval_metadata: RetrievalMetadata;
  insufficient_evidence: boolean;
}

export interface TutorChatMessage {
  id: string;
  role: 'student' | 'tutor';
  content: string;
  timestamp: string;
  tutorResponse?: TutorAskResponse;
}
