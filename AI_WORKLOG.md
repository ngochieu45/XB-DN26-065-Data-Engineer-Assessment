# AI_WORKLOG

## A1 - Ingest và validate log JSONL

### Việc

Xây dựng bước đọc `app_logs_7days.jsonl`, validate từng dòng, tách bản ghi sạch và bản ghi bị loại, đồng thời giữ bằng chứng truy vết về dòng nguồn.

### Phần em tự quan sát và quyết định trước khi dùng AI

Em kiểm tra dữ liệu thật và xác định các vấn đề cần xử lý trong pipeline:

- File có 2.923 dòng vật lý.
- Có dòng JSON lỗi, không thể parse an toàn.
- Có bản ghi parse được nhưng thiếu trường bắt buộc `level`.
- Có timestamp không hợp lệ như `not-a-date`.
- Có `request_id` bị lặp.
- Timestamp có nhiều offset timezone, gồm `Z` và `+07:00`.
- `trace_id` là trường tùy chọn, không xuất hiện ở mọi bản ghi.

Em chốt các quyết định xử lý:

- Không sửa file nguồn.
- Quarantine malformed JSON, missing required field và invalid timestamp.
- Không tự đoán hoặc gán mặc định `level`, vì điều đó làm sai báo cáo ERROR.
- Deduplicate theo `request_id`, giữ lần xuất hiện hợp lệ đầu tiên.
- Chuẩn hóa timestamp hợp lệ về UTC nhưng giữ `timestamp_raw` để truy vết.
- Giữ `trace_id` trong schema và điền null khi thiếu.
- Mỗi dòng đầu vào phải có đúng một kết quả chính: clean hoặc rejected/deduplicated.

### Prompt

> Tôi đã kiểm tra `app_logs_7days.jsonl` và chốt các vấn đề cùng cách xử lý ở trên. Hãy viết module Python ingest từng dòng JSONL, validate theo đúng thứ tự đã chốt, trả về clean records, rejected records và quality metrics. Không tự thêm quy tắc xử lý ngoài danh sách. Với mỗi record bị loại, giữ số dòng nguồn, lý do và nội dung gốc có thể kiểm toán. Với record hợp lệ, chuẩn hóa timestamp về UTC, giữ timestamp gốc, xử lý `trace_id` tùy chọn là null khi thiếu và tạo các trường phục vụ phân tích lỗi. Thêm test cho JSON lỗi, thiếu field, timestamp không hợp lệ, duplicate request_id, timezone và trace_id tùy chọn.

### Output và đánh giá

AI tạo module `pipeline/processing.py` với các hàm nhỏ để parse timestamp, nhận diện error type, trích parameter, ghi rejection và chạy luồng `process_jsonl`. AI cũng tạo cấu trúc kết quả gồm clean records, rejected records và quality metrics.

Kết quả phù hợp với quyết định em đã đưa ra vì AI không tự gán mặc định cho `level`, không sửa input, giữ dòng nguồn cho bản ghi bị loại và chuẩn hóa timezone theo hướng có thể truy vết. Điểm cần ghi rõ trong bài là giả định `request_id` đại diện cho event duy nhất; giả định này đúng với bộ dữ liệu POC nhưng cần xác nhận thêm nếu đưa vào production.

### Verify và sửa

Em chạy pipeline và đối chiếu `pipeline/output/data_quality_report.json`:

- `total_lines`: 2.923
- `clean_records`: 2.839
- `rejected_records`: 84
- `malformed_json`: 18
- `missing_required_field`: 18
- `invalid_timestamp`: 20
- `duplicate_request_id`: 28

Phương trình đối soát khớp:

```text
2.839 clean records + 84 rejected/deduplicated records = 2.923 input lines
```

Em kiểm tra thêm `rejected_records.jsonl` để xác nhận record bị loại có `line_number`, `reason` và nội dung gốc.

---

## A2 - Transform và lưu trữ dataset sạch

### Việc

Chuẩn hóa schema của clean dataset và ghi ra file lưu trữ phục vụ phân tích downstream.

### Phần em tự quyết định trước khi dùng AI

