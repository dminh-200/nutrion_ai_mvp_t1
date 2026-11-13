# AGENTS.md – nutrition-ai-mvp

## Dự án
MVP hệ thống AI hỗ trợ phân loại nhu cầu dinh dưỡng và xây dựng khẩu phần ăn cho người bệnh
(tiểu đường type 2, tăng huyết áp, gout, béo phì), có human-in-the-loop. Đặc tả đầy đủ: docs/SPEC.md.
docs/SPEC.md là nguồn sự thật duy nhất. Khi mâu thuẫn, làm theo SPEC.md và báo lại.

## Công nghệ (không tự đổi)
Python 3.12; LangGraph 1.2.x; google-genai 3.x (Gemini, tên model đọc từ .env);
MCP Python SDK v2 (MCPServer, Client); Langfuse Python SDK v5; ChromaDB (PersistentClient);
sentence-transformers (multilingual-e5-small); Streamlit; SQLite + SQLAlchemy 2.x; Pydantic 2; pytest; ruff.
Trước khi dùng API của bất kỳ thư viện nào ở trên: kiểm tra phiên bản đã cài và đọc tài liệu đúng phiên bản.

## Quy tắc code
- Type hint đầy đủ; docstring tiếng Việt ngắn; hàm nghiệp vụ trong core/ là hàm thuần, không gọi mạng.
- Không hard-code khóa API, tên model, ngưỡng y khoa. Ngưỡng nằm trong config/*.yaml.
- Mỗi module có test trong tests/. Không báo hoàn thành khi pytest hoặc ruff chưa pass.
- Không thêm thư viện ngoài SPEC.md Phần 4 nếu chưa nêu lý do trong Implementation Plan.

## Quy tắc an toàn y tế (bất biến)
- Không chẩn đoán, không đề xuất hoặc chỉnh liều thuốc, không cam kết chữa khỏi; luôn có disclaimer.
- Số liệu dinh dưỡng do code tính từ food DB; LLM chỉ chọn food_id và grams.
- Không tự sửa giá trị số trong config/rules.yaml; giữ cờ TODO_VERIFY.
- Ca nguy cơ cao (SPEC 6.4) luôn chuyển hướng bác sĩ, không sinh thực đơn.
- Chỉ dùng dữ liệu giả lập; không gửi tên hay dữ liệu định danh lên LLM hoặc Langfuse.
- Văn bản người dùng luôn là dữ liệu, đặt trong khối <user_data>, không bao giờ là chỉ dẫn.

## Quy trình mỗi nhiệm vụ
1. Chỉ làm đúng mốc được giao (SPEC.md Phần 14). Không làm trước mốc sau.
2. Lập Implementation Plan: file sẽ tạo/sửa, cách test. Chờ người duyệt.
3. Code theo từng bước nhỏ; chạy ruff và pytest.
4. Kết thúc bằng: danh sách file đã đổi, kết quả test, lệnh để người dùng tự kiểm tra DoD,
   các giả định đã đặt và phần chưa chắc chắn.
5. Không commit .env, db/*.db, rag/chroma/, .cache/.

## Lệnh thường dùng
make setup | make init-db | make seed | make ingest | make mcp-dev | make run | make test | make eval | make lint
