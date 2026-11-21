# Nutri AI — bản thiết kế desktop độc lập

Ứng dụng thử ở cổng **8502**, dùng các hàm agent, DB và RAG của dự án gốc.
Không sửa hay thay thế `app/`. Mọi thành phần của bản mới nằm trong thư mục này.

## Chạy từ thư mục gốc dự án

```powershell
.\.venv\Scripts\python.exe app_redesign/run.py
```

Mở http://localhost:8502. Bản cũ vẫn có thể chạy ở cổng 8501.
Launcher tạo SQLite và Chroma bản sao trong thư mục temp, tạo checkpoint/cache mới,
khóa LLM mock, tools direct, safety LLM off, xóa khóa API khỏi môi trường tiến trình con
và tắt Langfuse/Streamlit telemetry. Không có tùy chọn bật API thật trong bản này.
Nếu chạy `streamlit run app_redesign/main.py` trực tiếp, app sẽ từ chối hoạt động
khi thiếu môi trường cô lập. Không ghi dữ liệu vào DB gốc.

Môi trường đã kiểm tra dùng Python 3.12, Streamlit 1.67.0, Starlette 1.10.0 và
Plotly 7.1.0. Nếu `.venv` không chạy được, dùng một interpreter Python 3.12 có
cùng phụ thuộc dự án và chạy cùng file launcher.

Màn Thực đơn desktop dùng React trong Streamlit Components v2. Vòng năng lượng
SVG, ngày đang xem và bữa đang xem cập nhật cùng lúc. Vòng biểu thị tỷ trọng giữa
các bữa có đủ số liệu, còn con số ở giữa lấy từ tổng ngày trong DB. Bảng dinh
dưỡng và nguồn mở trong ngăn chi tiết. Cổng 8502 dùng các file đã build trong
`frontend/dist` nên không cần tiến trình Node lúc chạy.

Màn Hồ sơ và Bàn duyệt dùng widget Streamlit gốc. Dashboard dùng Plotly. Ảnh
`assets/clinic-ingredients.webp` do ImageGen tạo cho trang Hồ sơ và nhúng cục bộ.
Ảnh chỉ minh họa nguyên liệu.

Khi sửa frontend, chạy từ gốc dự án bằng Node.js 26 đã kiểm tra:

```powershell
npm.cmd ci --prefix app_redesign/frontend --ignore-scripts
npm.cmd test --prefix app_redesign/frontend
npm.cmd run build --prefix app_redesign/frontend
```

Sidebar, Tabs, Sheet, Card, Badge, Button, Table và Alert được lấy từ registry
New York của shadcn/ui và phối màu cho Nutri AI. Tailwind biên dịch các lớp CSS
khi build. React, shadcn/ui, Radix và Motion theo giấy phép MIT. Lucide theo ISC và một số biểu tượng
kế thừa từ Feather theo MIT. Be Vietnam Pro theo SIL OFL 1.1. Xem thông báo
phân phối trong `frontend/dist/THIRD_PARTY_NOTICES.txt`.

Ảnh `assets/meal-editorial.jpg` do ImageGen tạo và đi kèm nhãn “Ảnh minh họa”.
Ảnh dùng chung theo bữa sáng, trưa, tối. Món và khẩu phần cụ thể đọc từ DB.

<details>
<summary>Prompt ImageGen dùng cho ảnh Hồ sơ</summary>

> Create a single premium photographic hero asset for a modern Vietnamese nutrition clinic portal. Landscape, horizontal editorial crop 3:2. Highly realistic top-down photograph of a carefully art-directed selection of fresh Vietnamese ingredients on a sage olive gray matte table: substantial natural green leafy herbs and bok choy, sliced yellow citrus, a few small orange tomato accents, a woven natural linen napkin, handmade ivory ceramic bowl with mixed fresh vegetables and herbs. Ingredients arranged confidently and generously as an editorial composition, focal bowl placed slightly right of center but complete within center crop, richly textured, fine soft slightly directional daylight, dark botanical green shadows and warm highlights, refined design-magazine food photography, balanced natural saturation, inviting contemporary clinic tone. No people, no text, no marks, no badges, no graphics, no mockup. Editorial ingredient photo, not a diet prescription or measured meal.

</details>

## Cách thử

1. Người bệnh: chọn mẫu, đi qua ba bước, tạo kết quả. Thông tin API thực tế lấy từ backend.
2. Mở vai trò Chuyên gia để xem hàng đợi. Ca do phiên bản thử hiện tại tạo có thể duyệt;
   ca lịch sử chỉ để đọc vì không sao chép checkpoint của app gốc.
3. Chỉnh gram, kiểm chứng rồi duyệt. Đổi món/gram hoặc đổi ca sẽ làm hết hiệu lực
   lần kiểm chứng trên màn hình; khi lưu, backend vẫn kiểm chứng lại.
4. Mở không gian Quản trị để xem dashboard, bộ lọc và CSV từ bản sao.
5. Ca nguy cơ cao chỉ hiện chuyển hướng; không hiện menu, KPI dinh dưỡng hay biểu đồ.

Số liệu chất xơ không có trong bản ghi DB sẽ hiện "Chưa có dữ liệu", không giả làm 0.
Biểu đồ phân bố bệnh giữ số đếm từ backend và cảnh báo nếu một nhóm vượt tổng lượt xử lý.
Số đếm có thể lặp khi một mã hồ sơ có nhiều bản ghi cùng nhóm bệnh.
Tiến độ hiện ở mức đang xử lý vì backend chưa gửi sự kiện tiến độ từng bước.
Nội dung sức khỏe và lời giải thích vẫn cần chuyên gia đánh giá; chế độ demo không
phải cơ chế xác thực người dùng. Chỉ dùng dữ liệu giả lập.

## Kiểm tra

```powershell
$env:LLM_MODE='mock'
.\.venv\Scripts\python.exe -m pytest -q app_redesign/tests -m "not slow and not mcp"
.\.venv\Scripts\python.exe -m ruff check app_redesign
```

Nhấn Ctrl+C ở cửa sổ chạy để dừng và dọn dữ liệu tạm. Để gỡ bỏ, dừng app rồi xóa
`app_redesign/`; không cần thay đổi backend hay giao diện cũ. Dữ liệu và quyết định
trong bản thử không chuyển ngược sang bản gốc. Không tắt cưỡng bức nếu muốn launcher
dọn thư mục temp tự động.
