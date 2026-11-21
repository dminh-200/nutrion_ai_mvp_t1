"""Trang 4: Bảng điều khiển lâm sàng & giám sát vận hành Clinical Dashboard (M11 - R2, R3)."""

from datetime import UTC, datetime, timedelta

import plotly.graph_objects as go
import streamlit as st

from app.ui_helpers import (
    init_session_state,
    inject_custom_css,
    render_disclaimer,
    render_hero_banner,
)
from db.repo import get_dashboard_dataset

init_session_state()
inject_custom_css()

render_hero_banner(
    title="Bảng Điều Khiển Lâm Sàng & Giám Sát Vận Hành",
    subtitle="Theo dõi an toàn y tế, phân bố bệnh lý, tỷ lệ can thiệp và hiệu năng hệ thống.",
    icon="📈",
)

# Bộ lọc đầu trang
now = datetime.now(UTC)
default_start = (now - timedelta(days=14)).date()
default_end = now.date()

col_f1, col_f2, col_f3 = st.columns([2, 1, 1])

with col_f1:
    date_range = st.date_input(
        "Khoảng thời gian phân tích:",
        value=(default_start, default_end),
        max_value=now.date(),
        key="dash_date_range",
    )

with col_f2:
    cond_options = {
        "Tất cả bệnh lý": None,
        "Đái tháo đường T2": "t2d",
        "Tăng huyết áp": "htn",
        "Gout": "gout",
        "Béo phì": "obesity",
    }
    selected_cond_label = st.selectbox(
        "Lọc theo bệnh lý:",
        options=list(cond_options.keys()),
        key="dash_cond_filter",
    )
    cond_filter = cond_options[selected_cond_label]

with col_f3:
    include_synthetic = st.checkbox(
        "Gồm dữ liệu giả lập (seed)",
        value=True,
        key="dash_include_synthetic",
    )
    if include_synthetic:
        st.caption("Bao gồm bản ghi giả lập khi có trong dữ liệu.")

# Xử lý khoảng ngày
has_start = isinstance(date_range, (list, tuple)) and len(date_range) > 0
has_end = isinstance(date_range, (list, tuple)) and len(date_range) > 1
start_d = date_range[0] if has_start else default_start
end_d = date_range[1] if has_end else default_end

# Lấy dataset từ DAL
dataset = get_dashboard_dataset(
    start_date=start_d,
    end_date=end_d,
    condition=cond_filter,
    include_synthetic=include_synthetic,
)

kpis = dataset["kpis"]
charts = dataset["charts"]
logs_list = dataset["logs"]
csv_data = dataset["csv_data"]

if not kpis["total_requests"]:
    st.info("Chưa có dữ liệu trong khoảng thời gian và bộ lọc đã chọn.")

# Hiển thị các thẻ KPI
st.markdown("#### 🏥 Chỉ Số Lâm Sàng & An Toàn Y Tế")
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.metric("Tổng ca tư vấn", f"{kpis['total_requests']:,}")
with k2:
    st.metric(
        "Tỷ lệ phê duyệt",
        f"{kpis['approval_rate_pct']:.1f}%",
        help="Tỷ lệ thực đơn được phê duyệt an toàn",
    )
with k3:
    st.metric(
        "Chuyển hướng bác sĩ",
        f"{kpis['redirect_rate_pct']:.1f}%",
        help="Ca nguy cơ cao tự động chuyển hướng khám trực tiếp",
    )
with k4:
    st.metric(
        "Đạt verifier lần đầu",
        f"{kpis['first_pass_verifier_rate_pct']:.1f}%",
        help="Tỷ lệ đạt 11 tiêu chí mà không cần retry",
    )

st.markdown("#### ⚡ Hiệu Năng Vận Hành & Chi Phí")
k5, k6, k7, k8 = st.columns(4)
with k5:
    st.metric("Độ trễ trung bình", f"{kpis['avg_latency_ms']:.0f} ms")
with k6:
    st.metric("Độ trễ P95", f"{kpis['p95_latency_ms']:.0f} ms")
with k7:
    st.metric("Tổng token sử dụng", f"{kpis['total_tokens']:,}")
with k8:
    st.metric("Chi phí ước tính", f"${kpis['est_cost_usd']:.4f}")

st.markdown("<br>", unsafe_allow_html=True)

# 4 Biểu đồ Plotly chuẩn Health-Tech
col_c1, col_c2 = st.columns(2)

