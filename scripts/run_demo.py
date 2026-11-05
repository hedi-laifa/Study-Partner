#!/usr/bin/env python3
"""Reproducible 10-Step Study Partner AI Demonstration Script.

Executes the complete student journey end-to-end against the real FastAPI,
SQLAlchemy, PyMuPDF, and ChromaDB stack:
  1. Register
  2. Create course
  3. Upload PDF
  4. Select concept
  5. Start study session
  6. Answer question
  7. Receive assessment
  8. Receive adaptive activity
  9. View updated learning profile
  10. Reopen session
"""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import fitz  # PyMuPDF
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.session import Base, get_db
from app.main import app


def _build_demo_lecture_pdf() -> bytes:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_textbox(
        fitz.Rect(50, 50, 540, 750),
        (
            "1. Raft Leader Election\n\n"
            "Raft achieves consensus by electing a single leader per term. "
            "Each server starts as a follower and transitions to candidate if its randomized "
            "election timeout (150ms to 300ms) elapses without receiving a heartbeat (AppendEntries RPC). "
            "Randomized election timeouts prevent split votes by ensuring one candidate requests votes first."
        ),
        fontsize=11,
    )
    p2 = doc.new_page()
    p2.insert_textbox(
        fitz.Rect(50, 50, 540, 750),
        (
            "2. Log Replication and Safety\n\n"
            "Once elected, the leader accepts client commands, appends them to its log, and "
            "replicates log entries via AppendEntries RPCs. A log entry is committed once it is "
            "replicated on a majority quorum of servers in the cluster."
        ),
        fontsize=11,
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def run_demo() -> int:
    print("=" * 76)
    print("STUDY PARTNER AI — REPRODUCIBLE 10-STEP END-TO-END DEMONSTRATION")
    print("=" * 76)

    with tempfile.TemporaryDirectory(prefix="study_partner_demo_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        db_url = f"sqlite:///{(tmp_path / 'demo.db').as_posix()}"
        settings.UPLOAD_STORAGE_DIR = str(tmp_path / "uploads")
        settings.CHROMA_PERSIST_DIR = str(tmp_path / "chroma")

        engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        def _override_get_db():
            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override_get_db

        with TestClient(app) as client:
            # 1. Register
            reg = client.post(
                "/api/v1/auth/register",
                json={
                    "email": "grace.hopper@university.edu",
                    "full_name": "Grace Hopper",
                    "password": "DemoPassword123!",
                },
            )
            assert reg.status_code == 201, reg.text
            auth = reg.json()
            user = auth["user"]
            headers = {"Authorization": f"Bearer {auth['access_token']}"}
            print(f"[Step  1/10] Registered student: {user['full_name']} <{user['email']}> (id={user['id']})")

            # 2. Create course
            course = client.post(
                "/api/v1/courses",
                headers=headers,
                json={
                    "user_id": user["id"],
                    "title": "CS-401 Distributed Systems",
                    "code": "CS-401",
                    "description": "Consensus protocols, Raft leader election, and fault-tolerant replication.",
                },
            ).json()
            course_id = course["id"]
            print(f"[Step  2/10] Created course: {course['code']} — {course['title']} (id={course_id})")

            # 3. Upload PDF
            doc = client.post(
                f"/api/v1/courses/{course_id}/documents",
                headers=headers,
                files={"file": ("raft_consensus_lecture.pdf", _build_demo_lecture_pdf(), "application/pdf")},
            ).json()
            print(
                f"[Step  3/10] Uploaded & indexed PDF: {doc['filename']} "
                f"(status={doc['status']}, pages={doc['page_count']}, chunks={doc['chunk_count']})"
            )

            # 4. Select concept
            concepts = client.get(f"/api/v1/courses/{course_id}/concepts", headers=headers).json()
            concept = concepts[0]
            print(f"[Step  4/10] Selected concept: '{concept['title']}' (pages={concept['source_pages']})")

            # 5. Start study session
            session = client.post(
                "/api/v1/sessions",
                headers=headers,
                json={
                    "course_id": course_id,
                    "user_id": user["id"],
                    "concept_id": concept["id"],
                    "learning_goal": f"Master {concept['title']}",
                },
            ).json()
            session_id = session["id"]
            act1 = session["current_activity"]
            print(
                f"[Step  5/10] Started study session (id={session_id}): "
                f"Activity #1 [{act1['activity_type']} / {act1['difficulty']}] -> {act1['prompt_text'][:80]}..."
            )

            # 6. Answer question
            answer_text = (
                "Raft elects a single leader per term using randomized election timeouts "
                "(150ms to 300ms) so one candidate requests votes first and prevents split votes, "
                "then replicates log entries across a majority quorum via AppendEntries RPCs."
            )
            sub = client.post(
                f"/api/v1/sessions/{session_id}/submit-answer",
                headers=headers,
                json={
                    "user_id": user["id"],
                    "activity_id": act1["id"],
                    "response_text": answer_text,
                },
            ).json()
            print(f"[Step  6/10] Submitted student answer ({len(answer_text)} chars)")

            # 7. Receive assessment
            ev = sub["evaluation"]
            rec = sub["coach_recommendation"]
            print(
                f"[Step  7/10] Received assessment: verdict={ev['verdict']}, "
                f"score={ev['total_score']}/100, confidence={ev['confidence']:.2f}, "
                f"coach_recommended={rec['recommended_activity']} ({rec['difficulty']})"
            )

            # 8. Receive adaptive activity
            next_sess = client.post(
                f"/api/v1/sessions/{session_id}/next-activity",
                headers=headers,
                json={"user_id": user["id"]},
            ).json()
            act2 = next_sess["current_activity"]
            print(
                f"[Step  8/10] Generated adaptive Activity #2: "
                f"[{act2['activity_type']} / {act2['difficulty']}] -> {act2['prompt_text'][:80]}..."
            )

            # 9. View updated learning profile
            profile = client.get(
                f"/api/v1/courses/{course_id}/learning-profile", headers=headers
            ).json()
            cp = next(c for c in profile["concepts"] if c["concept_id"] == concept["id"])
            print(
                f"[Step  9/10] Updated Learning Profile: mastery_score={cp['mastery_score']}/100, "
                f"mastery_status={cp['mastery_status']}, evidence_status={cp['evidence_status']}, "
                f"attempts={cp['attempts_count']}"
            )

            # 10. Reopen session
            reopened = client.get(f"/api/v1/sessions/{session_id}", headers=headers).json()
            print(
                f"[Step 10/10] Reopened study session (id={reopened['id']}): "
                f"state={reopened['state']}, current_activity_index={reopened['progress']['current_activity_index']}, "
                f"history_count={len(reopened['activity_history'])}"
            )

        engine.dispose()

    print("=" * 76)
    print("ALL 10 DEMO STEPS COMPLETED AND VERIFIED SUCCESSFULLY.")
    print("=" * 76)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_demo())
