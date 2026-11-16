"""Bộ kiểm thử tự động cho Milestone M11: Streamlit UI, DAL repo helpers, seed script và styling."""

import json
import py_compile
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ui_helpers import (
    format_activity_level,
    format_allergen,
    format_condition,
    format_meal_name,
    format_status,
    get_disclaimer_text,
    get_status_badge_html,
    init_session_state,
)
from db.models import (
    Food,
    HealthProfile,
    MealPlanItem,
    QueryLog,
    Review,
)
from db.repo import (
    create_meal_plan,
    ensure_db_ready,
    get_dashboard_dataset,
    get_meal_plan_detail,
    get_system_warnings,
    list_meal_plans_for_ui,
    load_sample_patients,
    preview_and_verify_edited_items,
    record_review_for_finalized_plan,
)
from db.session import create_db_engine
from scripts.seed_logs import seed_logs


def test_ui_formatters() -> None:
    """Kiểm tra các hàm định dạng tiếng Việt cho bệnh lý, dị nguyên, bữa ăn, trạng thái."""
    assert format_condition("t2d") == "Đái tháo đường T2"
    assert format_condition("htn") == "Tăng huyết áp"
    assert format_condition("gout") == "Gout"
    assert format_condition("obesity") == "Béo phì"
    assert format_condition("unknown") == "unknown"

    assert format_allergen("seafood") == "Hải sản"
    assert format_allergen("peanut") == "Đậu phộng"
    assert format_allergen("milk") == "Sữa"

    assert "Ít vận động" in format_activity_level("sedentary")
    assert format_meal_name("breakfast") == "Bữa sáng"
    assert format_meal_name("lunch") == "Bữa trưa"
    assert format_meal_name("dinner") == "Bữa tối"
    assert format_meal_name("snack") == "Bữa phụ"

    assert format_status("approved") == "Đã duyệt"
    assert format_status("redirect_to_doctor") == "Chuyển hướng bác sĩ"
    assert format_status("blocked") == "Bị chặn"


def test_status_badge_html() -> None:
    """Kiểm tra mã HTML sinh ra cho các pill status badges."""
    badge_app = get_status_badge_html("approved")
    assert "badge-approved" in badge_app
    assert "Đã duyệt" in badge_app

    badge_pend = get_status_badge_html("pending_review")
    assert "badge-pending" in badge_pend
    assert "Chờ duyệt" in badge_pend

    badge_needs = get_status_badge_html("needs_human_review")
    assert "badge-needs-review" in badge_needs
    assert "Cần chuyên gia xem" in badge_needs

    badge_redir = get_status_badge_html("redirect_to_doctor")
    assert "badge-redirect" in badge_redir
    assert "Chuyển hướng bác sĩ" in badge_redir

    badge_blk = get_status_badge_html("blocked")
    assert "badge-blocked" in badge_blk
    assert "Bị chặn" in badge_blk

    badge_rej = get_status_badge_html("rejected")
    assert "badge-rejected" in badge_rej
    assert "Từ chối" in badge_rej


def test_disclaimer_text() -> None:
    """Đảm bảo câu tuyên bố miễn trừ y tế bắt buộc được đọc chính xác."""
    text = get_disclaimer_text()
    assert "Thực đơn chỉ mang tính tham khảo hỗ trợ dinh dưỡng" in text
    assert "không thay thế chẩn đoán" in text


def test_init_session_state_mock() -> None:
    """Đảm bảo hàm init_session_state khởi tạo đầy đủ các trường mặc định."""
    import streamlit as st

    init_session_state()
    assert "current_role" in st.session_state
    assert "show_all_pages" in st.session_state
    assert "analyzing" in st.session_state


