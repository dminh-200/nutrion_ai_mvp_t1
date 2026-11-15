"""Tracing Langfuse Python SDK v5 kèm che dữ liệu nhạy cảm và fallback no-op (SPEC Phần 11)."""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from typing import Any

from langfuse import Langfuse, get_client, propagate_attributes
from langfuse.types import TraceContext
from langgraph.errors import GraphInterrupt

from config.settings import Settings, get_settings
from core.schemas import NutritionTargets, Violation

logger = logging.getLogger(__name__)

_UNSET = object()
_ACTIVE_SECRETS: ContextVar[tuple[str, ...]] = ContextVar("_ACTIVE_SECRETS", default=())
_CLIENT_OVERRIDE: ContextVar[Any] = ContextVar("_CLIENT_OVERRIDE", default=_UNSET)
_INIT_FAILED: bool = False
_INITIALIZED_SIGNATURE: tuple[str, str, str] | None = None

_USER_DATA_RE = re.compile(r"<user_data>(.*?)</user_data>", flags=re.DOTALL | re.IGNORECASE)


def create_request_trace_id(thread_id: str) -> str:
    """Tạo trace_id 32 ký tự hex tương thích Langfuse v5/OTEL (chạy offline không cần mạng)."""
    return Langfuse.create_trace_id(seed=thread_id)


def mask_sensitive_data(data: Any, *, extra_secrets: tuple[str, ...] = ()) -> Any:
    """Loại bỏ display_name, preferences_text gốc (chỉ giữ độ dài và cờ) trước khi gửi."""
    secrets = tuple(dict.fromkeys([*_ACTIVE_SECRETS.get(), *extra_secrets]))

    if isinstance(data, str):
        masked = _USER_DATA_RE.sub(
            lambda m: f"<user_data>[MASKED length={len(m.group(1).strip())}]</user_data>",
            data,
        )
        for sec in secrets:
            if sec and sec in masked:
                masked = masked.replace(sec, "[MASKED]")
        return masked

    if isinstance(data, list):
        return [mask_sensitive_data(item, extra_secrets=extra_secrets) for item in data]

    if isinstance(data, tuple):
        return [mask_sensitive_data(item, extra_secrets=extra_secrets) for item in data]

    if isinstance(data, dict):
        out: dict[str, Any] = {}
        for k, v in data.items():
            key_str = str(k)
            if key_str == "display_name":
                continue
            if key_str == "preferences_text":
                raw_txt = "" if v is None else str(v)
                out["preferences_length"] = len(raw_txt)
                continue
            out[key_str] = mask_sensitive_data(v, extra_secrets=extra_secrets)
        return out

    return data


def _langfuse_mask_callback(*, data: Any, **_kwargs: Any) -> Any:
    """Callback chuẩn Langfuse v5 MaskFunction áp dụng che dữ liệu cho mọi span/generation."""
    return mask_sensitive_data(data)


@contextmanager
def register_mask_secrets(
    *,
    display_name: str | None = None,
    preferences_text: str | None = None,
) -> Iterator[None]:
    """Đăng ký các chuỗi nhạy cảm của request hiện tại để hàm mask luôn che triệt để."""
    new_secrets = list(_ACTIVE_SECRETS.get())
    if display_name and len(display_name.strip()) >= 2:
        new_secrets.append(display_name.strip())
    if preferences_text and len(preferences_text.strip()) >= 6:
        new_secrets.append(preferences_text.strip())
    token = _ACTIVE_SECRETS.set(tuple(dict.fromkeys(new_secrets)))
    try:
        yield
    finally:
        _ACTIVE_SECRETS.reset(token)


@contextmanager
def override_langfuse_client(client: Any | None) -> Iterator[None]:
    """Cho phép test tiêm Langfuse client cục bộ (hoặc None để kiểm thử no-op)."""
    token = _CLIENT_OVERRIDE.set(client)
    try:
        yield
    finally:
        _CLIENT_OVERRIDE.reset(token)


def get_langfuse_client(settings: Settings | None = None) -> Any | None:
    """Lấy Langfuse client v5 qua get_client(); trả về None (no-op) nếu thiếu khóa hoặc lỗi."""
    override = _CLIENT_OVERRIDE.get()
    if override is not _UNSET:
        return override

    global _INIT_FAILED, _INITIALIZED_SIGNATURE
    cfg = settings or get_settings()
    if not cfg.langfuse_enabled:
        return None

    sig = (
        cfg.LANGFUSE_PUBLIC_KEY.strip(),
        cfg.LANGFUSE_SECRET_KEY.strip(),
        cfg.LANGFUSE_BASE_URL.strip(),
    )
    if _INIT_FAILED and _INITIALIZED_SIGNATURE == sig:
        return None

    try:
        if _INITIALIZED_SIGNATURE != sig:
            os.environ["LANGFUSE_PUBLIC_KEY"] = sig[0]
            os.environ["LANGFUSE_SECRET_KEY"] = sig[1]
            os.environ["LANGFUSE_BASE_URL"] = sig[2]
            Langfuse(
                public_key=sig[0],
                secret_key=sig[1],
                base_url=sig[2],
                mask=_langfuse_mask_callback,
            )
            _INITIALIZED_SIGNATURE = sig
            _INIT_FAILED = False
        return get_client(public_key=sig[0])
    except Exception as exc:  # pragma: no cover - bảo vệ mạng/khởi tạo
        _INITIALIZED_SIGNATURE = sig
        _INIT_FAILED = True
        logger.warning("Không thể khởi tạo Langfuse, chuyển sang chế độ no-op: %s", exc)
        return None