Em chọn lưu clean dataset dưới dạng Parquet vì:

- Parquet giữ schema và kiểu dữ liệu tốt hơn CSV, đặc biệt với timestamp.
- Đọc cột phục vụ phân tích hiệu quả hơn.
- Phù hợp với hướng data lake/Athena nếu pipeline được triển khai lên AWS sau này.

Schema sạch cần có:

- `timestamp_raw`
- `timestamp`
- `event_date`
- `service`
- `level`
- `message`
- `request_id`
- `trace_id`
- `error_type`
- `error_code`
- `message_parameters`
- `source_line_number`

Rejected records vẫn lưu JSONL vì cần giữ cấu trúc record gốc và tiện replay/correction.

### Prompt

> Tôi đã chọn lưu clean dataset bằng Parquet với schema đã chốt. Hãy viết code Python transform dataframe/list record hiện có sang schema chuẩn hóa này và ghi ra `clean_logs.parquet`. Rejected records ghi ra JSONL, giữ lý do loại và dòng nguồn. Không bàn lại lựa chọn format; chỉ viết code đúng quyết định trên, có thể đọc lại output để verify số dòng và schema.

### Output và đánh giá

AI cập nhật luồng ghi output để tạo:

- `pipeline/output/clean_logs.parquet`
- `pipeline/output/rejected_records.jsonl`
- `pipeline/output/data_quality_report.json`

Output đúng hướng vì clean dataset được tách khỏi raw input, rejected records vẫn giữ bằng chứng, và schema phân tích có thêm các trường chuẩn hóa mà không ghi đè message gốc.

### Verify và sửa

Em đọc lại output và đối chiếu:

- `clean_logs.parquet` có 2.839 records.
- `rejected_records.jsonl` có 84 records bị loại hoặc deduplicate.
- `data_quality_report.json` ghi rõ policy, counts, rejected reason, transformations, schema variants và observed fields.
- Số timestamp offset được chuẩn hóa về UTC là 588.
- Số record thiếu optional `trace_id` được điền null là 1.674.


---

## A3 - Báo cáo 4 câu hỏi phân tích

### Việc

Tạo báo cáo trả lời bốn câu hỏi của khách hàng từ clean dataset: service lỗi nhiều nhất, lỗi theo ngày và ngày bất thường, top 3 error type, số record bị loại hoặc được chuẩn hóa.

### Phần em tự quyết định trước khi dùng AI

Em chốt logic tính trước khi yêu cầu AI viết code:

- Chỉ tính báo cáo từ clean dataset, không dùng raw file.
- Service nhiều lỗi nhất: lọc `level == "ERROR"`, group theo `service`, count và sort giảm dần.
- Lỗi theo ngày: group ERROR records theo `event_date` UTC.
- Ngày bất thường: dùng IQR rule, high anomaly nếu count > `Q3 + 1.5 * IQR`.
- Top 3 error type: nhóm theo `error_type` đã chuẩn hóa, không để tham số động như `txn`, `uid`, `code` làm phân mảnh nhóm lỗi.
- Số record bị loại/sửa: dùng quality metrics và rejected reason từ bước A1, đồng thời hiển thị transformation count cho timestamp và trace_id.

### Prompt

> Dataset sạch đã có schema như trên. Hãy viết tầng reporting bằng pandas để tạo 4 báo cáo riêng theo đúng logic tôi đã chốt: ERROR by service, ERROR by UTC date và anomaly theo IQR, top 3 normalized error types, số record rejected/deduplicated và số transformation normalization. Không đổi cách tính. Không hardcode số liệu. Ghi CSV/JSON/Markdown deterministic để tôi đối chiếu lại bằng mắt và bằng phép group độc lập.

### Output và đánh giá

AI tạo `pipeline/reporting.py` và báo cáo Markdown/CSV/JSON trong `pipeline/output/`. Kết quả ban đầu trả lời tốt ba câu hỏi đầu, nhưng phần câu hỏi thứ tư mới liệt kê rejection/deduplication và chưa hiển thị rõ số lượng normalization như timestamp offset và `trace_id` thiếu.