def test_ensure_db_ready_and_idempotency(tmp_path: Path) -> None:
    """Kiểm tra ensure_db_ready khởi tạo bảng, seed bệnh nhân, nạp thực phẩm và idempotent."""
    db_file = tmp_path / "ready_test.db"
    engine = create_db_engine(f"sqlite:///{db_file}")

    # Lần 1: DB trống -> phải seed và import
    res1 = ensure_db_ready(engine)
    assert res1["ready"] is True
    assert res1["patient_count"] == 30
    assert res1["food_count"] >= 25
    assert res1["seeded"] is True
    assert res1["imported"] is True

    # Lần 2: DB đã có dữ liệu -> idempotent, không seed/import lại
    res2 = ensure_db_ready(engine)
    assert res2["ready"] is True
    assert res2["patient_count"] == 30
    assert res2["food_count"] >= 25
    assert res2["seeded"] is False
    assert res2["imported"] is False


def test_load_sample_patients() -> None:
    """Kiểm tra nạp 30 bệnh nhân mẫu từ data/patients_seed.json."""
    patients = load_sample_patients()
    assert len(patients) == 30
    p1 = patients[0]
    assert p1["patient_code"] == "P0001"
    assert "age" in p1
    assert "sex" in p1
    assert "height_cm" in p1
    assert "weight_kg" in p1
    assert "conditions" in p1
    assert "allergens" in p1


def test_get_system_warnings() -> None:
    """Kiểm tra phát hiện cảnh báo TODO_VERIFY và cấu hình LLM."""
    warnings_data = get_system_warnings()
    assert "has_warnings" in warnings_data
    assert "todo_verify_items" in warnings_data
    assert "todo_verify_count" in warnings_data
    assert warnings_data["todo_verify_count"] >= 1
    assert any("TODO_VERIFY" in w for w in warnings_data["warnings"])


def test_list_and_detail_meal_plans(tmp_path: Path) -> None:
    """Kiểm tra truy vấn danh sách thực đơn lọc theo trạng thái và lấy chi tiết kế hoạch."""
    db_file = tmp_path / "plans_test.db"
    engine = create_db_engine(f"sqlite:///{db_file}")
    ensure_db_ready(engine)

    with Session(engine) as sess:
        prof = sess.scalar(select(HealthProfile).limit(1))
        assert prof is not None

        # Tạo meal_plan mẫu
        targets = {
            "bmi": 24.5,
            "bmr": 1500.0,
            "tdee": 1800.0,
            "target_kcal": 1700.0,
            "protein_g": 85.0,
            "fat_g": 45.0,
            "carb_g": 230.0,
            "fiber_min_g": 25.0,
            "sodium_max_mg": 2000.0,
        }
        plan = create_meal_plan(
            sess,
            profile_id=prof.id,
            thread_id="test-thread-ui-001",
            status="pending_review",
            targets_json=json.dumps(targets),
            needs_json=json.dumps({"needs": ["t2d_standard"], "rule_refs": ["ADA-2024"]}),
            explanation_md="Thực đơn giảm tinh bột nhanh cho đái tháo đường.",
            retry_count=1,
            verifier_passed_first_try=False,
        )

        food = sess.scalar(select(Food).limit(1))
        assert food is not None
        food_id = int(food.id)
        item = MealPlanItem(
            meal_plan_id=plan.id,
            day=1,
            meal="breakfast",
            food_id=food_id,
            grams=150.0,
            kcal=180.0,
            protein_g=10.0,
            fat_g=2.0,
            carb_g=30.0,
            sodium_mg=150.0,
        )
        sess.add(item)
        sess.commit()
        plan_id = plan.id

    with Session(engine) as sess:
        # Kiểm tra list_meal_plans_for_ui
        all_plans = list_meal_plans_for_ui(session=sess, status="pending_review")
        assert len(all_plans) >= 1
        assert any(p["id"] == plan_id for p in all_plans)

        empty_plans = list_meal_plans_for_ui(session=sess, status="blocked")
        assert len(empty_plans) == 0

        # Kiểm tra get_meal_plan_detail
        detail = get_meal_plan_detail(plan_id, session=sess)
        assert detail is not None
        assert detail["meal_plan"]["id"] == plan_id
        assert detail["meal_plan"]["status"] == "pending_review"
        assert detail["targets"]["target_kcal"] == 1700.0
        assert len(detail["items"]) == 1
        assert detail["items"][0]["food_id"] == food_id
        assert len(detail["daily_totals"]) == 1

        # Non-existent ID returns None
        assert get_meal_plan_detail(999999, session=sess) is None


