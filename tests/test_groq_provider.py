"""Kiểm thử tích hợp nhà cung cấp Groq (LLM_PROVIDER=groq) song song với Gemini và Mock."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import groq
import httpx
import pytest

from agent.llm import (
    DraftMenu,
    ExplainOutput,
    LLMConfigError,
    _build_groq_client,
    _call_with_retry,
    _RateLimiter,
    call_explain_llm,
    call_planner_llm,
    explain_menu,
    plan_menu,
)
from agent.prompts import (
    build_explain_prompt,
    build_planner_prompt,
    format_allowed_foods_compact_groq,
)
from config.settings import Settings
from core.schemas import GuidelineSnippet, NeedsResult, NutritionTargets, PatientProfile


def _sample_allowed_foods() -> list[dict[str, Any]]:
    return [
        {
            "id": 1,
            "code": "VN001",
            "name_vi": "Cơm gạo tẻ",
            "food_group": "ngu_coc",
            "unit_default_g": 150.0,
            "kcal": 130.0,
            "protein_g": 2.7,
            "fat_g": 0.3,
            "carb_g": 28.2,
            "sodium_mg": 2.0,
            "purine_level": "low",
            "tags": "tinh_bot",
        },
        {
            "id": 2,
            "code": "VN002",
            "name_vi": "Thịt lợn nạc luộc",
            "food_group": "thit_trung",
            "unit_default_g": 100.0,
            "kcal": 145.0,
            "protein_g": 25.0,
            "fat_g": 5.0,
            "carb_g": 0.0,
            "sodium_mg": 65.0,
            "purine_level": "medium",
            "tags": "giau_dam",
        },
    ]


def _sample_targets() -> NutritionTargets:
    return NutritionTargets(
        bmi=23.0,
        bmr=1450.0,
        tdee=1800.0,
        target_kcal=1600.0,
        protein_g=80.0,
        fat_g=40.0,
        carb_g=230.0,
        sodium_max_mg=2000.0,
        fiber_min_g=20.0,
        sugar_max_g=25.0,
        kcal_floor=1200.0,
    )


def _sample_profile() -> PatientProfile:
    return PatientProfile(
        patient_code="PAT_GROQ_01",
        age=45,
        sex="male",
        height_cm=168.0,
        weight_kg=65.0,
        activity_level="moderate",
        conditions=["t2d"],
        allergens=[],
        days=1,
    )


class _MockGroqChat:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if not self._responses:
            raise RuntimeError("Hết phản hồi giả lập trong mock Groq.")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _MockGroqClient:
    def __init__(self, responses: list[Any]) -> None:
        self.completions = _MockGroqChat(responses)
        self.chat = SimpleNamespace(completions=self.completions)


def _make_groq_completion(
    content: str,
    prompt_tokens: int = 450,
    completion_tokens: int = 120,
) -> Any:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, role="assistant"),
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )


def test_settings_groq_config_validation() -> None:
    """Kiểm tra cấu hình Groq mặc định và kiểm tra lỗi thiếu GROQ_API_KEY khi LLM_MODE=real."""
    # 1. Mặc định (bỏ qua file .env để kiểm tra class defaults)
    default_cfg = Settings(_env_file=None)
    assert default_cfg.LLM_PROVIDER == "gemini"
    assert default_cfg.GROQ_MODEL == "qwen/qwen3.8-27b"
    assert default_cfg.GROQ_API_KEY == ""

    # 2. Thiếu GROQ_API_KEY ở mode real
    groq_cfg_missing = Settings(
        _env_file=None, LLM_MODE="real", LLM_PROVIDER="groq", GROQ_API_KEY=""
    )
    ok, err = groq_cfg_missing.validate_llm_config()
    assert not ok
    assert "Thiếu GROQ_API_KEY" in (err or "")

    # 3. _build_groq_client ném LLMConfigError
    with pytest.raises(LLMConfigError, match="Thiếu GROQ_API_KEY"):
        _build_groq_client(groq_cfg_missing)

    # 4. Có GROQ_API_KEY hợp lệ, khởi tạo với max_retries=0
    groq_cfg_ok = Settings(
        _env_file=None,
        LLM_MODE="real",
        LLM_PROVIDER="groq",
        GROQ_API_KEY="gsk_test_key_123",
    )
    ok2, err2 = groq_cfg_ok.validate_llm_config()
    assert ok2
    assert err2 is None
    client = _build_groq_client(groq_cfg_ok)
    assert isinstance(client, groq.Groq)
    assert client.max_retries == 0


def test_groq_planner_structured_output_and_usage(tmp_path: Path) -> None:
    """Kiểm tra plan_menu gọi Groq với json_object, reasoning flags và parse DraftMenu."""
    json_text = """
    {
      "days": [
        {
          "day": 1,
          "meals": [
            {
              "meal": "sang",
              "items": [
                {"food_id": 1, "grams": 150.0},
                {"food_id": 2, "grams": 100.0}
              ]
            }
          ]
        }
      ],
      "cannot_plan": false,
      "reason": ""
    }
    """
    mock_resp = _make_groq_completion(json_text, prompt_tokens=600, completion_tokens=150)
    fake_client = _MockGroqClient([mock_resp])

    cfg = Settings(
        _env_file=None,
        LLM_MODE="real",
        LLM_PROVIDER="groq",
        GROQ_API_KEY="gsk_mock",
        GROQ_MODEL="qwen/qwen3.8-27b",
        LLM_CACHE_DIR=str(tmp_path / "cache"),
    )

    plan, usage = plan_menu(
        allowed_foods=_sample_allowed_foods(),
        targets=_sample_targets(),
        profile=_sample_profile(),
        client=fake_client,
        settings=cfg,
    )

    assert isinstance(plan, DraftMenu)
    assert not plan.cannot_plan
    assert len(plan.days) == 1
    assert len(plan.days[0].meals[0].items) == 2
    assert usage["tokens_in"] == 600
    assert usage["tokens_out"] == 150

    # Kiểm tra tham số truyền vào completions.create
    assert len(fake_client.completions.calls) == 1
    call_args = fake_client.completions.calls[0]
    assert call_args["model"] == "qwen/qwen3.8-27b"
    assert call_args["temperature"] == 0.2
    assert call_args["max_completion_tokens"] == 950
    assert call_args["reasoning_effort"] == "none"
    assert call_args["reasoning_format"] == "hidden"
    assert "include_reasoning" not in call_args
    assert call_args["response_format"] == {"type": "json_object"}


def test_groq_model_branching_params(tmp_path: Path) -> None:
    """Kiểm tra phân nhánh tham số reasoning theo tên model (gpt-oss vs qwen vs khác)."""
    json_text = '{"days": [], "cannot_plan": true, "reason": ""}'

    # 1. gpt-oss model
    client_oss = _MockGroqClient([_make_groq_completion(json_text)])
    cfg_oss = Settings(
        _env_file=None,
        LLM_MODE="real",
        LLM_PROVIDER="groq",
        GROQ_API_KEY="gsk_mock",
        GROQ_MODEL="openai/gpt-oss-120b",
        LLM_CACHE_DIR=str(tmp_path / "c1"),
    )
    plan_menu(
        allowed_foods=_sample_allowed_foods(),
        targets=_sample_targets(),
        profile=_sample_profile(),
        client=client_oss,
        settings=cfg_oss,
    )
    call_oss = client_oss.completions.calls[0]
    assert call_oss["reasoning_effort"] == "low"
    assert call_oss["include_reasoning"] is False
    assert "reasoning_format" not in call_oss
    assert call_oss["max_completion_tokens"] == 950

    # 2. Model khác (ví dụ llama)
    client_llama = _MockGroqClient([_make_groq_completion(json_text)])
    cfg_llama = Settings(
        _env_file=None,
        LLM_MODE="real",
        LLM_PROVIDER="groq",
        GROQ_API_KEY="gsk_mock",
        GROQ_MODEL="llama-3.3-70b-versatile",
        LLM_CACHE_DIR=str(tmp_path / "c2"),
    )
    plan_menu(
        allowed_foods=_sample_allowed_foods(),
        targets=_sample_targets(),
        profile=_sample_profile(),
        client=client_llama,
        settings=cfg_llama,
    )
    call_llama = client_llama.completions.calls[0]
    assert "reasoning_effort" not in call_llama
    assert "reasoning_format" not in call_llama
    assert "include_reasoning" not in call_llama
    assert call_llama["max_completion_tokens"] == 950


def test_groq_planner_resolves_food_code_to_id(tmp_path: Path) -> None:
    """Nếu Groq trả về food_id là mã chuỗi VN001, hệ thống tự động map sang id số 1."""
    json_text = """
    {
      "days": [
        {
          "day": 1,
          "meals": [
            {
              "meal": "trua",
              "items": [
                {"food_id": "VN001", "grams": 120.0},
                {"food_id": "VN002", "grams": 80.0}
              ]
            }
          ]
        }
      ],
      "cannot_plan": false,
      "reason": ""
    }
    """
    fake_client = _MockGroqClient([_make_groq_completion(json_text)])
    cfg = Settings(
        _env_file=None,
        LLM_MODE="real",
        LLM_PROVIDER="groq",
        GROQ_API_KEY="gsk_mock",
        GROQ_MODEL="qwen/qwen3.8-27b",
        LLM_CACHE_DIR=str(tmp_path / "cache"),
    )

    plan, _ = call_planner_llm(
        allowed_foods=_sample_allowed_foods(),
        targets=_sample_targets(),
        profile=_sample_profile(),
        client=fake_client,
        settings=cfg,
    )

    items = plan.days[0].meals[0].items
    assert items[0].food_id == 1
    assert items[1].food_id == 2


def test_groq_explain_menu_structured_output(tmp_path: Path) -> None:
    """Kiểm tra explain_menu trả về ExplainOutput qua response_format json_object."""
    json_text = """
    {
      "explanation_md": "## Giải thích nhu cầu\\nPhù hợp cho t2d.\\n- Ăn cá hấp [BYT, tr. 12]"
    }
    """
    comp = _make_groq_completion(json_text, prompt_tokens=350, completion_tokens=90)
    fake_client = _MockGroqClient([comp])
    cfg = Settings(
        _env_file=None,
        LLM_MODE="real",
        LLM_PROVIDER="groq",
        GROQ_API_KEY="gsk_mock",
        GROQ_MODEL="qwen/qwen3.8-27b",
        LLM_CACHE_DIR=str(tmp_path / "cache"),
    )

    snippets = [
        GuidelineSnippet(
            text="Hạn chế đồ ngọt",
            source_name="BYT",
            year=2020,
            page="12",
            disease="t2d",
            score=0.9,
        )
    ]

    out, usage = explain_menu(
        needs=NeedsResult(needs=["kiem_soat_carb"], rule_refs=[]),
        targets=_sample_targets(),
        snippets=snippets,
        client=fake_client,
        settings=cfg,
    )

    assert isinstance(out, ExplainOutput)
    assert "Giải thích nhu cầu" in out.explanation_md
    assert usage["tokens_in"] == 350
    assert usage["tokens_out"] == 90

    # Kiểm tra hàm gốc call_explain_llm cũng trả về text tương đương
    fake_client2 = _MockGroqClient([_make_groq_completion(json_text)])
    raw_text, _ = call_explain_llm(
        needs=NeedsResult(needs=["kiem_soat_carb"], rule_refs=[]),
        targets=_sample_targets(),
        snippets=snippets,
        client=fake_client2,
        settings=cfg,
    )
    assert isinstance(raw_text, str)
    assert "Giải thích nhu cầu" in raw_text


def test_groq_planner_retries_on_rate_limit(tmp_path: Path) -> None:
    """Kiểm tra retry tenacity khi Groq gặp lỗi RateLimitError (HTTP 429)."""
    http_req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    http_resp = httpx.Response(429, request=http_req)
    rate_limit_err = groq.RateLimitError(
        message="Rate limit reached: 8000 TPM",
        response=http_resp,
        body=None,
    )
    json_ok = '{"days": [], "cannot_plan": true, "reason": "Thử nghiệm retry thành công"}'
    fake_client = _MockGroqClient([rate_limit_err, _make_groq_completion(json_ok)])

    cfg = Settings(
        _env_file=None,
        LLM_MODE="real",
        LLM_PROVIDER="groq",
        GROQ_API_KEY="gsk_mock",
        GROQ_MODEL="qwen/qwen3.8-27b",
        LLM_CACHE_DIR=str(tmp_path / "cache"),
    )

    slept_times: list[float] = []
    plan, _ = plan_menu(
        allowed_foods=_sample_allowed_foods(),
        targets=_sample_targets(),
        profile=_sample_profile(),
        client=fake_client,
        settings=cfg,
        sleep_fn=lambda s: slept_times.append(s),
        retry_wait=lambda _: 0.001,
    )

    assert plan.cannot_plan
    assert "Thử nghiệm retry thành công" in plan.reason
    assert len(fake_client.completions.calls) == 2


def test_groq_rate_limit_wait_strategy() -> None:
    """Kiểm tra nếu gặp lỗi 429, wait strategy tự động đợi từ 15 đến 65 giây."""
    http_req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    http_resp = httpx.Response(429, request=http_req)
    rate_limit_err = groq.RateLimitError(
        message="Rate limit reached: 8000 TPM",
        response=http_resp,
        body=None,
    )
    calls = 0
    slept: list[float] = []

    def _failing_fn() -> str:
        nonlocal calls
        calls += 1
        if calls < 2:
            raise rate_limit_err
        return "ok"

    res = _call_with_retry(
        _failing_fn,
        rate_limiter=_RateLimiter(),
        max_rpm=100,
        sleep_fn=lambda s: slept.append(s),
    )
    assert res == "ok"
    assert len(slept) == 1
    assert 15.0 <= slept[0] <= 65.0


def test_groq_compact_foods_format() -> None:
    """Kiểm tra danh sách rút gọn cho Groq chỉ gồm các trường cần thiết theo yêu cầu."""
    foods = _sample_allowed_foods()
    compact = format_allowed_foods_compact_groq(foods)
    lines = compact.strip().splitlines()
    assert len(lines) == 2

    # id|code|name_vi|food_group|unit_default_g|kcal|protein|fat|carb|sodium|purine|tags
    first = lines[0]
    parts = first.split("|")
    assert len(parts) == 12
    assert parts[0] == "1"
    assert parts[1] == "VN001"
    assert parts[2] == "Cơm gạo tẻ"
    assert parts[3] == "ngu_coc"
    assert parts[4] == "150"
    assert parts[5] == "130.0"
    assert parts[10] == "low"
    assert parts[11] == "tinh_bot"

    # Kiểm tra prompt dựng với provider="groq" có chứa yêu cầu minified và dưới 700 tokens
    prompt = build_planner_prompt(
        profile=_sample_profile(),
        targets=_sample_targets(),
        needs=NeedsResult(needs=["duy_tri_can_bang"], rule_refs=[]),
        allowed_foods=foods,
        provider="groq",
    )
    assert "LƯU Ý ĐỊNH DẠNG BẮT BUỘC CHO GROQ (json_object)" in prompt
    assert "minified JSON trên đúng 1 dòng" in prompt
    assert "dưới 700 tokens" in prompt
    assert "VN001" in prompt

    explain_prompt = build_explain_prompt(
        needs=NeedsResult(needs=["duy_tri_can_bang"], rule_refs=[]),
        targets=_sample_targets(),
        snippets=[],
        provider="groq",
    )
    assert "LƯU Ý ĐỊNH DẠNG BẮT BUỘC CHO GROQ (json_object)" in explain_prompt
    assert "150-200 từ" in explain_prompt
    assert "dưới 700 tokens" in explain_prompt


def test_groq_disk_cache_hit(tmp_path: Path) -> None:
    """Kiểm tra lưu và tái sử dụng kết quả từ cache đĩa khi cùng prompt và model."""
    json_text = '{"days": [], "cannot_plan": true, "reason": "Lần 1 sinh và cache"}'
    fake_client = _MockGroqClient([_make_groq_completion(json_text)])

    cache_dir = tmp_path / "llm_cache"
    cfg = Settings(
        LLM_MODE="real",
        LLM_PROVIDER="groq",
        GROQ_API_KEY="gsk_mock",
        LLM_CACHE_DIR=str(cache_dir),
    )

    # Lần 1: Gọi mock client
    p1, _ = plan_menu(
        allowed_foods=_sample_allowed_foods(),
        targets=_sample_targets(),
        profile=_sample_profile(),
        client=fake_client,
        settings=cfg,
        cache_dir=cache_dir,
    )
    assert p1.reason == "Lần 1 sinh và cache"
    assert len(fake_client.completions.calls) == 1

    # Lần 2: Trúng cache, không gọi client
    p2, _ = plan_menu(
        allowed_foods=_sample_allowed_foods(),
        targets=_sample_targets(),
        profile=_sample_profile(),
        client=fake_client,
        settings=cfg,
        cache_dir=cache_dir,
    )
    assert p2.reason == "Lần 1 sinh và cache"
    assert len(fake_client.completions.calls) == 1