Em đánh giá đây là thiếu sót vì câu hỏi yêu cầu số bản ghi bị loại hoặc sửa trong quá trình làm sạch. Chỉ mô tả normalization bằng chữ là chưa đủ.

### Verify và sửa

Em yêu cầu cập nhật báo cáo để thêm bảng normalization. Sau khi chạy lại pipeline, `pipeline/output/analysis_report.md` trả lời đầy đủ:

- Service nhiều ERROR nhất: `payment-api` với 139 records.
- Ngày bất thường: `2026-07-30` với 140 ERROR records.
- Top 3 error type:
  - `ConnTimeout`: 114, `payment-api`
  - `HTTP 502`: 41, `web-portal`
  - `NullPointer`: 37, `batch-report`
- Records bị rejected/deduplicated: 84.
- Transformations trên accepted records:
  - `missing_optional_trace_id_filled_null`: 1.674
  - `timezone_offset_normalized_to_utc`: 588

Em cũng ghi rõ rằng transformation counts là operation counts và có thể overlap trên cùng một accepted record.

---

## A4 - Thiết kế AWS cho pipeline hằng ngày

### Việc

Tạo thiết kế AWS trên giấy cho pipeline chạy hằng ngày, sau đó kiểm tra và
chỉnh lại bản đề xuất để khớp với kiến trúc cuối cùng trong
`design/AWS_pipeline.drawio`.

### Phần em tự quyết định trước khi dùng AI

Trước khi dùng AI, em xác định pipeline cần giữ các nguyên tắc sau:

- Raw logs phải được giữ nguyên để audit.
- Clean data nên lưu dạng Parquet để Athena query hiệu quả hơn CSV.
- Pipeline chạy hằng ngày, không cần realtime streaming.
- Thiết kế nên đơn giản, dùng managed services và không vận hành database riêng.
- IAM phải theo least privilege; reporting không được ghi vào raw logs.
- Monitoring cần phát hiện Glue job fail hoặc timeout.

### Prompt

> Tôi muốn triển khai pipeline log cục bộ lên AWS để khách hàng có thể chạy
> hằng ngày. Yêu cầu: raw logs phải giữ nguyên để audit; clean data lưu Parquet;
> pipeline chạy theo lịch hằng ngày; dùng Athena cho báo cáo tần suất thấp;
> IAM least privilege; có monitoring cho job fail/timeout.
>
> Hãy đề xuất một kiến trúc AWS đơn giản cho use case này, nêu service nào dùng
> cho bước nào và dữ liệu chảy ra sao. Sau đó viết phần giải thích ngắn gọn để
> tôi kiểm tra lại, chỉnh các điểm chưa ổn và chuyển thành sơ đồ nộp bài.

### Kết quả và đánh giá

AI đề xuất kiến trúc batch gồm S3 raw/processed, EventBridge, Glue ETL,
Glue Data Catalog, Athena, IAM và CloudWatch. Đề xuất này phù hợp với hướng
em cần vì không thêm database riêng và dùng Athena trực tiếp trên S3 cho báo
cáo hằng ngày.

Sau khi kiểm tra, em thấy một số điểm cần chỉnh trước khi chấp nhận:

- Không thêm VPC vì pipeline này chỉ dùng S3, Glue, Catalog và Athena; chưa có
  nguồn private cần truy cập trong VPC.
- `Rejected record prefix` phải là output riêng từ Glue, không chỉ là label
  trên đường ghi clean Parquet.
- Athena chỉ query `Processed (parquet)` cho báo cáo chính; rejected records
  được giữ riêng để audit/data-quality review.
- CloudWatch nên được mô tả là monitor Glue job logs/status/runtime và alert
  khi fail/timeout.
- IAM nên ghi ở mức role/least-privilege, không cần viết policy JSON chi tiết
  cho paper design.

### Kiểm chứng và sửa

Em chỉnh lại thành kiến trúc hiện tại trong `design/AWS_pipeline.drawio`:

- `Logs source` upload vào `Raw logs bucket`.
- `Daily schedule` trigger `Glue ETL job`.
- `Glue ETL job` đọc raw logs, ghi clean records vào `Processed (parquet)`,
  và ghi invalid records vào `Rejected record prefix`.
