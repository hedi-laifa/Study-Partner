# Study Partner AI — Requirements Specification

## 1. Functional Requirements (MVP)

### 1.1 Course & Document Management (`FR-DOC`)
- **FR-DOC-01:** Users shall be able to create, view, and delete courses (title, course code, description).
- **FR-DOC-02:** Users shall be able to upload PDF files (up to 50 MB per file) to a specific course.
- **FR-DOC-03:** The system shall extract text and page numbers from uploaded PDFs using **PyMuPDF**.
- **FR-DOC-04:** The system shall reject corrupted, encrypted, or empty (zero extractable text) PDFs with a clear validation message.
- **FR-DOC-05:** The system shall chunk extracted text with configurable chunk size and overlap, preserving source document ID and page number metadata.
- **FR-DOC-06:** The system shall generate vector embeddings for each chunk using **Sentence Transformers** and store them in **ChromaDB**.
- **FR-DOC-07:** During or immediately after ingestion, the system shall extract a structured list of core **Concepts** (title, summary, difficulty level) from the document and persist them in **PostgreSQL**.

### 1.2 Study Session & Orchestration (`FR-SES`)
- **FR-SES-01:** Users shall be able to start a study session for a specific course or target concept.
- **FR-SES-02:** The **Orchestrator** (Python state machine) shall manage session state transitions deterministically (`IDLE`, `SELECTING_CONCEPT`, `TEACHING`, `QUESTIONING`, `EVALUATING`, `COACHING`, `COMPLETED`).
- **FR-SES-03:** All session state transitions, messages, and agent outputs shall be persisted in PostgreSQL so a student can resume an interrupted session.

### 1.3 Tutor Agent (`FR-TUT`)
- **FR-TUT-01:** Given a target concept, the Tutor Agent shall retrieve the top-$k$ relevant chunks from ChromaDB.
- **FR-TUT-02:** The Tutor Agent shall generate a clear, structured explanation grounded strictly in the retrieved course material, citing source page numbers.
- **FR-TUT-03:** When triggered for remediation (after a low assessment score), the Tutor Agent shall adapt its explanation by addressing the specific misconceptions identified in the rubric evaluation.

### 1.4 Assessment Agent (`FR-ASS`)
- **FR-ASS-01:** Given a concept and retrieved context chunks, the Assessment Agent shall generate a targeted comprehension question (conceptual or applied) along with an explicit **Evaluation Rubric** (criteria, point weights, expected key points).
- **FR-ASS-02:** When a student submits an answer, the Assessment Agent shall evaluate the response against the generated rubric and retrieved source text.
- **FR-ASS-03:** The evaluation output shall be validated via **Pydantic** to return a deterministic structure:
  - Total score (0–100)
  - Criterion-by-criterion breakdown (score, max score, comment)
  - Identified strengths
  - Identified gaps / misconceptions
  - Constructive feedback summary

### 1.5 Learning Coach & Mastery Tracking (`FR-COA`)
- **FR-COA-01:** The system shall maintain a `mastery_score` (0.0 to 100.0) and `status` (`NOT_STARTED`, `LEARNING`, `NEEDS_REVIEW`, `MASTERED`) for every concept.
- **FR-COA-02:** After each assessment evaluation, the system shall update the concept's mastery score using a weighted moving average of historical and current assessment scores.
- **FR-COA-03:** The Learning Coach shall analyze the updated mastery score and rubric gaps to recommend the next pedagogical action:
  - `ADVANCE`: Move to the next unmastered concept (if score $\ge 80$).
  - `PRACTICE_AGAIN`: Try a follow-up question on the same concept (if score between $50$ and $79$).
  - `RETEACH`: Return to the Tutor Agent for a simplified explanation focusing on missed rubric criteria (if score $< 50$).

---

## 2. Non-Functional Requirements (`NFR`)

### 2.1 Performance & Responsiveness
- **NFR-PERF-01:** Standard CRUD API endpoints (courses, concept lists, mastery dashboard) shall respond within $< 200\text{ ms}$ (p95).
- **NFR-PERF-02:** PDF text extraction and vector indexing for a standard 30-page lecture PDF shall complete within $< 15\text{ seconds}$ on consumer hardware.
- **NFR-PERF-03:** LLM-backed agent endpoints (Tutor explanation, Assessment evaluation) shall support clear loading states and complete within $< 30\text{ seconds}$ depending on local hardware/Ollama model size.

### 2.2 Reliability & Output Determinism
- **NFR-REL-01:** All LLM responses that drive application logic (concept extraction, question generation, rubric grading, coaching decision) shall use structured JSON schemas enforced by **Pydantic** validation.
- **NFR-REL-02:** If an Ollama LLM call returns malformed JSON, the backend shall automatically retry up to 2 times with a repair prompt before returning a graceful error state.
- **NFR-REL-03:** Relational database state (PostgreSQL) and vector store state (ChromaDB) shall remain synchronized during document deletion or re-indexing.

### 2.3 Maintainability & Modularity
- **NFR-MAIN-01:** Strict separation of concerns across API routers, domain services, database repositories/models, RAG pipeline, and AI agents.
- **NFR-MAIN-02:** The Orchestrator interface shall be abstracted so that the initial Python State Machine can be swapped for **LangGraph** in the future without changing FastAPI endpoints or React frontend contracts.

### 2.4 Local Deployment & Portability
- **NFR-DEP-01:** The entire stack (Frontend, Backend, PostgreSQL, ChromaDB) shall be reproducible via a single `docker compose up` command (with Ollama running either on the host machine or as a container service).

---

## 3. Constraints & Assumptions
1. **Local LLM Capabilities:** Prompts and JSON schemas must be concise enough for 7B–8B parameter open-weights models (e.g., `llama3.1:8b`, `qwen2.5:7b`, or `mistral:7b`) running on Ollama to follow reliably.
2. **PDF Format:** MVP assumes digital/text-selectable PDFs (lecture slides, syllabi, textbook chapters). Optical Character Recognition (OCR) is deferred to post-MVP.
3. **Single Active Student Context:** MVP focuses on the core pedagogical loop for a single student workspace rather than enterprise LMS administrative features.
