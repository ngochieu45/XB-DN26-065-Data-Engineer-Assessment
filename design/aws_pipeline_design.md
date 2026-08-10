# Thiết kế AWS cho pipeline log hằng ngày

## Mục tiêu

Triển khai pipeline log cục bộ thành một batch workflow chạy hằng ngày trên AWS. Thiết kế giữ log gốc không thay đổi để phục vụ audit, ghi dữ liệu sạch dạng Parquet, và cho phép khách hàng truy vấn báo cáo hằng ngày mà không cần vận hành một database riêng.

## Kiến trúc đề xuất

```text
Daily schedule
  -> EventBridge rule
  -> AWS Glue ETL job
  -> S3 processed Parquet
  -> Glue Data Catalog
  -> Athena queries / daily report
```

## Luồng dữ liệu

1. **Ingest log gốc vào S3 raw bucket**
   - Các file log ứng dụng được upload vào một raw S3 bucket riêng.
   - Với pipeline, raw bucket được xem là append-only: file nguồn không bị sửa hoặc ghi đè.
   - Tách raw và processed giúp audit, replay và điều tra sự cố an toàn hơn.

2. **Điều phối hằng ngày bằng EventBridge**
   - EventBridge rule trigger pipeline mỗi ngày một lần.
   - Rule khởi chạy AWS Glue ETL job theo lịch cố định sau thời điểm dự kiến log đã được gửi đủ.

3. **Làm sạch và transform bằng AWS Glue**
   - Glue job đọc các file JSONL từ raw bucket.
   - Job áp dụng cùng logic validation như pipeline cục bộ ở Phần A:
     - quarantine malformed JSON
     - reject bản ghi thiếu required fields
     - reject timestamp không hợp lệ
     - deduplicate `request_id` bị lặp
     - normalize timestamp có timezone về UTC
     - giữ optional `trace_id` là null khi thiếu
     - tạo `error_type`, `error_code` và message parameters ổn định
   - Clean records được ghi vào processed bucket dưới dạng Parquet.
   - Rejected records được ghi riêng kèm source file, line number, reason và nội dung gốc.

4. **Lưu trữ processed data và catalog**
   - Processed S3 bucket lưu clean Parquet files.
   - Dữ liệu nên được partition theo event date, ví dụ `event_date=YYYY-MM-DD`, để Athena chỉ scan ngày hoặc khoảng ngày cần query.
   - Glue Data Catalog lưu table schema và partition metadata cho cả clean dataset và rejected-record dataset.

5. **Truy vấn và báo cáo bằng Athena**
   - Athena query dữ liệu Parquet trong processed bucket thông qua Glue Data Catalog.
   - Cách này tránh phải load dữ liệu vào database riêng và phù hợp với workload phân tích tần suất thấp như báo cáo hằng ngày.
   - Bốn câu hỏi báo cáo của Phần A có thể được triển khai bằng saved Athena queries hoặc một report job nhỏ theo lịch.

6. **IAM và bảo mật**
   - Glue role có quyền đọc raw bucket và chỉ được ghi vào processed/rejected prefixes.
   - Athena/reporting role có quyền đọc processed data và query metadata thông qua Glue Data Catalog.
   - Reporting role không có quyền ghi vào raw bucket.
   - Quyền ghi raw bucket chỉ giới hạn cho ingestion producer.

7. **Monitoring**
   - CloudWatch thu thập Glue job logs và metrics.
   - CloudWatch alarms cảnh báo nếu Glue job fail, timeout hoặc không chạy đúng lịch.
   - Số lượng rejected records nên được theo dõi hằng ngày; nếu tăng đột biến thì đó là tín hiệu data-quality cần kiểm tra.

## Quyết định thiết kế chính

| Quyết định | Lý do |
| --- | --- |
| Tách raw và processed S3 buckets | Bảo vệ dữ liệu raw phục vụ audit và tránh transformation job vô tình ghi đè log gốc. |
| Dùng Parquet cho processed data | Giữ schema tốt, nén hiệu quả, và giảm chi phí scan của Athena so với CSV khi dữ liệu tăng. |
| EventBridge + Glue | Kiến trúc batch theo lịch đơn giản, không cần vận hành server. |
| Glue Data Catalog + Athena | Cho phép khách hàng query dữ liệu trên S3 trực tiếp mà không cần database riêng. |
| IAM roles theo least privilege | Giảm blast radius và ngăn reporting job/user sửa raw logs. |
| CloudWatch alarms | Giúp đội vận hành thấy ngay daily run bị fail hoặc chạy trễ. |

