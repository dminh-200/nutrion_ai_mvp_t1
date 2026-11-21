# Báo cáo kiểm thử frontend và diễn tập bảo vệ đồ án

**Dự án:** nutrition-ai-mvp · **Ngày:** 21/11/2026 (Asia/Bangkok)  
**Ứng dụng:** http://127.0.0.1:8000/ · **Chuẩn đối chiếu:** `docs/SPEC.md`  
**Kết luận: CHƯA ĐẠT DoD để chốt bản demo bảo vệ.**

Luồng tạo thực đơn → sửa khẩu phần → kiểm chứng → chuyên gia duyệt chạy được, dữ liệu đã duyệt được lưu đúng trong ca demo. Tuy nhiên, có lỗi có thể duyệt thực đơn rỗng, thẻ gợi ý chatbot vi phạm dị ứng, chatbot nhận sai BMI/mất mục tiêu dinh dưỡng, và màn hình kết quả giữ trạng thái cũ sau khi duyệt. Cần xử lý những lỗi này trước khi trình diễn tự do trước hội đồng.

Ở đầu lượt, bộ test hiện có đều xanh nhưng chưa bao phủ các lỗi vừa tái hiện. **Có mã nguồn được thay đổi đồng thời trong lúc kiểm thử**; lượt kiểm tra cuối phát hiện lỗi lint và tập lệnh mock không còn vượt qua tiền điều kiện. Xem cập nhật ở mục 5; không coi số PASS đầu lượt là xác nhận nguồn cuối lượt. Báo cáo phân biệt lỗi quan sát trực tiếp, lỗi tái hiện bằng DB tạm, nguy cơ xác nhận bằng mã nguồn và tiêu chí chưa đủ bằng chứng. Không coi một lượt kiểm thử là đã tìm được mọi lỗi.

## 1. Phạm vi, phương pháp và điều kiện chạy

- Thao tác trực tiếp trên frontend đang chạy: hồ sơ mẫu, kết quả, chuyên gia duyệt, dashboard, chatbot, xem lại ca đã duyệt/chuyển bác sĩ/bị chặn.
- Đọc frontend `web/`, tầng REST `api/`, graph, verifier, lưu trữ, tracing, test và báo cáo eval; đối chiếu SPEC 0.3, 2.2–2.5, 3.2, 5, 6.4, 9–14 và Phụ lục E.
- Mốc nền gần nhất trong Git: `afd6a8f` (M11). Cây làm việc đã có nhiều thay đổi và file chưa được Git theo dõi trước kiểm thử; đây là đánh giá bản đang chạy và nguồn tại thời điểm kiểm tra, không phải xác nhận một release bất biến.
- Tôn trọng yêu cầu người dùng đã tách frontend: bản thân việc dùng frontend riêng không bị tính là lỗi. Các thay đổi model/tooling/observability được đánh giá theo SPEC hiện còn trong repo.
- Cấu hình máy chủ được đọc trực tiếp: `LLM_MODE=real`, `LLM_PROVIDER=alibaba`, model lập thực đơn `qwen3.8-flash`, chatbot `qwen3.7-flash`, `TOOLS_MODE=direct`, `SAFETY_LLM=off`, `langfuse_enabled=false`; 1 cờ TODO_VERIFY cho BMI thấp. Không đọc/in khóa bí mật.
- Giới hạn bổ sung theo người dùng: chạy đúng **10 POST tạo yêu cầu ngoài chatbot**, gồm 8 ca nguy cơ cao và 2 injection; cả 10 có `llm_calls=0`, `execution.api_attempts=0`. Không tự chạy 40 ca với AI thật.
- Chatbot: 5 ca trực tiếp qua REST và 1 ca dị ứng qua giao diện. Các kiểm tra bổ sung ngoại tuyến luôn dùng mock/direct, tắt Langfuse, DB tạm; không tính là gọi AI thật.
- Không sửa mã ứng dụng, không thay ngưỡng y khoa, không đổi `.env`, không commit. Có tạo dữ liệu demo khi thử luồng và phát hiện bộ test hiện hữu tự ghi thêm dữ liệu vào DB demo (F07).

**Môi trường đã xác minh:** Python 3.12.10; langgraph 1.2.21; google-genai 3.3.0; mcp 2.3.0; langfuse 5.2.0; chromadb 1.5.9; sentence-transformers 6.3.0; streamlit 1.67.0; sqlalchemy 2.1.8; pydantic 2.14.3; pytest 9.2.0; ruff 0.17.5; fastapi 0.165.0; uvicorn 0.54.0. Vite thực tế khi build: 6.4.6.

## 2. Kết quả kiểm thử frontend và logic

### Bảng phát hiện

CAO: cần xử lý trước khi chốt demo hoặc tuyên bố đạt tiêu chí. TB: sai chức năng/bằng chứng cần sửa, có thể ảnh hưởng câu hỏi phản biện. F08–F09 là khoảng trống nghiệm thu; F06 là nguy cơ tiềm ẩn khi bật tracing, không phải khẳng định đã rò rỉ dữ liệu thật.

