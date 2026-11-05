# Study Partner AI — API Specification

## 1. API Design Conventions
- **Base URL:** `/api/v1`
- **Format:** JSON (`application/json`), except PDF upload (`multipart/form-data`).
- **Validation:** All request payloads and response bodies are strictly validated via **Pydantic v2** schemas.
- **Standard Error Payload:**
  ```json
  {
    "detail": "Human-readable error description",
  "error_code": "INVALID_PDF_UPLOAD | SCANNED_OR_EMPTY_PDF | CORRUPTED_PDF | FORBIDDEN_OWNERSHIP_VIOLATION | NOT_FOUND | INVALID_SESSION_STATE"
  }
  ```

---

## 2. Implemented Endpoints (Phases 1–5)

| Domain | Method | Path | Responsibility | Status |
| :--- | :---: | :--- | :--- | :---: |
| **Health** | `GET` | `/api/v1/health` | Liveness check | Implemented |
| **Health** | `GET` | `/api/v1/health/ready` | Readiness check (validates DB connectivity) | Implemented |
| **Users** | `GET` | `/api/v1/users/default` | Get or initialize default local student profile | Implemented |
| **Users** | `POST` | `/api/v1/users` | Register a new student user (`UserRead` excludes `password_hash`) | Implemented |
| **Users** | `GET` | `/api/v1/users/{user_id}` | Get user profile by UUID | Implemented |
| **Users** | `PATCH` | `/api/v1/users/{user_id}` | Update user profile | Implemented |
| **Courses** | `POST` | `/api/v1/courses` | Create a new course workspace | Implemented |
| **Courses** | `GET` | `/api/v1/courses?user_id={uuid}` | List all courses owned by a user | Implemented |
| **Courses** | `GET` | `/api/v1/courses/{course_id}` | Get course details (enforces ownership when `user_id` supplied) | Implemented |
| **Courses** | `PATCH` | `/api/v1/courses/{course_id}` | Update course metadata | Implemented |
| **Courses** | `DELETE` | `/api/v1/courses/{course_id}` | Delete course, ChromaDB vectors, and cascade child records | Implemented |
| **Concepts** | `GET` | `/api/v1/courses/{course_id}/concepts` | List course concepts (auto-populates from `READY` PDF chunks if empty) | Implemented |
| **Concepts** | `POST` | `/api/v1/courses/{course_id}/concepts` | Create a custom course concept for study sessions | Implemented |
| **Documents** | `POST` | `/api/v1/courses/{course_id}/documents` | Upload PDF, validate, extract page-aware text, detect warnings, chunk, persist `ChunkMetadata`, and index embeddings in ChromaDB | Implemented |
| **Documents** | `GET` | `/api/v1/courses/{course_id}/documents` | List uploaded documents, statuses, errors, and extraction warnings | Implemented |
| **Documents** | `GET` | `/api/v1/documents/{document_id}` | Get single document metadata and processing status | Implemented |
| **Documents** | `GET` | `/api/v1/documents/{document_id}/chunks` | List extracted `ChunkMetadata` (`page_start`, `page_end`, `section_title`, `chunk_text`, `chunk_index`) | Implemented |
| **Documents** | `DELETE` | `/api/v1/documents/{document_id}` | Delete document, its ChromaDB vectors, its `ChunkMetadata` rows, and its stored PDF file | Implemented |
| **Retrieval** | `POST` | `/api/v1/courses/{course_id}/reindex` | Rebuild ChromaDB vector embeddings for all `READY` documents in the course | Implemented |
| **AI Tutor** | `POST` | `/api/courses/{course_id}/ask` (and `/api/v1/courses/{course_id}/ask`) | Ask a question grounded in uploaded course PDFs; returns explanation, citations, pages, comprehension questions, hints, retrieval metadata, and `insufficient_evidence` status | Implemented |
| **Sessions** | `GET` | `/api/v1/courses/{course_id}/sessions` | List interactive study sessions for a course (`ACTIVE`, `IDLE`, `COMPLETED`) | Implemented |
| **Sessions** | `POST` | `/api/v1/sessions` | Start a new interactive study session and generate the initial diagnostic activity | Implemented |
| **Sessions** | `GET` | `/api/v1/sessions/{session_id}` | Retrieve full interactive session state, progress, current activity, and activity history (auto-resumes `IDLE` sessions) | Implemented |
| **Sessions** | `POST` | `/api/v1/sessions/{session_id}/resume` | Explicitly resume an interrupted (`IDLE` or `ACTIVE`) study session | Implemented |
| **Sessions** | `POST` | `/api/v1/sessions/{session_id}/submit-answer` | Submit a student answer with idempotency deduplication (`idempotency_key` + normalized text hash) and receive rubric feedback | Implemented |
| **Sessions** | `POST` | `/api/v1/sessions/{session_id}/hint` | Request a graduated hint (levels 1–3) for the active question without spoiling the solution | Implemented |
| **Sessions** | `POST` | `/api/v1/sessions/{session_id}/explain` | Request a concise, source-grounded explanation of the active concept/question | Implemented |
| **Sessions** | `POST` | `/api/v1/sessions/{session_id}/next-activity` | Advance to the next question with adaptive difficulty (`BASIC` $\leftrightarrow$ `INTERMEDIATE` $\leftrightarrow$ `ADVANCED`) | Implemented |
| **Sessions** | `POST` | `/api/v1/sessions/{session_id}/end` | End the study session, mark status `COMPLETED`, and persist a structured `SessionSummaryData` | Implemented |
| **Assessment** | `GET` | `/api/v1/sessions/{session_id}/activities/{activity_id}/rubric` | Retrieve the explicit `ActivityRubric` (`required_ideas`, `criteria`, `misconception_patterns`, `numerical_check`) | Implemented |

