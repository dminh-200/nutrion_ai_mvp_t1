"""Kiểm thử hồi quy cho 2 bug backend phát hiện ở live E2E test."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

import db.session as db_session
from agent.graph import resume_review, run_request
from agent.tools_gateway import ToolsGateway
from config.settings import get_settings
from core.schemas import PatientProfile
from db.import_food import import_food_csv
from db.init_db import init_db
from db.models import MealPlan, MealPlanItem, QueryLog
from db.repo import (
    get_dashboard_dataset,
    get_meal_plan_detail,
    preview_and_verify_edited_items,
    record_review_for_finalized_plan,
)
from db.seed_patients import seed_patients
from guardrails.input import log_guardrail_event
from observability.tracing import mask_sensitive_data


@pytest.fixture()
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Cô lập SQLite DB và checkpoint DB tạm cho từng test."""
    db_file = tmp_path / "bugfix_test.db"
    ckpt_file = tmp_path / "bugfix_ckpt.sqlite"
    db_url = f"sqlite:///{db_file.as_posix()}"

    monkeypatch.setenv("DB_URL", db_url)
    monkeypatch.setenv("CHECKPOINT_DB", ckpt_file.as_posix())
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.setenv("TOOLS_MODE", "direct")
    get_settings.cache_clear()

    old_engine = db_session._engine
    old_factory = db_session._SessionLocal
    engine = db_session.create_db_engine(db_url)
    db_session._engine = engine
    db_session._SessionLocal = None
    init_db(engine)
    seed_patients(engine=engine)
    import_food_csv(engine=engine)

    try:
        yield db_file
    finally:
        engine.dispose()
        db_session._engine = old_engine
        db_session._SessionLocal = old_factory
        get_settings.cache_clear()


def test_resume_review_preserves_initial_query_log_latency(
    isolated_db: Path, tmp_path: Path
) -> None:
    """resume_review() không được làm mất latency_ms ban đầu của run_request() trên QueryLog."""
    _ = isolated_db
    ckpt = str(tmp_path / "bugfix_ckpt.sqlite")
    profile = PatientProfile(
        patient_code="P0001",
        age=48,
        sex="male",
        height_cm=170.0,
        weight_kg=70.0,
        activity_level="moderate",
        conditions=["t2d"],
        days=1,
    )
    tid = f"thread-bugfix-{uuid4().hex[:8]}"
    res1 = run_request(profile, thread_id=tid, checkpoint_db=ckpt, tools_mode="direct")
    assert res1["status"] == "pending_review"
    initial_latency = float(res1["metrics"]["latency_ms"])
    assert initial_latency > 0.0

    # Gửi giá trị latency gốc lớn hơn rõ rệt trong DB để kiểm tra chắc chắn không bị ghi đè
    with Session(db_session.get_engine()) as sess:
        qlog = sess.scalar(select(QueryLog).where(QueryLog.trace_id == res1["trace_id"]))
        assert qlog is not None
        qlog.latency_ms = 25000.0
        sess.commit()

    res2 = resume_review(
        thread_id=tid,
        decision="approve",
        note="Đạt chuẩn",
        checkpoint_db=ckpt,
        tools_mode="direct",
    )
    assert res2["status"] == "approved"
    assert float(res2["metrics"]["latency_ms"]) >= 25000.0

    with Session(db_session.get_engine()) as sess:
        qlog_after = sess.scalar(select(QueryLog).where(QueryLog.trace_id == res1["trace_id"]))
        assert qlog_after is not None
        assert qlog_after.status == "approved"
        assert qlog_after.latency_ms >= 25000.0