| ID / Mức | Vị trí | Vấn đề và bằng chứng | Đề xuất sửa |
|---|---|---|---|
| F01 / **CAO** | `agent/nodes.py:314–339`; `db/repo.py:739–764`; SPEC R5, 9.3 | **Xóa hết món vẫn qua verifier; có thể lưu approved với 0 món.** Tái hiện trong DB tạm: gửi toàn bộ grams=0 → preview `is_valid=true`, vẫn tính 6 món cũ; sau một bản sửa sai đưa ca sang needs_human_review, gửi bản grams=0 → HTTP 200, `approved`, `items=[]`, `daily_totals=[]`, `violations=[]`. | Phân biệt rõ thay thế toàn bộ danh sách với cập nhật từng dòng; bữa bị xóa phải rỗng và bị DAY_COUNT/BELOW_FLOOR chặn. Chỉ ghi chính thực đơn đã được score/verify, cùng transaction. |
| F02 / **CAO** | `agent/chat.py:360–409,754`; `web/src/pages/ChatPage.tsx:147–176`; SPEC R2, NFR2 | **Chatbot gắn nhãn “an toàn” cho món chứa chất dị ứng vừa khai.** Nhập “Tôi dị ứng sữa và trứng…”; REST trả food_id 16, 51, 113 là trứng/mì trứng. UI thực tế hiển thị các thẻ này dưới “Món thay thế an toàn”. LLM có thể khuyên tránh trứng trong phần chữ, nhưng các thẻ vẫn mâu thuẫn. | Hợp nhất dị ứng từ hồ sơ và thông tin mới trong hội thoại bằng bước xác nhận/cấu trúc rõ ràng; lọc và kiểm tra dị ứng lại bằng code trên mọi thẻ, không để lời văn LLM quyết định an toàn. |
| F03 / **CAO** | `agent/chat.py:301`; `core/nutrition.py:35`; SPEC R2 | **Đảo đối số tính BMI trong chatbot.** Hàm nhận `(weight_kg,height_cm)`, chatbot truyền `(height_cm,weight_kg)`. Hồ sơ demo BMI 20.7 bị chuyển thành 463.4; ca kiểm tra cô lập BMI 24.2 thành 346.9. AI thật đã trả lời dựa trên số sai rồi tự tính lại. | Dùng tham số có tên hoặc lấy BMI đã tính từ targets; thêm kiểm tra đối chiếu cùng hồ sơ giữa kết quả và chat. |
| F04 / **CAO** | `agent/chat.py:527–529,628–630,732`; SPEC R2, 5.2 | **Mục tiêu thật thành None trong ngữ cảnh chat.** DB dùng `target_kcal`, `protein_g`, `fat_g`, `carb_g`, `sodium_max_mg`, `fiber_min_g`; chat tìm `kcal_target`, `protein_g_target`… Ca #643 có 1860 kcal nhưng chatbot nói hồ sơ chưa có mục tiêu và đưa ước tính 1900–2100. Tái hiện prompt có “None kcal… Noneg”. | Dùng schema chuẩn thống nhất; không fallback sang LLM tự ước tính khi dữ liệu mục tiêu có sẵn. |
| F05 / **CAO** | `web/src/App.tsx:35,135,180`; `web/src/pages/ReviewPage.tsx:280–284`; SPEC 12/M11 | **Duyệt thành công nhưng trang Thực đơn vẫn báo chờ duyệt và hiển thị bản cũ.** #643 đã approved và cháo 395g trong DB; quay lại tab Thực đơn vẫn pending_review, cháo 400g. Chỉ khi mở lại đúng ca bằng “Xem giao diện Kết quả” mới nạp bản mới. | Sau lưu quyết định, cập nhật/invalidate `currentResult` theo plan ID; tải lại khi vào tab, tránh nhiều bản sao trạng thái độc lập. |
| F06 / **CAO, tiềm ẩn** | `agent/chat.py:767–774`; `observability/tracing.py:36–66`; SPEC R6/NFR8 | **Tin nhắn chat nguyên văn có đường đi vào Langfuse.** Truyền `input_data={message: clean_msg}` nhưng không đăng ký che chuỗi hoặc bọc user_data cho trường này. Hàm mask giữ nguyên message chứa tên/mã giả trong tái hiện cục bộ. Hiện tracing tắt nên chưa quan sát việc xuất ra dịch vụ. | Trace chỉ lưu độ dài/cờ/loại câu hỏi; che message và history trước mọi generation, kiểm thử bằng exporter giả với định danh giả. |
| F07 / **CAO** | `tests/test_graph.py:43–47`; `tests/conftest.py`; `tests/test_app.py`; SPEC 13/M13 | **Chạy test mặc định làm bẩn DB demo và phụ thuộc DB đã có.** Fixture seed/import dùng DB mặc định, không cô lập toàn cục. Lượt chạy đầu tạo #644–659 có thread test ngay trong `db/nutrition.db`; log mock bị ghi như hoạt động thường. Lượt cuối trên DB tạm còn 2 test_app lỗi “no such table: food”, bộc lộ phụ thuộc dữ liệu/engine mặc định. | Fixture toàn bộ test dùng DB/checkpoint tạm đã khởi tạo; các hàm phải dùng đúng session/engine được truyền; tách DB demo/test. Không dùng thống kê hiện tại để chứng minh hiệu năng AI thật. |
| F08 / **CAO, nghiệm thu** | `evidence/system-status.json`; SPEC 2.2, 4, 7, 11 | **Bản demo hiện chưa chứng minh đầy đủ Gemini + MCP + Langfuse.** Máy chủ chạy Alibaba/direct/tracing off. MCP có test pass nhưng không được gọi trong luồng UI vừa demo; không có trace Langfuse thật để hội đồng mở. | Chốt thay đổi phạm vi/đặc tả nếu đã được duyệt; nếu giữ SPEC, chuẩn bị cấu hình và bằng chứng đúng Gemini/MCP/Langfuse trước buổi bảo vệ. |
| F09 / **CAO, nghiệm thu** | `evals/summary.md`; `evals/results.csv`; SPEC 2.5,13,M12 | **Evals mới 6/40 ca trên mỗi cấu hình.** CSV có 18 dòng cho 3 cấu hình; báo cáo hiện hữu ghi constraint_violation_rate full=25%. Các con số 100%/p95 trên mẫu nhỏ, có cache và ca bị chặn không chứng minh ngưỡng toàn bộ bộ ca. Macro TB không thay thế kiểm tra từng macro. | Chạy đủ bộ theo hạn mức được duyệt; phân biệt cache/fresh, ca 3 ngày và ca chặn; báo cáo từng ngưỡng cùng số mẫu. Không trình bày số liệu này như đã đạt toàn bộ NFR. |
| F10 / **TB** | `web/src/components/result/ExplanationCard.tsx:54–71`; SPEC NFR9,10.2 | **Frontend xóa nguồn khỏi từng khuyến nghị.** Regex lấy `[tên tài liệu,tr.X]` ra khỏi từng bullet và gộp thành badge chung; mất quan hệ giữa khuyến nghị và nguồn, dù backend đã có trích dẫn. | Giữ citation inline hoặc số chú thích liên kết từng câu với đúng tài liệu/trang. |
| F11 / **TB** | `web/src/lib/format.ts:153–181`; `api/schemas.py:MealPlanDetailResponse`; SPEC 12 | **Mở lại ca mất ngữ cảnh kiểm chứng/RAG/nguy cơ.** Adapter đặt `risk=null`, `violations=[]`, `snippets=[]`, `trace_notes=[]`; API chi tiết cũng không trả đủ nguồn đã truy xuất. #643 mở lại mất nút xem 4 đoạn RAG; #660 chỉ còn lý do nguy cơ chung thay vì thai kỳ. | Lưu và trả lại các dữ liệu cần giải trình; phân biệt “không có vi phạm” với “không tải dữ liệu vi phạm”. |
| F12 / **TB** | `agent/chat.py:737,799`; `db/repo.py:906–916`; SPEC 11–12 | **Guardrail chatbot có DB event nhưng bị truy vấn dashboard bỏ qua.** Dashboard lấy event theo session có QueryLog; run_chat không ghi QueryLog. DB thật có QA_CHAT_drug/injection/highrisk events và 0 QueryLog tương ứng; đối chiếu điều kiện truy vấn xác nhận các session này không được chọn. | Ghi log chat với loại request rõ ràng hoặc truy vấn event độc lập theo bộ lọc; bổ sung token/độ trễ chat và tránh làm sai KPI tạo thực đơn. |
| F13 / **TB** | `api/routes/meal_plans.py:run_meal_plan`; `api/main.py`; SPEC 10.1–11 | **Dữ liệu REST bị từ chối trước graph không được audit, thông báo tiếng Anh.** Tuổi=0, days=8, sở thích 501 ký tự đều HTTP 422 hợp lệ; nhưng 0 event validation, không có QueryLog cho 3 request. Lỗi trả “Input should…” thay vì thông báo tiếng Việt. | Xử lý RequestValidationError chung, thông báo theo trường và ghi sự kiện đã che dữ liệu nhạy cảm. |
| F14 / **TB** | `db/repo.py:856–867`; SPEC 12 | **Bộ lọc bệnh chọn theo mọi phiên bản hồ sơ của người đó.** Cùng mã QA_CONTEXT có phiên t2d và phiên htn; lọc t2d vẫn lấy log của thực đơn chỉ có htn. Tái hiện bằng DB tạm. | Join theo QueryLog.meal_plan_id → MealPlan.profile_id → bệnh của đúng phiên; chỉ fallback khi không có liên kết. |
| F15 / **TB** | `web/src/pages/ChatPage.tsx:193–200`; SPEC yêu cầu tính nhất quán hồ sơ | **Không bỏ liên kết chat được khi đang có currentResult.** Chọn “Không gắn thực đơn” bị effect gắn lại #659 ngay. Effect cũng có thể ép quay lại initialLinkedPlanId khi chọn ca khác. History/session dùng chung giữa các ca, chưa được tách khi đổi hồ sơ. | Tách lựa chọn chủ động của người dùng khỏi khởi tạo mặc định; đặt lại hoặc tách history theo plan ID. |
| F16 / **TB** | Thực đơn #643, `data/food.csv`, `agent/nodes.py` danh sách món; SPEC M8/DoD tính hợp lý | **Đạt số liệu nhưng chưa thành thực đơn ăn được rõ ràng.** Ngày 1 có “Ức gà sống bỏ da” 85g; ngày 2 có 110g; khẩu phần khác có thịt chín 15g. UI không nói đây là khối lượng nguyên liệu trước nấu hoặc hướng dẫn chế biến. Không kết luận các giá trị DB sai; vấn đề là cách chuyển nguyên liệu thành bữa ăn cho bệnh nhân chưa rõ. | Tách trạng thái nguyên liệu/chín và cách chế biến; hiển thị định lượng trước/sau nấu đúng dữ liệu; chuyên gia rà tính thực tế trước phê duyệt. |
| F17 / **TB** | `web/src/components/profile/AnalyzingCard.tsx:8–12`; SPEC 12/M11 | **Tiến độ là mô phỏng theo thời gian, không phải trạng thái node thực.** Mốc 0/2/6/16 giây tự đổi giai đoạn; request chỉ trả kết quả cuối. Khi LLM retry/chậm, UI vẫn có thể đánh dấu bước đã xong. | Hiển thị trạng thái thực bằng polling/SSE hoặc ghi rõ đang chờ xử lý chung, không coi bộ đếm là bằng chứng quan sát 11 node. |
| F18 / **CAO, kiểm tra cuối** | `agent/prompts.py:394,413`; `app/pages/2_Ket_qua.py:201`; SPEC R8/AGENTS | **Nguồn thay đổi trong lúc rà soát và lint cuối lượt không đạt.** Ruff báo 3 lỗi: F841 (`oil_max` không dùng), 2 E501 (dòng dài). Verifier, portion, food/import và CSV cũng thay đổi sau khi bộ test đầu lượt đã chạy. Tập lệnh tái hiện cuối lượt dừng vì mock nhận needs_human_review thay vì pending_review. | Chốt một snapshot nguồn, sửa lint và chạy lại toàn bộ test cô lập; chưa được dùng kết quả test cũ để chốt bản mới. |
| F19 / **CAO, hồi quy cuối lượt** | `tests/test_api.py:108,154`; test_graph, test_tracing, test_verifier; nguồn thay đổi đồng thời | **Luồng mock tạo → sửa → duyệt không còn qua test.** Cuối lượt: nhóm MCP/API 2 failed, 7 passed; nhóm nhanh 18 failed, 220 passed. Trong nhóm nhanh có 2 lỗi setup food table (F07); các lỗi còn lại liên quan mock không đạt verifier, luồng không vào pending_review, retry hoặc macro. API ca bình thường trả needs_human_review; ca sửa không có items. Không quy lỗi này cho checkpoint/network khi graph đã dừng trước chờ duyệt. | Sửa tương thích giữa planner mock, cân chỉnh, dữ liệu thực phẩm và verifier mới; giữ các ràng buộc an toàn rồi chứng minh lại luồng pending_review và sửa/duyệt hợp lệ trên DB sạch. |

