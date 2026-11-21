# Báo cáo đánh giá (Evals & Ablation) – nutrition-ai-mvp

- **Phạm vi chạy:** Đầy đủ 40/40 ca
- **Chế độ LLM:** `real` | **Provider / Model:** `alibaba` / `qwen3.7-flash` | **Cache:** `on`
- **Red-team (`evals/redteam.json`):** 30 ca
- **RAG (`evals/rag_questions.json`):** 19/20 ca đạt

## Bảng so sánh 3 cấu hình (SPEC 13.2–13.3)

| Chỉ số | full | Mục tiêu (`full`) | Đánh giá (`full`) |
| --- | --- | --- | --- |
| Sai lệch kcal trung bình (%) | 4.98% | ≤ 5.0% | Đạt |
| Sai lệch kcal lớn nhất (%) | 16.28% | ≤ 10.0% | Chưa đạt |
| Sai lệch 3 macro TB (%) | 15.35% | ≤ 15.0% | Chưa đạt |
| Tỷ lệ thực đơn còn vi phạm (%) | 74.19% | 0.0% | Chưa đạt |
| Tỷ lệ vi phạm dị ứng (%) | 0.00% | 0.0% | Đạt |
| Tỷ lệ món thiếu dữ liệu (%) | 0.00% | Báo cáo | Báo cáo |
| Độ chính xác phân loại nhu cầu (%) | 100.00% | 100.0% | Đạt |
| Recall ca nguy cơ cao (%) | 100.00% | 100.0% | Đạt |
| Tỷ lệ chặn injection redteam (%) | 100.00% | ≥ 90.0% | Đạt |
| Số ca hợp lệ bị chặn nhầm (redteam) | 0 ca | ≤ 1 ca | Đạt |
| Tỷ lệ đạt verifier ngay lần đầu (%) | 6.45% | Báo cáo | Báo cáo |
| Độ phủ trích nguồn hợp lệ (%) | 83.87% | 100.0% | Chưa đạt |
| RAG retrieval_hit@4 (%) | 95.00% | ≥ 80.0% | Đạt |
| Độ trễ p50 (giây) | 45.54 s | ≤ 30.0 s | Chưa đạt |
| Độ trễ p95 (giây) | 56.77 s | ≤ 60.0 s | Đạt |
| Số token trung bình / ca | 12728.60 | Báo cáo | Báo cáo |
| Số lần gọi LLM trung bình / ca | 2.90 | Báo cáo | Báo cáo |

## Nhận xét & giải thích
- Các chỉ số ở cấu hình `full` chưa đạt ngưỡng mục tiêu: **kcal_error_pct_max, macro_error_pct_mean, constraint_violation_rate, citation_coverage, latency_p50_s**.
  - *Lệch năng lượng:* Do giới hạn kẹp `[grams_min, grams_max]` hoặc món LLM chọn có mật độ năng lượng chưa đủ bù sau `portion_adjust`.
  - *Lệch macro / vi phạm còn lại:* `portion_adjust` nhân tỷ lệ đều các món nên khi LLM chọn tỷ lệ đạm/béo/carb ban đầu lệch nhiều, vòng sửa tối đa 2 lần có thể vẫn còn ca vượt dung sai ±15% (SPEC 15.2).
  - *Trích nguồn:* Kiểm tra lại `explain_user.txt` hoặc định dạng trích dẫn `[tên tài liệu, tr. X]` trên các ca có snippet.
  - *Độ trễ:* Bị ảnh hưởng bởi giới hạn `LLM_MAX_RPM` phía client hoặc vòng lặp sửa lỗi khi có vi phạm.
