"""Script kiểm tra các giá trị còn gắn cờ TODO_VERIFY trong config/*.yaml."""

import sys
from pathlib import Path
from typing import Any

import yaml

CONFIG_FILES = [
    Path("config/rules.yaml"),
    Path("config/risk_rules.yaml"),
]


def find_todo_verify(data: Any, prefix: str = "") -> list[str]:
    """Duyệt đệ quy tìm các khóa hoặc giá trị còn TODO_VERIFY."""
    found: list[str] = []
    if isinstance(data, dict):
        if data.get("status") == "TODO_VERIFY":
            found.append(f"{prefix} (value={data.get('value')})")
        if data.get("macro_status") == "TODO_VERIFY":
            found.append(f"{prefix}.macro_pct")
        for k, v in data.items():
            if k in ("status", "macro_status"):
                continue
            next_prefix = f"{prefix}.{k}" if prefix else str(k)
            found.extend(find_todo_verify(v, next_prefix))
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            found.extend(find_todo_verify(item, f"{prefix}[{idx}]"))
    return found


def main() -> int:
    """In danh sách TODO_VERIFY và trả về mã thoát 1 nếu còn giá trị chưa kiểm chứng."""
    all_items: list[str] = []
    for path in CONFIG_FILES:
        if not path.exists():
            continue
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
        items = find_todo_verify(content, str(path))
        all_items.extend(items)

    if all_items:
        print(f"Cảnh báo: Còn {len(all_items)} giá trị TODO_VERIFY chưa kiểm chứng:")
        for item in all_items:
            print(f"  - {item}")
        return 1

    print("Tất cả giá trị trong config/*.yaml đã được kiểm chứng.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
