# Task B - Prompt trích xuất `message` log thành JSON

## B1 - Prompt hoàn chỉnh

```text
Bạn là parser cho log vận hành. Input là đúng một JSON object có dạng
{"message":"<text>"}. Chỉ đọc `message` và trả đúng một JSON object; không
trả Markdown hoặc giải thích, không suy đoán từ service, level hay timestamp.

Output schema:
{
  "message_raw": "string | null",
  "parse_status": "parsed | partial | unparsed",
  "event_category": "error | performance | business | job | retry | auth | notification | health | unknown",
  "event_name": "string | null",
  "component": "string | null",
  "parameters": {},
  "extra_parameters": {},
  "missing_information": []
}

Nếu input không phải object, thiếu `message` hoặc `message` không phải string,
trả schema trên với message_raw=null, parse_status="unparsed",
event_category="unknown", các object/list rỗng và
missing_information=["message missing or not a string"].

Kiểu dữ liệu:
- string: error_code, path, table, step, host, uid, txn.
- number: amount.
- integer: http_status, timeout_seconds, retry_count, retry_total,
  response_time_ms, rows, expected, got, depth.
- Mapping: retry->retry_count, code->error_code, upstream->component.
- Key `key=value` chưa biết được giữ nguyên dạng string trong extra_parameters.

Precedence khi nhiều rule cùng khớp:
invalid > error > retry > performance > business > job > auth > notification > health > unknown.

Các rule dưới đây là pattern tổng quát; `<...>` là phần cần trích xuất:
1. Error: `ERR HTTP <status> ...` -> event_name/error_code="HTTP <status>",
   http_status=<status>. `ERR <error> ...` -> event_name/error_code=<error>.
   `upstream=<x>` hoặc tên ngay sau error -> component=<x>;
   `after <n>s` -> timeout_seconds=<n>; `retry=<n>` -> retry_count=<n>.
2. Retry: `Retry <n>/<total> calling <x>` -> retry_call, hai retry count,
   component=<x>.
3. Performance: `Response time <n>ms`, `Request completed path=<p> in <n>ms`,
   `Slow query <n>ms`, `Slow login <n>ms uid=<u>` -> event_name tương ứng,
   response_time_ms=<n> và các parameter xuất hiện.
4. Business: `Payment processed txn=<t> amount=<a>` -> payment_processed;
   `Balance check ok uid=<u>` -> balance_check_ok.
5. Job: `<name> job started|finished` -> snake_case `<name>_started|finished`;
   `Report row mismatch expected=<n> got=<n>` -> report_row_mismatch.
6. Auth: `Session created`, `Token refreshed`, `User login success` có uid
   -> event_name snake_case. Không gán auth chỉ vì message có uid.
7. Notification: `Email|SMS sent uid=<u>` -> email_sent hoặc sms_sent.
8. Health: `Heartbeat ok`, `Clock sync failed`, `Queue depth high depth=<n>`
   -> heartbeat_ok, clock_sync_failed hoặc queue_depth_high.
9. Không khớp rule -> unparsed/unknown; vẫn giữ key=value tìm được.

parse_status="parsed" khi pattern khớp và đủ giá trị được pattern yêu cầu;
"partial" khi nhận diện được event nhưng thiếu giá trị; "unparsed" khi input
không hợp lệ hoặc không có rule phù hợp.

Chống bịa: message_raw phải bằng input. Mọi giá trị trong component,
parameters và extra_parameters phải xuất hiện trong message; ngoại lệ duy nhất
là event_name chuẩn hóa và chuỗi số được đổi đúng kiểu mà không đổi giá trị.
Không có căn cứ thì dùng null, object rỗng hoặc missing_information.
```

## B2 - Năm test case và expected output

Các message đều lấy từ data pack. Test 1 là ca khó vì chứa error, component, timeout và retry trong cùng một câu.

### Test 1

Input: `{"message":"ERR ConnTimeout db-primary after 30s retry=3"}`

