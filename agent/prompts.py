"""Nạp và dựng prompt từ thư mục prompts/ theo SPEC Phụ lục C và mục 10.1."""

from pathlib import Path
from typing import Any

from core.nutrition import load_rules
from core.schemas import (
    GuidelineSnippet,
    MealPlanLLM,
    NeedsResult,
    NutritionTargets,
    PatientProfile,
    Violation,
)

DEFAULT_PROMPTS_DIR = Path("prompts")


def load_prompt_template(filename: str, prompts_dir: Path = DEFAULT_PROMPTS_DIR) -> str:
    """Đọc nội dung template prompt từ thư mục prompts/."""
    path = prompts_dir / filename
    return path.read_text(encoding="utf-8")


def sanitize_user_data(text: str) -> str:
    """Khử thẻ rào <user_data> bên trong văn bản người dùng để chống thoát khối dữ liệu."""
    if not text:
        return ""
    cleaned = text.replace("</user_data>", "[/user_data]").replace("<user_data>", "[user_data]")
    return cleaned.strip()


def format_allowed_foods_compact(allowed_foods: list[dict[str, Any]]) -> str:
    """Định dạng danh sách món được phép dạng gọn kèm macro/natri/đường trên 100g."""
    if not allowed_foods:
        return "Không có món hợp lệ."
    lines: list[str] = []
    for food in allowed_foods:
        fid = int(food["id"])
        name_vi = str(food.get("name_vi", "")).replace("|", "/")
        kcal = food.get("kcal")
        kcal_str = f"{float(kcal):.1f}" if kcal is not None else "0.0"
        group = str(food.get("food_group", "khac")).replace("|", "/")
        tags = str(food.get("tags", "")).strip() or "-"
        fiber = food.get("fiber_g")
        fiber_str = f"{float(fiber):.1f}" if fiber is not None else "0.0"
        base = f"{fid}|{name_vi}|{kcal_str}|{group}|{tags}|{fiber_str}"
        if any(k in food for k in ("protein_g", "fat_g", "carb_g", "sodium_mg")):
            p_str = _fmt_compact_num(food.get("protein_g"), decimals=1)
            f_str = _fmt_compact_num(food.get("fat_g"), decimals=1)
            c_str = _fmt_compact_num(food.get("carb_g"), decimals=1)
            sg_str = _fmt_compact_num(food.get("sugar_g"), decimals=1)
            na_str = _fmt_compact_num(food.get("sodium_mg"), decimals=0)
            purine = str(food.get("purine_level", "low")).strip() or "low"
            lines.append(f"{base}|{p_str}|{f_str}|{c_str}|{sg_str}|{na_str}|{purine}")
        else:
            lines.append(base)
    return "\n".join(lines)


