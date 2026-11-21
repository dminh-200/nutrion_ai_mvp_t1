"""Dashboard desktop đọc dữ liệu bằng hàm thống kê gốc."""

from datetime import date, timedelta

import plotly.graph_objects as go
import streamlit as st

from app_redesign import ui

EVENT_LABELS = {
    "missing_citation": "Thiếu nguồn",
    "high_risk": "Nguy cơ cao",
    "injection": "Chỉ dẫn chèn",
    "validation": "Dữ liệu chưa hợp lệ",
    "medical_advice": "Tư vấn y khoa",
    "boundary_case": "Ca sát ngưỡng",
    "off_topic": "Ngoài phạm vi",
}


def _chart(fig: go.Figure) -> None:
    """Thống nhất biểu đồ và chú giải."""
    fig.update_layout(
        height=278,
        margin=dict(l=14, r=14, t=16, b=28),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Segoe UI, sans-serif", color="#4B635A", size=12),
        legend=dict(orientation="h", y=-0.16),
        hoverlabel=dict(bgcolor="#173F33", font_color="#FFFFFF"),
        separators=",.",
    )
    fig.update_xaxes(gridcolor="#E6EEE7", automargin=True)
    fig.update_yaxes(gridcolor="#E6EEE7", automargin=True)
    st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})


def render() -> None:
    """Hiển thị bốn biểu đồ, lọc và xuất dữ liệu tạm."""
    from db.repo import get_dashboard_dataset

    ui.heading(
        "Tổng quan vận hành",
        "Theo dõi hoạt động, kiểm chứng và chuyển hướng trên dữ liệu thử nghiệm.",
        "chart",
    )
    with st.container(border=True):
        start, end, cond = st.columns([1, 1, 1.5])
        first = start.date_input("Từ ngày", date.today() - timedelta(days=30), format="DD/MM/YYYY")
        last = end.date_input("Đến ngày", date.today(), format="DD/MM/YYYY")
        condition = cond.selectbox(
            "Nhóm bệnh",
            ["all", *ui.CONDITIONS],
            format_func=lambda c: "Tất cả bệnh lý" if c == "all" else ui.CONDITIONS[c],
        )
        synthetic = st.toggle("Bao gồm nhật ký giả lập dựng sẵn", value=True)
        if synthetic:
            st.caption("Số liệu gồm nhật ký dựng sẵn để trình diễn luồng vận hành.")
    if first > last:
        st.warning("Ngày bắt đầu phải trước hoặc trùng ngày kết thúc.")
        return
    data = get_dashboard_dataset(
        start_date=first,
        end_date=last,
        condition=None if condition == "all" else condition,
        include_synthetic=synthetic,
    )
    kpi, charts = data["kpis"], data["charts"]
    if not kpi["total_requests"]:
        ui.empty_state(
            "Không có dữ liệu phù hợp", "Mở rộng khoảng ngày hoặc thay bộ lọc bệnh lý.", "chart"
        )
        return
    cols = st.columns(4)
    metrics = [
        ("Lượt xử lý", f"{kpi['total_requests']:,}", "Trong khoảng thời gian đã chọn", "teal"),
        ("Tỷ lệ được duyệt", f"{kpi['approval_rate_pct']:.1f}%", "Trạng thái quyết định", "blue"),
        (
            "Chuyển hướng bác sĩ",
            f"{kpi['redirect_rate_pct']:.1f}%",
            "Hồ sơ cần tư vấn trực tiếp",
            "orange",
        ),
        (
            "Đạt kiểm chứng lần đầu",
            f"{kpi['first_pass_verifier_rate_pct']:.1f}%",
            "Theo nhật ký xử lý",
            "purple",
        ),
    ]
    for col, args in zip(cols, metrics, strict=True):
        with col:
            ui.metric(*args)
    with st.container(border=True):
        ui.section("", "Lượt xử lý theo ngày", "Phân theo trạng thái được ghi trong nhật ký.")
        trend = charts.get("trend_by_date", [])
        fig = go.Figure()
        for field, label, color in [
            ("approved", "Đã duyệt", "#286752"),
            ("pending", "Chờ xem", "#C18B2D"),
            ("redirect", "Chuyển bác sĩ", "#AC593B"),
            ("blocked", "Bị chặn", "#953D46"),
        ]:
            fig.add_bar(
                x=[d["date"] for d in trend],
                y=[d[field] for d in trend],
                name=label,
                marker_color=color,
                hovertemplate="%{x|%d/%m/%Y} · %{y} lượt<extra>%{fullData.name}</extra>",
            )
        fig.update_layout(barmode="stack")
        fig.update_xaxes(tickformat="%d/%m")
        fig.update_yaxes(rangemode="tozero")
        _chart(fig)
    a, b, c = st.columns(3)
    with a, st.container(border=True):
        st.markdown("#### Phân bố bệnh lý")
        distribution = charts.get("condition_distribution", {})
        _chart(
            go.Figure(
                go.Bar(
                    x=distribution.get("values", []),
                    y=distribution.get("labels", []),
                    orientation="h",
                    marker_color="#286752",
                )
            )
        )
        st.caption("Một hồ sơ có thể thuộc nhiều nhóm bệnh. Đơn vị: lượt ghi nhận.")
        if any(value > kpi["total_requests"] for value in distribution.get("values", [])):
            st.warning(
                "Có nhóm bệnh vượt tổng lượt xử lý. Số đếm gốc có thể bị lặp khi "
                "một mã hồ sơ có nhiều bản ghi. Cần đối soát trước khi diễn giải."
            )
    with b, st.container(border=True):
        st.markdown("#### Các lớp bảo vệ")
        events = charts.get("guardrails_by_type", {})
        _chart(
            go.Figure(
                go.Bar(
                    x=events.get("counts", []),
                    y=[EVENT_LABELS.get(label, label) for label in events.get("labels", [])],
                    orientation="h",
                    marker_color="#545787",
                )
            )
        )
    with c, st.container(border=True):
        st.markdown("#### Thời gian phản hồi")
        latency = charts.get("latency_distribution", {})
        fig = go.Figure(
            go.Histogram(x=latency.get("latencies", []), nbinsx=20, marker_color="#397787")
        )
        fig.update_layout(xaxis_title="Mili giây", yaxis_title="Số lượt")
        _chart(fig)
    ui.section("", "Hiệu năng và mức sử dụng")
    cols = st.columns(4)
    cols[0].metric("Độ trễ trung bình", f"{kpi['avg_latency_ms']:.0f} ms")
    cols[1].metric("Độ trễ P95", f"{kpi['p95_latency_ms']:.0f} ms")
    cols[2].metric("Token đã ghi nhận", f"{kpi['total_tokens']:,}")
    cols[3].metric("Chi phí đã ước tính", f"${kpi['est_cost_usd']:.4f}")
    with st.expander("Nhật ký và xuất dữ liệu"):
        st.download_button(
            "Tải nhật ký CSV", data["csv_data"], "preview_query_logs.csv", "text/csv"
        )
        st.dataframe(
            data["logs"],
            width="stretch",
            hide_index=True,
            column_config={
                "trace_url": st.column_config.LinkColumn("Trace", display_text="Mở trace"),
                "trace_id": "Mã trace",
                "is_synthetic_log": st.column_config.CheckboxColumn("Log giả lập"),
            },
        )
