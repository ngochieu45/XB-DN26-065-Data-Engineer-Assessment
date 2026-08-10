# SOP cập nhật Knowledge Base

SOP này dùng khi khách hàng gửi tài liệu vận hành mới hoặc sửa tài liệu cũ. Mục tiêu là cập nhật KB mà vẫn giữ được truy vết nguồn, xử lý đúng version/freshness và không làm giảm chất lượng retrieval.

## Phạm vi và vai trò

- Phạm vi: tài liệu nguồn trong `Xbrain_Assessment_DE_DataPack/data/docs/`, code và output trong `kb/`.
- Người thực hiện: Data Engineer.
- Người xác nhận nội dung: document owner hoặc người phụ trách vận hành, đặc biệt với policy/SOP.
- Artifact đầu ra: `kb/output/chunks.jsonl`, `kb/output/kb.sqlite`, `kb/output/build_report.md`, `kb/output/eval_results.md`.

## Quy trình cập nhật

### 1. Nhận tài liệu và xác định loại thay đổi

1. Lưu tài liệu mới hoặc bản sửa vào `Xbrain_Assessment_DE_DataPack/data/docs/`.
2. Không ghi đè file policy cũ nếu file đó là một version cần giữ để audit. Ví dụ giữ cả `POL-01_chinh_sach_backup_v1.md` và `POL-01_chinh_sach_backup_v2.md`.
3. Ghi lại loại thay đổi:
   - tài liệu mới;
   - sửa nội dung tài liệu hiện có;
   - version mới thay thế version cũ;
   - đổi metadata nhưng không đổi nội dung.

Điều kiện đạt: file nằm đúng thư mục, tên file rõ `DOC-ID_mo_ta.md`, và không làm mất bản cũ cần audit.

### 2. Kiểm tra metadata trước khi build

Mở file mới/sửa và kiểm tra phần header:

```text
Title / doc_id
Owner hoặc phòng ban chịu trách nhiệm
Version nếu là policy
Ngày ban hành hoặc ngày cập nhật
Câu "Thay thế phiên bản trước" nếu đây là bản thay thế
```

Quyết định xử lý:

- Nếu là policy/SOP có nhiều version nhưng thiếu version/date: không release KB, hỏi lại document owner.
- Nếu là FAQ/guide/runbook không có version nhưng có ngày cập nhật: cho phép build, nhưng phải kiểm tra `build_report.md`.
- Nếu file ghi rõ thay thế bản trước: bản cũ được giữ lại nhưng phải bị đánh dấu `is_superseded=true` trong chunks.

Điều kiện đạt: metadata đủ để người vận hành biết chunk thuộc tài liệu nào, section nào, ngày nào và có còn hiệu lực không.

### 3. Kiểm tra conflict hoặc superseded document

1. Tìm tài liệu cùng `doc_id`, ví dụ `POL-01`.
2. So sánh version/date giữa bản mới và bản cũ.
3. Nếu nội dung khác nhau về cùng một chính sách, ghi đây là conflict cần rule freshness.
4. Với bản thay thế, KB phải ưu tiên bản mới khi query nhưng vẫn giữ bản cũ để audit.

Ví dụ rule hiện tại:

```text
POL-01 v2 được ưu tiên vì có version 2.0, ban hành 05/2026,
và ghi rõ "Thay thế phiên bản trước".
POL-01 v1 được giữ lại nhưng đánh dấu is_superseded=true.
```

Điều kiện đạt: có quyết định rõ bản nào là hiện hành, dựa trên version/date/evidence trong file, không dựa vào tên file đoán mò.

### 4. Rebuild KB

Chạy từ repo root:

```powershell
python -m kb build
```

Sau khi chạy, mở `kb/output/build_report.md` và kiểm tra:

```text
Số tài liệu đọc được
Số chunk tạo ra
Số chunk thuộc tài liệu đã bị thay thế
Số chunk thiếu metadata
Số chunk theo từng source file
```

Với bộ dữ liệu hiện tại, baseline đang là:

```text
Số tài liệu đọc được: 8
Số chunk tạo ra: 30
Số chunk thuộc tài liệu đã bị thay thế: 3
```

Điều kiện đạt: build không lỗi, số tài liệu đúng kỳ vọng, chunk có thể trace về `source_file` và `section`.

### 5. Kiểm tra thủ công một vài query quan trọng

Chạy tối thiểu các query sau:

```powershell
python -m kb query "Chính sách backup hiện hành giữ bản sao lưu bao lâu?"
python -m kb query "Khi gặp ERR ConnTimeout db-primary có nên restart service không?"
python -m kb query "payment-api restart không giải quyết được thì escalation thế nào?"
```

Kết quả mong đợi:

- Query backup phải ưu tiên `POL-01_chinh_sach_backup_v2.md`.
- Query `ERR ConnTimeout` phải trả về `FAQ-01_loi_thuong_gap.md`.
- Query restart/escalation phải có `SOP-01_khoi_dong_lai_dich_vu.md` và `SOP-02_quy_trinh_escalation.md` trong top results.

Điều kiện đạt: các source quan trọng xuất hiện trong top results; nếu không, kiểm tra lại chunking, metadata hoặc search terms.

### 6. Chạy eval regression

Chạy:

```powershell
python -m kb.evaluate
```

Sau đó mở `kb/output/eval_results.md`.

Điều kiện đạt với bộ eval hiện tại:

```text
Retrieval hit FAIL: 0
```

Case out-of-scope phải được kiểm tra thủ công: câu hỏi không có trong tài liệu thì trợ lý phải nói không có thông tin, không được bịa.

Nếu eval fail:

1. Xác định fail do retrieval thiếu source, metadata sai, ranking sai hay câu eval viết chưa rõ.
2. Sửa nguyên nhân nhỏ nhất có thể.
3. Chạy lại `python -m kb build` và `python -m kb.evaluate`.
4. Không release KB nếu version-trap fail hoặc nếu câu trả lời có nguy cơ dùng tài liệu superseded như bản hiện hành.

### 7. Review và release

Trước khi release hoặc commit, kiểm tra:

- Tài liệu mới/sửa đã nằm đúng thư mục.
- `chunks.jsonl` có chunk mới và metadata đúng.
- `build_report.md` không có metadata thiếu bất thường.
- `eval_results.md` không có retrieval fail.
- Với policy thay thế bản cũ, query version-trap trả về bản hiện hành.
- Nếu có thay đổi policy/SOP, document owner đã xác nhận.

Khi đạt, commit các file liên quan:

```powershell
git add Xbrain_Assessment_DE_DataPack/data/docs
git add kb
git add sop/kb_update_sop.md
git add README.md AI_WORKLOG.md
```

Commit message nên ghi rõ tài liệu nào thay đổi, KB đã rebuild, eval result và limitation nếu có.

## Tần suất

Chạy SOP này mỗi khi khách hàng gửi tài liệu mới hoặc sửa tài liệu cũ. Với production KB, nên review metadata và chạy lại eval định kỳ tối thiểu hằng tháng, ngay cả khi chưa có thay đổi tài liệu được báo.
