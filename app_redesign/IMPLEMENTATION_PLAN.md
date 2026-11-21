# Kế hoạch redesign Streamlit — bản thử 8502

Ngày: 18/11/2026.
Trạng thái: được giao triển khai toàn diện trên bản thử 8502.

## Đợt Thực đơn React desktop đã duyệt

Đợt hoàn thiện dùng mã nguồn chính thức của shadcn/ui trong `frontend/src/components/ui`.
Sidebar, Tabs, Sheet, Button, Card, Badge, Table và Alert thống nhất hành vi và
kiểu dáng. Tailwind biên dịch các utility của registry. `main.py` xử lý sự kiện
điều hướng và vai trò từ Sidebar. Ảnh ba bữa là minh họa biên tập trong
`assets/meal-editorial.jpg`. Test thêm việc giới hạn trang theo vai trò demo.

Đợt này triển khai riêng màn Thực đơn. `pages/results.py` đọc bản ghi của ca,
`meal_studio.py` chuẩn bị dữ liệu cho React và đăng ký Components v2.
`frontend/` giữ mã React/TypeScript, CSS, phiên bản npm, lệnh build và test vòng
năng lượng. `style.css` có phần riêng cho khung Thực đơn. Nút đổi ngày/bữa xử lý
trong trình duyệt, còn lệnh về Hồ sơ đi qua điều hướng Streamlit.

React cho bố cục và tương tác của toàn màn. Radix Dialog áp dụng mẫu Shadcn Sheet
cho ngăn chi tiết và xử lý bàn phím. Motion làm rõ nội dung vừa đổi. Lucide dùng
cho biểu tượng và Be Vietnam Pro dùng để hiển thị tiếng Việt nhất quán. Tất cả
tài nguyên cần lúc chạy được build cục bộ.

Nghiệm thu ca P0005 ở 1280, 1440 và 1920 px. Thử đổi ngày/bữa, mở nguồn theo vai
trò, mở/đóng ngăn chi tiết, cập nhật kết quả duyệt và ca chuyển bác sĩ chỉ bằng dữ
liệu giả lập trong DB tạm. Chạy bộ test Node, ruff, bộ pytest nhanh và MCP riêng.

Hướng triển khai: xây dựng giao diện theo phong cách cổng dinh dưỡng phòng khám.
Khung ứng dụng có nhận diện Nutri AI, điều hướng theo vai trò, hệ màu xanh rừng /
kem / xanh bạc hà và bộ thành phần nhất quán. Hồ sơ có ảnh nguyên liệu do ImageGen
tạo và lưu WebP cục bộ. Thực đơn có dải trạng thái, điều hướng ngày bằng Components
v2, thẻ bữa và biểu đồ dùng chung bảng màu. Bàn duyệt có hàng đợi tìm kiếm được,
thông tin ca và thao tác kiểm chứng trong cùng khu vực. Dashboard dùng bộ thẻ KPI
và biểu đồ với định dạng tiếng Việt. File tạo thêm nếu dùng gồm
`assets/clinic-ingredients.webp` và `components.py`; các file khác theo Phần 10.

Thử Shadcn 1.5.0 trong thư mục tạm trước. Nếu không lấy hoặc chạy được gói trên
runtime hiện có, dùng Streamlit + CSS riêng và Components v2 cho điều hướng ngày.
Giữ chất lượng thiết kế theo cùng hệ màu, kiểu chữ và trạng thái ở cả hai phương án.

## 1. Mục tiêu và phạm vi

Thiết kế lại bố cục và trải nghiệm của bốn màn hình hiện có theo docs/SPEC.md Phần 12 và M11. Mục tiêu chất lượng cảm nhận khoảng 8/10 trên desktop, hướng tới 9/10 nếu kết quả chạy thực tế đạt. Điểm số mang tính chủ quan, không phải cam kết trước khi kiểm tra.

Hướng thiết kế: ấm áp, dễ hiểu với người bệnh; rõ ràng, có căn cứ với chuyên gia. Đưa khẩu phần, kiểm chứng, nguồn tham khảo và trạng thái duyệt thành điểm nhấn của sản phẩm.

