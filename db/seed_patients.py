"""Sinh 30 bệnh nhân giả lập (P0001–P0030) với seed 42 theo SPEC mục 7.2."""

import json
import random
from pathlib import Path

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from db.init_db import init_db
from db.models import (
    Allergen,
    Condition,
    HealthProfile,
    Patient,
    ProfileAllergen,
    ProfileCondition,
)
from db.session import get_engine

FIRST_NAMES = [
    "Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng",
]
MIDDLE_NAMES = ["Văn", "Thị", "Minh", "Hoàng", "Thanh", "Ngọc", "Quốc", "Anh"]
LAST_NAMES = [
    "An", "Bình", "Chi", "Dũng", "Em", "Giang", "Hà", "Hùng", "Khanh", "Lan",
    "Linh", "Long", "Mai", "Nam", "Ngân", "Phúc", "Quân", "Thảo", "Trang", "Tuấn",
]
ACTIVITIES = ["sedentary", "light", "moderate", "active", "very_active"]
ALLERGEN_CODES = ["seafood", "peanut", "milk", "egg", "gluten", "soy"]
MULTI_COMBOS = [
    ["t2d", "htn"],
    ["t2d", "obesity"],
    ["htn", "obesity"],
    ["gout", "htn"],
    ["t2d", "gout"],
    ["htn", "gout", "obesity"],
    ["t2d", "htn", "obesity"],
    ["gout", "obesity"],
]


def build_synthetic_patients(seed: int = 42) -> list[dict]:
    """Tạo danh sách 30 bệnh nhân giả lập đúng phân bố SPEC 7.2."""
    rng = random.Random(seed)
    patients: list[dict] = []

    def _make_name() -> str:
        return f"{rng.choice(FIRST_NAMES)} {rng.choice(MIDDLE_NAMES)} {rng.choice(LAST_NAMES)}"

    def _base_profile(idx: int, sex: str | None = None, age: int | None = None) -> dict:
        chosen_sex = sex or rng.choice(["male", "female"])
        chosen_age = age if age is not None else rng.randint(25, 72)
        height = round(rng.uniform(152.0, 178.0), 1)
        weight = round(rng.uniform(52.0, 88.0), 1)
        return {
            "patient_code": f"P{idx:04d}",
            "display_name": _make_name(),
            "age": chosen_age,
            "sex": chosen_sex,
            "height_cm": height,
            "weight_kg": weight,
            "activity_level": rng.choice(ACTIVITIES),
            "conditions": [],
            "allergens": [],
            "pregnancy": False,
            "lactating": False,
            "ckd_stage": 0,
            "dialysis": False,
            "eating_disorder": False,
            "preferences_text": rng.choice(["", "Ít dầu mỡ", "Ưa món luộc", "Không ăn cay"]),
            "days": rng.choice([3, 5, 7]),
            "group": "",
        }

    idx = 1
    # 1. 12 đơn bệnh (3 mỗi bệnh)
    for cond in ["t2d", "htn", "gout", "obesity"]:
        for _ in range(3):
            p = _base_profile(idx)
            p["conditions"] = [cond]
            if cond == "obesity":
                p["weight_kg"] = round(rng.uniform(82.0, 105.0), 1)
            p["group"] = f"single_{cond}"
            patients.append(p)
            idx += 1

    # 2. 8 đa bệnh
    for combo in MULTI_COMBOS:
        p = _base_profile(idx)
        p["conditions"] = list(combo)
        if "obesity" in combo:
            p["weight_kg"] = round(rng.uniform(80.0, 102.0), 1)
        p["group"] = "multi"
        patients.append(p)
        idx += 1

    # 3. 5 có dị ứng
    for i in range(5):
        p = _base_profile(idx)
        p["conditions"] = [rng.choice(["t2d", "htn", "gout", "obesity"])]
        p["allergens"] = [ALLERGEN_CODES[i % len(ALLERGEN_CODES)]]
        p["group"] = "allergen"
        patients.append(p)
        idx += 1

    # 4. 5 nguy cơ cao (1 mỗi luật: RISK_PREG, RISK_LACT, RISK_MINOR, RISK_CKD, RISK_ED)
    high_risk_specs = [
        ("RISK_PREG", {"sex": "female", "age": 29, "pregnancy": True, "conditions": ["t2d"]}),
        ("RISK_LACT", {"sex": "female", "age": 31, "lactating": True, "conditions": ["htn"]}),
        ("RISK_MINOR", {"sex": "male", "age": 14, "conditions": ["obesity"]}),
        ("RISK_CKD", {"sex": "male", "age": 62, "ckd_stage": 4, "conditions": ["htn", "t2d"]}),
        (
            "RISK_ED",
            {"sex": "female", "age": 24, "eating_disorder": True, "conditions": ["obesity"]},
        ),
    ]
    for risk_code, overrides in high_risk_specs:
        p = _base_profile(idx, sex=overrides.get("sex"), age=overrides.get("age"))
        p.update(overrides)
        p["group"] = risk_code
        patients.append(p)
        idx += 1

    return patients


def seed_patients(
    engine: Engine | None = None,
    json_path: Path = Path("data/patients_seed.json"),
) -> int:
    """Ghi 30 bệnh nhân giả lập vào DB (idempotent) và xuất JSON."""
    target_engine = engine or get_engine()
    init_db(target_engine)

    patients = build_synthetic_patients(seed=42)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(patients, ensure_ascii=False, indent=2), encoding="utf-8")

    inserted = 0
    with Session(target_engine) as session:
        cond_map = {c.code: c.id for c in session.scalars(select(Condition)).all()}
        allergen_map = {a.code: a.id for a in session.scalars(select(Allergen)).all()}
        existing_codes = set(session.scalars(select(Patient.code)).all())

        for p in patients:
            if p["patient_code"] in existing_codes:
                continue

            patient_row = Patient(
                code=p["patient_code"],
                display_name=p["display_name"],
                is_synthetic=True,
            )
            session.add(patient_row)
            session.flush()

            profile_row = HealthProfile(
                patient_id=patient_row.id,
                age=p["age"],
                sex=p["sex"],
                height_cm=p["height_cm"],
                weight_kg=p["weight_kg"],
                activity_level=p["activity_level"],
                pregnancy=p["pregnancy"],
                lactating=p["lactating"],
                ckd_stage=p["ckd_stage"],
                dialysis=p["dialysis"],
                eating_disorder=p["eating_disorder"],
                preferences_text=p["preferences_text"],
                days=p["days"],
            )
            session.add(profile_row)
            session.flush()

            for c_code in p["conditions"]:
                session.add(
                    ProfileCondition(profile_id=profile_row.id, condition_id=cond_map[c_code])
                )
            for a_code in p["allergens"]:
                session.add(
                    ProfileAllergen(profile_id=profile_row.id, allergen_id=allergen_map[a_code])
                )
            inserted += 1

        session.commit()
    return inserted


if __name__ == "__main__":
    count = seed_patients()
    print(f"Đã seed {count} bệnh nhân mới và xuất data/patients_seed.json.")
