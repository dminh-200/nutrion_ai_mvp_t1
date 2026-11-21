"""Thành phần trình bày desktop của bản thiết kế mới."""

from base64 import b64encode
from functools import cache, lru_cache
from html import escape
from pathlib import Path
from typing import Any

import streamlit as st

CONDITIONS = {
    "t2d": "Tiểu đường type 2",
    "htn": "Tăng huyết áp",
    "gout": "Gout",
    "obesity": "Béo phì",
}
ALLERGENS = {
    "seafood": "Hải sản",
    "peanut": "Đậu phộng",
    "milk": "Sữa",
    "egg": "Trứng",
    "gluten": "Gluten",
    "soy": "Đậu nành",
}
ACTIVITIES = {
    "sedentary": "Ít vận động",
    "light": "Vận động nhẹ",
    "moderate": "Vận động vừa",
    "active": "Vận động nhiều",
    "very_active": "Vận động rất nhiều",
}
MEALS = {"breakfast": "Bữa sáng", "lunch": "Bữa trưa", "dinner": "Bữa tối", "snack": "Bữa phụ"}
STATUS = {
    "approved": ("Đã được chuyên gia duyệt", "green"),
    "pending_review": ("Đang chờ chuyên gia duyệt", "amber"),
    "needs_human_review": ("Cần chuyên gia xem xét", "amber"),
    "redirect_to_doctor": ("Cần tư vấn trực tiếp", "red"),
    "blocked": ("Chưa thể xử lý yêu cầu", "red"),
    "rejected": ("Thực đơn đã bị từ chối", "red"),
}
STATUS_ICONS = {
    "approved": "check",
    "pending_review": "clock",
    "needs_human_review": "clock",
    "redirect_to_doctor": "shield",
    "blocked": "shield",
    "rejected": "shield",
}
ICONS = {
    "brand": (
        '<path d="M12 4v16M4 12h16"/>'
        '<path d="M12 12c3.8 0 5.8-2 5.8-5.8-3.8 0-5.8 2-5.8 5.8Z" fill="currentColor"/>'
    ),
    "profile": (
        '<rect x="5" y="3" width="14" height="18" rx="3"/>'
        '<circle cx="12" cy="9" r="2"/><path d="M8.5 16c0-3 7-3 7 0"/>'
    ),
    "sample": (
        '<rect x="6" y="5" width="13" height="16" rx="2"/>'
        '<path d="M3 15V5a3 3 0 0 1 3-3h8M10 10h5m-5 4h5"/>'
    ),
    "meal": (
        '<path d="M3 12h18c-.5 5-3.4 7.5-9 7.5S3.5 17 3 12ZM8 21h8'
        'M8 9q-2-2 0-4m4 4q-2-2 0-4m4 4q-2-2 0-4"/>'
    ),
    "shield": '<path d="M12 3 4 6v5c0 5 3.4 8 8 10 4.6-2 8-5 8-10V6Z"/><path d="M9 12l2 2 4-4"/>',
    "clock": '<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/>',
    "check": '<path d="m5 12 4 4L19 6"/>',
    "chart": '<path d="M4 4v16h16M8 15l4-4 3 2 5-6"/>',
    "sun": (
        '<circle cx="12" cy="12" r="4"/>'
        '<path d="M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2m0-14-2 2M7 17l-2 2"/>'
    ),
    "moon": '<path d="M20 15a8 8 0 0 1-11-11 8.5 8.5 0 1 0 11 11Z"/>',
}


@cache
def icon(name: str) -> str:
    """Vẽ biểu tượng cục bộ và bỏ qua trong cây trợ năng."""
    color = "#D9ECA9" if name == "brand" else "#286752"
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'color="{color}" stroke="{color}" stroke-width="1.65" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>'
    )
    source = b64encode(svg.encode("utf-8")).decode("ascii")
    return f'<img class="clinic-icon" src="data:image/svg+xml;base64,{source}" alt="">'


def brand() -> None:
    """Hiển thị nhận diện cổng dinh dưỡng."""
    st.html(
        f'<div class="brand"><span class="brand-symbol">{icon("brand")}</span>'
        "<div><strong>Nutri AI</strong><small>Cổng dinh dưỡng</small></div></div>"
    )