- Chỉ triển khai trong app_redesign/, chạy ở cổng 8502.
- Giữ nguyên app/ và bản 8501; không sửa agent/, core/, guardrails/, mcp_server/, db/, config/, data/, rag/ hoặc dữ liệu gốc.
- Không thay backend, ngưỡng y khoa, thuật toán, schema dữ liệu hoặc cơ chế duyệt.
- SQLite, checkpoint, Chroma và cache thử nghiệm chỉ nằm trong thư mục tạm của hệ thống; launcher dọn sau khi dừng.
- Không gọi API LLM thật, không gửi telemetry hoặc dữ liệu định danh.
- Không thêm nhận diện ảnh, đăng nhập, lịch sử sức khỏe hoặc tính năng nghiệp vụ mới ngoài SPEC.

## 2. Thư viện và quyết định kỹ thuật

### Bộ giao diện ưu tiên

Thử **streamlit-shadcn-ui** làm bộ thành phần chính để có nút, lựa chọn, tab, thẻ, hộp thoại và bảng nhất quán. Thư viện có giấy phép MIT, không yêu cầu dịch vụ trả phí cho các thành phần sử dụng cục bộ.

Lý do bổ sung ngoài danh sách SPEC Phần 4: cải thiện thành phần tương tác và tính nhất quán mà vẫn giữ Streamlit, không phải tách frontend/backend. Việc thêm thư viện phải nằm trong phạm vi kế hoạch được duyệt.

Nguồn chính thức: https://github.com/ObservedObserver/streamlit-shadcn-ui

### Thử tương thích trước khi áp dụng

Metadata thư viện trong .venv hiện ghi Streamlit 1.67.0 và Plotly 7.1.0. Python được .venv tham chiếu hiện không chạy được; cần xác định interpreter đang phục vụ 8502 và kiểm tra phiên bản trong đúng môi trường đó. Không tự sửa hoặc nâng cấp môi trường dùng chung.

Tài liệu Shadcn có lưu ý về tổ hợp Streamlit/Starlette đã kiểm chứng và lỗi phục vụ tài nguyên ở một tổ hợp khác. Không mặc định phiên bản mới nhất tương thích với dự án.

1. Dùng môi trường thử riêng trong thư mục temp, tận dụng các phụ thuộc hiện có nếu phù hợp; không cài đè môi trường đang phục vụ bản gốc.
2. Chọn và ghim phiên bản sau khi đọc tài liệu đúng phiên bản.
3. Thử nút, lựa chọn, tab, hộp thoại và thẻ trên Streamlit thực tế.
4. Kiểm tra rerun, key ổn định, trao đổi giá trị với Python, bàn phím, overlay và giữ dữ liệu khi chuyển bước/trang.
5. Nếu tương thích tốt mới áp dụng vào hai màn hình chính, sau đó mở rộng.
6. Nếu không đạt, dùng widget Streamlit gốc và Custom Components v2 ở các khối cần thiết kế riêng. Không hạ cấp Streamlit hoặc đổi Starlette của môi trường gốc để ép chạy.

### Những phần dùng kèm

- Plotly đang có: thống nhất màu, đơn vị, tooltip, chú giải và bố cục biểu đồ.
- CSS và SVG tự thiết kế: bản sắc, minh họa ẩm thực và các khối trình bày riêng, lưu cục bộ.
- Biểu tượng và font: dùng một hệ thống thống nhất; tài nguyên thêm phải có giấy phép miễn phí phù hợp và lưu thông tin giấy phép.
- Custom Components v2: chỉ dùng khi cần tương tác riêng; đọc tài liệu đúng phiên bản. Không dùng script sửa DOM nội bộ của Streamlit.
- Giữ widget Streamlit gốc cho thao tác mà thư viện bổ sung chưa bảo đảm đúng hành vi, đặc biệt form và bảng chỉnh sửa chuyên gia.
- Không ghép đồng thời Shadcn, Antd và Material UI. Antd/streamlit-elements là lựa chọn tham khảo, chưa nằm trong danh sách cài đặt.

Tài liệu nền tảng:
- https://docs.streamlit.io/develop/concepts/custom-components/components-v2
- https://docs.streamlit.io/develop/concepts/multipage-apps/page-and-navigation

## 3. Hệ thống thiết kế