- `Glue data catalog` giữ schema/partition metadata.
- `Amazon Athena Daily report` query clean Parquet thông qua Catalog.
- `Amazon CloudWatch` theo dõi Glue job.
- `AWS IAM least privilege` cấp quyền cho Glue và Athena/reporting.

Em xác nhận đây chỉ là paper design theo yêu cầu đề bài, không claim rằng hạ
tầng AWS đã được deploy. Em cũng kiểm tra file `.drawio` parse được XML hợp lệ.

---

## B1 - Thiết kế chunking, metadata và index cho KB

### Việc

Thiết kế Mini Knowledge Base từ 8 tài liệu vận hành trong `Xbrain_Assessment_DE_DataPack/data/docs/`.

### Phần em tự quyết định trước khi dùng AI

Em chốt giả thuyết ban đầu:

- Chunking nên đi theo cấu trúc heading/section vì tài liệu là SOP, policy, FAQ, guide và runbook.
- Metadata phải giữ được nguồn, section, version/date, owner và trạng thái superseded để xử lý freshness.
- Index nên chạy local bằng SQLite FTS5 vì POC nhỏ, dễ chạy lại và dễ giải thích hơn embeddings/service ngoài.

### Prompt

> Tôi đang làm Phần B - Mini Knowledge Base cho 8 tài liệu vận hành. Tôi đang nghiêng về structure-based chunking theo heading/section, metadata gồm source/version/date/owner/is_superseded, và SQLite FTS5 cho search local. Hãy phản biện giả thuyết này, nêu trade-off với fixed-size chunking và embeddings, chỉ ra rủi ro cần verify. Không chốt quyết định thay tôi.

### Output và đánh giá

AI đồng ý structure-based chunking là hướng hợp lý cho tài liệu có heading rõ, nhưng nhắc rủi ro chunk không đều và retrieval multi-source có thể thiếu nguồn nếu top-k bị một file chiếm hết. AI cũng đề xuất metadata version/date để xử lý tài liệu bị thay thế.

Em giữ hướng SQLite FTS5 vì đúng phạm vi POC local. Em không dùng embeddings vì bộ tài liệu nhỏ, đề bài chấm lý do chọn quan trọng hơn công cụ, và local FTS giúp người chấm chạy lại không cần API key.

### Verify và sửa

Em đối chiếu với `reading/01_chunking_basics.md`: tài liệu nói structure-based phù hợp với SOP/chính sách vì giữ trọn ngữ nghĩa từng mục. Sau khi build thật, `kb/output/build_report.md` cho thấy:

- Số tài liệu đọc được: 8
- Số chunk tạo ra: 30
- Superseded chunks: 3

Em kiểm tra `kb/output/chunks.jsonl` và thấy mỗi chunk có `source_file`, `section`, `version`, `issued_or_updated_date`, `owner`, `is_superseded`.

---

## B2 - Build KB bằng code theo thiết kế đã chọn

### Việc

Viết code build chunks, metadata, SQLite FTS5 index và query CLI trong thư mục `kb/`.

### Prompt

> Tôi đã quyết định thiết kế KB: input docs ở `Xbrain_Assessment_DE_DataPack/data/docs/`, chunk theo heading/section, metadata gồm source_file/doc_id/title/section/version/issued_or_updated_date/owner/is_superseded, index bằng SQLite FTS5. Hãy viết code Python trong `kb/` để build đúng thiết kế, tạo `chunks.jsonl`, `kb.sqlite`, `build_report.md`, CLI query top-k và smoke tests. Không tự đổi schema hoặc bịa metadata thiếu.

### Output và đánh giá

AI tạo code build/query/test. Lần chạy đầu có lỗi thật: `chunk_id` bị trùng giữa `POL-01` v1 và v2 vì code dùng chung `doc_id` cho cả hai version. Đây là lỗi nghiêm trọng vì KB cần giữ cả bản cũ để audit nhưng vẫn phân biệt được version.

AI cũng chưa xử lý tốt việc đóng SQLite connection trên Windows; unit test logic gần như đúng nhưng fail khi dọn temp directory vì file `kb.sqlite` còn bị lock.

