# Task A - Review câu trả lời AI

Một trợ lý AI được hỏi: "Thiết kế pipeline trên AWS thu log hằng ngày từ hệ thống của khách vào data lake, và tổ chức knowledge base cho RAG." Nó trả lời như sau:
Bạn nên lưu toàn bộ log vào S3 Standard-IA vì đây là lựa chọn mặc định rẻ nhất cho data lake. Để thu dữ liệu, cấu hình một Glue job đọc trực tiếp từ database RDS production của khách mỗi 5 phút — đây là pattern chuẩn cho near-real-time. Dữ liệu nên chuyển sang Parquet, một format lưu theo hàng (row-based) nên ghi rất nhanh, phù hợp cho analytics. Với các bước transform nặng chạy khoảng 30–45 phút, dùng AWS Lambda là phù hợp nhất vì không phải quản lý server. Về knowledge base cho RAG, hãy chia tài liệu thành các chunk cố định 4.000 token — kích thước này luôn tốt nhất cho mọi loại tài liệu. Cuối cùng, không cần đánh version cho knowledge base, vì bản mới nhất luôn là bản đúng — cứ ghi đè là được.


## 1. "S3 Standard-IA là lựa chọn mặc định rẻ nhất cho data lake"

**Sai:** Standard-IA được thiết kế cho dữ liệu ít truy cập, có minimum storage duration 30 ngày, minimum billable object size 128 KB và chi phí truy xuất riêng. Vì vậy không thể kết luận Standard-IA luôn là lựa chọn rẻ nhất cho data lake, đặc biệt với raw logs mới ingest còn cần đọc lại để ETL, audit hoặc replay.

**Sửa:** Chọn storage class dựa trên access pattern. Với raw logs mới ingest và còn được xử lý thường xuyên, bắt đầu bằng S3 Standard; sau đó dùng Lifecycle chuyển sang IA khi dữ liệu đã cũ và ít truy cập hơn.

**Nguồn:** AWS S3 storage classes; AWS S3 pricing.

## 2. "Glue đọc trực tiếp RDS production mỗi 5 phút là pattern chuẩn cho near-real-time"

**Sai:** AWS Glue có thể kết nối JDBC tới RDS và Glue job có thể được schedule; AWS docs cũng nêu schedule có độ chính xác tối thiểu 5 phút. Nhưng khả năng kỹ thuật này không có nghĩa polling production RDS mỗi 5 phút là "pattern chuẩn" cho mọi near-real-time workload. Với requirement hiện tại là log hằng ngày, thiết kế polling RDS 5 phút không khớp bài toán.

**Sửa:** Với yêu cầu hiện tại, nên làm batch hằng ngày: hệ thống đẩy log vào S3 raw, rồi Glue chạy theo lịch để xử lý. Nếu khách muốn gần realtime, đó là một bài toán khác và cần xác nhận lại nguồn dữ liệu, tần suất đọc, ảnh hưởng tới production và cơ chế ingestion phù hợp; không nên mặc định polling production DB mỗi 5 phút.

**Nguồn:** AWS Glue JDBC connections; AWS Glue time-based schedules; AWS EventBridge Scheduler

## 3. "Parquet là row-based"

**Sai:** Parquet là column-oriented format, không phải row-based. Apache Parquet được thiết kế cho lưu trữ và truy xuất dữ liệu hiệu quả; Athena cũng khuyến nghị Parquet/ORC cho analytical workload vì có thể giảm lượng dữ liệu cần đọc và I/O.

**Sửa:** Nói chính xác hơn: Parquet là format lưu theo cột, phù hợp cho phân tích vì có thể nén dữ liệu tốt và khi query chỉ cần đọc những cột liên quan thay vì đọc toàn bộ dòng như CSV.

**Nguồn:** AWS Athena columnar storage docs.

## 4. "Transform 30-45 phút nên dùng Lambda"

**Sai:** Một Lambda invocation có timeout tối đa 15 phút. Vì vậy một ETL job dự kiến chạy 30-45 phút không phù hợp với Lambda.