def theme() -> None:
    """Áp dụng bộ màu và bố cục desktop độc lập."""
    st.html((Path(__file__).parent / "style.css").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _hero_asset() -> str:
    """Đọc ảnh WebP cục bộ một lần cho mỗi tiến trình."""
    content = (Path(__file__).parent / "assets" / "clinic-ingredients.webp").read_bytes()
    return b64encode(content).decode("ascii")


def hero(kicker: str, title: str, subtitle: str) -> None:
    """Hiển thị lời dẫn và ảnh nguyên liệu trong cùng một khối."""
    st.html(
        '<section class="intro"><div class="intro-copy">'
        f'<span class="eyebrow">{escape(kicker)}</span>'
        f"<h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>"
        f'<figure><img src="data:image/webp;base64,{_hero_asset()}" '
        'alt="Rau thơm, rau xanh và lát chanh trên bàn" width="1200" height="800">'
        "<figcaption>Ảnh minh họa nguyên liệu</figcaption></figure></section>"
    )


def heading(title: str, description: str, symbol: str) -> None:
    """Hiển thị đầu trang phụ bằng kiểu chữ và biểu tượng chung."""
    st.html(
        f'<header class="page-heading"><span class="tile-icon">{icon(symbol)}</span>'
        f"<div><h1>{escape(title)}</h1><p>{escape(description)}</p></div></header>"
    )


def card_heading(title: str, description: str, symbol: str) -> None:
    """Tạo điểm nhận diện và tên cho thẻ thao tác."""
    st.html(
        f'<div class="card-heading"><span class="tile-icon">{icon(symbol)}</span>'
        f"<div><h2>{escape(title)}</h2><p>{escape(description)}</p></div></div>"
    )


def empty_state(title: str, description: str, symbol: str) -> None:
    """Hiển thị trạng thái trống có biểu tượng và hướng dẫn."""
    st.html(
        f'<section class="empty-state"><span class="tile-icon">{icon(symbol)}</span>'
        f"<h2>{escape(title)}</h2><p>{escape(description)}</p></section>"
    )


def section(kicker: str, title: str, description: str = "") -> None:
    """Hiển thị đầu mục có phân cấp."""
    eyebrow = f'<span class="eyebrow">{escape(kicker)}</span>' if kicker else ""
    note = f"<p>{escape(description)}</p>" if description else ""
    st.html(f'<div class="section-title">{eyebrow}<h2>{escape(title)}</h2>{note}</div>')


def metric(label: str, value: str, note: str = "", color: str = "teal") -> None:
    """Hiển thị chỉ số kèm đơn vị và lời giải thích."""
    st.html(
        f'<div class="stat {color}"><span>{escape(label)}</span>'
        f"<strong>{escape(value)}</strong><small>{escape(note)}</small></div>"
    )


def status_panel(status: str, message: str) -> None:
    """Hiển thị trạng thái cùng giải thích và biểu tượng."""
    label, color = STATUS.get(status, ("Bản nháp", "amber"))
    symbol = STATUS_ICONS.get(status, "clock")
    st.html(
        f'<div class="status-panel {color}" role="status">'
        f'<span class="tile-icon">{icon(symbol)}</span><div>'
        f"<strong>{escape(label)}</strong><p>{escape(message)}</p></div></div>"
    )


def footer() -> None:
    """Hiển thị disclaimer cố định từ cấu hình gốc."""
    import yaml

    cfg = yaml.safe_load(Path("config/guardrails.yaml").read_text(encoding="utf-8"))
    text = str(cfg["disclaimer_vi"]).strip("* ")
    st.html(
        f'<footer class="clinic-footer"><span class="footer-icon">{icon("shield")}</span>'
        f"<span>{escape(text)}</span></footer>"
    )


def execution_note(result: dict[str, Any]) -> None:
    """Mô tả nguồn thực thi, không suy đoán từ số token."""
    info = result.get("execution")
    if info is None:
        st.caption("Bản ghi cũ: chưa có thông tin nguồn thực thi.")
    else:
        st.caption(
            f"Lượt gửi API: {info.get('api_attempts', 0)} · "
            f"Lượt giả lập: {info.get('mock_calls', 0)} · "
            f"Lượt đọc cache: {info.get('cache_hits', 0)}"
        )


def references(explanation: str | None, snippets: list[Any]) -> None:
    """Hiển thị giải thích và các đoạn nguồn sẵn có của đúng ca."""
    st.markdown(explanation or "Chưa có giải thích lưu cho ca này.")
    for snippet in snippets:
        data = snippet.model_dump() if hasattr(snippet, "model_dump") else snippet
        if isinstance(data, dict) and data.get("source_name"):
            st.text(f"{data['source_name']} · Trang {data.get('page', '—')}")
            st.caption(data.get("text", ""))