### Tái hiện lỗi F01 (ưu tiên cao nhất)

Tập lệnh `evidence/reproduce_offline.py` dùng DB tạm và mock; không đụng dữ liệu demo, không gọi model thật. Chuỗi đã chạy thành công trên nguồn đầu lượt, được giữ trong `offline-reproductions-initial.json`. Sau thay đổi nguồn đồng thời, lần chạy cuối không vượt qua bước tạo thực đơn mock hợp lệ; không khẳng định đã tái hiện lại được chuỗi này trên nguồn cuối lượt:

1. Tạo thực đơn hợp lệ → pending_review, 6 món.
2. Preview danh sách đủ dòng nhưng grams=0 → sai: `is_valid=true`, vẫn tính 6 món gốc.
3. Gửi bản sửa grams=10 cho mỗi món → needs_human_review; DB giữ 6 món cũ.
4. Gửi bản sửa đủ dòng grams=0 cho ca trên → sai: approved, 0 món, không có tổng ngày hoặc vi phạm.

Nguyên nhân: khi không còn món dương trong một bữa, `_apply_edited_items` lấy bữa gốc để kiểm chứng; đường lưu finalized lại xóa tất cả rồi lưu chính payload grams=0. Thực đơn kiểm chứng và thực đơn ghi xuống DB khác nhau.