---

## 3. Detailed Phase 3 Ingestion Contracts

### `POST /api/v1/courses/{course_id}/documents?user_id={user_uuid}`
- **Request:** `multipart/form-data` with field `file` (`.pdf`) and `user_id` (query parameter or form field).
- **Pipeline Execution:**
  1. Verifies `course_id` exists and is owned by `user_id` (`403 Forbidden` otherwise).
  2. Validates `.pdf` extension, MIME type, non-empty size ($\le 50\text{ MB}$), and `%PDF-` magic header (`400 Bad Request` / `413 Content Too Large` otherwise).
  3. Saves PDF under `storage/uploads/{course_id}/{document_id}_{safe_filename}` and creates a `Document` record (`status = "PROCESSING"`).
  4. Extracts page-aware text with **PyMuPDF**, normalizes paragraphs and hyphenated line wraps, detects section titles, and records warnings for empty or low-text pages (`< 40` chars).
  5. If the PDF is encrypted, corrupted, or contains no selectable text (`< 20` total chars, e.g., scanned image PDF), updates `Document.status = "FAILED"` with `error_message` and returns `422 Unprocessable Entity`.
  6. Generates overlapping chunks (`chunk_size = 800`, `chunk_overlap = 150`), persists `ChunkMetadata` records, embeds chunks with `EmbeddingService`, and indexes them into `PersistentChromaStore`.
  7. Updates `Document.status = "READY"` and returns `201 Created`.
- **Response `201 Created` (`DocumentRead`):**
  ```json
  {
    "id": "d1a2b3c4-0000-4000-8000-000000000001",
    "user_id": "u111-uuid",
    "course_id": "b3d7a100-4c1a-4b7f-9b2a-112233445566",
    "filename": "Lecture_01_Scheduling.pdf",
    "file_path": "../storage/uploads/b3d7a100.../d1a2b3c4_Lecture_01_Scheduling.pdf",
    "file_size_bytes": 184320,
    "mime_type": "application/pdf",
    "page_count": 4,
    "chunk_count": 3,
    "status": "READY",
    "error_message": null,
    "extraction_warnings": [
      "1 page(s) contained no extractable text (page(s): 2). Scanned images or blank pages were skipped."
    ],
    "created_at": "2026-11-03T19:45:00Z",
    "updated_at": "2026-11-03T19:45:01Z"
  }
  ```

### `GET /api/v1/documents/{document_id}/chunks?user_id={user_uuid}`
- **Response `200 OK` (`list[ChunkMetadataRead]`):**
  ```json
  [
    {
      "id": "chk-001-uuid",
      "document_id": "d1a2b3c4-0000-4000-8000-000000000001",
      "course_id": "b3d7a100-4c1a-4b7f-9b2a-112233445566",
      "chroma_vector_id": "d1a2b3c4-0000-4000-8000-000000000001_chunk_0",
      "chunk_index": 0,
      "page_start": 1,
      "page_end": 1,
      "page_number": 1,
      "section_title": "Chapter 1: Process Scheduling",
      "chunk_text": "Chapter 1: Process Scheduling\n\nOperating systems allocate CPU time across runnable processes...",
      "text_content": "Chapter 1: Process Scheduling\n\nOperating systems allocate CPU time across runnable processes...",
      "char_count": 342,
      "metadata_json": {
        "page_start": 1,
        "page_end": 1,
        "section_title": "Chapter 1: Process Scheduling"
      },
      "created_at": "2026-11-03T19:45:01Z"
    }
  ]
  ```