with col_c1:
    with st.container(border=True):
        st.markdown("##### 📅 Số Ca Tư Vấn Theo Ngày & Kết Quả")
        trend_data = charts.get("trend_by_date", [])
        dates = [d["date"] for d in trend_data]
        appr = [d["approved"] for d in trend_data]
        pend = [d["pending"] for d in trend_data]
        redir = [d["redirect"] for d in trend_data]
        bloc = [d["blocked"] for d in trend_data]

        fig1 = go.Figure()
        fig1.add_trace(go.Bar(x=dates, y=appr, name="Đã duyệt", marker_color="#0D9488"))
        fig1.add_trace(go.Bar(x=dates, y=pend, name="Chờ duyệt", marker_color="#F59E0B"))
        fig1.add_trace(go.Bar(x=dates, y=redir, name="Chuyển bác sĩ", marker_color="#0284C7"))
        fig1.add_trace(go.Bar(x=dates, y=bloc, name="Bị chặn", marker_color="#EF4444"))
        fig1.update_layout(
            barmode="stack",
            height=280,
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig1, width="stretch", config={"displayModeBar": False})

with col_c2:
    with st.container(border=True):
        st.markdown("##### 👥 Phân Bố Bệnh Lý Người Bệnh")
        c_chart = charts.get("condition_distribution", {})
        labels = c_chart.get("labels", [])
        values = c_chart.get("values", [])
        fig2 = go.Figure(go.Bar(
            x=values, y=labels, orientation="h",
            marker_color=["#0D9488", "#2563EB", "#7C3AED", "#F97316"],
            text=values, textposition="auto",
        ))
        fig2.update_layout(
            height=280, margin=dict(t=10, b=30, l=10, r=10),
            xaxis_title="Số lượt ghi nhận bệnh lý",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
        st.caption("Một hồ sơ có thể thuộc nhiều nhóm bệnh.")
        st.plotly_chart(fig2, width="stretch", config={"displayModeBar": False})

col_c3, col_c4 = st.columns(2)

with col_c3:
    with st.container(border=True):
        st.markdown("##### 🛡️ Sự Kiện Guardrails Theo Loại")
        g_chart = charts.get("guardrails_by_type", {})
        fig3 = go.Figure(
            data=[
                go.Bar(
                    x=g_chart.get("counts", []),
                    y=g_chart.get("labels", []),
                    orientation="h",
                    marker_color="#0D9488",
                )
            ]
        )
        fig3.update_layout(
            height=260,
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig3, width="stretch", config={"displayModeBar": False})

with col_c4:
    with st.container(border=True):
        st.markdown("##### ⏱️ Phân Bố Độ Trễ Xử Lý (ms)")
        l_chart = charts.get("latency_distribution", {})
        latencies = l_chart.get("latencies", [])
        fig4 = go.Figure(
            data=[
                go.Histogram(
                    x=latencies,
                    nbinsx=20,
                    marker_color="#0284C7",
                    opacity=0.85,
                )
            ]
        )
        fig4.add_vline(
            x=l_chart.get("avg", 0),
            line_dash="dash",
            line_color="#0D9488",
            annotation_text="Avg",
        )
        fig4.add_vline(
            x=l_chart.get("p95", 0),
            line_dash="dot",
            line_color="#EF4444",
            annotation_text="P95",
        )
        fig4.update_layout(
            height=260,
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig4, width="stretch", config={"displayModeBar": False})

# Bảng nhật ký truy vấn QueryLog & Xuất CSV
st.markdown("---")
st.markdown("#### 📜 Nhật Ký Truy Vấn Chi Tiết (QueryLog)")

col_d1, col_d2 = st.columns([3, 1])
with col_d1:
    st.caption(f"Hiển thị {len(logs_list)} bản ghi gần nhất phù hợp với bộ lọc.")
with col_d2:
    st.download_button(
        label="📥 Xuất dữ liệu QueryLog (CSV)",
        data=csv_data,
        file_name="query_logs_export.csv",
        mime="text/csv",
        type="primary",
        key="btn_export_csv",
    )

if logs_list:
    table_display = [
        {
            "Thời gian": it["created_at"],
            "Session ID": it["session_id"][:16] + "...",
            "Mã BN": it["patient_code"],
            "Trạng thái": it["status"],
            "Độ trễ (ms)": f"{it['latency_ms']:.0f}",
            "LLM": it["llm_calls"],
            "Tokens": f"{it['tokens_in'] + it['tokens_out']:,}",
            "Chi phí ($)": f"${it['est_cost_usd']:.4f}",
            "Langfuse Trace": it["trace_url"] if it["trace_url"] else it["trace_id"],
            "Giả lập": "Có" if it["is_synthetic_log"] else "Không",
        }
        for it in logs_list
    ]
    st.dataframe(
        table_display,
        width="stretch",
        hide_index=True,
    )
else:
    st.info("Không có bản ghi nhật ký nào thỏa mãn điều kiện lọc.")

render_disclaimer()