- Nền trắng ngà, chữ xanh than, xanh ngọc cho hành động chính; cam ấm làm điểm nhấn thực phẩm.
- Màu cảnh báo chỉ dùng đúng trạng thái; luôn có chữ hoặc biểu tượng, không truyền đạt bằng màu đơn thuần.
- Chữ hỗ trợ tiếng Việt tốt; giảm tiêu đề quá đậm và khoảng cách chữ âm hiện tại.
- Có cấp độ khoảng cách, kích thước chữ và mật độ riêng cho màn hình người bệnh và chuyên gia.
- Thay hình chiếc đĩa CSS lặp lại bằng minh họa có chủ đích. Ảnh món ăn chỉ dùng khi gắn đúng nội dung; ảnh nhóm thực phẩm phải ghi là minh họa, không đại diện chính xác khẩu phần.
- Bố cục phối hợp vùng lớn/nhỏ và nội dung/hình ảnh, không biến mọi vùng thành thẻ giống nhau.
- Chuyển động nhẹ; hỗ trợ giảm chuyển động; không dùng hiệu ứng làm chậm thao tác.
- HTML động phải escape; không bật thực thi nội dung HTML/JavaScript từ người dùng.

## 4. Điều hướng và khung ứng dụng

- Một menu tiếng Việt duy nhất, loại bỏ menu tự sinh main/dashboard/profile/results/review.
- Người bệnh: Hồ sơ, Thực đơn. Chuyên gia: thêm Bàn duyệt. Quản trị: thêm Tổng quan vận hành.
- Bộ chọn vai trò vẫn là cơ chế demo, không trình bày như phân quyền bảo mật thật.
- Sidebar gọn, có biểu tượng và trạng thái chọn rõ. Đặt nhãn bản thử/dữ liệu giả lập riêng.
- Thông tin kỹ thuật chi tiết thu gọn; cảnh báo dữ liệu mẫu và quy tắc TODO_VERIFY vẫn hiện rõ từ thông tin thực tế.
- Giữ disclaimer trên mọi trang; không che cảnh báo để tăng tính thẩm mỹ.

## 5. Hồ sơ: nhập thông tin có dẫn dắt

- Màn bắt đầu gồm khối giới thiệu ngắn và lựa chọn nhập mới/thử hồ sơ mẫu.
- Hồ sơ mẫu trình bày dễ hiểu theo bệnh lý; mã kỹ thuật là thông tin phụ. Không nạp mẫu làm mất bản nháp mà không có cảnh báo phù hợp.
- Khi nhập, thu gọn giới thiệu; phần chính khoảng 70%, tóm tắt khoảng 30%.
- Ba bước: Cơ thể & vận động → Sức khỏe & dị ứng → Sở thích & xác nhận.
- Nhóm trường hợp lý, đơn vị rõ; vận động có mô tả; tình trạng nguy cơ cao và dị ứng không bị giấu trong mục khó tìm.
- Tóm tắt đúng dữ liệu đã lưu; nếu chỉ cập nhật sau khi gửi bước phải nói rõ, không tạo cảm giác cập nhật trực tiếp sai thực tế.
- Giữ thông tin khi quay lại/chuyển trang theo thiết kế; có đường trở lại sửa trước khi tạo.
- Lỗi gần trường liên quan; nút Quay lại/Tiếp tục/Tạo đặt nhất quán.

## 6. Thực đơn: màn hình điểm nhấn

- Bỏ banner lớn. Đầu trang gồm kế hoạch, mã hồ sơ, số ngày và trạng thái duyệt.
- Chọn ngày ngay bên dưới; nguồn thực thi và số API/cache/giả lập gắn đúng lượt xử lý.
- Vùng chính khoảng 2/3: bữa ăn, danh sách món, gram, tổng dinh dưỡng bữa. Vùng phụ khoảng 1/3: năng lượng so với mục tiêu, macro và chỉ số liên quan.
- Thẻ bữa ăn có phân cấp rõ, không chỉ đổi màu đường viền. Nếu mở chi tiết bằng hộp thoại, thao tác phải hoạt động thật và giữ ngày đang chọn.
- Giải thích có nguồn, ghi chú chuyên gia và bảng dinh dưỡng đầy đủ dễ truy cập.
- Giữ BMI, BMR, TDEE, nhu cầu, số lần sửa và các thông tin SPEC yêu cầu ở vị trí hợp lý.
- Không giả số thiếu thành 0; biểu đồ không hiển thị nếu thiếu dữ liệu cần thiết.
- Phân biệt chờ duyệt/đã duyệt/từ chối/cần xem xét. Chuyển bác sĩ hoặc bị chặn không có menu hay KPI như một kết quả hợp lệ.
- Không biến đạt verifier thành đã được chuyên gia duyệt.

