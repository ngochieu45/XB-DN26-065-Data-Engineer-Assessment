# Task A - Review câu trả lời AI

Từ kiến thức học tại XBrain và tài liệu `reading/` của đề, em xác định sáu nhận định sau là sai hoặc gây hiểu nhầm. Em dùng AI để phản biện, tìm nguồn chính thống, sau đó tự mở nguồn và chốt nội dung review.

## 1. "S3 Standard-IA là lựa chọn mặc định rẻ nhất"

**Sai:** Standard-IA dành cho dữ liệu ít truy cập, có minimum storage duration 30 ngày, minimum billable object size 128 KB và phí retrieval. Vì vậy không thể mặc định đây là lựa chọn rẻ nhất, nhất là với raw log mới còn được ETL hoặc replay.

**Sửa:** Chọn storage class theo access pattern. Raw log mới có thể dùng S3 Standard; khi dữ liệu cũ và ít truy cập, dùng Lifecycle chuyển sang IA.

**Nguồn:** [AWS S3 Storage Classes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-class-intro.html), [AWS S3 Pricing](https://aws.amazon.com/s3/pricing/).

## 2. "Glue đọc RDS production mỗi 5 phút là pattern chuẩn"

**Sai:** Glue có thể kết nối RDS qua JDBC và chạy theo lịch, nhưng khả năng kỹ thuật đó không chứng minh polling production DB mỗi 5 phút là pattern chuẩn. Nó cũng không phù hợp requirement log hằng ngày của bài.

**Sửa:** Với use case này, log được đưa vào S3 raw và Glue xử lý daily batch. Nếu cần near-real-time, phải đánh giá riêng nguồn dữ liệu, tải production và cơ chế CDC/streaming thay vì mặc định polling.

**Nguồn:** [AWS Glue JDBC](https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-connect-jdbc-home.html), [AWS Glue Schedules](https://docs.aws.amazon.com/glue/latest/dg/monitor-data-warehouse-schedule.html), [Amazon EventBridge Scheduler](https://docs.aws.amazon.com/eventbridge/latest/userguide/using-eventbridge-scheduler.html).

## 3. "Parquet là row-based"

**Sai:** Parquet là column-oriented format. Với analytical query, Athena có thể chỉ đọc các cột cần thiết thay vì quét toàn bộ dữ liệu như định dạng theo hàng.

**Sửa:** Parquet là format lưu theo cột, nén tốt và phù hợp cho workload phân tích vì giúp giảm dữ liệu cần đọc.

**Nguồn:** [AWS Athena - Columnar storage](https://docs.aws.amazon.com/athena/latest/ug/columnar-storage.html).

## 4. "Transform 30-45 phút nên dùng Lambda"

**Sai:** Một Lambda invocation có timeout tối đa 15 phút, nên không phù hợp ETL dự kiến chạy 30-45 phút.

**Sửa:** Dùng AWS Glue cho ETL dài hoặc nặng hơn; Lambda phù hợp với tác vụ ngắn như validation nhẹ, trigger hoặc orchestration.

**Nguồn:** [AWS Lambda timeout](https://docs.aws.amazon.com/lambda/latest/dg/configuration-timeout.html), [AWS Glue](https://docs.aws.amazon.com/glue/), kinh nghiệm thực hành Lambda tại XBrain.

## 5. "Chunk cố định 4.000 token luôn tốt nhất"

**Sai:** Không có kích thước chunk tốt nhất cho mọi tài liệu. Chunk quá nhỏ mất ngữ cảnh; chunk quá lớn làm retrieval kém chính xác. Bedrock cũng hỗ trợ nhiều chiến lược thay vì một kích thước bắt buộc.

**Sửa:** Chọn chunking theo cấu trúc tài liệu và retrieval requirement, sau đó kiểm chứng bằng eval. Với SOP/policy có heading rõ, structure-based chunking phù hợp hơn một mức 4.000 token cố định.

**Nguồn:** `Xbrain_Assessment_DE_DataPack/reading/01_chunking_basics.md`, [Amazon Bedrock chunking](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-chunking.html).

## 6. "Không cần version, cứ ghi đè bản cũ"

**Sai:** Ghi đè làm mất traceability và không bảo đảm file mới nhất là bản đã được xác nhận có hiệu lực. Điều này đặc biệt nguy hiểm khi các policy mâu thuẫn.

**Sửa:** Lưu `version`, ngày hiệu lực/cập nhật, `owner` và `is_superseded`; giữ bản cũ để audit nhưng chỉ ưu tiên bản được xác nhận hiện hành khi retrieval. Bộ eval cần có version-trap để phát hiện trả lời theo bản cũ.

**Nguồn:** `Xbrain_Assessment_DE_DataPack/reading/01_chunking_basics.md`, `Xbrain_Assessment_DE_DataPack/reading/02_rag_eval_basics.md`.