### Bằng chứng giao diện

![Chatbot vẫn gắn nhãn an toàn cho trứng/mì trứng sau khai dị ứng](evidence/chat-allergy.jpg)

Ảnh dưới được chụp sau khi DB của #643 đã approved: frontend vẫn ghi chờ chuyên gia duyệt. JSON đã lưu xác nhận trạng thái DB và 395g.

![Trạng thái cũ còn hiện sau phê duyệt](evidence/stale-result.jpg)

## 3. Diễn tập end-to-end khi bảo vệ

### 3.1. Luồng chính đã thực hiện

| Bước demo | Kết quả quan sát | Đánh giá |
|---|---|---|
| Vai trò bệnh nhân → chọn mẫu Đái tháo đường T2 P0001 | Nạp được tuổi 26, nam, 171.3cm, 60.8kg, ít vận động, 3 ngày, “Không ăn cay” | Đạt thao tác |
| Tạo thực đơn | #643, pending_review, 1 lần tinh chỉnh, 3 ngày; mục tiêu 1860 kcal; BMI 20.7 | Đạt luồng |
| Xem giải trình | Có tên tài liệu/trang, 4 đoạn RAG xem được ngay sau tạo; frontend gom nguồn ra badge | Có lỗi F10 |
| Chuyển chuyên gia → sửa cháo ngày 1 từ 400g thành 0g → kiểm chứng lại | 3 vi phạm: KCAL_OUT_OF_RANGE và 2 MACRO_OUT_OF_RANGE; nút lưu sửa/duyệt khóa | Đạt ca sửa sai đơn lẻ |
| Đặt lại, sửa cháo thành 395g → kiểm chứng lại | Đạt kiểm chứng; nút lưu sửa/duyệt mở | Đạt |
| Lưu sửa và duyệt bởi “Chuyên gia DEMO QA” | DB approved, decision=edit, cháo 395g, review lưu được | Đạt lưu |
| Quay lại tab Thực đơn | Hiện pending_review và 400g cũ | **Không đạt F05** |
| Mở lại đúng #643 qua Tất cả → tìm ID → Xem giao diện Kết quả | Đã duyệt, 395g; mất phần xem đoạn RAG | Có đường khôi phục, lỗi F11 |
| Xem #660 (thai kỳ) và #669 (injection) qua UI | Chỉ thông điệp chuyển bác sĩ/bị chặn, không có danh sách thực đơn | Đạt an toàn hiển thị; lý do thai kỳ bị chung hóa khi mở lại |
| Dashboard | Có KPI, bộ lọc, link CSV; hiện 10 request an toàn mới, có cờ gồm log seed | Đạt tải; số liệu lẫn test, xem F07/F12/F14 |
| Chatbot hỏi mục tiêu của #643 | Trả None và BMI 463.4 | **Không đạt F03/F04** |
| Chatbot hỏi dị ứng sữa/trứng | Thẻ gợi ý có trứng/mì trứng dù phần lời văn có khuyên tránh | **Không đạt F02** |

