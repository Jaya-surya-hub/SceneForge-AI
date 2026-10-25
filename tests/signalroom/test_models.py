"""Tests for foundational models and proof ledger integrity."""

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from signalroom.models.project import Project
from signalroom.models.question import Question
from signalroom.models.run import Run
from signalroom.models.evidence import EvidenceReference
from signalroom.storage.artifact_store import GENESIS_PREV_HASH


def test_create_project_and_questions(db_session: Session):
    project = Project(
        id="PRJ-TEST-01",
        name="Test IncuBrix Project",
        slug="test-incubrix-project",
        description="Testing foundational models",
        target_domains=["incubrix.com"],
        default_markets=["US", "UK", "IN"],
    )
    db_session.add(project)
    db_session.commit()

    question = Question(
        id="Q-TEST-01",
        project_id=project.id,
        text="How do creators repurpose long-form podcast video into vertical shorts?",
        journey_stage="Repurpose",
        search_intent="informational",
        source_type="google_autocomplete",
        source_url="https://www.google.com/search?q=test",
        target_market="US",
        language="en",
        is_demo=True,
    )
    db_session.add(question)
    db_session.commit()

    retrieved_q = db_session.query(Question).filter(Question.id == "Q-TEST-01").first()
    assert retrieved_q is not None
    assert retrieved_q.journey_stage == "Repurpose"
    assert retrieved_q.project.name == "Test IncuBrix Project"


def test_create_run_and_evidence_ledger(db_session: Session):
    run = Run(
        id="RUN-TEST-01",
        run_type="full_discovery",
        status="completed",
        markets=["US", "UK"],
        assistants=["google_search", "chatgpt"],
    )
    db_session.add(run)
    db_session.commit()

    evidence = EvidenceReference(
        id="EV-TEST-01",
        question_id="Q-TEST-01",
        run_id="RUN-TEST-01",
        provider="google_search",
        collection_method="browser_fixture",
        timestamp=datetime.now(timezone.utc),
        market="US",
        artifact_path="test_sub/artifact_01.json",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        prev_ledger_hash=GENESIS_PREV_HASH,
        current_ledger_hash="a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e",
        execution_status="success",
        runtime_ms=120,
        cost_usd=0.005,
        is_demo=True,
    )
    db_session.add(evidence)
    db_session.commit()

    retrieved_ev = db_session.query(EvidenceReference).filter(EvidenceReference.id == "EV-TEST-01").first()
    assert retrieved_ev is not None
    assert retrieved_ev.prev_ledger_hash == GENESIS_PREV_HASH
    assert retrieved_ev.execution_status == "success"
