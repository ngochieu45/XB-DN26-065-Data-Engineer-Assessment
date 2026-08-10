# Kết quả eval KB

Lần chạy eval này kiểm tra retrieval hit cho 10 câu hỏi đã chuẩn bị. Groundedness vẫn là bước kiểm tra thủ công bằng cách đối chiếu câu trả lời mong đợi với các source chunks được retrieve.

- Số case đã chạy: 10
- Số case kiểm tra retrieval: 9
- Retrieval hit PASS: 9
- Retrieval hit FAIL: 0
- Số case out-of-scope cần kiểm tra thủ công: 1

| ID | Loại câu hỏi | Retrieval | Source mong đợi | Top source retrieve được |
| --- | --- | --- | --- | --- |
| Q01 | version-trap | PASS | `POL-01_chinh_sach_backup_v2.md` | `POL-01_chinh_sach_backup_v2.md, RUN-01_runbook_batch_report.md, POL-02_chinh_sach_truy_cap.md` |
| Q02 | direct | PASS | `FAQ-01_loi_thuong_gap.md` | `FAQ-01_loi_thuong_gap.md, RUN-01_runbook_batch_report.md, SOP-01_khoi_dong_lai_dich_vu.md` |
| Q03 | multi-source | PASS | `SOP-02_quy_trinh_escalation.md, SOP-01_khoi_dong_lai_dich_vu.md` | `SOP-01_khoi_dong_lai_dich_vu.md, SOP-02_quy_trinh_escalation.md, RUN-01_runbook_batch_report.md` |
| Q04 | direct | PASS | `GUIDE-01_giam_sat_he_thong.md` | `GUIDE-01_giam_sat_he_thong.md, SOP-02_quy_trinh_escalation.md, SOP-01_khoi_dong_lai_dich_vu.md` |
| Q05 | direct | PASS | `RUN-01_runbook_batch_report.md` | `RUN-01_runbook_batch_report.md, POL-01_chinh_sach_backup_v2.md, FAQ-01_loi_thuong_gap.md` |
| Q06 | direct | PASS | `POL-02_chinh_sach_truy_cap.md` | `POL-02_chinh_sach_truy_cap.md, FAQ-01_loi_thuong_gap.md, GUIDE-01_giam_sat_he_thong.md` |
| Q07 | multi-source | PASS | `FAQ-01_loi_thuong_gap.md, GUIDE-01_giam_sat_he_thong.md` | `FAQ-01_loi_thuong_gap.md, GUIDE-01_giam_sat_he_thong.md, SOP-01_khoi_dong_lai_dich_vu.md` |
| Q08 | direct | PASS | `RUN-01_runbook_batch_report.md` | `FAQ-01_loi_thuong_gap.md, RUN-01_runbook_batch_report.md, SOP-01_khoi_dong_lai_dich_vu.md` |
| Q09 | out-of-scope | MANUAL | `` | `POL-01_chinh_sach_backup_v2.md, SOP-02_quy_trinh_escalation.md, GUIDE-01_giam_sat_he_thong.md` |
| Q10 | direct | PASS | `SOP-01_khoi_dong_lai_dich_vu.md` | `SOP-01_khoi_dong_lai_dich_vu.md, RUN-01_runbook_batch_report.md, GUIDE-01_giam_sat_he_thong.md` |