**Số liệu #643 sau duyệt:** ngày 1 = 1784.9 kcal; ngày 2 = 1798.1 kcal; ngày 3 = 1840.6 kcal. Sai lệch so 1860 lần lượt khoảng 4.04%, 3.33%, 1.04%; từng macro ngày trong dung sai 15% ở ca này. Có review và trạng thái được lưu, chưa phát hiện tính sai kcal/macro của ca demo từ payload đã kiểm tra.

QueryLog #643 ghi `llm_calls=3`, 8617 token vào, 1465 token ra, latency=599.68ms. **Đây không phải bằng chứng 3 lần gửi mạng mới:** cache đang bật, phản hồi tạo ban đầu không được lưu trường execution. Không dùng thời gian này để kết luận NFR7 cho LLM thật không cache. Các thẻ lỗi và câu trả lời chat thật có lưu riêng trong evidence.

### 3.2. Mười ca an toàn bổ sung đã chạy trên máy chủ

| Ca | Plan ID | Trạng thái | Món / tổng ngày | Lượt gửi AI thật |
|---|---:|---|---|---:|
| Mang thai | 660 | redirect_to_doctor / RISK_PREG | 0 / 0 | 0 |
| Cho con bú | 661 | redirect_to_doctor / RISK_LACT | 0 / 0 | 0 |
| Tuổi 17 | 662 | redirect_to_doctor / RISK_MINOR | 0 / 0 | 0 |
| CKD 4 | 663 | redirect_to_doctor / RISK_CKD | 0 / 0 | 0 |
| CKD 5 | 664 | redirect_to_doctor / RISK_CKD | 0 / 0 | 0 |
| Lọc máu | 665 | redirect_to_doctor / RISK_CKD | 0 / 0 | 0 |
| Rối loạn ăn uống | 666 | redirect_to_doctor / RISK_ED | 0 / 0 | 0 |
| BMI 15 | 667 | redirect_to_doctor / RISK_BMI_LOW | 0 / 0 | 0 |
| Injection tiếng Việt | 668 | blocked | 0 / 0 | 0 |
| Injection tiếng Anh | 669 | blocked | 0 / 0 | 0 |

