# Contributing to Study Partner AI

Thank you for contributing to **Study Partner AI**. To keep the codebase clean, modular, and maintainable, please follow these engineering guidelines.

---

## 1. Architectural Boundaries
- **Frontend (`frontend/src/`):** Organized by feature (`features/courses`, `features/study-session`, `features/assessment`, `features/learning-progress`, `features/auth`) and shared UI/layout primitives (`components/ui`, `components/layout`). All HTTP calls go through `src/services/`.
- **Backend (`backend/app/`):**
  - `api/routes/`: FastAPI route handlers (HTTP parsing and status codes only).
  - `schemas/`: Pydantic v2 request/response validation schemas.
  - `services/`: Application and domain orchestration logic.
  - `repositories/`: Database query encapsulation.
  - `models/` & `db/`: SQLAlchemy 2.0 ORM models and session management.
  - `ingestion/`, `retrieval/`, `tutor/`, `assessment/`, `learning/`, `orchestration/`: Modular RAG and pedagogical AI agent components.

## 2. Development Workflow
1. Check [`docs/IMPLEMENTATION_STATUS.md`](./docs/IMPLEMENTATION_STATUS.md) and [`docs/DEVELOPMENT_ROADMAP.md`](./docs/DEVELOPMENT_ROADMAP.md) before starting a task.
2. Never commit secrets (`.env`), virtual environments (`.venv/`), `node_modules/`, database files, or uploaded PDFs (`storage/`).
3. Verify your changes before marking a task complete:
   - **Backend:** Run `pytest` inside `backend/`.
   - **Frontend:** Run `npm.cmd run lint` and `npm.cmd run build` inside `frontend/`.
4. Update `docs/IMPLEMENTATION_STATUS.md` only when features are actually implemented and verified.
