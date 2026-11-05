export type CoachActivityType =
  | 'EXPLANATION'
  | 'DIAGNOSTIC_QUESTION'
  | 'EASIER_PRACTICE'
  | 'TARGETED_PRACTICE'
  | 'HINT_AND_RETRY'
  | 'HARDER_PRACTICE'
  | 'TRANSFER_QUESTION'
  | 'REVIEW';

export type MasteryStatus =
  | 'NOT_STARTED'
  | 'NEEDS_REVIEW'
  | 'LEARNING'
  | 'MASTERED';

export type EvidenceStatus =
  | 'NO_EVIDENCE'
  | 'MISCONCEPTION_DETECTED'
  | 'NEEDS_FOUNDATION'
  | 'PARTIAL_EVIDENCE'
  | 'ASSISTED_PROFICIENCY'
  | 'EMERGING_EVIDENCE'
  | 'STRONG_INDEPENDENT_EVIDENCE'
  | 'DUE_FOR_REVIEW';

export interface AlternativeActivityOption {
  activity_type: CoachActivityType;
  label: string;
  difficulty: 'BASIC' | 'INTERMEDIATE' | 'ADVANCED';
  description: string;
}

export interface CoachRecommendation {
  recommended_activity: CoachActivityType;
  target_concept_id: string;
  target_concept_title: string;
  difficulty: 'BASIC' | 'INTERMEDIATE' | 'ADVANCED';
  reason: string;
  requires_student_confirmation: boolean;
  policy_rule_applied: string;
  evidence_status: EvidenceStatus;
  uncertainty_score: number;
  alternative_activities: AlternativeActivityOption[];
}

export interface ConceptProgressRecord {
  id: string;
  user_id: string;
  course_id: string;
  concept_id: string;
  mastery_score: number;
  mastery_status: MasteryStatus;
  attempts_count: number;
  correct_attempts_count: number;
  last_score: number | null;
  last_practiced_at: string | null;
  next_review_at: string | null;
}

export interface LearningEvidenceRecord {
  id: string;
  user_id: string;
  concept_id: string;
  evaluation_id: string | null;
  evidence_type: string;
  score_delta: number;
  observed_score: number;
  summary: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ConceptLearningProfileItem {
  concept_id: string;
  course_id: string;
  title: string;
  summary: string;
  display_order: number;
  source_pages: number[];
  prerequisite_concept_ids: string[];
  mastery_score: number;
  mastery_status: MasteryStatus;
  evidence_status: EvidenceStatus;
  uncertainty_score: number;
  attempts_count: number;
  correct_attempts_count: number;
  independent_success_count: number;
  assisted_success_count: number;
  last_score: number | null;
  last_practiced_at: string | null;
  next_review_at: string | null;
  observed_strengths: string[];
  areas_needing_practice: string[];
  recent_evidence: LearningEvidenceRecord[];
  recommended_next_action: CoachRecommendation;
}

export interface ConceptMapNode {
  concept_id: string;
  title: string;
  summary: string;
  display_order: number;
  difficulty: string;
  source_pages: number[];
  prerequisite_ids: string[];
  dependent_ids: string[];
  mastery_score: number;
  mastery_status: MasteryStatus;
  evidence_status: EvidenceStatus;
}

export interface RecentLearningActivityItem {
  evidence_id: string;
  concept_id: string;
  concept_title: string;
  evidence_type: string;
  observed_score: number;
  score_delta: number;
  verdict: string | null;
  hints_used: number;
  difficulty: string;
  summary: string;
  created_at: string;
}

export interface RevisionRecommendationItem {
  id: string;
  course_id: string;
  concept_id: string;
  concept_title: string;
  title: string;
  reason: string;
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  status: 'PENDING' | 'COMPLETED' | 'DISMISSED';
  recommended_activity: CoachActivityType;
  due_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface CourseLearningProfile {
  user_id: string;
  course_id: string;
  course_title: string;
  total_concepts: number;
  mastered_concepts_count: number;
  learning_concepts_count: number;
  needs_review_concepts_count: number;
  not_started_concepts_count: number;
  overall_mastery_score: number;
  overall_uncertainty_score: number;
  concepts: ConceptLearningProfileItem[];
  concept_map: ConceptMapNode[];
  recent_activity: RecentLearningActivityItem[];
  observed_strengths: string[];
  areas_needing_practice: string[];
  revision_recommendations: RevisionRecommendationItem[];
}
