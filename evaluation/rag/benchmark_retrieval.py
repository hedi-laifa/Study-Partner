"""Retrieval & Grounded Tutor Benchmark for Study Partner AI (Phase 4).

Evaluates:
1. Relevant passage retrieval accuracy (Top-1 & Top-3 hit rate)
2. Page and document citation correctness
3. Retrieval latency (mean & max in milliseconds)
4. Strict course ownership & cross-course isolation
5. Insufficient-evidence detection on unsupported out-of-syllabus questions
"""

from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure backend package is importable when executed directly
ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.models  # noqa: E402, F401
from app.db.session import Base  # noqa: E402
from app.retrieval.embeddings import EmbeddingService  # noqa: E402
from app.retrieval.retriever import RetrievalService  # noqa: E402
from app.retrieval.vector_store import PersistentChromaStore  # noqa: E402
from app.schemas.course import CourseCreate  # noqa: E402
from app.schemas.tutor import TutorAskRequest  # noqa: E402
from app.services.course_service import CourseService  # noqa: E402
from app.services.ingestion_service import IngestionService  # noqa: E402
from app.services.user_service import UserService  # noqa: E402
from app.tutor.llm_client import OllamaLLMClient  # noqa: E402
from app.tutor.service import TutorService  # noqa: E402


@dataclass
class BenchmarkQueryCase:
    """Single benchmark query specification."""

    query_id: str
    question: str
    expected_keywords: list[str]
    expected_page: int | None
    should_be_insufficient: bool = False


@dataclass
class BenchmarkQueryResult:
    """Evaluation result for a single benchmark query."""

    query_id: str
    question: str
    top1_hit: bool
    top3_hit: bool
    citation_page_correct: bool
    insufficient_evidence_actual: bool
    insufficient_evidence_expected: bool
    cross_course_leaked: bool
    latency_ms: float
    max_relevance_score: float
    retrieved_pages: list[int]