def _sample_foods_by_group(
    allowed_foods: list[dict[str, Any]],
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Chọn tối đa `limit` món đại diện chia đều theo từng `food_group`."""
    if len(allowed_foods) <= limit:
        return list(allowed_foods)

    buckets: dict[str, list[dict[str, Any]]] = {}
    for food in allowed_foods:
        group = str(food.get("food_group") or "khac").strip() or "khac"
        buckets.setdefault(group, []).append(food)

    selected: list[dict[str, Any]] = []
    group_lists = list(buckets.values())
    idx = 0
    while len(selected) < limit:
        added_in_round = False
        for grp_items in group_lists:
            if idx < len(grp_items):
                selected.append(grp_items[idx])
                added_in_round = True
                if len(selected) >= limit:
                    break
        if not added_in_round:
            break
        idx += 1
    return selected


def format_allowed_foods_compact_groq(allowed_foods: list[dict[str, Any]]) -> str:
    """Rút gọn danh sách món ăn cho Groq theo các trường cần thiết để tiết kiệm token."""
    if not allowed_foods:
        return "Không có món hợp lệ."
    sampled = _sample_foods_by_group(allowed_foods, limit=100)
    lines: list[str] = []
    for food in sampled:
        fid = int(food["id"])
        code = str(food.get("code") or fid).strip()
        name_vi = str(food.get("name_vi", "")).replace("|", "/")
        group = str(food.get("food_group", "khac")).replace("|", "/")
        unit = food.get("unit_default_g")
        unit_str = f"{float(unit):.0f}" if unit is not None else "100"
        kcal = food.get("kcal")
        kcal_str = f"{float(kcal):.1f}" if kcal is not None else "0.0"
        p = food.get("protein_g")
        p_str = f"{float(p):.1f}" if p is not None else "0.0"
        f = food.get("fat_g")
        f_str = f"{float(f):.1f}" if f is not None else "0.0"
        c = food.get("carb_g")
        c_str = f"{float(c):.1f}" if c is not None else "0.0"
        fib = food.get("fiber_g")
        fib_str = f"{float(fib):.1f}" if fib is not None else "0.0"
        na = food.get("sodium_mg")
        na_str = f"{float(na):.0f}" if na is not None else "0"
        purine = str(food.get("purine_level", "low")).strip()
        tags = str(food.get("tags", "")).strip() or "-"
        lines.append(
            f"{fid}|{code}|{name_vi}|{group}|{unit_str}|{kcal_str}|{p_str}|{f_str}|{c_str}|{fib_str}|{na_str}|{purine}|{tags}"
        )
    return "\n".join(lines)


def _fmt_compact_num(value: Any, decimals: int = 1) -> str:
    """Định dạng số gọn để tiết kiệm token, bỏ phần thập phân .0 dư thừa."""
    if value is None:
        return "0"
    num = float(value)
    if decimals <= 0:
        return str(int(round(num)))
    rounded = round(num, decimals)
    if abs(rounded - round(rounded)) < 1e-6:
        return str(int(round(rounded)))
    return f"{rounded:.{decimals}f}".rstrip("0").rstrip(".")


def _food_role_bucket(food: dict[str, Any]) -> str:
    """Gom nhóm food_group đa dạng từ DB/CSV về vai trò dinh dưỡng để chọn mẫu cân bằng."""
    grp = str(food.get("food_group") or "khac").strip().lower()
    if grp == "ngu_coc":
        return "carb"
    if grp in ("thit_gia_cam", "thit_ca"):
        return "meat"
    if grp == "thuy_hai_san":
        return "seafood"
    if grp in ("trung_sua_dau", "trung_sua", "dau_hat"):
        return "protein_other"
    if grp == "rau_cu":
        return "veg"
    if grp == "trai_cay":
        return "fruit"
    if grp == "dau_mo_hat":
        if float(food.get("fat_g") or 0.0) >= 80.0:
            return "oil"
        return "fat"
    return "other"


def _curate_foods_for_alibaba(
    allowed_foods: list[dict[str, Any]],
    limit: int = 56,
) -> list[dict[str, Any]]:
    """Chọn tối đa `limit` món đa dạng, cân bằng nhóm (tách riêng dầu thực vật & hạt)."""
    if len(allowed_foods) <= limit:
        return list(allowed_foods)

    buckets: dict[str, list[dict[str, Any]]] = {}
    for food in allowed_foods:
        buckets.setdefault(_food_role_bucket(food), []).append(food)

    def _clean_rank(food: dict[str, Any]) -> tuple[int, int, int, int, int, float, float, int]:
        na = float(food.get("sodium_mg") or 0.0)
        sg = float(food.get("sugar_g") or 0.0)
        fib = float(food.get("fiber_g") or 0.0)
        grp = str(food.get("food_group") or "").strip().lower()
        tags = str(food.get("tags") or "").lower()
        is_condiment_trap = 1 if (grp == "mon_che_bien_gia_vi" or na > 500.0) else 0
        is_sugary_trap = 1 if ((grp == "do_uong" and sg > 5.0) or sg > 15.0) else 0
        is_sat_fat = 1 if "chat_beo_bao_hoa" in tags else 0
        na_bucket = int(na // 25.0)
        return (
            is_condiment_trap,
            is_sugary_trap,
            is_sat_fat,
            1 if sg > 10.0 else 0,
            na_bucket,
            -min(fib, 12.0),
            na,
            int(food["id"]),
        )

    for b_items in buckets.values():
        b_items.sort(key=_clean_rank)

    quotas: list[tuple[str, int]] = [
        ("carb", 13),
        ("meat", 9),
        ("seafood", 6),
        ("protein_other", 7),
        ("veg", 10),
        ("fruit", 5),
        ("oil", 3),
        ("fat", 3),
    ]
    selected: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    seen_stems: set[tuple[str, str]] = set()

    def _name_stem(food: dict[str, Any]) -> tuple[str, str]:
        words = str(food.get("name_vi", "")).lower().split()
        stem = " ".join(words[:3]) if len(words) >= 3 else " ".join(words)
        return (_food_role_bucket(food), stem)

    # Vòng 1: ưu tiên mỗi nhóm lấy đủ hạn ngạch và tránh món gần trùng tên giữa seed/CSV
    for bucket_name, quota in quotas:
        count = 0
        for food in buckets.get(bucket_name, []):
            if count >= quota or len(selected) >= limit:
                break
            fid = int(food["id"])
            stem = _name_stem(food)
            if fid in seen_ids or stem in seen_stems:
                continue
            selected.append(food)
            seen_ids.add(fid)
            seen_stems.add(stem)
            count += 1

    # Vòng 2: bù tròn nếu nhóm nào bị thiếu (vd dị ứng hải sản) từ các nhóm lành mạnh
    if len(selected) < limit:
        healthy_order = [
            "carb",
            "meat",
            "protein_other",
            "veg",
            "fruit",
            "seafood",
            "oil",
            "fat",
            "other",
        ]
        while len(selected) < limit:
            progressed = False
            for b_name in healthy_order:
                for cand in buckets.get(b_name, []):
                    fid = int(cand["id"])
                    if fid not in seen_ids:
                        selected.append(cand)
                        seen_ids.add(fid)
                        progressed = True
                        break
                if len(selected) >= limit:
                    break
            if not progressed:
                break

    return selected


def format_allowed_foods_compact_alibaba(allowed_foods: list[dict[str, Any]]) -> str:
    """Rút gọn tối đa 56 món đại diện gọn token cho Alibaba (11 cột dinh dưỡng trên 100g)."""
    if not allowed_foods:
        return "Không có món hợp lệ."
    sampled = _curate_foods_for_alibaba(allowed_foods, limit=56)
    lines: list[str] = []
    for food in sampled:
        fid = int(food["id"])
        name_vi = str(food.get("name_vi", "")).replace("|", "/")
        group = str(food.get("food_group", "khac")).replace("|", "/")
        kcal_str = _fmt_compact_num(food.get("kcal"), decimals=0)
        p_str = _fmt_compact_num(food.get("protein_g"), decimals=1)
        f_str = _fmt_compact_num(food.get("fat_g"), decimals=1)
        c_str = _fmt_compact_num(food.get("carb_g"), decimals=1)
        fib_str = _fmt_compact_num(food.get("fiber_g"), decimals=1)
        sugar_str = _fmt_compact_num(food.get("sugar_g"), decimals=1)
        na_str = _fmt_compact_num(food.get("sodium_mg"), decimals=0)
        purine = str(food.get("purine_level", "low")).strip() or "low"
        lines.append(
            f"{fid}|{name_vi}|{group}|{kcal_str}|{p_str}|{f_str}|{c_str}|"
            f"{fib_str}|{sugar_str}|{na_str}|{purine}"
        )
    return "\n".join(lines)


def format_violations_text(violations: list[Violation] | None) -> str:
    """Định dạng danh sách vi phạm từ vòng trước để planner sửa chính xác."""
    if not violations:
        return "Không có"
    lines: list[str] = []
    for v in violations:
        loc_parts: list[str] = []
        if v.day is not None:
            loc_parts.append(f"ngày {v.day}")
        if v.meal:
            loc_parts.append(f"bữa {v.meal}")
        if v.food_id is not None:
            loc_parts.append(f"food_id={v.food_id}")
        loc = f" ({', '.join(loc_parts)})" if loc_parts else ""
        lines.append(f"- [{v.code}]{loc}: {v.message_vi}")
    return "\n".join(lines)


def format_menu_summary(
    plan_scored: list[dict[str, Any]] | None,
    plan_llm: MealPlanLLM | None = None,
    food_name_map: dict[int, str] | None = None,
) -> str:
    """Tạo tóm tắt thực đơn đã kiểm chứng từ số liệu do code tính."""
    parts: list[str] = []
    if plan_scored:
        for d in plan_scored:
            parts.append(
                f"Ngày {d['day']}: {float(d.get('kcal', 0.0)):.0f} kcal "
                f"(Đạm {float(d.get('protein_g', 0.0)):.1f}g, "
                f"Béo {float(d.get('fat_g', 0.0)):.1f}g, "
                f"Carb {float(d.get('carb_g', 0.0)):.1f}g, "
                f"Xơ {float(d.get('fiber_g', 0.0)):.1f}g, "
                f"Natri {float(d.get('sodium_mg', 0.0)):.0f}mg)"
            )
    if plan_llm and plan_llm.days:
        name_map = food_name_map or {}
        for day_plan in plan_llm.days:
            meal_strs: list[str] = []
            for meal in day_plan.meals:
                item_strs = [
                    f"{name_map.get(it.food_id, f'food#{it.food_id}')} ({it.grams:.0f}g)"
                    for it in meal.items
                ]
                if item_strs:
                    meal_strs.append(f"{meal.meal}: {', '.join(item_strs)}")
            if meal_strs:
                parts.append(f"Chi tiết ngày {day_plan.day}: " + "; ".join(meal_strs))
    return " | ".join(parts) if parts else "Chưa có chi tiết thực đơn."


def format_snippets_with_source(snippets: list[GuidelineSnippet]) -> str:
    """Định dạng các đoạn hướng dẫn kèm trích dẫn chuẩn [tên tài liệu, tr. X]."""
    if not snippets:
        return "Không có đoạn hướng dẫn nào được truy xuất."
    lines: list[str] = []
    for idx, snip in enumerate(snippets, start=1):
        cite = f"[{snip.source_name}, tr. {snip.page}]"
        clean_text = " ".join(snip.text.split())
        lines.append(f"{idx}. ({snip.disease or 'chung'}) {clean_text} {cite}")
    return "\n".join(lines)


def _render_placeholders(template: str, mapping: dict[str, str]) -> str:
    """Thay thế các biến {{key}} an toàn mà không lỗi khi dữ liệu chứa dấu ngoặc nhọn."""
    rendered = template
    for key, value in mapping.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


GROQ_PLANNER_SCHEMA_INSTRUCTION = (
    "\n\nLƯU Ý ĐỊNH DẠNG BẮT BUỘC CHO GROQ (json_object):\n"
    "Chỉ trả về duy nhất 1 JSON object hợp lệ theo schema sau: "
    '{"days":[{"day":1,"meals":[{"meal":"sang","items":[{"food_id":1,"grams":150.0}]}]}],'
    '"cannot_plan":false,"reason":""}\n'
    "BẮT BUỘC: Xuất minified JSON trên đúng 1 dòng (không khoảng trắng thừa, không xuống dòng) "
    "để tổng output luôn dưới 700 tokens. "
    'Mỗi món trong items phải có "food_id" (id thực phẩm) và "grams" (từ 10.0-400.0).\n'
    "Không kèm bất kỳ văn bản giải thích nào ngoài chuỗi JSON này."
)

GROQ_EXPLAIN_SCHEMA_INSTRUCTION = (
    "\n\nLƯU Ý ĐỊNH DẠNG BẮT BUỘC CHO GROQ (json_object):\n"
    'Chỉ trả về duy nhất 1 JSON object hợp lệ: {"explanation_md":"<nội_dung>"}\n'
    "BẮT BUỘC: Xuất minified JSON trên đúng 1 dòng (không khoảng trắng thừa, không xuống dòng). "
    "Viết giải thích ngắn gọn đúng 150-200 từ gồm 3 phần kèm trích dẫn [tên tài liệu, tr. X] "
    "để tổng output luôn dưới 700 tokens. "
    "Không kèm bất kỳ văn bản giải thích nào ngoài chuỗi JSON này."
)

ALIBABA_PLANNER_SCHEMA_INSTRUCTION = (
    "\n\nLƯU Ý ĐỊNH DẠNG BẮT BUỘC (json_object):\n"
    "Chỉ trả về duy nhất 1 JSON object hợp lệ theo schema: "
    '{"days":[{"day":1,"meals":[{"meal":"breakfast","items":[{"food_id":1,"grams":150}]},'
    '{"meal":"lunch","items":[{"food_id":1,"grams":150}]},'
    '{"meal":"dinner","items":[{"food_id":1,"grams":150}]}]}],"cannot_plan":false,"reason":""}\n'
    "BẮT BUỘC: Xuất minified JSON trên 1 dòng (không khoảng trắng thừa, không xuống dòng). "
    'Mỗi ngày bắt buộc có đủ 3 bữa chính ("breakfast", "lunch", "dinner", có thể thêm "snack"). '
    "Không kèm bất kỳ văn bản nào ngoài chuỗi JSON này."
)


def _build_alibaba_macro_guide(
    targets: NutritionTargets,
    violations: list[Violation] | None = None,
    rules: dict[str, Any] | None = None,
) -> str:
    """Dựng hướng dẫn khoảng đạt kcal/macro động từ targets và config/rules.yaml."""
    cfg = rules or load_rules()
    v_cfg = cfg["verifier"]
    kcal_tol = float(v_cfg["kcal_tolerance_pct"]) / 100.0
    macro_tol = float(v_cfg["macro_tolerance_pct"]) / 100.0
    fiber_tol = float(v_cfg.get("fiber_tolerance_pct", v_cfg["macro_tolerance_pct"])) / 100.0
    grams_min = float(v_cfg["grams_min"])
    grams_max = float(v_cfg["grams_max"])

    kcal_low = targets.target_kcal * (1.0 - kcal_tol)
    if targets.kcal_floor > 0 and targets.target_kcal >= targets.kcal_floor:
        kcal_low = max(kcal_low, targets.kcal_floor)
    kcal_high = targets.target_kcal * (1.0 + kcal_tol)

    p_low = targets.protein_g * (1.0 - macro_tol)
    p_high = targets.protein_g * (1.0 + macro_tol)
    f_low = targets.fat_g * (1.0 - macro_tol)
    f_high = targets.fat_g * (1.0 + macro_tol)
    c_low = targets.carb_g * (1.0 - macro_tol)
    c_high = targets.carb_g * (1.0 + macro_tol)
    fiber_floor = targets.fiber_min_g * (1.0 - fiber_tol)

    sugar_note = (
        f"; đường <= {targets.sugar_max_g:.0f}g"
        if targets.sugar_max_g is not None
        else ""
    )
    lines = [
        "\n\nNGƯỠNG ĐẠT MỖI NGÀY (BẮT BUỘC):",
        (
            f"- Năng lượng: {kcal_low:.0f}-{kcal_high:.0f} kcal "
            f"(tuyệt đối >= {targets.kcal_floor:.0f}); "
            f"Đạm: {p_low:.0f}-{p_high:.0f}g; Béo: {f_low:.0f}-{f_high:.0f}g; "
            f"Carb: {c_low:.0f}-{c_high:.0f}g; "
            f"Chất xơ >= {targets.fiber_min_g:.0f}g "
            f"(ngưỡng đạt >= {fiber_floor:.1f}g){sugar_note}; "
            f"Natri <= {targets.sodium_max_mg:.0f}mg; "
            f"mỗi món {grams_min:.0f}-{grams_max:.0f}g."
        ),
        (
            "- Giá trị trong bảng tính trên 100g: đóng góp = chỉ_số × (grams/100). "
            "Cộng nhẩm tổng ngày trước khi xuất JSON."
        ),
        (
            "- Cách chia khẩu phần cân macro, xơ & thực tế bữa ăn: mỗi bữa chính "
            "(breakfast/lunch/dinner) phân bổ 25–40% kcal ngày (không dồn >48% vào 1 bữa); "
            "thịt/cá chính >= 50g/bữa; hạt chia/hạt khô tối đa 20–30g/ngày; nhóm dầu ăn "
            "tối đa 10–15g/bữa; ưu tiên đa dạng món khác nhau giữa các ngày (không lặp "
            "chu kỳ giống hệt nhau) và tôn trọng cách chế biến trong SỞ_THÍCH (vd: luộc/hấp)."
        ),
        (
            "- Cân bằng macro: ngũ cốc góp 2-9g đạm/100g nên thịt/cá/trứng "
            f"chỉ lấy vừa đủ để Đạm <= {p_high:.0f}g; ưu tiên yến mạch nấu chín/cơm gạo lứt/khoai "
            f"lang, rau xanh, đậu nấu chín để vừa đạt Carb >= {c_low:.0f}g "
            f"vừa đạt Chất xơ >= {fiber_floor:.1f}g (không đẩy xơ quá 45g/ngày)."
        ),
        (
            f"- Đạt đủ Béo ({f_low:.0f}-{f_high:.0f}g/ngày) trong giới hạn thực tế: "
            "bố trí đủ 2-3 bữa có nguồn chất béo lành mạnh mỗi ngày (vd: 10-15g dầu thực vật "
            "chia cho bữa trưa và tối, kết hợp thêm cá béo/quả bơ/trứng hoặc hạt trong giới hạn "
            "<= 30g/ngày)."
            + (
                f" Do giới hạn đường <= {targets.sugar_max_g:.0f}g/ngày, hạn chế trái cây ngọt "
                "và sữa có đường, ưu tiên rau xanh và tinh bột ít đường."
                if targets.sugar_max_g is not None and targets.sugar_max_g <= 25.0
                else ""
            )
        ),
    ]
    if violations and any(
        v.code
        in (
            "MACRO_OUT_OF_RANGE",
            "BELOW_FLOOR",
            "KCAL_OUT_OF_RANGE",
            "FIBER_LOW",
            "SUGAR_OVER",
            "PORTION_UNREALISTIC",
            "MEAL_IMBALANCE",
            "DAY_DUPLICATE",
        )
        for v in violations
    ):
        lines.append(
            "- SỬA VI PHẠM LẦN TRƯỚC: Điều chỉnh trực tiếp đúng chiều lỗi "
            "(thừa Đạm -> giảm nhẹ thịt/cá nhưng giữ >= 50g/bữa; "
            "thiếu Béo -> thêm 10-15g dầu thực vật ở 2 bữa hoặc bổ sung cá béo/quả bơ/hạt "
            "<= 30g/ngày; thừa Béo -> giảm dầu/hạt; "
            "SUGAR_OVER -> giảm hoặc bỏ trái cây ngọt/sữa có đường, thay bằng rau xanh hoặc "
            "tinh bột ít đường; "
            "PORTION_UNREALISTIC -> hạt khô <= 30g, dầu <= 20g, thịt/cá >= 50g; "
            "MEAL_IMBALANCE -> chia lại đều hơn giữa sáng/trưa/tối; "
            "DAY_DUPLICATE -> thay đổi món đạm, tinh bột và rau khác nhau giữa các ngày)."
        )
    return "\n".join(lines)


def format_rag_guidelines_for_planner(
    snippets: list[GuidelineSnippet] | None,
    *,
    max_items: int = 3,
    max_chars: int = 240,
) -> str:
    """Rút gọn tối đa `max_items` đoạn RAG kèm nguồn cho planner để tiết kiệm token."""
    if not snippets:
        return ""
    lines: list[str] = []
    for snip in snippets[:max_items]:
        clean = " ".join(snip.text.split())
        if len(clean) > max_chars:
            clean = clean[: max_chars - 3].rstrip() + "..."
        lines.append(f"- ({snip.disease or 'chung'}) {clean} [{snip.source_name}, tr. {snip.page}]")
    return "\n".join(lines)


def build_planner_prompt(
    *,
    profile: PatientProfile,
    targets: NutritionTargets,
    needs: NeedsResult,
    allowed_foods: list[dict[str, Any]],
    violations: list[Violation] | None = None,
    snippets: list[GuidelineSnippet] | None = None,
    prompts_dir: Path = DEFAULT_PROMPTS_DIR,
    provider: str = "gemini",
) -> str:
    """Dựng prompt cho planner từ prompts/planner_system.txt (bọc <user_data>, không gửi tên)."""
    template = load_prompt_template("planner_system.txt", prompts_dir=prompts_dir)
    needs_str = ", ".join(needs.needs) if needs.needs else "duy_tri_can_bang"
    allergens_str = ", ".join(profile.allergens) if profile.allergens else "Không có"
    norm_provider = provider.lower().strip()
    if norm_provider == "alibaba":
        allowed_str = "\n" + format_allowed_foods_compact_alibaba(allowed_foods)
    elif norm_provider == "groq":
        allowed_str = "\n" + format_allowed_foods_compact_groq(allowed_foods)
    else:
        allowed_str = "\n" + format_allowed_foods_compact(allowed_foods)
    violations_str = format_violations_text(violations)
    preferences_str = sanitize_user_data(profile.preferences_text) or "Không có"

    rendered = _render_placeholders(
        template,
        {
            "days": str(profile.days),
            "patient_code": profile.patient_code,
            "target_kcal": f"{targets.target_kcal:.0f}",
            "protein_g": f"{targets.protein_g:.1f}",
            "fat_g": f"{targets.fat_g:.1f}",
            "carb_g": f"{targets.carb_g:.1f}",
            "fiber_min_g": f"{targets.fiber_min_g:.1f}",
            "sodium_max_mg": f"{targets.sodium_max_mg:.0f}",
            "needs": needs_str,
            "allergens": allergens_str,
            "allowed_foods": allowed_str,
            "violations": violations_str,
            "preferences": preferences_str,
        },
    )
    rag_block = format_rag_guidelines_for_planner(snippets)
    if rag_block:
        rendered += f"\n\nHƯỚNG_DẪN_LÂM_SÀNG_THAM_KHẢO (RAG):\n{rag_block}"
    if norm_provider == "alibaba":
        rendered = rendered.replace(
            "(id|tên|kcal/100g|nhóm|tags|xơ_g)",
            "(trên 100g: id|tên|nhóm|kcal|đạm_g|béo_g|carb_g|xơ_g|đường_g|natri_mg|purin)",
        )
        rendered += _build_alibaba_macro_guide(targets, violations=violations)
        rendered += ALIBABA_PLANNER_SCHEMA_INSTRUCTION
    elif norm_provider == "groq":
        rendered = rendered.replace(
            "(id|tên|kcal/100g|nhóm|tags|xơ_g)",
            "(trên 100g: id|mã|tên|nhóm|đơn_vị_g|kcal|đạm_g|béo_g|carb_g|xơ_g|natri_mg|purin|tags)",
        )
        rendered += GROQ_PLANNER_SCHEMA_INSTRUCTION
    elif any(
        any(k in f for k in ("protein_g", "fat_g", "carb_g", "sodium_mg"))
        for f in allowed_foods
    ):
        rendered = rendered.replace(
            "(id|tên|kcal/100g|nhóm|tags|xơ_g)",
            "(trên 100g: id|tên|kcal|nhóm|tags|xơ_g|đạm_g|béo_g|carb_g|đường_g|natri_mg|purin)",
        )
    return rendered


def build_explain_prompt(
    *,
    needs: NeedsResult,
    targets: NutritionTargets,
    snippets: list[GuidelineSnippet],
    plan_scored: list[dict[str, Any]] | None = None,
    plan_llm: MealPlanLLM | None = None,
    food_name_map: dict[int, str] | None = None,
    prompts_dir: Path = DEFAULT_PROMPTS_DIR,
    provider: str = "gemini",
) -> str:
    """Dựng prompt cho bước explain từ prompts/explain_user.txt (chỉ dùng snippets đã truy xuất)."""
    template = load_prompt_template("explain_user.txt", prompts_dir=prompts_dir)
    needs_str = ", ".join(needs.needs) if needs.needs else "duy_tri_can_bang"
    menu_summary = format_menu_summary(
        plan_scored=plan_scored,
        plan_llm=plan_llm,
        food_name_map=food_name_map,
    )
    snippets_str = "\n" + format_snippets_with_source(snippets)

    rendered = _render_placeholders(
        template,
        {
            "needs": needs_str,
            "target_kcal": f"{targets.target_kcal:.0f}",
            "menu_summary": menu_summary,
            "snippets_with_source": snippets_str,
        },
    )
    if provider.lower().strip() in ("groq", "alibaba"):
        rendered += GROQ_EXPLAIN_SCHEMA_INSTRUCTION
    return rendered
