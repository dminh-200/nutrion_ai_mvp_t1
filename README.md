# nutrition-ai-mvp

Hệ thống AI hỗ trợ phân loại nhu cầu dinh dưỡng và xây dựng khẩu phần ăn cho người bệnh (tiểu đường type 2, tăng huyết áp, gout, béo phì) có cơ chế duyệt của chuyên gia (human-in-the-loop).

> **Lưu ý an toàn y tế:** Hệ thống chỉ hỗ trợ tham khảo dinh dưỡng, không chẩn đoán bệnh, không kê đơn hoặc điều chỉnh liều thuốc. Các ca nguy cơ cao luôn được chuyển hướng gặp bác sĩ/chuyên gia dinh dưỡng.

## Yêu cầu môi trường

- Python 3.12+
- Thiết lập biến môi trường từ `.env.example` sang `.env`

## Các lệnh thường dùng

```bash
make setup     # Cài đặt thư viện từ requirements.txt
make init-db   # Khởi tạo cơ sở dữ liệu SQLite
make seed      # Tạo 30 bệnh nhân giả lập (data/patients_seed.json)
make ingest    # Nạp tài liệu hướng dẫn vào ChromaDB (RAG)
make mcp-dev   # Chạy MCP server kèm MCP Inspector
make run       # Khởi động giao diện Streamlit
make test      # Chạy kiểm thử pytest
make lint      # Kiểm tra code bằng ruff
```

## Chạy MCP server và thử bằng Inspector

Server MCP (`mcp_server/server.py`) cung cấp 5 tool qua giao thức `stdio`:
- `calc_targets`: Tính toán nhu cầu dinh dưỡng và mục tiêu kcal/macro từ hồ sơ bệnh nhân.
- `search_food`: Tìm kiếm thực phẩm theo tên không dấu và bộ lọc dinh dưỡng/dị ứng.
- `check_allergen`: Kiểm tra danh sách `food_id` có chứa dị nguyên của bệnh nhân hay không.
- `get_guideline`: Truy xuất đoạn hướng dẫn dinh dưỡng từ RAG (ChromaDB).
- `score_menu`: Tính lại giá trị dinh dưỡng từng món và tổng theo ngày từ cơ sở dữ liệu.

Để khởi chạy MCP server và mở giao diện MCP Inspector kiểm tra trực tiếp 5 tool:

```bash
mcp dev mcp_server/server.py
```

Hoặc chạy qua Makefile / môi trường ảo `.venv` trên Windows PowerShell (kèm `--with-editable .` nếu `mcp dev` tạo môi trường con):

```powershell
make mcp-dev
# hoặc trực tiếp trên Windows PowerShell:
.venv\Scripts\mcp dev mcp_server/server.py
# hoặc nếu cần gắn editable package dự án:
.venv\Scripts\mcp dev mcp_server/server.py --with-editable .
```