### Verify và sửa

Em chạy `python -m kb build` và `python -m unittest discover -s kb/tests -v`, phát hiện lỗi thay vì chỉ đọc code. Em sửa:

- `chunk_id` dùng source file stem + section index để không trùng giữa v1/v2.
- SQLite connection được đóng rõ bằng `finally`.
- Query result được materialize thành `dict` trước khi đóng connection.

Sau khi sửa, test KB chạy OK:

```text
Ran 4 tests
OK
```

---

## B3 - Xử lý mâu thuẫn tài liệu POL-01 v1/v2

### Việc

Tìm và xử lý cặp tài liệu mâu thuẫn để KB trả lời theo bản hiện hành.

### Prompt

> Tôi đã thấy conflict candidate giữa `POL-01_chinh_sach_backup_v1.md` và `POL-01_chinh_sach_backup_v2.md`. Hãy lập bảng kiểm chứng các điểm khác nhau, metadata giúp chọn bản đúng, rule đề xuất cho KB và query test để bắt lỗi nếu KB trả lời theo bản cũ. Không tự kết luận nếu không có evidence từ file.

### Output và đánh giá

AI chỉ ra các điểm khác nhau: giờ backup, retention, nơi lưu backup và quyền restore. AI đề xuất ưu tiên version mới khi có metadata rõ ràng.

Em chấp nhận hướng này vì có evidence trong file, không phải vì AI tự kết luận.

### Verify và sửa

Em đối chiếu trực tiếp hai file nguồn:

- v1: backup 22:00, retention 7 ngày, lưu server nội bộ, restore không cần phê duyệt.
- v2: backup 23:30, retention 30 ngày, lưu cloud mã hóa, restore cần Trưởng phòng Vận hành phê duyệt.
- v2 ghi `Phiên bản 2.0`, `Ban hành: 05/2026`, `Thay thế phiên bản trước`.

Em quyết định giữ v1 cho audit nhưng đánh dấu chunks của v1 là `is_superseded=true`; search ưu tiên bản chưa superseded. Eval Q01 dùng version-trap để verify KB không trả lời theo v1.

---

## B4 - Bộ eval 10 câu cho KB

### Việc

Tạo bộ eval 10 câu gồm direct lookup, multi-source, version-trap và out-of-scope.

### Prompt

> Tôi đã chốt sơ bộ 3 câu eval: một câu version-trap cho POL-01 v1/v2, một câu direct lookup cho `ERR ConnTimeout db-primary`, và một câu multi-source cho payment-api restart/escalation. Hãy đề xuất thêm 7 câu để đủ 10 câu theo `reading/02_rag_eval_basics.md`. Mỗi câu phải có expected source, expected answer bullets, retrieval hit criterion, groundedness criterion và PASS/FAIL rule. Không chốt bộ eval cuối thay tôi.

### Output và đánh giá

AI đề xuất thêm các câu về monitoring threshold, batch-report schedule, access policy, HTTP 502, NullPointer ReportBuilder, out-of-scope HR policy và restart `payment-api`.

Em giữ các câu có nguồn rõ và bỏ/sửa wording nếu câu hỏi dễ khiến expected source không rõ. Bộ cuối nằm trong `kb/eval_questions.json`.

### Verify và sửa

Em đối chiếu từng expected answer với tài liệu nguồn và chạy `python -m kb.evaluate`. Kết quả hiện tại trong `kb/output/eval_results.md`:

- Cases run: 10
- Số case kiểm tra retrieval: 9
- Retrieval hit PASS: 9
- Retrieval hit FAIL: 0
- Manual out-of-scope checks: 1

Em giữ out-of-scope là manual check vì câu đúng không phải retrieval trúng một tài liệu, mà là trợ lý phải nói không có thông tin và không bịa chính sách HR.

---

## B5 - Debug eval và retrieval

### Việc

Kiểm tra kết quả chạy eval thật và sửa lỗi retrieval thay vì chỉ ghi pass/fail.

### Prompt