```json
{"message_raw":"ERR ConnTimeout db-primary after 30s retry=3","parse_status":"parsed","event_category":"error","event_name":"ConnTimeout","component":"db-primary","parameters":{"error_code":"ConnTimeout","timeout_seconds":30,"retry_count":3},"extra_parameters":{},"missing_information":[]}
```

### Test 2

Input: `{"message":"ERR HTTP 502 upstream=payment-api path=/checkout"}`

```json
{"message_raw":"ERR HTTP 502 upstream=payment-api path=/checkout","parse_status":"parsed","event_category":"error","event_name":"HTTP 502","component":"payment-api","parameters":{"error_code":"HTTP 502","http_status":502,"path":"/checkout"},"extra_parameters":{},"missing_information":[]}
```

### Test 3

Input: `{"message":"Daily report job finished rows=1001"}`

```json
{"message_raw":"Daily report job finished rows=1001","parse_status":"parsed","event_category":"job","event_name":"daily_report_finished","component":null,"parameters":{"rows":1001},"extra_parameters":{},"missing_information":[]}
```

### Test 4

Input: `{"message":"Email sent uid=u3328"}`

```json
{"message_raw":"Email sent uid=u3328","parse_status":"parsed","event_category":"notification","event_name":"email_sent","component":null,"parameters":{"uid":"u3328"},"extra_parameters":{},"missing_information":[]}
```

### Test 5

Input: `{"message":"Clock sync failed"}`

```json
{"message_raw":"Clock sync failed","parse_status":"parsed","event_category":"health","event_name":"clock_sync_failed","component":null,"parameters":{},"extra_parameters":{},"missing_information":[]}
```

## B3 - Cách đánh giá trên khoảng 3.000 dòng

**Ground truth:** Chạy kiểm tra JSON/schema trên toàn bộ output. Chọn 200-300 message theo các nhóm phổ biến, hiếm, mơ hồ và input lỗi; em tự gán expected output trước khi xem kết quả LLM để tạo golden set.

**Metrics:** Đo JSON validity và schema compliance; precision/recall/F1 theo từng field; exact-match toàn object; tỷ lệ `parsed` nhưng còn thiếu field; confusion matrix của `event_category`. So sánh các phiên bản prompt trên cùng golden set.

**Phát hiện hallucination:** Tự động kiểm tra `message_raw`, provenance của mọi giá trị và việc chuyển kiểu số. Giá trị không có trong message hoặc nằm sai field được đưa vào review. Bổ sung adversarial test gần giống pattern nhưng thiếu component/parameter để kiểm tra model có trả null/partial hay tự điền.

**Khi cần người kiểm tra:** Review mọi output partial, unparsed, sai schema, có missing information hoặc fail provenance; review format message mới và khi unknown tăng bất thường; spot-check ngẫu nhiên 1-2% nhóm parsed. Mỗi lần sửa prompt phải chạy regression trên toàn golden set.

Tham khảo: [OpenAI evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices), [OpenAI graders](https://developers.openai.com/api/docs/guides/graders), [scikit-learn F1](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.f1_score.html), [NIST sampling](https://www.itl.nist.gov/div898/handbook/prc/section2/prc242.htm).

## B4 - Kết quả chạy thử (điểm cộng)

Em chạy cùng năm test trên ChatGPT và Claude rồi so sánh với expected output, không coi output model là đáp án mặc định.

| Test | Claude | ChatGPT | Đánh giá |
| --- | --- | --- | --- |
| 1 | Thiếu `timeout_seconds` | Thiếu `timeout_seconds` và `error_code` | FAIL; bổ sung rule `after <n>s` vào prompt cuối |
| 2 | Khớp expected | Khớp expected | PASS |
| 3 | Khớp expected | Khớp expected | PASS |
| 4 | Khớp expected | Khớp expected | PASS |
| 5 | Khớp expected | Khớp expected | PASS |

Kết quả test 1 cho thấy JSON hợp lệ chưa đồng nghĩa trích xuất đủ field; vì vậy cần golden set, field-level metrics và regression sau mỗi lần sửa prompt.