---

## 4. Detailed Phase 4 RAG & AI Tutor Contracts

### `POST /api/courses/{course_id}/ask` (and `POST /api/v1/courses/{course_id}/ask`)
- **Request Body (`TutorAskRequest`):**
  ```json
  {
    "question": "How does Raft leader election work and what RPC replicates log entries?",
    "user_id": "u111-uuid",
    "top_k": 3,
    "conversation_history": [
      {
        "role": "student",
        "content": "What are Lamport logical clocks?"
      },
      {
        "role": "tutor",
        "content": "Lamport logical timestamps establish a partial happens-before ordering across causal events [Source 1, p. 1]."
      }
    ]
  }
  ```
- **Response `200 OK` (`TutorAskResponse`):**
  ```json
  {
    "answer": "Based on your uploaded course material, Raft achieves consensus via an elected leader that accepts client log entries and replicates them via AppendEntries RPCs [Source 1, p. 2].",
    "comprehension_questions": [
      "Using the definitions in 2. Raft Leader Election and Log Replication (p. 2), how would you explain how Raft prevents split votes in your own words?"
    ],
    "hints": [
      "Review '2. Raft Leader Election and Log Replication' in distributed_systems.pdf (page 2)."
    ],
    "source_references": [
      {
        "source_index": 1,
        "course_id": "b3d7a100-4c1a-4b7f-9b2a-112233445566",
        "document_id": "d1a2b3c4-0000-4000-8000-000000000001",
        "filename": "distributed_systems.pdf",
        "chunk_index": 1,
        "page_start": 2,
        "page_end": 2,
        "section_title": "2. Raft Leader Election and Log Replication",
        "excerpt": "2. Raft Leader Election and Log Replication\n\nRaft achieves consensus via an elected leader...",
        "relevance_score": 0.6124
      }
    ],
    "relevant_pages": [2],
    "relevant_page_numbers": [2],
    "retrieval_metadata": {
      "top_k_requested": 3,
      "passages_retrieved": 2,
      "total_candidates_indexed": 2,
      "retrieval_latency_ms": 1.15,
      "embedding_model": "all-MiniLM-L6-v2",
      "llm_model": "llama3.1:8b",
      "max_relevance_score": 0.6124
    },
    "insufficient_evidence": false
  }
  ```

---

## 5. Detailed Phase 5 Interactive Study Session Contracts

### `POST /api/v1/sessions`
- **Request Body (`InteractiveSessionStartRequest`):**
  ```json
  {
    "user_id": "u111-uuid",
    "course_id": "b3d7a100-4c1a-4b7f-9b2a-112233445566",
    "concept_id": "c999-uuid",
    "session_goal": "Understand how Raft leader election and AppendEntries log replication prevent split-brain",
    "target_activities": 3
  }
  ```
- **Response `201 Created` (`InteractiveSessionDetail`):**
  Returns session metadata, `progress`, `current_activity` (`DIAGNOSTIC_QUESTION`), `activity_history`, and `summary: null`.

### `POST /api/v1/sessions/{session_id}/submit-answer`
- **Request Body (`AnswerSubmissionRequest`):**
  ```json
  {
    "user_id": "u111-uuid",
    "activity_id": "act-001-uuid",
    "response_text": "Raft uses randomized election timeouts so a single candidate collects a majority of votes via RequestVote RPCs, and the elected leader replicates log entries via AppendEntries RPCs.",
    "idempotency_key": "attempt-act-001-1730664000"
  }
  ```
- **Response `200 OK` (`AnswerSubmissionResponse`):**
  - If `idempotency_key` or normalized `response_text` matches an existing attempt on `activity_id`, returns the existing attempt with `duplicate_prevented: true` without creating a second `Attempt` row.
  - Otherwise persists `Attempt` and `Evaluation` and updates `Activity.status = "COMPLETED"`.

### `POST /api/v1/sessions/{session_id}/hint` & `POST /api/v1/sessions/{session_id}/explain`
- **Graduated Hints (`/hint`):** Increments `hints_used` (levels `1`, `2`, `3`) on the active activity and returns a progressive hint that guides student reasoning before revealing solutions.
- **Grounded Explanation (`/explain`):** Generates a concise explanation grounded in retrieved course passages (`[Source N, p. X]`) and persists it in `Activity.content_payload`.

