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
`design/aws_pipeline.drawio`.

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

### Output & đánh giá

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
  khi fail/timeout, không claim quá mức nếu chưa có heartbeat kiểm tra missing
  schedule.
- IAM nên ghi ở mức role/least-privilege, không cần viết policy JSON chi tiết
  cho paper design.

### Verify & sửa

Em chỉnh lại thành kiến trúc hiện tại trong `design/aws_pipeline.drawio`:

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