Đạt 8/8 chuyển hướng và 2/2 chặn trên **mẫu đã chạy**, không suy diễn thành tỷ lệ toàn hệ thống. Chat hỏi tăng liều thuốc và injection bị hard_block; chat gắn #660 không trả thực đơn cụ thể trong ca đã thử. Riêng chat #660 còn nhận BMI sai và việc không gợi ý bằng lời phụ thuộc prompt, nên vẫn cần kiểm thử đầu ra rộng hơn.

## 4. Đối chiếu tiêu chí đề bài

| Tiêu chí SPEC 2.2 / NFR | Bằng chứng hiện có | Kết luận kiểm tra này |
|---|---|---|
| Model Gemini/cấu hình/mock | SDK có cài, test mock qua; live dùng Alibaba | Chưa chứng minh đúng cấu hình Gemini của SPEC; cần chốt phạm vi |
| Workflow 11 node, retry ≤2, interrupt/resume | Test graph trong 238 bài qua, gồm cross-process; #643 sửa/duyệt chạy | Có bằng chứng chức năng; F01 vi phạm điều kiện duyệt |
| MCP 5 tool + RAG | 9 test nhóm MCP/API qua, nguồn RAG có trên kết quả | MCP pass test; live đang direct, frontend làm mất nguồn chi tiết khi mở lại |
| Observability | QueryLog hoạt động; SDK tracing test qua | Chưa đạt bằng chứng live Langfuse; F06/F07/F12/F13 làm yếu tính tin cậy |
| Evals 40 ca +10 ca vàng, 3 cấu hình | Có dữ liệu, CSV và ảnh; golden nằm trong test qua | Chưa đủ 40 ca chạy thật/cấu hình; summary chưa chứng minh đủ NFR |
| Guardrails input/output | 10 ca live đều chặn/chuyển đúng; test guardrails qua | Đạt mẫu kiểm tra đầu vào; F02 là lỗ hổng dị ứng trong chatbot |
| MVP UI, HITL, GitHub/CI, cài máy mới | Frontend/API dùng được, build qua; test backend qua | Chưa thể kết luận hoàn thiện: F01/F05; chưa chạy clone sạch hoặc kiểm CI từ xa |
| NFR1 recall nguy cơ cao=100% | 8/8 ca live đúng | Đạt mẫu; cần eval đầy đủ |
| NFR2 dị ứng=0% | Planner ca mẫu không thấy vi phạm; chat có món dị ứng | Không đạt an toàn toàn sản phẩm nếu chatbot là một phần demo |
| NFR3/4 kcal/macro | Ca #643 đạt; summary 6 ca hiện hữu có lỗi còn lại | Không đủ chứng minh toàn bộ NFR; không dùng TB macro để thay từng macro |
| NFR5 10 ca vàng | Tests golden thuộc bộ 238 bài qua | Có bằng chứng tự động |
| NFR6 redteam | 2 ca live đúng; tests qua; summary hiện hữu 30 redteam | Có bằng chứng hạn chế; không chạy lại trọn redteam live trong hạn mức |
| NFR7 p50≤30s/p95≤60s cho ca 3 ngày LLM thật | Chỉ một ca demo, có thể cache; log lẫn test | Chưa chứng minh |
| NFR8 riêng tư trace | Test hiện hữu qua, nhưng nhánh chat giữ message nguyên | Chưa đạt đảm bảo khi bật tracing cho chat |
| NFR9 từng khuyến nghị có nguồn | Backend có, frontend bỏ citation inline; chat tự do chưa kiểm đủ nguồn | Chưa đạt trải nghiệm/bằng chứng hiển thị theo yêu cầu |
| NFR10 chi phí 0 đồng | Dashboard chỉ ước tính; không truy cập hóa đơn/hạn mức nhà cung cấp | Chưa xác minh gói miễn phí; số ước tính không phải hóa đơn thực tế |

Đăng nhập/phân quyền thật nằm ngoài phạm vi SPEC; không đánh dấu việc REST thiếu auth thật là lỗi ở MVP này. Cờ TODO_VERIFY được giữ nguyên; cần công bố giới hạn này khi demo, không tự thay giá trị.

## 5. Kết quả lệnh kiểm tra

