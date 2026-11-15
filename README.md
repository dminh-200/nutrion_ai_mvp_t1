# nutrition-ai-mvp

Hệ thống AI hỗ trợ phân loại nhu cầu dinh dưỡng và xây dựng khẩu phần ăn cho người bệnh (tiểu đường type 2, tăng huyết áp, gout, béo phì) có cơ chế duyệt của chuyên gia (human-in-the-loop).

> **Lưu ý an toàn y tế:** Hệ thống chỉ hỗ trợ tham khảo dinh dưỡng, không chẩn đoán bệnh, không kê đơn hoặc điều chỉnh liều thuốc. Các ca nguy cơ cao luôn được chuyển hướng gặp bác sĩ/chuyên gia dinh dưỡng.

## Yêu cầu môi trường

- Python 3.12+
- Cài đặt thư viện chuẩn từ `requirements.txt` (`make setup`).
- Nếu dùng nhà cung cấp tùy chọn `LLM_PROVIDER=groq` hoặc `LLM_PROVIDER=alibaba`, cần cài thêm gói tương ứng (`groq` hoặc `openai`) trong `.venv`.
- Sao chép `.env.example` thành `.env` và điền biến môi trường phù hợp (không commit `.env`).

## Cấu hình `.env` (trạng thái đến M10)

- **Chế độ LLM (`LLM_MODE`):** `mock` (tất định offline, mặc định khi test/CI) hoặc `real`.
- **Nhà cung cấp (`LLM_PROVIDER`):**
  - `gemini` (mặc định theo `docs/SPEC.md`): dùng `GEMINI_API_KEY`, `GEMINI_PLANNER_MODEL`, `GEMINI_LIGHT_MODEL`.
  - `groq` (tùy chọn): dùng `GROQ_API_KEY`, `GROQ_MODEL`.
  - `alibaba` (tùy chọn, OpenAI-compatible): dùng `ALIBABA_API_KEY`, `ALIBABA_BASE_URL`, `ALIBABA_MODEL`.
- **Công cụ & An toàn (`TOOLS_MODE`, `SAFETY_LLM`):**
  - `TOOLS_MODE=mcp` (mặc định production/MCP) hoặc `direct` (gọi hàm trực tiếp).
  - `SAFETY_LLM=off` (mặc định theo luật từ điển) hoặc `on` (lớp phân loại an toàn bổ sung, chỉ siết chặt thêm).
- **Observability (`LANGFUSE_*`):** Langfuse v5 tự kích hoạt khi có đủ `LANGFUSE_PUBLIC_KEY` và `LANGFUSE_SECRET_KEY`; để trống sẽ tự tắt an toàn.

## Các lệnh thường dùng

```bash
make setup        # Cài đặt thư viện từ requirements.txt
make init-db      # Khởi tạo cơ sở dữ liệu SQLite
make import-food  # Nạp data/food.csv vào SQLite
make seed         # Tạo 30 bệnh nhân giả lập (data/patients_seed.json)
make ingest       # Nạp tài liệu hướng dẫn vào ChromaDB (RAG)
make mcp-dev      # Chạy MCP server kèm MCP Inspector
make test         # Chạy pytest mặc định (-m "not slow")
make eval-rag     # Đánh giá truy xuất RAG (retrieval_hit@4) trên evals/rag_questions.json
make check-rules  # Kiểm tra cờ TODO_VERIFY trong config/*.yaml
make lint         # Kiểm tra code bằng ruff
```

> **Ghi chú lộ trình mốc:** Đến hết M10, các lệnh `make run` (`app/main.py` — thuộc M11 Streamlit UI) và `make eval` (`evals/run_eval.py` — thuộc M12 Evals đầy đủ) là mục tiêu giữ chỗ theo `docs/SPEC.md` và chưa được triển khai.

### Chạy kiểm thử offline trên Windows PowerShell

```powershell
$env:LLM_MODE = "mock"
.venv\Scripts\ruff.exe check .
.venv\Scripts\pytest.exe -q -m "not slow"
.venv\Scripts\python.exe -m evals.rag_eval --k 4
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

> Trên Windows, `asyncio` sử dụng loopback socket nội bộ (`socketpair`) cho MCP `stdio`; nếu chạy trong môi trường hạn chế loopback socket, dùng `TOOLS_MODE=direct` để chạy luồng chính theo phương án dự phòng của `docs/SPEC.md` mục 15.2.
