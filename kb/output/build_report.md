# Báo cáo build KB

## Tóm tắt

- Thư mục tài liệu nguồn: `Xbrain_Assessment_DE_DataPack/data/docs`
- SQLite index: `kb/output/kb.sqlite`
- Số tài liệu đọc được: 8
- Số chunk tạo ra: 30
- Số chunk thuộc tài liệu đã bị thay thế: 3

## Quyết định chunking

KB dùng structure-based chunking. Mỗi tài liệu Markdown được chia theo heading/section để từng phần SOP, policy, FAQ, guide và runbook vẫn giữ đủ ngữ cảnh khi được retrieve độc lập.

## Số chunk thiếu metadata

| Trường | Số chunk thiếu |
| --- | ---: |
| `version` | 21 |
| `issued_or_updated_date` | 0 |
| `owner` | 0 |

## Số chunk theo tài liệu nguồn

| Tài liệu nguồn | Số chunk |
| --- | ---: |
| `FAQ-01_loi_thuong_gap.md` | 6 |
| `GUIDE-01_giam_sat_he_thong.md` | 4 |
| `POL-01_chinh_sach_backup_v1.md` | 3 |
| `POL-01_chinh_sach_backup_v2.md` | 3 |
| `POL-02_chinh_sach_truy_cap.md` | 3 |
| `RUN-01_runbook_batch_report.md` | 4 |
| `SOP-01_khoi_dong_lai_dich_vu.md` | 4 |
| `SOP-02_quy_trinh_escalation.md` | 3 |

## Xử lý mâu thuẫn tài liệu

`POL-01_chinh_sach_backup_v2.md` được đánh dấu là chính sách backup hiện hành vì là phiên bản 2.0, ban hành 05/2026 và ghi rõ thay thế phiên bản trước. Các chunk từ `POL-01_chinh_sach_backup_v1.md` vẫn được giữ để audit nhưng được đánh dấu `is_superseded=true` để search ưu tiên bản hiện hành.