### `POST /api/v1/sessions/{session_id}/next-activity` & `POST /api/v1/sessions/{session_id}/end`
- **Next Activity (`/next-activity`):** Validates via `SessionStateMachine` that the current activity has at least one submitted attempt (`409 Conflict` if unanswered), uses the `LearningCoachService` recommendation (or the student's `requested_activity_type` override), and generates the next grounded activity across all 8 canonical types (`EXPLANATION`, `DIAGNOSTIC_QUESTION`, `EASIER_PRACTICE`, `TARGETED_PRACTICE`, `HINT_AND_RETRY`, `HARDER_PRACTICE`, `TRANSFER_QUESTION`, `REVIEW`).
- **End Session (`/end`):** Transitions `StudySession.status` to `COMPLETED`, records `ended_at`, and persists `SessionSummaryData` (`strengths`, `areas_for_improvement`, `key_takeaways`, `recommended_next_steps`, `average_score`). Any subsequent attempt to submit answers, request hints, or generate activities on a `COMPLETED` session returns `409 Conflict` (`error_code = "INVALID_SESSION_STATE"`).

---

## 6. Phase 6 & Phase 7: Assessment Rubric, Adaptive Learning & Learning Profile Contracts

### `GET /api/v1/sessions/{session_id}/activities/{activity_id}/rubric`
- Returns the explicit `ActivityRubric` (`required_ideas`, `criteria`, `misconception_patterns`, `numeric_check`).

### `GET /api/v1/courses/{course_id}/learning-profile`
- Returns `CourseLearningProfile` containing:
  - `overall_mastery_score`, `overall_uncertainty_score`, `mastered_concepts_count`, `learning_concepts_count`, `needs_review_concepts_count`, `not_started_concepts_count`
  - `concepts`: list of `ConceptLearningProfileItem` (`mastery_score`, `mastery_status`, `evidence_status`, `uncertainty_score`, `independent_success_count`, `assisted_success_count`, `recent_evidence`, `recommended_next_action`)
  - `concept_map`: prerequisite/dependent concept graph (`ConceptMapNode`)
  - `recent_activity`: chronological `LearningEvidence` items across the course
  - `observed_strengths` & `areas_needing_practice`
  - `revision_recommendations`: prioritized `RevisionRecommendationItem` tasks

### `GET /api/v1/courses/{course_id}/concepts/{concept_id}/progress`
- Returns `ConceptLearningProfileItem` for a single concept.

### `GET /api/v1/courses/{course_id}/concept-map`
- Returns `list[ConceptMapNode]` with prerequisite and dependent edges.

### `GET /api/v1/courses/{course_id}/revision-recommendations` & `PATCH /api/v1/revision-tasks/{task_id}`
- Lists or updates (`PENDING` / `COMPLETED` / `DISMISSED`) spaced-review and remediation `RevisionTask` records.

---

## 7. Phase 8: Authentication & Document Streaming Contracts

### `POST /api/v1/auth/register` & `POST /api/v1/auth/login`
- **Register Request (`AuthRegisterRequest`):** `{ "email": "student@university.edu", "full_name": "Ada Lovelace", "password": "..." }`
- **Login Request (`AuthLoginRequest`):** `{ "email": "student@university.edu", "password": "..." }`
- **Response (`AuthTokenResponse`):**
  ```json
  {
    "access_token": "<hmac-sha256-signed-token>",
    "token_type": "bearer",
    "expires_at": 1762286400,
    "user": {
      "id": "11111111-1111-1111-1111-111111111111",
      "email": "student@university.edu",
      "full_name": "Ada Lovelace",
      "is_active": true,
      "created_at": "2026-11-04T10:00:00Z",
      "updated_at": "2026-11-04T10:00:00Z"
    }
  }
  ```

### `GET /api/v1/auth/me`
- Validates `Authorization: Bearer <token>` via `AuthIdentityMiddleware` and returns `UserRead`. Returns `401 TOKEN_EXPIRED` or `401 INVALID_TOKEN` when expired or malformed, and `403 FORBIDDEN_IDENTITY_MISMATCH` if a caller attempts to spoof another user's `user_id`.

### `GET /api/v1/documents/{document_id}/file?user_id={user_uuid}`
- Verifies document ownership and streams the raw PDF file (`application/pdf`, `Content-Disposition: inline`) for the in-app PDF viewer (`#/courses/:courseId/documents/:docId?page=N`).