> Tôi đã chạy eval thật. Đây là output case fail: câu multi-source về payment-api restart/escalation chỉ retrieve được SOP-01, FAQ/RUN nhưng thiếu SOP-02 trong top-k. Hãy phân tích nguyên nhân có thể là chunking, tokenization, ranking hay eval query. Chỉ dùng output tôi dán, không tự tưởng tượng kết quả.

### Output và đánh giá

AI gợi ý xem lại tokenization và ranking. Khi kiểm tra output thật, em phát hiện hai vấn đề:

- Query tiếng Việt có dấu bị tách thành token ngắn ở một số trường hợp, làm search nhiễu.
- Query builder giới hạn 12 token đầu nên từ quan trọng `escalate` bị cắt mất.
- Top-k có thể bị nhiều chunk từ cùng một source chiếm chỗ, không tốt cho câu multi-source.

### Verify và sửa

Em sửa search theo ba hướng có thể giải thích được:

- Index thêm bản text normalized không dấu bên cạnh text gốc.
- Bỏ giới hạn 12 token và lọc stopword nhẹ.
- Thêm expansion hẹp cho `restart` và `escalate/escalation`.
- Đa dạng hóa top results theo `source_file` để hỗ trợ câu multi-source.

Sau khi chạy lại:

```text
python -m kb build
python -m kb.evaluate
python -m unittest discover -s kb/tests -v
```

Kết quả:

- `python -m kb.evaluate`: `Eval retrieval hit: 9/9; manual checks: 1`
- Unit tests: `Ran 4 tests - OK`

---

## B6 - SOP cập nhật KB

### Việc

Viết SOP ngắn cho quy trình cập nhật KB khi khách gửi tài liệu mới hoặc sửa tài liệu cũ.

### Prompt

> Tôi cần viết SOP cập nhật KB tối đa 1 trang. Thiết kế hiện tại: docs nằm trong `data/docs`, KB build ra chunks/index trong `kb/`, metadata quan trọng gồm source/section/version/date/owner/is_superseded, conflict quan trọng là POL-01 v1/v2, eval phải chạy lại khi tài liệu thay đổi. Hãy đề xuất SOP gồm nhận tài liệu, kiểm tra metadata, phát hiện superseded/conflict, rebuild index, chạy eval regression, review/approval và changelog. Không làm SOP quá nặng so với POC.

### Output và đánh giá

AI đề xuất SOP theo các bước nhận tài liệu, kiểm tra metadata, rebuild, eval regression và approval. Bản đầu tiên đúng hướng kiểm soát rủi ro nhưng còn giống checklist, chưa đủ cụ thể để một người khác làm theo từng bước cập nhật KB.

### Verify và sửa

Em review lại và quyết định sửa SOP thành quy trình thao tác cụ thể hơn trong `sop/kb_update_sop.md`. Bản cuối có:

- Trigger khi khách gửi tài liệu mới hoặc sửa tài liệu cũ.
- Bước lưu file và không ghi đè policy cũ cần audit.
- Checklist metadata trước khi build.
- Rule xử lý conflict/superseded document.
- Command rebuild KB và command chạy eval.
- Các query thủ công cần kiểm tra.
- Điều kiện pass/fail và cách xử lý nếu eval fail.
- Checklist release/commit.

Em kiểm tra SOP có xử lý đủ bốn rủi ro đã thấy trong KB:

- Metadata thiếu version/date.
- Tài liệu bị superseded.
- Index cũ sau khi tài liệu đổi.
- Eval regression fail, đặc biệt version-trap POL-01.

---

## B7 - Cập nhật README cho Phần B

### Việc

Cập nhật `README.md` để người chấm biết cách chạy KB, xem output, hiểu quyết định thiết kế và kết quả eval.

### Prompt

> Tôi đã build xong Phần B với code trong `kb/`, SOP trong `sop/`, output thật gồm `build_report.md` và `eval_results.md`. Hãy giúp tôi cập nhật README tiếng Anh cho đúng yêu cầu đề: tổng quan repo, cách chạy KB, quyết định chunking/metadata/index, conflict POL-01 v1/v2, kết quả eval và đường dẫn SOP. Không tự thêm claim chưa có output kiểm chứng.