def test_resume_older_plan_after_newer_profile_for_same_patient(
    isolated_db: Path, tmp_path: Path
) -> None:
    """Duyệt thực đơn cũ của một patient_code vẫn phải thành công khi đã tạo hồ sơ mới hơn."""
    _ = isolated_db
    ckpt = str(tmp_path / "bugfix_ckpt.sqlite")
    profile = PatientProfile(
        patient_code="P0001",
        age=48,
        sex="male",
        height_cm=170.0,
        weight_kg=70.0,
        activity_level="moderate",
        conditions=["t2d"],
        days=1,
    )
    tid1 = f"thread-old-{uuid4().hex[:8]}"
    res1 = run_request(profile, thread_id=tid1, checkpoint_db=ckpt, tools_mode="direct")
    assert res1["status"] == "pending_review"

    # Tạo một yêu cầu khác cho cùng P0001 để sinh HealthProfile mới hơn trong DB
    tid2 = f"thread-new-{uuid4().hex[:8]}"
    profile_v2 = profile.model_copy(update={"preferences_text": "Ít ngọt hơn"})
    res2 = run_request(profile_v2, thread_id=tid2, checkpoint_db=ckpt, tools_mode="direct")
    assert res2["status"] == "pending_review"

    # Phê duyệt thực đơn cũ (tid1) không được lỗi mismatch profile_id
    res_app = resume_review(
        thread_id=tid1,
        decision="approve",
        note="Duyệt ca cũ sau khi có hồ sơ mới",
        checkpoint_db=ckpt,
        tools_mode="direct",
    )
    assert res_app["status"] == "approved"