def test_record_review_for_finalized_plan(tmp_path: Path) -> None:
    """Kiểm tra ghi nhận quyết định phê duyệt / từ chối của chuyên gia cho ca needs_human_review."""
    db_file = tmp_path / "review_test.db"
    engine = create_db_engine(f"sqlite:///{db_file}")
    ensure_db_ready(engine)

    with Session(engine) as sess:
        prof = sess.scalar(select(HealthProfile).limit(1))
        assert prof is not None
        plan = create_meal_plan(
            sess,
            profile_id=prof.id,
            thread_id="test-review-002",
            status="needs_human_review",
        )
        sess.commit()
        plan_id = plan.id

    with Session(engine) as sess:
        # Quyết định từ chối bắt buộc có note
        with pytest.raises(ValueError, match="bắt buộc phải có lý do"):
            record_review_for_finalized_plan(
                meal_plan_id=plan_id,
                reviewer_name="BS. Hùng",
                decision="reject",
                note="",
                session=sess,
            )

        # Từ chối hợp lệ
        res_rej = record_review_for_finalized_plan(
            meal_plan_id=plan_id,
            reviewer_name="BS. Hùng",
            decision="reject",
            note="Khẩu phần chưa tối ưu cho đường huyết dao động.",
            session=sess,
        )
        assert res_rej["status"] == "rejected"

        # Phê duyệt hợp lệ
        res_app = record_review_for_finalized_plan(
            meal_plan_id=plan_id,
            reviewer_name="BS. Hùng",
            decision="approve",
            note="Đã kiểm tra và phê duyệt.",
            session=sess,
        )
        assert res_app["status"] == "approved"

        # Kiểm tra bảng Review
        rev_stmt = (
            select(func.count())
            .select_from(Review)
            .where(Review.meal_plan_id == plan_id)
        )
        rev_count = sess.scalar(rev_stmt)
        assert rev_count == 2


def test_preview_and_verify_edited_items(tmp_path: Path) -> None:
    """Kiểm tra tính toán lại dinh dưỡng và kiểm chứng khô (dry-run, không mutate DB)."""
    db_file = tmp_path / "preview_test.db"
    engine = create_db_engine(f"sqlite:///{db_file}")
    ensure_db_ready(engine)

    with Session(engine) as sess:
        prof = sess.scalar(select(HealthProfile).limit(1))
        assert prof is not None

        food = sess.scalar(select(Food).limit(1))
        assert food is not None
        food_id = int(food.id)

        targets = {
            "bmi": 22.0,
            "bmr": 1400.0,
            "tdee": 1700.0,
            "target_kcal": 1600.0,
            "protein_g": 80.0,
            "fat_g": 40.0,
            "carb_g": 220.0,
            "fiber_min_g": 25.0,
            "sodium_max_mg": 2000.0,
            "sugar_max_g": 25.0,
            "kcal_floor": 1500.0 if prof.sex == "male" else 1200.0,
        }
        plan = create_meal_plan(
            sess,
            profile_id=prof.id,
            thread_id="test-preview-thread",
            status="needs_human_review",
            targets_json=json.dumps(targets),
            needs_json=json.dumps({"needs": ["t2d_standard"], "rule_refs": ["ADA-2024"]}),
        )
        # Thêm 1 món
        sess.add(
            MealPlanItem(
                meal_plan_id=plan.id,
                day=1,
                meal="breakfast",
                food_id=food_id,
                grams=100.0,
                kcal=150.0,
                protein_g=8.0,
                fat_g=2.0,
                carb_g=25.0,
                sodium_mg=100.0,
            )
        )
        sess.commit()
        plan_id = plan.id

    with Session(engine) as sess:
        # Sửa grams thành 150g
        edited = [{"day": 1, "meal": "breakfast", "food_id": food_id, "grams": 150.0}]
        res = preview_and_verify_edited_items(plan_id, edited, session=sess)
        assert "is_valid" in res
        assert "violations" in res
        assert "daily_totals" in res
        assert "scored_items" in res

        # Đảm bảo DB không bị mutate (số bản ghi meal_plan_item vẫn là 1)
        item_in_db = sess.scalar(select(MealPlanItem).where(MealPlanItem.meal_plan_id == plan_id))
        assert item_in_db is not None
        assert item_in_db.grams == 100.0