### Output và đánh giá

AI hỗ trợ biên tập phần README cho Phần B, gồm command chạy KB, bảng quyết định thiết kế, output sinh ra và kết quả eval. Em đánh giá phần này hữu ích để README dễ đọc hơn, nhưng các con số trong README không được lấy theo suy đoán.

### Verify và sửa

Em đối chiếu README với output thật:

- `kb/output/build_report.md`: 8 docs, 30 chunks, 3 superseded chunks.
- `kb/output/eval_results.md`: 10 cases, 9 retrieval cases pass, 1 out-of-scope manual check.
- `kb/eval_questions.json`: có đủ direct lookup, multi-source, version-trap và out-of-scope.
- `sop/kb_update_sop.md`: tồn tại và đúng phạm vi SOP cập nhật KB.

Em chỉ giữ các claim khớp với file output thật và sửa tên diagram trong README thành `design/AWS_pipeline.drawio` để khớp file hiện có.

---

## Bài 2 - Task A: Review câu trả lời AI

### Việc

Review sáu nhận định kỹ thuật sai hoặc gây hiểu nhầm về AWS, data pipeline và knowledge base. Bài review cần chỉ ra vấn đề, đề xuất cách sửa dễ trình bày và dẫn nguồn kiểm chứng phù hợp.

### Phần em tự quyết định trước khi dùng AI

Từ kiến thức đã học trong chương trình XBrain và các tài liệu `reading/` được cung cấp cùng đề, em tự chỉ ra sáu nhận định có dấu hiệu sai hoặc gây hiểu nhầm. Em cũng tự đề xuất hướng sửa ban đầu và quyết định trình bày từng nhận định theo ba mục `Sai`, `Sửa` và `Nguồn`. Sau đó em mới dùng AI để phản biện kết luận của mình và tìm tài liệu chính thống của AWS nhằm xác nhận các thông tin liên quan đến dịch vụ AWS.

### Prompt

> Dựa trên quá trình học tại XBrain và tài liệu `reading/` được cung cấp trong đề, tôi đã xác định sáu nhận định sau là sai hoặc gây hiểu nhầm: S3 Standard-IA luôn là lựa chọn mặc định rẻ nhất; Glue đọc RDS production mỗi 5 phút là pattern chuẩn; Parquet là row-based; Lambda phù hợp với transform 30-45 phút; chunk cố định 4.000 token luôn tốt nhất; và KB không cần version vì có thể ghi đè bằng bản mới nhất. Hãy phản biện từng kết luận của tôi, không mặc định rằng tôi đúng. Với các nhận định về AWS, hãy xác nhận bằng AWS documentation chính thống và chỉ rõ nguồn nào hỗ trợ kết luận. Với chunking và versioning, hãy đối chiếu thêm tài liệu `reading/` của đề. Trình bày kết quả theo format `Sai`, `Sửa`, `Nguồn`; không dùng `data/docs/` làm căn cứ.

### Output và đánh giá

AI xác nhận phần lớn các lỗi em đã chỉ ra và cung cấp tài liệu AWS chính thống về S3 storage class, Glue, Parquet/Athena, giới hạn thời gian chạy của Lambda và các chiến lược chunking của Amazon Bedrock. AI đồng thời giúp diễn đạt lại hướng sửa theo workload và trade-off. Tuy nhiên, ở nhận định về Glue đọc RDS, nguồn AI đưa ra ban đầu chỉ chứng minh Glue có thể kết nối JDBC hoặc được lập lịch, chưa chứng minh đây là một pattern chuẩn cho near-real-time. Vì vậy em không chấp nhận kết luận đó chỉ dựa trên câu trả lời của AI.

### Verify và sửa

