# Study Partner AI

**Study Partner AI** is an adaptive, local-first AI learning companion for university students. Students upload course PDFs, explore extracted concepts, ask course-grounded questions with clickable source references, practice in guided interactive study sessions, receive explicit rubric-based assessments, and progress through transparent Learning Coach adaptive activities and spaced-review recommendations.

---

## Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Monorepo Structure](#2-monorepo-structure)
3. [Installation Guide](#3-installation-guide)
4. [Environment Setup](#4-environment-setup)
5. [API Documentation](#5-api-documentation)
6. [Testing Guide](#6-testing-guide)
7. [Reproducible 10-Step Demonstration](#7-reproducible-10-step-demonstration)
8. [AI Evaluation Results](#8-ai-evaluation-results)
9. [Security & Resilience Guarantees](#9-security--resilience-guarantees)
10. [Known Limitations](#10-known-limitations)

---

## 1. Architecture Overview

Study Partner AI follows a clean, layered architecture separating presentation, API routing, domain orchestration, deterministic pedagogical heuristics, and local AI/vector storage:

```mermaid
flowchart LR
    UI["React 18 + TypeScript + Tailwind SPA\n(12 Screens, Light/Dark Mode)"] --> API["FastAPI REST API (/api/v1)\nAuthIdentityMiddleware + Pydantic v2"]
    API --> ING["PDF Ingestion Pipeline\nPyMuPDF + Overlapping Chunker"]
    API --> RAG["Course-Grounded RAG Tutor\nSentenceTransformers + ChromaDB + Ollama"]
    API --> SESS["Interactive Study Session\nState Machine + Graduated Hints"]
    API --> ASS["Assessment Agent\nExplicit Rubrics + Deterministic Math Check"]
    API --> COACH["Learning Coach & Mastery Engine\nTransparent Rules + Spaced Revision"]
    ING --> DB[("PostgreSQL 16\n12 SQLAlchemy 2.0 Models")]
    ING --> VEC[("ChromaDB\nPersistent Vector Store")]
    SESS --> DB
    ASS --> DB
    COACH --> DB
```

Detailed architectural documentation is available in [`docs/`](./docs/):
- [`docs/PROJECT_OVERVIEW.md`](./docs/PROJECT_OVERVIEW.md) — Vision, learning workflow, and tech stack
- [`docs/REQUIREMENTS.md`](./docs/REQUIREMENTS.md) — Functional and non-functional requirements
- [`docs/SYSTEM_ARCHITECTURE.md`](./docs/SYSTEM_ARCHITECTURE.md) — Layered architecture and Docker topology
- [`docs/AI_ARCHITECTURE.md`](./docs/AI_ARCHITECTURE.md) — RAG pipeline, agent contracts, state machine, and mastery heuristic
- [`docs/DATABASE_DESIGN.md`](./docs/DATABASE_DESIGN.md) — PostgreSQL ER diagram and 12-model schema
- [`docs/API_SPECIFICATION.md`](./docs/API_SPECIFICATION.md) — Complete REST endpoint and payload reference
- [`docs/TESTING_STRATEGY.md`](./docs/TESTING_STRATEGY.md) — Unit, integration, benchmark, and Playwright E2E strategy
- [`docs/IMPLEMENTATION_STATUS.md`](./docs/IMPLEMENTATION_STATUS.md) — Master checklist across Phases 0–9
- [`docs/DECISIONS.md`](./docs/DECISIONS.md) — Architectural Decision Records (ADRs)

---

## 2. Monorepo Structure

```text
study-partner-ai/
├── frontend/               # React 18 + TypeScript + Vite 6 + Tailwind CSS SPA + Playwright E2E
├── backend/                # Python + FastAPI + SQLAlchemy 2.0 + Alembic + PyMuPDF + ChromaDB
├── docs/                   # System, AI, Database, API, and Testing Architecture Documentation
├── evaluation/             # Reproducible AI Benchmarks (RAG, Assessment Agent, Adaptation)
│   ├── rag/
│   ├── assessment/
│   └── adaptation/
├── scripts/                # Local dev scripts + reproducible 10-step demo (run_demo.py)
├── storage/                # Local runtime storage for uploaded PDFs & vectors (git-ignored)
│   └── .gitkeep
├── docker-compose.yml      # Local PostgreSQL 16 & ChromaDB services
├── .env.example            # Environment variable template
├── .gitignore              # Excludes secrets, .venv, node_modules, and runtime storage
├── README.md
└── CONTRIBUTING.md
```

---

## 3. Installation Guide

### Prerequisites
- **Python:** 3.11+
- **Node.js:** 20+ and `npm`
- **Docker & Docker Compose:** (Optional for local PostgreSQL 16 and standalone ChromaDB containers; the backend also supports embedded persistent ChromaDB and SQLite for zero-Docker local execution)
- **Ollama:** (Optional for live local LLM generation; deterministic course-grounded engines provide full offline fallback when Ollama is not running)

### Step-by-Step Reproducible Setup

1. **Copy the environment template:**
   ```powershell
   Copy-Item .env.example .env
   ```

2. **Start PostgreSQL and ChromaDB via Docker Compose (optional):**
   ```powershell
   docker compose up -d
   ```

3. **Install Backend Dependencies & Run Migrations:**
   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   alembic upgrade head
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Install Frontend Dependencies & Start the Web App:**
   ```powershell
   cd frontend
   npm.cmd install
   npm.cmd run dev
   ```
   Open `http://localhost:5173` in your browser.

---

## 4. Environment Setup

All configuration is controlled via environment variables (`.env` at repository root, validated by [`backend/app/core/config.py`](./backend/app/core/config.py)):

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql+psycopg://studypartner:...@localhost:5432/study_partner_db` | SQLAlchemy 2.0 connection URL |
| `CHROMA_PERSIST_DIR` | `../storage/chroma` | Persistent directory for ChromaDB vector indices |
| `UPLOAD_STORAGE_DIR` | `../storage/uploads` | Local directory for uploaded course PDFs (excluded from Git) |
| `MAX_UPLOAD_SIZE_MB` | `50` | Maximum allowed PDF file size in MB |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama HTTP endpoint |
| `OLLAMA_MODEL` | `llama3.1:8b` | Configurable Ollama model name |
| `OLLAMA_TIMEOUT_SECONDS` | `30.0` | Timeout per LLM request before raising/falling back |
| `EMBEDDING_MODEL_NAME` | `all-MiniLM-L6-v2` | Sentence Transformers embedding model |
| `AUTH_SECRET_KEY` | `study-partner-dev-secret-...` | HMAC-SHA256 secret key for signing access tokens |
| `AUTH_TOKEN_TTL_MINUTES` | `480` | Access token lifetime in minutes |
| `AUTH_REQUIRED` | `false` | Enforce bearer tokens on all non-public endpoints |
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | Frontend API base URL |

---

## 5. API Documentation

Interactive OpenAPI documentation is served at `http://localhost:8000/docs`. Full payload contracts are documented in [`docs/API_SPECIFICATION.md`](./docs/API_SPECIFICATION.md):

- **Health & Readiness:** `GET /api/v1/health`, `GET /api/v1/health/ready` (`503` when DB is unavailable)
- **Authentication:** `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`
- **Courses:** `POST /api/v1/courses`, `GET /api/v1/courses`, `GET /api/v1/courses/{id}`, `PATCH /api/v1/courses/{id}`, `DELETE /api/v1/courses/{id}`
- **Documents & PDF Streaming:** `POST /api/v1/courses/{id}/documents`, `GET /api/v1/courses/{id}/documents`, `GET /api/v1/documents/{id}`, `GET /api/v1/documents/{id}/chunks`, `GET /api/v1/documents/{id}/file`, `DELETE /api/v1/documents/{id}`
- **Grounded AI Tutor & Retrieval:** `POST /api/v1/courses/{id}/ask`, `POST /api/v1/courses/{id}/reindex`
- **Interactive Study Sessions:** `POST /api/v1/sessions`, `GET /api/v1/sessions/{id}`, `POST /api/v1/sessions/{id}/resume`, `POST /api/v1/sessions/{id}/submit-answer`, `POST /api/v1/sessions/{id}/hint`, `POST /api/v1/sessions/{id}/explain`, `POST /api/v1/sessions/{id}/next-activity`, `POST /api/v1/sessions/{id}/end`, `GET /api/v1/sessions/{id}/activities/{act_id}/rubric`
- **Adaptive Learning & Progress:** `GET /api/v1/courses/{id}/learning-profile`, `GET /api/v1/courses/{id}/concepts/{cid}/progress`, `GET /api/v1/courses/{id}/concept-map`, `GET /api/v1/courses/{id}/revision-recommendations`, `PATCH /api/v1/revision-tasks/{task_id}`

---

## 6. Testing Guide

Every test suite in Study Partner AI is deterministic and verified:

```powershell
# 1. Run all 40 backend unit, integration, security, resilience, and migration tests
.\backend\.venv\Scripts\pytest.exe backend/tests -v

# 2. Run frontend ESLint and TypeScript + Vite production build
cd frontend
npm.cmd run lint
npm.cmd run build

# 3. Run Playwright End-to-End browser tests (all 12 screens + 10-step demo workflow)
cd frontend
npx.cmd playwright test

# 4. Run AI Evaluation Benchmarks (RAG, Assessment Agent, Adaptive Routing)
.\backend\.venv\Scripts\python.exe evaluation/rag/benchmark_retrieval.py
.\backend\.venv\Scripts\python.exe evaluation/assessment/benchmark_assessment.py
.\backend\.venv\Scripts\python.exe evaluation/adaptation/benchmark_adaptation.py
```

---

## 7. Reproducible 10-Step Demonstration

You can run the complete 10-step student workflow (**1. Register $\rightarrow$ 2. Create course $\rightarrow$ 3. Upload PDF $\rightarrow$ 4. Select concept $\rightarrow$ 5. Start study session $\rightarrow$ 6. Answer question $\rightarrow$ 7. Receive assessment $\rightarrow$ 8. Receive adaptive activity $\rightarrow$ 9. View updated learning profile $\rightarrow$ 10. Reopen session**) in three ways:

1. **Automated CLI/API Demo Script:**
   ```powershell
   .\backend\.venv\Scripts\python.exe scripts/run_demo.py
   ```
2. **Automated Browser E2E Demo (Playwright):**
   ```powershell
   cd frontend
   npx.cmd playwright test e2e/phase9_demo_workflow.spec.ts
   ```
3. **Interactive Browser Walkthrough:**
   - Start backend (`./scripts/dev-backend.ps1`) and frontend (`./scripts/dev-frontend.ps1`), then open `http://localhost:5173`.
   - Create an account on `#/register`, create a course on `#/`, upload a lecture PDF on `#/courses/:id/documents`, select a concept on `#/courses/:id`, click **Start Session**, submit an answer, inspect the **Assessment Feedback & Learning Coach** card, click **Continue** to receive the adapted activity, view `#/courses/:id/profile`, and reopen the session from `#/courses/:id/sessions`.

---

## 8. AI Evaluation Results

All three AI subsystems are benchmarked with reproducible scripts under [`evaluation/`](./evaluation/):

| Benchmark Suite | Script | Dataset Size | Key Verified Metrics |
| :--- | :--- | :---: | :--- |
| **RAG & Grounded Citation** | [`evaluation/rag/benchmark_retrieval.py`](./evaluation/rag/benchmark_retrieval.py) | 6 multi-topic queries + 2 out-of-scope queries | **100% Top-1 Concept Hit Rate**, **100% Page Citation Accuracy**, **100% Out-of-Scope Abstention (`insufficient_evidence=True`)**, **0% Cross-Course Leakage** |
| **Assessment Agent vs. Human Gold** | [`evaluation/assessment/benchmark_assessment.py`](./evaluation/assessment/benchmark_assessment.py) | 18 human-reviewed cases (`correct`, `partial`, `incorrect`, `vague`, `off-topic`, `ambiguous`) | **100.0% Verdict Agreement**, **Cohen's $\kappa = 1.0000$**, **MAE $= 4.19$ pts**, **0.0% False-Positive Misconceptions**, **100% Uncertainty Detection on Ambiguous Answers** |
| **Adaptive Learning Coach** | [`evaluation/adaptation/benchmark_adaptation.py`](./evaluation/adaptation/benchmark_adaptation.py) | 8 canonical pedagogical scenarios | **100% Policy Routing Accuracy (8/8)**, **0 Single-Answer Mastery Violations** (1st attempt capped at `76.0/100`), **Hint-Assisted Discounting Verified** |

---

## 9. Security & Resilience Guarantees

- **Strict Ownership Enforcement:** Every endpoint verifies resource ownership against the authenticated user (`AuthIdentityMiddleware` + service-level checks), returning `403 FORBIDDEN` on cross-user access or identity spoofing attempts.
- **Upload Validation & Path Traversal Protection:** Uploads are validated for `.pdf` extension, MIME type, non-empty size ($\le 50\text{ MB}$), `%PDF-` magic header, and sanitized filenames (`validate_pdf_upload`). PDF streaming (`GET /api/v1/documents/{id}/file`) verifies that the resolved path resides strictly inside `UPLOAD_STORAGE_DIR` and sends `X-Content-Type-Options: nosniff`.
- **Untrusted PDF Prompt-Injection Defense:** Extracted PDF passages are sanitized via `sanitize_untrusted_passage` (`[REDACTED_UNTRUSTED_DIRECTIVE]`) and wrapped in `<untrusted_course_material>` delimiters before LLM prompting.
- **Secret & Log Confidentiality:** `password_hash` is excluded from all Pydantic response schemas (`UserRead`), and raw PDF document text and passwords are never written to application logs.
- **Complete Cascade Deletion:** Deleting a course (`DELETE /api/v1/courses/{id}`) removes all child database rows (`Document`, `ChunkMetadata`, `Concept`, `StudySession`, `Activity`, `Attempt`, `Evaluation`, `LearningEvidence`, `ConceptProgress`, `RevisionTask`), purges course vectors from ChromaDB, and deletes uploaded PDF files from disk.
- **Fault Tolerance & Resilience:**
  - **Ollama Unavailable / Timeout:** Raises `503 LLM_UNAVAILABLE` (or seamlessly falls back to deterministic grounded question/assessment engines in interactive study sessions).
  - **ChromaDB Unavailable:** Automatically falls back to relational `ChunkMetadata` cosine + lexical similarity search so students can continue studying.
  - **Database Unavailable:** Readiness probe (`GET /api/v1/health/ready`) returns `503 Service Unavailable` (`status="degraded"`).
  - **Interrupted Sessions:** Session progress, hints used, and attempt history are persisted after every step and automatically resumed via `GET /api/v1/sessions/{id}` or `POST /api/v1/sessions/{id}/resume`.

---

## 10. Known Limitations

1. **Scanned Image-Only PDFs (No OCR in MVP):** PyMuPDF extracts embedded digital text. Image-only scanned PDFs without an OCR text layer are detected and rejected gracefully with a clear `422 SCANNED_OR_EMPTY_PDF` warning rather than silently indexing empty chunks.
2. **Single-Node Local Storage:** Uploaded PDFs are stored on the local filesystem (`UPLOAD_STORAGE_DIR`), which is ideal for local-first and single-node deployments; multi-replica cloud deployments would require an S3-compatible object store adapter.
3. **Local Hardware Latency for Large LLMs:** Live generation latency with Ollama (`llama3.1:8b`) depends on local GPU/CPU hardware; configurable timeouts (`OLLAMA_TIMEOUT_SECONDS`) and deterministic fallback engines prevent UI blocking on constrained machines.