def test_seed_logs_script(tmp_path: Path) -> None:
    """Kiểm tra script seed_logs tạo đúng 200 QueryLog giả lập và idempotent."""
    db_file = tmp_path / "logs_test.db"
    engine = create_db_engine(f"sqlite:///{db_file}")
    ensure_db_ready(engine)

    # Chạy lần 1: sinh 200 bản ghi
    c1 = seed_logs(engine=engine, count=200, seed=42)
    assert c1 == 200

    with Session(engine) as sess:
        synth_count = sess.scalar(
            select(func.count()).select_from(QueryLog).where(QueryLog.is_synthetic_log == True)  # noqa: E712
        )
        assert synth_count == 200

    # Chạy lần 2: vẫn duy trì 200 bản ghi, không bị trùng lặp
    c2 = seed_logs(engine=engine, count=200, seed=42)
    assert c2 == 200

    with Session(engine) as sess:
        synth_count2 = sess.scalar(
            select(func.count()).select_from(QueryLog).where(QueryLog.is_synthetic_log == True)  # noqa: E712
        )
        assert synth_count2 == 200


def test_get_dashboard_dataset(tmp_path: Path) -> None:
    """Kiểm tra get_dashboard_dataset tính toán đầy đủ KPI, cấu trúc biểu đồ và CSV."""
    db_file = tmp_path / "dash_test.db"
    engine = create_db_engine(f"sqlite:///{db_file}")
    ensure_db_ready(engine)
    seed_logs(engine=engine, count=200, seed=42)

    with Session(engine) as sess:
        data = get_dashboard_dataset(session=sess, include_synthetic=True)
        assert "kpis" in data
        assert "charts" in data
        assert "logs" in data
        assert "csv_data" in data

        kpis = data["kpis"]
        assert kpis["total_requests"] >= 200
        assert kpis["approval_rate_pct"] > 0
        assert kpis["redirect_rate_pct"] > 0
        assert kpis["avg_latency_ms"] > 0

        charts = data["charts"]
        assert "trend_by_date" in charts
        assert "condition_distribution" in charts
        assert "guardrails_by_type" in charts
        assert "latency_distribution" in charts

        assert len(data["csv_data"]) > 100
        assert "session_id" in data["csv_data"]

        # Lọc theo exclude synthetic
        data_no_synth = get_dashboard_dataset(session=sess, include_synthetic=False)
        assert data_no_synth["kpis"]["total_requests"] == 0


def test_pages_syntax_compilation() -> None:
    """Kiểm tra cú pháp của toàn bộ file giao diện trong app/ và app/pages/."""
    files_to_check = [
        Path("app/main.py"),
        Path("app/ui_helpers.py"),
        Path("app/pages/1_Ho_so.py"),
        Path("app/pages/2_Ket_qua.py"),
        Path("app/pages/3_Chuyen_gia_duyet.py"),
        Path("app/pages/4_Dashboard.py"),
    ]
    for p in files_to_check:
        assert p.exists(), f"Thiếu file: {p}"
        py_compile.compile(str(p), doraise=True)


def test_theme_config_exists() -> None:
    """Kiểm tra tệp cấu hình .streamlit/config.toml có các thông số theme y tế."""
    cfg_file = Path(".streamlit/config.toml")
    assert cfg_file.exists()
    content = cfg_file.read_text(encoding="utf-8")
    assert 'primaryColor = "#0D9488"' in content
    assert 'backgroundColor = "#F8FAFC"' in content
    assert 'secondaryBackgroundColor = "#FFFFFF"' in content
    assert 'textColor = "#0F172A"' in content