Em mở từng liên kết AWS mà AI cung cấp để kiểm tra tài liệu có thực sự hỗ trợ kết luận hay không, đồng thời đối chiếu lại các nhận định về chunking và versioning với tài liệu của đề. Với nhận định Glue đọc RDS, em loại bỏ nguồn không đủ liên quan và giữ kết luận của mình: use case log hằng ngày phù hợp với S3 raw và Glue chạy daily batch; nếu cần near-real-time thì phải đánh giá riêng nguồn dữ liệu, tải lên production và phương án CDC hoặc streaming. Em cũng sửa các từ tuyệt đối như “rẻ nhất”, “pattern chuẩn” và “luôn tốt nhất” thành quyết định có điều kiện theo access pattern và workload. Quyết định cuối cùng thuộc về em; AI chỉ hỗ trợ phản biện, xác nhận nguồn và biên tập. Kết quả được lưu tại `ai_proficiency/task_a_ai_answer_review.md`.

---

## Bài 2 - Task B: Thiết kế và đánh giá prompt trích xuất log

### Việc

Thiết kế prompt chuyển `message` trong log thành JSON có cấu trúc, tạo năm test case kèm expected output và mô tả cách đánh giá độ chính xác, hallucination và trường hợp cần người kiểm tra.

### Phần em tự quyết định trước khi dùng AI

Em quyết định không chấp nhận prompt chỉ dựa trên vài ví dụ riêng lẻ. Prompt cuối phải có schema cố định, pattern tổng quát, thứ tự ưu tiên khi nhiều rule cùng khớp, quy tắc kiểu dữ liệu, `extra_parameters` để giữ key mới và cách xử lý input hỏng. Sau khi thử trên ChatGPT và Claude, em quyết định bỏ `confidence` vì hai model có thể gán điểm khác nhau nhưng prompt không có cơ sở hiệu chỉnh để chứng minh điểm đó phản ánh độ chính xác.

### Prompt

> Tôi cần hoàn thành Task B: thiết kế prompt trích xuất log thành JSON, đưa ra năm input/output mẫu và kế hoạch đánh giá. Tôi đang nghiêng về schema cố định và rule theo pattern tổng quát thay vì lookup theo ví dụ. Hãy phản biện thiết kế này dựa trên các message thật trong `app_logs_7days.jsonl`: kiểm tra độ bao phủ category, ranh giới `event_name`, precedence, key mapping, kiểu dữ liệu, tiêu chí `parsed`/`partial`, input JSON hỏng và nguy cơ bịa dữ liệu. Sau đó đề xuất cách đánh giá theo từng field, exact match, schema validity, confusion matrix, provenance check, test đối nghịch và human review. Mọi đề xuất phải chỉ rõ cách em có thể kiểm chứng bằng dữ liệu, test case hoặc tài liệu tham khảo.

### Output và đánh giá

AI tạo bản prompt ban đầu nhưng các category rule còn giống danh sách ví dụ và bỏ sót nhiều pattern thật, gồm `Request completed`, `Payment processed`, `Balance check ok`, `Slow login` và `Queue depth high`. Em đối chiếu các message shape trong data pack và chỉ ra nhóm chưa được bao phủ chiếm tỷ lệ đáng kể, nên không dùng nguyên bản trả lời đó. Phần đánh giá B3 ban đầu cũng còn mơ hồ; em yêu cầu viết lại thành các phép kiểm tra có đầu vào, cách tính và điều kiện đưa bản ghi cho người review.

### Verify và sửa

Em sửa prompt để các ví dụ chỉ minh họa cho pattern tổng quát, thêm precedence và rule rõ ràng cho các shape bị thiếu. Năm message trong bộ test cuối được đối chiếu với file log thật; các expected output được parse lại để bảo đảm là JSON hợp lệ và đúng kiểu dữ liệu. Em dùng kết quả chạy thử trên cả ChatGPT và Claude như một kiểm tra chéo: hai model cho kết quả khác nhau với `ConnTimeout`, và cả hai đều bỏ sót thời gian `30s`, cho thấy cần golden set và kiểm tra theo từng field thay vì chỉ nhìn JSON có vẻ hợp lý. Em giữ `message_raw`, dùng provenance/type-cast check để phát hiện giá trị không có căn cứ, review toàn bộ `partial`/`unknown` và chạy regression test khi prompt thay đổi. Kết quả cuối được lưu tại `ai_proficiency/task_b_message_extraction_prompt.md`; các nguồn phương pháp đánh giá được ghi trực tiếp trong file này.