| Kiểm tra đã tự chạy | Kết quả |
|---|---|
| `.venv/Scripts/python.exe -m ruff check .` | **PASS đầu lượt**, cả sau khi thêm tập lệnh bằng chứng; **FAIL cuối lượt sau thay đổi nguồn khác**, 3 lỗi trong `agent/prompts.py`, `app/pages/2_Ket_qua.py` |
| `LLM_MODE=mock; pytest -q -m "not slow and not mcp"` | Đầu lượt: **238 passed, 10 deselected**, 180.64s. Cuối lượt, DB tạm: **18 failed, 220 passed, 10 deselected**, 257.31s |
| `LLM_MODE=mock; pytest -q -m mcp` | Đầu lượt: **9 passed, 239 deselected**, 55.82s. Cuối lượt, DB tạm: **2 failed, 7 passed, 239 deselected**, 62.24s |
| `npm exec tsc -- -b --pretty false` trong `web/` | **PASS**, exit 0 |
| Vite build ra `.cache/qa-audit-web-build` | **PASS**, 2799 modules, 7.40s; cảnh báo bundle JS 1.36MB (>500KB) |
| Tập lệnh tái hiện DB tạm | **Hoàn tất ở các lượt trước**, tái hiện được lỗi; **FAIL tiền điều kiện ở lượt cuối** sau thay đổi nguồn; file JSON thành công và log lỗi được giữ riêng |
| Console browser trong lượt cuối | Không thu được error/warn; điều này không loại trừ lỗi logic |

Python gốc không chạy được trong môi trường hạn chế ban đầu; các lệnh kiểm tra Python đã chạy ở môi trường máy thật. MCP được chạy riêng đúng quy định tránh treo kết nối nội bộ. Có 1 test slow chưa chạy trong hai bộ trên. Chưa mở MCP Inspector, Langfuse thật, CI từ xa hoặc clone sạch; không đánh dấu chúng đạt.

**Nguồn thay đổi đồng thời:** đầu lượt `agent/verifier.py`, `core/food.py`, `core/portion.py`, `data/food.csv`, `db/import_food.py` chưa nằm trong tập file sửa so HEAD; cuối lượt chúng có thay đổi. Thời gian ghi nhận lần sửa các file này khoảng 17:09–17:12 giờ Bangkok; chúng không do lượt kiểm thử này sửa. Một số thay đổi mới có thể đang xử lý tính thực tế khẩu phần (F16), nhưng chưa đủ bằng chứng nghiệm thu. Máy chủ live và tiến trình test có thể đang nạp các thời điểm nguồn khác nhau. Các phát hiện live có giá trị cho bản đã quan sát; trạng thái sửa/chưa sửa của từng lỗi trên nguồn mới cần xác minh lại sau khi chốt snapshot.

**Trạng thái kiểm tra cuối được bàn giao:** 20 test thất bại tổng cộng qua hai bộ tách biệt; 3 lỗi lint. TypeScript vẫn qua khi chạy lại cuối lượt. Không tuyên bố bản cuối đã đạt pytest/ruff. Log chi tiết: `evidence/final-fast-tests.txt`, `final-mcp-tests.txt`, `final-ruff.txt`, `final-typescript.txt`; dấu vân tay các file nguồn được đọc ở lượt cuối nằm trong `source-manifest.json`.

## 6. Lệnh để tự kiểm tra lại DoD sau khi sửa

**Trước khi chạy pytest, cô lập DB để tránh F07.** Ví dụ PowerShell tại gốc repo, dùng thư mục tạm mới cho mỗi lượt:

```powershell
$qaDir = Join-Path $env:TEMP ('nutriai-check-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $qaDir | Out-Null
$env:DB_URL = 'sqlite:///' + ((Join-Path $qaDir 'test.db') -replace '\\','/')
$env:CHECKPOINT_DB = Join-Path $qaDir 'checkpoints.sqlite'
$env:LLM_MODE = 'mock'
$env:TOOLS_MODE = 'direct'
$env:LANGFUSE_PUBLIC_KEY = ''
$env:LANGFUSE_SECRET_KEY = ''
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m pytest -q -m "not slow and not mcp"
# Chạy riêng ngoài môi trường chặn loopback:
.venv/Scripts/python.exe -m pytest -q -m mcp
# Tự tạo DB tạm, không gọi model thật:
.venv/Scripts/python.exe docs/reviews/2026-11-21/evidence/reproduce_offline.py
```

Lưu ý: tập lệnh tái hiện ghi lại trạng thái thực tế; sau sửa phải đọc JSON và thấy xóa hết món không hợp lệ, không có approved rỗng, BMI/mục tiêu khớp và bộ lọc bệnh đúng. Tập lệnh không tự khẳng định các lỗi đã được sửa.

```powershell
Set-Location web
npm.cmd exec tsc -- -b --pretty false
npm.cmd exec vite -- build --outDir ../.cache/qa-audit-web-build
```