## 7. Bàn duyệt: ưu tiên quyết định chuyên môn

- Không dùng banner quảng bá. Hàng đợi bên trái, ca đang xem bên phải.
- Mã ca, trạng thái, bệnh lý, dị ứng và cảnh báo hiện có dễ nhận biết.
- Khẩu phần chỉnh sửa, vi phạm, nguồn và ghi chú đặt cạnh nhau theo nhiệm vụ.
- Sửa gram/xóa món làm mất hiệu lực kiểm chứng cũ; hiện rõ cần kiểm chứng lại.
- Nút bị khóa có lý do; Kiểm chứng → Duyệt rõ thứ tự; từ chối bắt buộc lý do.
- Giữ cơ chế gắn kiểm chứng với đúng ca/phiên bản và kiểm chứng lại khi lưu.
- Ca lịch sử thiếu checkpoint ở bản thử chỉ đọc; không làm như có thể resume được.

## 8. Dashboard: thông tin trước trang trí

- Tiêu đề gọn, bộ lọc và KPI xuất hiện trên màn hình đầu; không lặp banner người bệnh.
- Hoạt động theo ngày là biểu đồ chính; phân bố bệnh, guardrail và độ trễ là các vùng phụ.
- Giữ bốn biểu đồ, KPI, CSV, nhật ký và liên kết trace theo SPEC khi có dữ liệu.
- Chú giải, đơn vị, màu trạng thái và cách định dạng số nhất quán.
- Ghi rõ log giả lập; không trình bày như bằng chứng chất lượng thực tế.
- Đối soát cách đếm và đơn vị khi biểu đồ có chênh lệch bất thường; nếu lỗi thuộc backend/dữ liệu thì báo riêng, không che bằng biến đổi biểu đồ tùy tiện.
- Không bịa nhận xét, xu hướng hoặc phần trăm tăng trưởng khi thiếu dữ liệu đối chiếu.

## 9. Phản hồi và trạng thái

- Tiếp tục bước: xác nhận lưu bước và chưa gọi API, không tái dùng nhãn kết quả của lần chạy trước làm trạng thái lần bấm mới.
- Tạo thực đơn: chống gửi lặp, trạng thái đang xử lý và lỗi rõ; giữ bản nháp khi lỗi.
- Kết quả lấy api_attempts/mock_calls/cache_hits từ execution thực tế; bản ghi cũ ghi chưa có thông tin.
- Chỉ hiện tiến độ từng node nếu có sự kiện thật từ backend. Nếu chưa có, dùng trạng thái đang xử lý trung thực và ghi phần tiến độ node là giới hạn; không dựng phần trăm giả hoặc sửa backend trong đợt này.
- Thiết kế đầy đủ trạng thái trống, đang chạy, thành công, thiếu dữ liệu, lỗi và không được phép duyệt.

## 10. File dự kiến

Tất cả nằm trong app_redesign/:

| File/thư mục | Thay đổi |
|---|---|
| main.py | Một hệ điều hướng, khung và vai trò demo |
| ui.py | Thành phần dùng chung, tích hợp thư viện, trạng thái và lớp trình bày |
| style.css | Hệ thống thiết kế, bố cục và kích thước màn hình |
| pages/profile.py | Luồng nhập và tóm tắt |
| pages/results.py | Kế hoạch theo ngày, bữa ăn, dinh dưỡng, nguồn |
| pages/review.py | Hàng đợi, chỉnh sửa và kiểm chứng |
| pages/dashboard.py | KPI, bộ lọc, bốn biểu đồ và nhật ký |
| assets/ (mới nếu cần) | SVG, ảnh/font hợp lệ, ghi nhận giấy phép |
| requirements-preview.txt (mới nếu cần) | Phụ thuộc thêm được ghim cho bản thử; không sửa requirements gốc |
| tests/ | Bổ sung test hành vi và hồi quy phù hợp |
| README.md | Cách chạy môi trường thử, phụ thuộc và giới hạn |
| run.py | Chỉ chỉnh khi cần cấu hình riêng; giữ khóa mock và cô lập temp |