@pytest.mark.mcp
def test_mcp_subprocess_inherits_parent_db_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MCP stdio subprocess phải kế thừa DB_URL từ tiến trình cha thay vì đọc nhầm DB mặc định."""
    db_file = tmp_path / "mcp_isolated.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DB_URL", db_url)
    get_settings.cache_clear()

    engine = db_session.create_db_engine(db_url)
    init_db(engine)
    # Không import food để DB tạm có 0 món; nếu MCP đọc đúng DB_URL tạm thì search_food phải trả []
    try:
        assert "DB_URL" in os.environ
        with ToolsGateway(mode="mcp") as gw:
            items = gw.search_food(query="", limit=10)
        assert items == []
    finally:
        engine.dispose()
        get_settings.cache_clear()


def test_f01_cannot_preview_or_approve_all_zero_or_empty_menu(
    isolated_db: Path, tmp_path: Path
) -> None:
    """F01: gửi toàn bộ grams=0 hoặc danh sách rỗng không thể qua verifier hay thành approved."""
    _ = isolated_db
    ckpt = str(tmp_path / "f01_ckpt.sqlite")
    profile = PatientProfile(
        patient_code="P0001",
        age=45,
        sex="male",
        height_cm=170.0,
        weight_kg=70.0,
        activity_level="moderate",
        conditions=["t2d"],
        days=1,
    )
    tid = f"thread-f01-{uuid4().hex[:8]}"
    paused = run_request(profile, thread_id=tid, checkpoint_db=ckpt, tools_mode="direct")
    assert paused["status"] == "pending_review"
    plan_id = int(paused["meal_plan_id"])

    detail = get_meal_plan_detail(plan_id)
    assert detail is not None and len(detail["items"]) > 0
    zeros = [
        {"day": it["day"], "meal": it["meal"], "food_id": it["food_id"], "grams": 0.0}
        for it in detail["items"]
    ]

    preview_zero = preview_and_verify_edited_items(plan_id, zeros)
    assert preview_zero["is_valid"] is False
    assert preview_zero["scored_items"] == []
    assert any(v["code"] in ("DAY_COUNT", "BELOW_FLOOR") for v in preview_zero["violations"])

    preview_empty = preview_and_verify_edited_items(plan_id, [])
    assert preview_empty["is_valid"] is False

    reduced = [
        {"day": it["day"], "meal": it["meal"], "food_id": it["food_id"], "grams": 10.0}
        for it in detail["items"]
    ]
    res_invalid = resume_review(
        thread_id=tid,
        decision="edit",
        note="Thử sửa sai",
        edited_items=reduced,
        checkpoint_db=ckpt,
        tools_mode="direct",
    )
    assert res_invalid["status"] == "needs_human_review"

    with pytest.raises(ValueError, match="vi phạm kiểm chứng"):
        record_review_for_finalized_plan(
            meal_plan_id=plan_id,
            reviewer_name="QA",
            decision="edit",
            note="Thử duyệt rỗng",
            edited_items=zeros,
        )

    with Session(db_session.get_engine()) as sess:
        plan_row = sess.get(MealPlan, plan_id)
        assert plan_row is not None
        assert plan_row.status == "needs_human_review"
        db_items = sess.scalars(
            select(MealPlanItem).where(MealPlanItem.meal_plan_id == plan_id)
        ).all()
        assert len(db_items) > 0


def test_f06_mask_sensitive_data_masks_chat_message_and_history() -> None:
    """F06: mask_sensitive_data phải che nội dung message và history chat thô."""
    masked = mask_sensitive_data(
        {
            "message": "Tên giả: NGUOI_GIA_LAP_QA; mã QA_PRIVATE_123",
            "history": [{"role": "user", "content": "Bí mật hội thoại"}],
        }
    )
    assert "message" not in masked
    assert "history" not in masked
    assert masked["message_length"] > 0
    assert masked["history_turns"] == 1
    assert "NGUOI_GIA_LAP_QA" not in str(masked)
    assert "Bí mật hội thoại" not in str(masked)


def test_f11_f12_f14_detail_snippets_risk_and_dashboard_filtering(
    isolated_db: Path, tmp_path: Path
) -> None:
    """F11/F12/F14: get_meal_plan_detail giữ risk/snippets; dashboard lọc đúng bệnh & đếm chat."""
    _ = isolated_db
    ckpt = str(tmp_path / "f11_f14_ckpt.sqlite")

    # F11: Ca nguy cơ cao giữ nguyên risk khi đọc lại từ DB
    res_risk = run_request(
        PatientProfile(
            patient_code="P_F11_LACT",
            age=28,
            sex="female",
            height_cm=160.0,
            weight_kg=55.0,
            activity_level="light",
            conditions=["t2d"],
            lactating=True,
            days=1,
        ),
        thread_id=f"thread-lact-{uuid4().hex[:8]}",
        checkpoint_db=ckpt,
        tools_mode="direct",
    )
    det_risk = get_meal_plan_detail(int(res_risk["meal_plan_id"]))
    assert det_risk is not None
    assert det_risk["risk"] is not None
    assert "RISK_LACT" in det_risk["risk"]["reasons"]

    # F12: Event chat_input không có QueryLog vẫn được đếm trên dashboard
    log_guardrail_event(
        session_id="chat-f12-sess",
        layer="chat_input",
        event_type="MEDICAL_ADVICE",
        reason="Chặn yêu cầu kê đơn thuốc",
    )
    dash = get_dashboard_dataset(include_synthetic=False)
    assert dash["kpis"]["guardrail_trigger_count"] >= 1
    assert "MEDICAL_ADVICE" in dash["charts"]["guardrails_by_type"]["labels"]

    # F14: Cùng patient_code có phiên t2d và phiên htn -> lọc t2d không trả về phiên htn
    p_t2d = PatientProfile(
        patient_code="P_F14_SAME",
        age=49,
        sex="male",
        height_cm=170.0,
        weight_kg=70.0,
        activity_level="moderate",
        conditions=["t2d"],
        days=1,
    )
    p_htn = p_t2d.model_copy(update={"conditions": ["htn"]})
    r1 = run_request(
        p_t2d, thread_id=f"t2d-{uuid4().hex[:8]}", checkpoint_db=ckpt, tools_mode="direct"
    )
    r2 = run_request(
        p_htn, thread_id=f"htn-{uuid4().hex[:8]}", checkpoint_db=ckpt, tools_mode="direct"
    )

    dash_t2d = get_dashboard_dataset(condition="t2d", include_synthetic=False)
    sids = {row["session_id"] for row in dash_t2d["logs"]}
    assert r1["session_id"] in sids
    assert r2["session_id"] not in sids
