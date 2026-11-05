import type {
  CoachRecommendation,
  ConceptProgressRecord,
  LearningEvidenceRecord,
} from './learningProfile';

export interface CourseConcept {
  id: string;
  course_id: string;
  source_document_id: string | null;
  title: string;
  summary: string;
  difficulty: 'BASIC' | 'INTERMEDIATE' | 'ADVANCED';
  display_order: number;
  source_pages: number[];
  created_at: string;
  updated_at: string;
}

export type AssessmentVerdict =
  | 'CORRECT'
  | 'PARTIALLY_CORRECT'
  | 'INCORRECT'
  | 'OFF_TOPIC'
  | 'INSUFFICIENT_EVIDENCE';

export type ErrorClassification =
  | 'NONE'
  | 'INCOMPLETE_REASONING'
  | 'FACTUAL_MISTAKE'
  | 'CALCULATION_ERROR'
  | 'AMBIGUOUS_OR_VAGUE'
  | 'OFF_TOPIC';

export interface RubricCriterionScore {
  criterion_id: string;
  name: string;
  awarded_points: number;
  max_points: number;
  matched_ideas?: string[];
  missing_ideas?: string[];
  feedback: string;
}

export interface AttemptRecord {
  id: string;
  activity_id: string;
  user_id: string;
  attempt_number: number;
  response_text: string;
  time_spent_seconds: number | null;
  submitted_at: string;
  created_at: string;
}

export interface EvaluationRecord {
  id: string;
  attempt_id: string;
  concept_id: string | null;
  verdict: AssessmentVerdict;
  rubric_score: number;
  total_score: number;
  max_score: number;
  passed: boolean;
  criteria_scores_json: RubricCriterionScore[];
  strengths_json: string[];
  strengths: string[];
  gaps_json: string[];
  gaps: string[];
  misconception: string | null;
  evidence_json: string[];
  evidence: string[];
  confidence: number;
  next_activity: string | null;
  error_classification: ErrorClassification;
  uncertain_evaluation: boolean;
  prompt_version: string | null;
  overall_feedback: string;
  evaluator_model: string | null;
  coach_action: 'ADVANCE' | 'PRACTICE_AGAIN' | 'RETEACH' | null;
  evaluated_at: string;
  created_at: string;
}

export interface ActivityAttemptDetail {
  attempt: AttemptRecord;
  evaluation: EvaluationRecord | null;
}

export interface SourceExcerpt {
  document_id: string;
  filename: string;
  page_start: number;
  page_end: number;
  section_title: string | null;
  excerpt: string;
}

export interface ActivityHistoryItem {
  id: string;
  session_id: string;
  concept_id: string;
  activity_type: string;
  difficulty: string;
  prompt_text: string;
  status: 'ACTIVE' | 'COMPLETED' | 'SKIPPED';
  order_index: number;
  relevant_pages: number[];
  source_excerpts: SourceExcerpt[];
  hints_used: string[];
  total_hints_available: number;
  explanation_requested: string | null;
  attempts: ActivityAttemptDetail[];
  created_at: string;
}

export interface SessionProgressInfo {
  total_activities_generated: number;
  completed_activities_count: number;
  current_activity_index: number;
  total_attempts_submitted: number;
  hints_used_count: number;
  explanations_requested_count: number;
  current_difficulty: string;
  average_score: number | null;
}

export interface SessionSummaryData {
  total_activities: number;
  completed_activities: number;
  total_attempts: number;
  hints_used_count: number;
  explanations_requested_count: number;
  average_score: number;
  concept_title: string;
  learning_goal: string;
  pages_reviewed: number[];
  strengths: string[];
  areas_for_improvement: string[];
  key_takeaways: string[];
  recommended_next_steps: string;
}

export interface InteractiveSessionDetail {
  id: string;
  user_id: string;
  course_id: string;
  course_title: string;
  current_concept_id: string | null;
  concept_title: string;
  concept_summary: string;
  learning_goal: string;
  state: string;
  started_at: string;
  updated_at: string;
  completed_at: string | null;
  current_activity: ActivityHistoryItem | null;
  activity_history: ActivityHistoryItem[];
  progress: SessionProgressInfo;
  coach_recommendation?: CoachRecommendation | null;
  concept_progress?: ConceptProgressRecord | null;
  summary: SessionSummaryData | null;
}

export interface AnswerSubmissionResponse {
  session: InteractiveSessionDetail;
  attempt: AttemptRecord;
  evaluation: EvaluationRecord;
  coach_recommendation?: CoachRecommendation | null;
  concept_progress?: ConceptProgressRecord | null;
  learning_evidence?: LearningEvidenceRecord | null;
  duplicate_prevented: boolean;
}

export interface HintResponse {
  session_id: string;
  activity_id: string;
  hint_level: number;
  max_hints: number;
  hint_text: string;
  relevant_pages: number[];
}

export interface ExplanationResponse {
  session_id: string;
  activity_id: string | null;
  explanation: string;
  key_takeaways: string[];
  relevant_pages: number[];
}
