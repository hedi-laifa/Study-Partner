# Study Partner AI — Architectural Decisions & Risk Register

## 1. Architectural Decision Records (ADRs)

### ADR-001: Python State Machine Initially Over LangGraph for MVP Orchestration
- **Context:** Multi-agent educational workflows require strict progression through pedagogical phases (`TEACHING -> QUESTIONING -> EVALUATING -> COACHING`). Frameworks like LangGraph are powerful for cyclic graphs but introduce extra abstraction layers and debugging overhead during initial MVP development.
- **Decision:** Implement the MVP **Orchestrator** as an explicit, deterministic **Python State Machine** operating over a typed `SessionContext` object.
- **Consequences:**
  - *Pros:* Zero framework lock-in, straightforward debugging, fast unit testing, deterministic state guards, and complete control over database transaction boundaries.
  - *Migration Path:* Because each agent accepts `SessionContext` and returns a Pydantic model, the `Orchestrator` can be replaced by a LangGraph `StateGraph` in a future iteration without modifying agents or API routers.

### ADR-002: Local AI Stack (Ollama + Sentence Transformers + ChromaDB)
- **Context:** University students upload large course PDFs and run frequent study/assessment loops. Cloud LLM APIs incur recurring per-token costs and raise privacy concerns for copyrighted course materials.
- **Decision:** Use **Ollama** for local LLM inference, **Sentence Transformers (`all-MiniLM-L6-v2`)** for local CPU/GPU embeddings, and **ChromaDB** for vector storage.
- **Consequences:**
  - *Pros:* 100% free runtime cost, full data privacy, offline capability once models are downloaded.
  - *Cons:* Local 7B–8B parameter models are less forgiving with complex nested JSON than frontier cloud models, requiring strict Pydantic validation and retry wrappers.

### ADR-003: Deterministic Python Mastery Calculation vs. LLM-Decided Scores
- **Context:** Having an LLM directly output a student's cumulative mastery percentage across sessions leads to inconsistent math and erratic progression.
- **Decision:** The **Assessment Agent** evaluates only the *current answer* against the explicit rubric criteria (producing a session assessment score $S_{\text{new}} \in [0, 100]$). The backend `MasteryService` computes the cumulative concept mastery score deterministically in Python using an exponential moving average ($0.4 \cdot M_{\text{old}} + 0.6 \cdot S_{\text{new}}$).
- **Consequences:**
  - *Pros:* Auditable, mathematically consistent mastery scores and predictable thresholds (`< 50` Reteach, `50–79` Practice Again, `>= 80` Mastered/Advance).

### ADR-004: Hybrid Persistence (PostgreSQL for State + ChromaDB for Vectors)
- **Context:** Vector databases excel at semantic similarity search but are poorly suited for relational integrity, transactional session state, and structured rubric analytics.
- **Decision:** Use **PostgreSQL 16** (via SQLAlchemy 2.0 + Alembic) as the primary system of record for all domain entities, and use **ChromaDB** strictly as a secondary index for document text chunks.
- **Consequences:**
  - *Pros:* Strong foreign-key integrity, clean cascading deletes, and rich querying for mastery dashboards.
  - *Cons:* Requires application-level synchronization when deleting documents so ChromaDB vectors are cleaned up alongside PostgreSQL records.

### ADR-005: PyMuPDF (`fitz`) for PDF Extraction
- **Context:** Python offers several PDF libraries (`pypdf`, `pdfplumber`, `PyMuPDF`).
- **Decision:** Use **PyMuPDF (`fitz`)**.
- **Consequences:**
  - *Pros:* Significantly faster extraction speed on multi-page lecture slides and textbooks, reliable page boundary preservation for citation metadata, and minimal memory overhead.

---

## 2. Technical Risk Register & Mitigations

| ID | Risk Description | Likelihood | Impact | Mitigation Strategy |
| :--- | :--- | :---: | :---: | :--- |
| **R-01** | **Local LLM outputs malformed JSON** or misses required rubric fields when grading or extracting concepts. | High | High | Use Ollama's structured JSON mode (`format="json"` or JSON schema), keep Pydantic schemas flat and well-documented in prompts, and implement an automatic 2-attempt repair retry in `llm_client.py`. |
| **R-02** | **Hallucinated explanations or off-syllabus questions** not grounded in the uploaded PDF. | Medium | High | Inject top-$k$ retrieved ChromaDB chunks directly into Tutor and Assessment system prompts with strict instructions to rely *only* on provided context and require explicit page citations (`cited_pages`). |
| **R-03** | **Slow PDF ingestion or LLM inference latency** on machines without a dedicated GPU. | Medium | Medium | Use lightweight `all-MiniLM-L6-v2` embeddings (runs in milliseconds on CPU), cap chunk count per concept extraction prompt, and display clear step-by-step progress indicators in the React UI. |
| **R-04** | **Scanned / image-only PDFs** uploaded by students yield zero extractable text. | Medium | Medium | Validate extracted character count in `pdf_extractor.py`. If a PDF contains $< 50$ extractable characters, fail fast with a clear `422 Unprocessable Entity` message informing the student that text-selectable PDFs are required in the MVP. |
| **R-05** | **PostgreSQL and ChromaDB drift** if a document upload fails halfway through processing. | Low | Medium | Track `Document.status` (`UPLOADED -> PROCESSING -> READY / FAILED`). Wrap DB updates in transactions and clean up partial ChromaDB vectors on failure. |