Nếu cần tách module thành phần để dễ bảo trì, chỉ tạo trong app_redesign/ và ghi lại khi bàn giao.

## 11. Thứ tự triển khai

1. Xác định môi trường đang chạy, kiểm chứng Shadcn ở temp, chọn phiên bản/phương án dự phòng.
2. Làm hệ thống thiết kế và điều hướng; thiết kế hoàn chỉnh Hồ sơ và Thực đơn trước.
3. Kiểm tra hai màn chính trong trình duyệt với dữ liệu giả lập có nội dung; điều chỉnh bố cục trước khi nhân rộng.
4. Làm Bàn duyệt và Dashboard theo bố cục riêng.
5. Hoàn thiện trạng thái, bàn phím, kích thước màn hình, test và chụp bằng chứng.
6. Chấm lại theo cùng tiêu chí; nêu điểm còn yếu, không tự gán 8–9 chỉ vì đã thêm thư viện.

Không triển khai sang bản 8501 trong kế hoạch này.

## 12. Kiểm thử và nghiệm thu

### Tự động

- Dùng dữ liệu giả trong tmp_path/tempfile. Không dùng DB/checkpoint gốc làm nơi ghi test.
- Kiểm tra cô lập launcher, thiếu môi trường an toàn, giữ bản nháp, đổi mẫu, chuyển bước, trạng thái kết quả và API.
- Kiểm tra ca không menu không vẽ số giả; sửa/đổi ca không tái dùng kiểm chứng; ca rỗng không duyệt được; escape nội dung động.
- Thành phần ngoài phải kiểm tra thêm bằng trình duyệt; AppTest đơn thuần không đủ chứng minh phần JavaScript hoạt động.
- Chạy ruff và pytest phù hợp. Nếu chạy bộ chung trong sandbox Windows, tách `not slow and not mcp` khỏi MCP; không gộp `not slow` trong sandbox.
- Chỉ báo hoàn thành khi các kiểm tra bắt buộc pass. Không chạy API thật để nghiệm thu redesign.

### Trình duyệt thực tế

- Xem ở ít nhất 1280×720 và 1440×900; kiểm tra thu nhỏ khoảng 1024px, không tràn ngang hoặc đè nút.
- Hồ sơ → kết quả chờ duyệt → chuyên gia sửa/kiểm chứng/duyệt → kết quả cập nhật.
- Ca nguy cơ cao chuyển bác sĩ; ca bị chặn; thiếu dữ liệu; verifier thất bại; từ chối không có lý do.
- Kiểm tra chọn ngày, đóng/mở chi tiết, đổi vai trò, trạng thái rỗng và bộ lọc không có dữ liệu.
- Nút và trường có nhãn rõ, focus bàn phím nhìn thấy, tương phản dễ đọc, không phụ thuộc hover.
- Chụp các trang có dữ liệu giả lập và trạng thái quan trọng, lưu bằng chứng trong temp; giao diện trống không đủ để nghiệm thu.

### Thước đo chất lượng cảm nhận

| Tiêu chí | Trọng số |
|---|---:|
| Bố cục, phân cấp và ưu tiên thông tin | 25% |
| Dễ tương tác và phản hồi đúng | 25% |
| Hình thức, bản sắc và tính nhất quán | 25% |
| Trạng thái an toàn và độ rõ của nội dung | 15% |
| Đọc dễ, bàn phím và thích ứng kích thước | 10% |

Mục tiêu: một menu, không banner lặp; nội dung/thao tác chính thấy ngay trên laptop; hai màn Hồ sơ/Thực đơn đủ nổi bật và hữu dụng; không lỗi luồng duyệt hoặc che cảnh báo vì thẩm mỹ.

## 13. Bàn giao và giới hạn

- Danh sách file đổi, phiên bản phụ thuộc, lệnh chạy/test theo môi trường thực tế, kết quả kiểm thử và ảnh trước/sau khi có.
- Nêu rõ mock/direct trên 8502 không chứng minh chất lượng LLM thật hoặc tích hợp MCP thật.
- Điểm 8–9 chỉ được đánh giá sau khi xem sản phẩm chạy; không cam kết điểm hội đồng.
- Nếu cần sửa ngoài phạm vi để xử lý lỗi phát hiện, báo nguyên nhân và phương án trước; không âm thầm sửa source/dữ liệu gốc.
