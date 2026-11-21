"""Điểm vào ứng dụng FastAPI bọc agent/graph.py và db/repo.py (dev proxy & static web/dist)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api.routes.chat import router as chat_router
from api.routes.dashboard import router as dashboard_router
from api.routes.meal_plans import router as meal_plans_router
from api.routes.patients import router as patients_router
from api.routes.reviews import router as reviews_router
from api.routes.system import router as system_router
from db.repo import ensure_db_ready
from guardrails.input import _FIELD_NAME_VI, log_guardrail_event

WEB_DIST_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Đảm bảo SQLite đã được khởi tạo, seed bệnh nhân mẫu và nạp bảng thực phẩm."""
    ensure_db_ready()
    yield


def create_app(dist_dir: Path | None = None) -> FastAPI:
    """Khởi tạo FastAPI app kèm CORS cho Vite dev server và phục vụ web/dist nếu tồn tại."""
    application = FastAPI(
        title="NutriAI Clinical API",
        description="REST API wrapper cho nutrition-ai-mvp (LangGraph + MCP + RAG + HITL).",
        version="0.1.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(system_router, prefix="/api")
    application.include_router(patients_router, prefix="/api")
    application.include_router(meal_plans_router, prefix="/api")
    application.include_router(reviews_router, prefix="/api")
    application.include_router(dashboard_router, prefix="/api")
    application.include_router(chat_router, prefix="/api")

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Trả thông báo lỗi 422 bằng tiếng Việt và ghi nhận audit validation đã che PII."""
        extra_labels = {
            **_FIELD_NAME_VI,
            "message": "nội dung tin nhắn",
            "meal_plan_id": "mã thực đơn",
            "history": "lịch sử hội thoại",
            "edited_items": "danh sách món chỉnh sửa",
            "grams": "định lượng (g)",
            "decision": "quyết định duyệt",
            "reviewer_name": "tên chuyên gia",
        }
        parts: list[str] = []
        field_keys: list[str] = []
        errors_vi: list[dict[str, Any]] = []
        for err in exc.errors():
            loc = [str(x) for x in (err.get("loc") or ()) if str(x) != "body"]
            field_key = loc[-1] if loc else "dữ liệu"
            label = extra_labels.get(field_key, field_key)
            err_type = str(err.get("type", ""))
            ctx = err.get("ctx") or {}
            if err_type == "greater_than_equal" and "ge" in ctx:
                msg_vi = f"{label} phải lớn hơn hoặc bằng {ctx['ge']}"
            elif err_type == "less_than_equal" and "le" in ctx:
                msg_vi = f"{label} phải nhỏ hơn hoặc bằng {ctx['le']}"
            elif err_type == "string_too_long" and "max_length" in ctx:
                msg_vi = f"{label} tối đa {ctx['max_length']} ký tự"
            elif err_type == "string_too_short" and "min_length" in ctx:
                msg_vi = f"{label} tối thiểu {ctx['min_length']} ký tự"
            elif err_type == "missing":
                msg_vi = f"thiếu trường {label}"
            elif err_type == "literal_error":
                msg_vi = f"{label} có giá trị không nằm trong danh sách cho phép"
            else:
                msg_vi = f"{label} chưa đúng định dạng"
            field_keys.append(field_key)
            parts.append(msg_vi)
            errors_vi.append({"field": ".".join(loc) or "body", "message_vi": msg_vi})

        detail_msg = (
            "Dữ liệu đầu vào chưa hợp lệ: "
            + ("; ".join(parts) if parts else "vui lòng kiểm tra lại các trường thông tin.")
            + "."
        )
        safe_fields = ", ".join(dict.fromkeys(field_keys)) or "body"
        try:
            log_guardrail_event(
                session_id=f"api-val-{uuid4().hex[:10]}",
                layer="input",
                event_type="validation",
                reason=f"REST 422 tại {request.url.path} (trường: {safe_fields})",
            )
        except Exception:
            pass
        return JSONResponse(status_code=422, content={"detail": detail_msg, "errors": errors_vi})

    resolved_dist = dist_dir if dist_dir is not None else WEB_DIST_DIR
    index_file = resolved_dist / "index.html"
    if resolved_dist.is_dir() and index_file.is_file():
        assets_dir = resolved_dist / "assets"
        if assets_dir.is_dir():
            application.mount("/assets", StaticFiles(directory=str(assets_dir)), name="web-assets")

        @application.get("/{full_path:path}", include_in_schema=False)
        def serve_spa(full_path: str) -> FileResponse:
            """Phục vụ SPA React (web/dist) cho mọi route không thuộc /api."""
            if full_path.startswith("api/") or full_path == "api":
                raise HTTPException(status_code=404, detail="Không tìm thấy endpoint API.")
            candidate = (resolved_dist / full_path).resolve()
            if (
                full_path
                and str(candidate).startswith(str(resolved_dist.resolve()))
                and candidate.is_file()
            ):
                return FileResponse(candidate)
            return FileResponse(index_file)

    return application


app = create_app()