**Sửa:** Dùng AWS Glue cho workload ETL dài/nặng hơn. Lambda phù hợp hơn với tác vụ ngắn như validation nhẹ, trigger hoặc orchestration đơn giản.

**Nguồn:** AWS Lambda docs; AWS Glue docs; kinh nghiệm đã từng dùng lambda ở Xbrain.

## 5. "Chunk cố định 4.000 token luôn tốt nhất"

**Sai:** Đây là lỗi tuyệt đối hóa. Không có một kích thước chunk luôn tốt nhất cho mọi loại tài liệu. Tài liệu `reading/01_chunking_basics.md` nêu trade-off giữa chunk quá to và quá nhỏ; AWS Bedrock Knowledge Bases cũng hỗ trợ nhiều chiến lược như fixed-size, hierarchical và semantic chunking, cho thấy chunking phải phụ thuộc dữ liệu và retrieval requirement.

**Sửa:** Chọn chunking theo cấu trúc tài liệu và nhu cầu retrieval, ví dụ ưu tiên section/heading hoặc semantic boundary, sau đó kiểm chứng bằng bộ eval.

**Nguồn:** `Xbrain_Assessment_DE_DataPack/reading/01_chunking_basics.md`; AWS Bedrock Knowledge Bases chunking docs.

## 6. "Không cần version, bản mới nhất luôn đúng và cứ ghi đè"

**Sai:** Đây là rủi ro lớn cho KB. Bài toán yêu cầu xử lý tài liệu mâu thuẫn bằng version + freshness; vì vậy ghi đè bản cũ sẽ làm mất traceability và không đảm bảo bản mới nhất là bản có hiệu lực. `reading/01_chunking_basics.md` cũng nhấn mạnh metadata version/date/owner để biết tài liệu còn hiệu lực không; `reading/02_rag_eval_basics.md` yêu cầu có version-trap trong eval.

**Sửa:** Giữ metadata như `version`, `effective_date` hoặc `issued_or_updated_date`, `owner`, `is_superseded`; giữ bản cũ để audit và chỉ ưu tiên bản được xác nhận là hiện hành khi retrieval.

**Nguồn:** `Xbrain_Assessment_DE_DataPack/reading/01_chunking_basics.md`; `Xbrain_Assessment_DE_DataPack/reading/02_rag_eval_basics.md`.

## Kết luận

Khi review output AI, em không chỉ kiểm tra câu trả lời có "nghe hợp lý" hay không, mà phải kiểm chứng từng claim quan trọng. Claim AWS cần đối chiếu AWS documentation; quyết định KB cần đối chiếu tài liệu `reading/`, yêu cầu bài và test/eval. Những từ tuyệt đối như "luôn", "mặc định", "pattern chuẩn" là tín hiệu cần kiểm tra kỹ trước khi dùng.

## Nguồn kiểm chứng

- AWS S3 storage classes: https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-class-intro.html
- AWS S3 pricing: https://aws.amazon.com/s3/pricing/
- AWS Glue JDBC connections: https://docs.aws.amazon.com/glue/latest/dg/aws-glue-programming-etl-connect-jdbc-home.html
- AWS Glue time-based schedules: https://docs.aws.amazon.com/glue/latest/dg/monitor-data-warehouse-schedule.html
- AWS EventBridge Scheduler: https://docs.aws.amazon.com/eventbridge/latest/userguide/using-eventbridge-scheduler.html
- AWS Lambda docs: https://docs.aws.amazon.com/lambda/latest/dg/configuration-timeout.html
- AWS Glue docs: https://docs.aws.amazon.com/glue/
- AWS Athena columnar storage: https://docs.aws.amazon.com/athena/latest/ug/columnar-storage.html
- AWS Bedrock Knowledge Bases chunking: https://docs.aws.amazon.com/bedrock/latest/userguide/kb-chunking.html
- `Xbrain_Assessment_DE_DataPack/reading/01_chunking_basics.md`
- `Xbrain_Assessment_DE_DataPack/reading/02_rag_eval_basics.md`
