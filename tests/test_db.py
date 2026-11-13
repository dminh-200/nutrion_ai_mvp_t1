"""Kiểm thử CSDL SQLite, 14 bảng, foreign_keys, seed bệnh nhân và repo CRUD."""

import json
from pathlib import Path

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.init_db import init_db
from db.models import Allergen, Condition, HealthProfile, Patient
from db.repo import (
    create_guardrail_event,
    create_meal_plan,
    create_query_log,
    create_review,
    get_meal_plan_by_thread,
    list_guardrail_events,
    list_query_logs,
    list_reviews_for_plan,
    update_meal_plan_status,
)
from db.seed_patients import seed_patients
from db.session import create_db_engine


def test_init_db_tables_and_foreign_keys(tmp_path: Path) -> None:
    """Đảm bảo đủ 14 bảng và PRAGMA foreign_keys=ON hoạt động."""
    db_file = tmp_path / "test.db"
    engine = create_db_engine(f"sqlite:///{db_file}")
    init_db(engine)

    tables = set(inspect(engine).get_table_names())
    expected = {
        "patient",
        "health_profile",
        "condition",
        "profile_condition",
        "allergen",
        "profile_allergen",
        "food",
        "food_nutrient",
        "meal_plan",
        "meal_plan_item",
        "guideline_doc",
        "review",
        "query_log",
        "guardrail_event",
    }
    assert expected.issubset(tables)
    assert len(tables) == 14

    with Session(engine) as session:
        fk_on = session.execute(text("PRAGMA foreign_keys")).scalar()
        assert fk_on == 1
        assert len(session.scalars(select(Condition)).all()) == 4
        assert len(session.scalars(select(Allergen)).all()) == 6

        # Thử vi phạm khóa ngoại
        session.add(
            HealthProfile(
                patient_id=9999,
                age=30,
                sex="male",
                height_cm=170,
                weight_kg=65,
                activity_level="light",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    # Chạy lại init_db không nhân đôi dữ liệu
    init_db(engine)
    with Session(engine) as session:
        assert len(session.scalars(select(Condition)).all()) == 4


def test_seed_patients_idempotent_and_distribution(tmp_path: Path) -> None:
    """Seed 30 bệnh nhân đúng phân bố, chạy lại không nhân đôi."""
    db_file = tmp_path / "seed.db"
    json_file = tmp_path / "patients_seed.json"
    engine = create_db_engine(f"sqlite:///{db_file}")

    inserted1 = seed_patients(engine=engine, json_path=json_file)
    inserted2 = seed_patients(engine=engine, json_path=json_file)

    assert inserted1 == 30
    assert inserted2 == 0
    assert json_file.exists()

    data = json.loads(json_file.read_text(encoding="utf-8"))
    assert len(data) == 30
    assert data[0]["patient_code"] == "P0001"
    assert data[-1]["patient_code"] == "P0030"

    with Session(engine) as session:
        assert len(session.scalars(select(Patient)).all()) == 30
        assert len(session.scalars(select(HealthProfile)).all()) == 30


def test_repo_crud(tmp_path: Path) -> None:
    """Kiểm thử CRUD cơ bản cho meal_plan, review, query_log, guardrail_event."""
    db_file = tmp_path / "repo.db"
    json_file = tmp_path / "patients_seed.json"
    engine = create_db_engine(f"sqlite:///{db_file}")
    seed_patients(engine=engine, json_path=json_file)

    with Session(engine) as session:
        profile = session.scalars(select(HealthProfile)).first()
        assert profile is not None

        plan = create_meal_plan(
            session,
            profile_id=profile.id,
            thread_id="thread-001",
            status="pending_review",
        )
        assert get_meal_plan_by_thread(session, "thread-001") is not None

        updated = update_meal_plan_status(session, plan.id, status="approved", retry_count=1)
        assert updated is not None
        assert updated.status == "approved"

        create_review(session, meal_plan_id=plan.id, reviewer_name="BS A", decision="approve")
        assert len(list_reviews_for_plan(session, plan.id)) == 1

        create_query_log(
            session,
            session_id="sess-1",
            patient_code="P0001",
            status="approved",
            meal_plan_id=plan.id,
        )
        assert len(list_query_logs(session)) == 1

        create_guardrail_event(
            session,
            session_id="sess-1",
            layer="input",
            event_type="high_risk",
            reason="RISK_PREG",
        )
        assert len(list_guardrail_events(session, session_id="sess-1")) == 1
        session.commit()