def _build_pdf_bytes(pages: list[tuple[str, str]]) -> bytes:
    """Create an in-memory multi-page PDF from (heading, body) tuples."""
    doc = fitz.open()
    for heading, body in pages:
        page = doc.new_page()
        text = f"{heading}\n\n{body}"
        page.insert_textbox(fitz.Rect(50, 50, 545, 780), text, fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def run_retrieval_benchmark() -> dict[str, Any]:
    """Execute the RAG retrieval & grounding benchmark and return structured metrics."""
    from app.core.config import settings

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        tmp_path = Path(tmp_dir)
        db_url = f"sqlite:///{(tmp_path / 'benchmark.db').as_posix()}"
        engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        embedding_service = EmbeddingService(model_name="all-MiniLM-L6-v2", dimension=384)
        vector_store = PersistentChromaStore(
            persist_dir=tmp_path / "chroma_bench",
            collection_name="benchmark_course_chunks",
        )
        prev_fallback = settings.TUTOR_OFFLINE_FALLBACK
        settings.TUTOR_OFFLINE_FALLBACK = True

        try:
            with SessionLocal() as session:
                user_service = UserService(session)
                course_service = CourseService(session)
                ingestion_service = IngestionService(
                    session,
                    storage_root=tmp_path / "uploads",
                    embedding_service=embedding_service,
                    vector_store=vector_store,
                )
                retrieval_service = RetrievalService(
                    session,
                    embedding_service=embedding_service,
                    vector_store=vector_store,
                )
                llm_client = OllamaLLMClient(
                    base_url="http://localhost:11434",
                    model="llama3.2",
                    timeout_seconds=0.15,
                )
                tutor_service = TutorService(
                    session,
                    retrieval_service=retrieval_service,
                    llm_client=llm_client,
                )

                student = user_service.get_or_create_default_user()

                # Course A: Operating Systems & Virtual Memory
                os_course = course_service.create_course(
                    CourseCreate(
                        title="CS-401 Operating Systems",
                        code="CS401",
                        description="Virtual memory, paging, scheduling, and concurrency.",
                        user_id=student.id,
                    )
                )

                # Course B: Molecular Biology (distractor course to verify strict isolation)
                bio_course = course_service.create_course(
                    CourseCreate(
                        title="BIO-202 Cellular Biology",
                        code="BIO202",
                        description="Cellular respiration, ATP synthesis, and mitosis.",
                        user_id=student.id,
                    )
                )

                os_pages = [
                    (
                        "1. Virtual Memory and Page Tables",
                        (
                            "Virtual memory is a memory management technique that provides an "
                            "idealized abstraction of the storage resources that are actually available "
                            "on a given machine. The hardware Memory Management Unit (MMU) translates "
                            "virtual addresses into physical frame addresses using a hierarchical page table. "
                            "When a process references a virtual page that is not mapped into physical RAM, "
                            "the MMU raises a page fault trap to the operating system kernel."
                        ),
                    ),
                    (
                        "2. Translation Lookaside Buffer (TLB)",
                        (
                            "A Translation Lookaside Buffer (TLB) is a specialized associative hardware cache "
                            "inside the CPU that stores recent virtual-to-physical address translations. "
                            "On a TLB hit, address translation completes in a single clock cycle without "
                            "reading the page table in main memory. On a TLB miss, the hardware or OS walks "
                            "the page table hierarchy and updates the TLB entry. Context switches flush "
                            "non-global TLB entries unless Address Space Identifiers (ASIDs) are used."
                        ),
                    ),
                    (
                        "3. Deadlock Conditions and Coffman Criteria",
                        (
                            "A deadlock occurs when a set of concurrent threads or processes are permanently "
                            "blocked because each thread holds a resource and waits for another resource held "
                            "by another thread in the same set. The four necessary Coffman conditions for "
                            "deadlock are: (1) Mutual Exclusion, (2) Hold and Wait, (3) No Preemption, and "
                            "(4) Circular Wait. Eliminating any single condition prevents deadlocks; in practice, "
                            "systems enforce a strict global lock acquisition ordering to break Circular Wait."
                        ),
                    ),
                    (
                        "4. CPU Scheduling and Multi-Level Feedback Queue",
                        (
                            "The Multi-Level Feedback Queue (MLFQ) scheduler dynamically adapts thread priorities "
                            "based on observed CPU burst behavior without requiring prior knowledge of job lengths. "
                            "Interactive I/O-bound jobs that yield the CPU before their time quantum expires stay "
                            "in high-priority queues, whereas CPU-bound jobs that exhaust their quantum are demoted "
                            "to lower-priority queues. Periodic priority boosts prevent starvation."
                        ),
                    ),
                ]

                bio_pages = [
                    (
                        "1. Mitochondrial ATP Synthase and Oxidative Phosphorylation",
                        (
                            "Oxidative phosphorylation occurs across the inner mitochondrial membrane where the "
                            "electron transport chain pumps protons into the intermembrane space, establishing "
                            "an electrochemical proton gradient. ATP synthase uses this proton-motive force "
                            "to phosphorylate ADP into adenosine triphosphate (ATP)."
                        ),
                    )
                ]

                os_pdf_bytes = _build_pdf_bytes(os_pages)
                bio_pdf_bytes = _build_pdf_bytes(bio_pages)

                ingestion_service.ingest_pdf(
                    course_id=os_course.id,
                    user_id=student.id,
                    filename="os_lecture_notes.pdf",
                    file_bytes=os_pdf_bytes,
                    content_type="application/pdf",
                )
                ingestion_service.ingest_pdf(
                    course_id=bio_course.id,
                    user_id=student.id,
                    filename="biology_notes.pdf",
                    file_bytes=bio_pdf_bytes,
                    content_type="application/pdf",
                )

                cases = [
                    BenchmarkQueryCase(
                        query_id="Q1_MMU_PAGE_FAULT",
                        question="How does the MMU translate virtual addresses and when does a page fault trap occur?",
                        expected_keywords=["mmu", "virtual", "page fault"],
                        expected_page=1,
                        should_be_insufficient=False,
                    ),
                    BenchmarkQueryCase(
                        query_id="Q2_TLB_ASID",
                        question="What is the role of the Translation Lookaside Buffer (TLB) and Address Space Identifiers (ASIDs)?",
                        expected_keywords=["tlb", "cache", "asid"],
                        expected_page=2,
                        should_be_insufficient=False,
                    ),
                    BenchmarkQueryCase(
                        query_id="Q3_DEADLOCK_COFFMAN",
                        question="What are the four Coffman conditions required for a deadlock and how is circular wait prevented?",
                        expected_keywords=["coffman", "mutual exclusion", "circular wait"],
                        expected_page=3,
                        should_be_insufficient=False,
                    ),
                    BenchmarkQueryCase(
                        query_id="Q4_MLFQ_SCHEDULING",
                        question="How does the Multi-Level Feedback Queue (MLFQ) scheduler prevent starvation and handle I/O-bound jobs?",
                        expected_keywords=["mlfq", "quantum", "starvation"],
                        expected_page=4,
                        should_be_insufficient=False,
                    ),
                    BenchmarkQueryCase(
                        query_id="Q5_UNSUPPORTED_BIO_IN_OS_COURSE",
                        question="How does mitochondrial ATP synthase use the proton gradient during oxidative phosphorylation?",
                        expected_keywords=[],
                        expected_page=None,
                        should_be_insufficient=True,
                    ),
                    BenchmarkQueryCase(
                        query_id="Q6_UNSUPPORTED_QUANTUM_GRAVITY",
                        question="Explain loop quantum gravity spin networks and black hole Bekenstein-Hawking entropy.",
                        expected_keywords=[],
                        expected_page=None,
                        should_be_insufficient=True,
                    ),
                ]

                results: list[BenchmarkQueryResult] = []
                for case in cases:
                    response = tutor_service.ask_question(
                        course_id=os_course.id,
                        payload=TutorAskRequest(
                            question=case.question,
                            top_k=3,
                            user_id=student.id,
                        ),
                        requesting_user_id=student.id,
                    )

                    cross_course_leaked = any(
                        ref.course_id != os_course.id for ref in response.source_references
                    )

                    if case.should_be_insufficient:
                        top1_hit = response.insufficient_evidence is True
                        top3_hit = response.insufficient_evidence is True
                        citation_ok = (
                            response.insufficient_evidence is True
                            and len(response.source_references) == 0
                        )
                    else:
                        top1_hit = False
                        top3_hit = False
                        if response.source_references:
                            first_ref = response.source_references[0]
                            top1_hit = (
                                case.expected_page is not None
                                and first_ref.page_start <= case.expected_page <= first_ref.page_end
                            )
                            top3_hit = any(
                                case.expected_page is not None
                                and ref.page_start <= case.expected_page <= ref.page_end
                                for ref in response.source_references[:3]
                            )
                        citation_ok = (
                            case.expected_page in response.relevant_pages
                            and not response.insufficient_evidence
                        )

                    results.append(
                        BenchmarkQueryResult(
                            query_id=case.query_id,
                            question=case.question,
                            top1_hit=top1_hit,
                            top3_hit=top3_hit,
                            citation_page_correct=citation_ok,
                            insufficient_evidence_actual=response.insufficient_evidence,
                            insufficient_evidence_expected=case.should_be_insufficient,
                            cross_course_leaked=cross_course_leaked,
                            latency_ms=response.retrieval_metadata.retrieval_latency_ms,
                            max_relevance_score=response.retrieval_metadata.max_relevance_score,
                            retrieved_pages=response.relevant_pages,
                        )
                    )

                supported_results = [r for r in results if not r.insufficient_evidence_expected]
                unsupported_results = [r for r in results if r.insufficient_evidence_expected]
                latencies = [r.latency_ms for r in results]

                summary = {
                    "total_queries": len(results),
                    "supported_queries": len(supported_results),
                    "unsupported_queries": len(unsupported_results),
                    "top1_accuracy": round(
                        sum(1 for r in supported_results if r.top1_hit) / len(supported_results), 4
                    ),
                    "top3_accuracy": round(
                        sum(1 for r in supported_results if r.top3_hit) / len(supported_results), 4
                    ),
                    "citation_accuracy": round(
                        sum(1 for r in results if r.citation_page_correct) / len(results), 4
                    ),
                    "insufficient_evidence_detection_rate": round(
                        sum(
                            1
                            for r in unsupported_results
                            if r.insufficient_evidence_actual is True
                        )
                        / len(unsupported_results),
                        4,
                    ),
                    "cross_course_leak_count": sum(1 for r in results if r.cross_course_leaked),
                    "mean_retrieval_latency_ms": round(sum(latencies) / len(latencies), 3),
                    "max_retrieval_latency_ms": round(max(latencies), 3),
                    "embedding_cache_hits": embedding_service.cache_hits,
                    "embedding_cache_misses": embedding_service.cache_misses,
                    "queries": [asdict(r) for r in results],
                }
                return summary
        finally:
            settings.TUTOR_OFFLINE_FALLBACK = prev_fallback
            engine.dispose()


if __name__ == "__main__":
    report = run_retrieval_benchmark()
    output_path = Path(__file__).resolve().parent / "latest_benchmark_report.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