def safe_flush(client: Any | None) -> None:
    """Đẩy dữ liệu trace an toàn, bỏ qua nếu thiếu client hoặc lỗi mạng."""
    if client is None:
        return
    try:
        client.flush()
    except Exception as exc:
        logger.warning("Lỗi flush Langfuse (đã bỏ qua để không gián đoạn luồng): %s", exc)


class TraceHandle:
    """Đối tượng bọc an toàn cho span gốc meal_plan_request hoặc node span."""

    def __init__(self, obs: Any | None) -> None:
        self._obs = obs

    def update(
        self,
        *,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> None:
        """Cập nhật output/metadata đã qua mask cho observation hiện tại."""
        if self._obs is None:
            return
        try:
            kwargs: dict[str, Any] = {}
            if output is not None:
                kwargs["output"] = mask_sensitive_data(output)
            if metadata is not None:
                kwargs["metadata"] = mask_sensitive_data(metadata)
            if level is not None:
                kwargs["level"] = level
            if status_message is not None:
                kwargs["status_message"] = status_message
            if kwargs:
                self._obs.update(**kwargs)
        except Exception as exc:
            logger.debug("Bỏ qua lỗi cập nhật span Langfuse: %s", exc)


class GenerationHandle:
    """Đối tượng bọc an toàn cho observation as_type='generation' của mỗi lần gọi Gemini."""

    def __init__(self, obs: Any | None) -> None:
        self._obs = obs

    def finish(
        self,
        *,
        output: Any | None = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
        metadata: dict[str, Any] | None = None,
        cost_details: dict[str, float] | None = None,
        level: str | None = None,
        status_message: str | None = None,
    ) -> None:
        """Cập nhật đầu ra và usage tokens (input/output) cho generation observation."""
        if self._obs is None:
            return
        try:
            kwargs: dict[str, Any] = {
                "usage_details": {"input": int(tokens_in), "output": int(tokens_out)},
            }
            if output is not None:
                kwargs["output"] = mask_sensitive_data(output)
            if metadata is not None:
                kwargs["metadata"] = mask_sensitive_data(metadata)
            if cost_details is not None:
                kwargs["cost_details"] = cost_details
            if level is not None:
                kwargs["level"] = level
            if status_message is not None:
                kwargs["status_message"] = status_message
            self._obs.update(**kwargs)
        except Exception as exc:
            logger.debug("Bỏ qua lỗi cập nhật generation Langfuse: %s", exc)


def _str_metadata(meta: dict[str, Any] | None) -> dict[str, str]:
    """Chuyển metadata sang chuỗi ngắn (<=200 ký tự) theo quy tắc propagate_attributes v5."""
    if not meta:
        return {}
    clean: dict[str, str] = {}
    for k, v in mask_sensitive_data(meta).items():
        s = str(v)
        clean[str(k)] = s[:200]
    return clean


@contextmanager
def trace_request(
    *,
    trace_id: str,
    session_id: str,
    patient_code: str,
    input_summary: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    display_name: str | None = None,
    preferences_text: str | None = None,
    settings: Settings | None = None,
) -> Iterator[TraceHandle]:
    """Mở observation gốc 'meal_plan_request' với session_id, user_id=patient_code và masking."""
    with register_mask_secrets(
        display_name=display_name,
        preferences_text=preferences_text,
    ):
        client = get_langfuse_client(settings=settings)
        if client is None:
            yield TraceHandle(None)
            return

        masked_input = mask_sensitive_data(input_summary or {})
        masked_meta = mask_sensitive_data(metadata or {})
        prop_meta = _str_metadata(metadata)
        tc = TraceContext(trace_id=trace_id)

        stack = ExitStack()
        try:
            root_span = stack.enter_context(
                client.start_as_current_observation(
                    trace_context=tc,
                    name="meal_plan_request",
                    as_type="span",
                    input=masked_input,
                    metadata=masked_meta,
                )
            )
            stack.enter_context(
                propagate_attributes(
                    user_id=str(patient_code)[:200],
                    session_id=str(session_id)[:200],
                    metadata=prop_meta or None,
                )
            )
        except Exception as exc:
            logger.warning("Langfuse trace_request lỗi (chuyển sang no-op): %s", exc)
            try:
                stack.close()
            except Exception:
                pass
            yield TraceHandle(None)
            return

        try:
            yield TraceHandle(root_span)
        finally:
            try:
                stack.close()
            except Exception as exc:
                logger.warning("Lỗi đóng trace_request Langfuse (đã bỏ qua): %s", exc)


@contextmanager
def trace_node(
    node_name: str,
    *,
    input_summary: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> Iterator[TraceHandle]:
    """Mở span con cho từng node LangGraph qua start_as_current_observation(as_type='span')."""
    client = get_langfuse_client(settings=settings)
    if client is None:
        yield TraceHandle(None)
        return

    stack = ExitStack()
    try:
        span = stack.enter_context(
            client.start_as_current_observation(
                name=node_name,
                as_type="span",
                input=mask_sensitive_data(input_summary or {}),
                metadata=mask_sensitive_data(metadata or {}),
            )
        )
    except Exception as exc:
        logger.debug("Bỏ qua lỗi mở node span '%s': %s", node_name, exc)
        try:
            stack.close()
        except Exception:
            pass
        yield TraceHandle(None)
        return

    handle = TraceHandle(span)
    try:
        yield handle
    except GraphInterrupt:
        handle.update(output={"interrupted": True, "status": "pending_review"})
        raise
    except Exception as exc:
        handle.update(level="ERROR", status_message=str(exc)[:300])
        raise
    finally:
        try:
            stack.close()
        except Exception as exc:
            logger.debug("Bỏ qua lỗi đóng node span '%s': %s", node_name, exc)


@contextmanager
def trace_llm_generation(
    *,
    name: str,
    model: str,
    input_data: Any = None,
    metadata: dict[str, Any] | None = None,
    model_parameters: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> Iterator[GenerationHandle]:
    """Mở observation as_type='generation' cho mỗi lần gọi Gemini (model, usage)."""
    client = get_langfuse_client(settings=settings)
    if client is None:
        yield GenerationHandle(None)
        return

    stack = ExitStack()
    try:
        gen = stack.enter_context(
            client.start_as_current_observation(
                name=name,
                as_type="generation",
                model=model,
                input=mask_sensitive_data(input_data),
                metadata=mask_sensitive_data(metadata or {}),
                model_parameters=model_parameters,
            )
        )
    except Exception as exc:
        logger.debug("Bỏ qua lỗi mở generation '%s': %s", name, exc)
        try:
            stack.close()
        except Exception:
            pass
        yield GenerationHandle(None)
        return

    handle = GenerationHandle(gen)
    try:
        yield handle
    except Exception as exc:
        handle.finish(level="ERROR", status_message=str(exc)[:300])
        raise
    finally:
        try:
            stack.close()
        except Exception as exc:
            logger.debug("Bỏ qua lỗi đóng generation '%s': %s", name, exc)


def calc_mean_kcal_error_pct(
    plan_scored: list[dict[str, Any]] | None,
    targets: NutritionTargets | dict[str, Any] | None,
) -> float | None:
    """Tính % sai lệch kcal trung bình giữa thực đơn và mục tiêu."""
    if not plan_scored or targets is None:
        return None
    target_kcal = (
        float(targets.target_kcal)
        if isinstance(targets, NutritionTargets)
        else float(targets.get("target_kcal", 0.0))
    )
    if target_kcal <= 0:
        return None
    errs = [
        abs(float(day.get("kcal", 0.0)) - target_kcal) / target_kcal * 100.0
        for day in plan_scored
    ]
    return round(sum(errs) / len(errs), 2) if errs else None


def record_trace_scores(
    *,
    trace_id: str,
    status: str,
    violations: list[Violation] | list[dict[str, Any]] | None = None,
    retry_count: int = 0,
    targets: NutritionTargets | dict[str, Any] | None = None,
    plan_scored: list[dict[str, Any]] | None = None,
    review_decision: str | None = None,
    settings: Settings | None = None,
) -> None:
    """Gắn đủ các score lên trace Langfuse (verifier_passed, first_try_pass, kcal_error_pct...)."""
    client = get_langfuse_client(settings=settings)
    if client is None or not trace_id:
        return

    has_plan = bool(plan_scored)
    has_violations = bool(violations)
    passed = (
        1.0
        if (
            has_plan
            and not has_violations
            and status not in ("blocked", "redirect_to_doctor", "needs_human_review")
        )
        else 0.0
    )
    first_try = 1.0 if (passed == 1.0 and int(retry_count) == 0) else 0.0
    blocked = 1.0 if status == "blocked" else 0.0
    kcal_err = calc_mean_kcal_error_pct(plan_scored, targets)

    def _safe_score(**kwargs: Any) -> None:
        try:
            client.create_score(trace_id=trace_id, **kwargs)
        except Exception as exc:
            logger.debug("Bỏ qua lỗi ghi score '%s': %s", kwargs.get("name"), exc)

    _safe_score(name="verifier_passed", value=passed, data_type="NUMERIC")
    _safe_score(name="first_try_pass", value=first_try, data_type="NUMERIC")
    _safe_score(name="blocked_by_guardrail", value=blocked, data_type="NUMERIC")
    if kcal_err is not None:
        _safe_score(name="kcal_error_pct", value=kcal_err, data_type="NUMERIC")
    if review_decision:
        _safe_score(name="review_decision", value=str(review_decision), data_type="CATEGORICAL")