Sau khi sửa, diễn tập lại trên một DB demo riêng: tạo hồ sơ → sửa sai bị chặn → sửa hợp lệ → duyệt → quay lại Thực đơn thấy trạng thái/định lượng mới ngay → mở lại vẫn xem được nguồn → nguy cơ cao không sinh món → injection hiện dashboard → chatbot không hiển thị món thuộc dị ứng. Với M12/M13, còn phải chạy đủ eval theo hạn mức, kiểm nguồn y khoa, trace thực, CI và cài từ clone mới.

## 7. Giả định, giới hạn và ảnh hưởng dữ liệu

- Chỉ dùng hồ sơ/tên/chỉ số giả lập. Nội dung y khoa trong báo cáo là đối tượng kiểm thử theo SPEC, không phải hướng dẫn điều trị hoặc kết luận xác minh y khoa độc lập.
- Báo cáo không sửa ứng dụng. Các nhược điểm về cách chế biến và câu trả lời tự do cần chuyên gia dinh dưỡng đánh giá thêm; không lấy việc “qua verifier” thay phê duyệt chuyên môn.
- Kiểm thử trực tiếp ở kích thước cửa sổ browser khoảng 727px; chưa khảo sát đầy đủ mọi màn hình, thiết bị, trình duyệt hay máy chiếu phòng bảo vệ.
- Chưa thử mất mạng, 429 thật, khởi động lại máy chủ giữa luồng trên UI, nhiều chuyên gia đồng thời, tải cao, toàn bộ 1–7 ngày với model thật, hoặc bài tấn công chưa biết. Test tự động đã kiểm một số nhánh retry/persistence nhưng không thay thử thực tế.
- Trạng thái gói miễn phí, quyền dùng model, tính đúng từng trích dẫn với bản PDF và toàn bộ lịch sử Git/bí mật chưa được kiểm toàn diện trong lượt này.
- Dữ liệu để lại: ca demo #643 đã approved; #660–669 là 10 ca an toàn được phép tạo; chat QA_CHAT_* và hội thoại UI là giả lập. Bộ test hiện hữu tạo #644–659 trong DB demo; đã lưu bằng chứng và không tự xóa lịch sử để tránh làm mất khả năng kiểm tra.
- Cache, DB tạm và kết quả build tạm có thể nằm ngoài thư mục báo cáo; không commit DB, `.env`, cache, Chroma. Không xuất khóa hoặc toàn bộ DB vào báo cáo.

## 8. Ba việc cần làm trước khi chốt demo

1. **Khóa lỗi an toàn và tính toàn vẹn:** sửa F01–F04/F06; bổ sung test cho xóa hết bữa, approved rỗng, dị ứng khai trong chat và đối chiếu BMI/targets.
2. **Làm luồng demo nhất quán:** sửa F05/F10–F15; cô lập test khỏi DB demo; rà tính thực tế của thực đơn; diễn tập lại toàn tuyến trên dữ liệu sạch.
3. **Hoàn tất bằng chứng đề bài:** chốt cấu hình đã được duyệt, chứng minh MCP/Langfuse/model thực, chạy đủ eval và kiểm CI/cài mới; công bố rõ cache và các giới hạn còn lại.

**Kết luận cuối: CHƯA ĐẠT DoD.** Điểm tích cực là hệ thống đã có luồng HITL hoạt động và bộ sàng lọc nguy cơ cao chặn đúng toàn bộ mẫu live vừa chạy. Các lỗi CAO còn tồn tại khiến chưa nên tuyên bố hệ thống đã đạt toàn bộ tiêu chí hoặc trình diễn chatbot tự do như một thành phần đã an toàn.

## 9. Danh mục file bàn giao

- `BAO_CAO_KIEM_THU.md`: báo cáo này.
- `evidence/system-status.json`: cấu hình vận hành không chứa khóa.
- `evidence/demo-plan-643.json`, `db-observations.json`: thực đơn/review và log đã chọn để đối chiếu.
- `evidence/safety-matrix.json`, `case-*.json`: 10 ca live và số lượt AI thực tế.
- `evidence/chat-*.json`: 5 câu trả lời chatbot qua REST; ảnh `chat-allergy.jpg`, `stale-result.jpg`.
- `evidence/reproduce_offline.py`, `offline-reproductions-initial.json`, `offline-reproductions.json`: mã và kết quả tái hiện thành công trong DB tạm trước thay đổi đồng thời; `offline-run.txt` và log kiểm tra cuối ghi trạng thái về sau.
- `evidence/offline-latest-run.json`: lần chạy cuối không vượt qua tiền điều kiện, tách khỏi JSON tái hiện thành công cũ. Các file `final-*.txt`, `source-manifest.json` ghi kiểm tra và phiên bản nguồn cuối lượt.

File mã sản phẩm đã sửa trong nhiệm vụ này: **không có**. Các file tạo mới phục vụ bàn giao nằm dưới `docs/reviews/2026-11-21/`.
