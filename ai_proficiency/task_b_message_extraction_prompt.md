# Task B - Prompt trích xuất `message` log thành JSON

## Mục tiêu

Trích xuất `message` tự do thành JSON có cấu trúc, có rule kiểm soát tính nhất quán và chống bịa.

## Prompt hoàn chỉnh

```text
Bạn là log message parser cho hệ thống vận hành nội bộ.

Đọc input JSON và trả đúng 1 JSON object. Chỉ dùng thông tin trong `message`; không suy đoán service, timestamp, level hoặc component. Không trả markdown hay giải thích.

Nếu input không phải JSON object, thiếu `message`, hoặc `message` không phải string, trả:
{
  "message_raw": null,
  "parse_status": "unparsed",
  "event_category": "unknown",
  "event_name": null,
  "component": null,
  "parameters": {},
  "extra_parameters": {},
  "missing_information": ["message missing or not a string"]
}

Output schema:
{
  "message_raw": "string | null",
  "parse_status": "parsed | partial | unparsed",
  "event_category": "error | performance | business | job | retry | auth | notification | health | unknown",
  "event_name": "string | null",
  "component": "string | null",
  "parameters": {"<allowed_key>": "<typed value>"},
  "extra_parameters": {"<original_key>": "<raw string value>"},
  "missing_information": ["string"]
}

Kiểu dữ liệu: string (`error_code`, `path`, `table`, `step`, `host`, `uid`, `txn`); number (`amount`); integer (`http_status`, `timeout_seconds`, `retry_count`, `retry_total`, `response_time_ms`, `rows`, `expected`, `got`, `depth`).

Key mapping:
- `retry` -> `retry_count`; `upstream` -> `component`; `code` -> `error_code`.
- `rows`, `expected`, `got`, `depth` giữ tên và đổi sang integer.
- uid, txn, amount, path, table, step, host giữ nguyên key
- Key mới dạng key=value được giữ nguyên trong `extra_parameters` dưới dạng string; không tự đổi tên hay đoán kiểu.

Precedence:
invalid input > ERR error > Retry > performance > business > job > auth > notification > health > unknown

Đây là pattern tổng quát, không phải câu cần khớp nguyên văn. `<...>` là phần cần trích xuất. Chỉ tổng quát trong cấu trúc và từ khóa đã nêu; cấu trúc mới phải là `unknown` hoặc `partial`.

Category rules:
1. ERR error:
   - Pattern `ERR HTTP <status> ...` -> event_name="HTTP <status>", error_code="HTTP <status>", http_status=<status>.
   - Pattern `ERR <error_token> ...` -> event_name=<error_token>, error_code=<error_token>; dừng trước token có `=` hoặc từ nối `in`, `after`.
   - component:
     - `upstream=<name>` -> component=<name>.
     - `ERR <error_token> <name> ...` -> component=<name>.
     - `ERR <error_token> in <name> ...` -> component=<name>.
     - `host=<name>` -> host=<name>; nếu không có component khác thì component=<name>.
2. Retry:
   - Pattern `Retry <current>/<total> calling <name>` -> event_name="retry_call", retry_count=<current>, retry_total=<total>, component=<name>.
3. Performance:
   - Pattern `Response time <n>ms ...` -> event_name="response_time", response_time_ms=<n>.
   - Pattern `Request completed path=<path> in <n>ms` -> event_name="request_completed", path=<path>, response_time_ms=<n>.
   - Pattern `Slow query <n>ms ...` -> event_name="slow_query", response_time_ms=<n>.
   - Pattern `Slow login <n>ms uid=<uid>` -> event_name="slow_login", response_time_ms=<n>, uid=<uid>; chọn performance vì thông tin chính là độ trễ.
4. Business:
   - Pattern `Payment processed txn=<txn> amount=<amount>` -> event_name="payment_processed", txn=<txn>, amount=<amount>.
   - Pattern `Balance check ok uid=<uid>` -> event_name="balance_check_ok", uid=<uid>.
5. Job:
   - Pattern `<job_name> job started` -> event_name là tên job chuẩn hóa snake_case + `_started`.
   - Pattern `<job_name> job finished ...` -> event_name là tên job chuẩn hóa snake_case + `_finished`.
   - Pattern `Report row mismatch expected=<n> got=<n>` -> event_name="report_row_mismatch", expected=<n>, got=<n>.
6. Auth:
   - Pattern có `uid=<uid>` và bắt đầu bằng `Session created`, `Token refreshed` hoặc `User login success` -> event_name tương ứng ở dạng snake_case.
   - Không gán auth chỉ vì có `uid`; `uid` cũng xuất hiện ở business, notification và performance.
7. Notification:
   - Pattern `<channel> sent uid=<uid>`, với channel thuộc `Email`, `SMS` -> event_name là channel viết thường + `_sent`.
8. Health:
   - Pattern `Heartbeat ok` -> event_name="heartbeat_ok".
   - Pattern `Clock sync failed` -> event_name="clock_sync_failed".
   - Pattern `Queue depth high depth=<n>` -> event_name="queue_depth_high", depth=<n>.
9. Unknown:
   - Nếu không match rule nào, dùng parse_status="unparsed", event_category="unknown", event_name=null, component=null. Vẫn giữ mọi key=value tìm được trong `parameters` hoặc `extra_parameters`.

parse_status:
- parsed: khớp pattern, xác định category/event_name và giữ đủ giá trị có cấu trúc.
- partial: nhận diện được category/event_name nhưng thiếu giá trị bắt buộc hoặc chỉ khớp một phần. Có `extra_parameters` không tự động thành partial.
- unparsed: không match category nào hoặc input không hợp lệ.

Anti-hallucination:
- Giá trị trong `component`, `parameters` và `extra_parameters` phải có trong message, trừ `event_name` được chuẩn hóa.
- Chỉ được đổi chuỗi số sang kiểu number/integer theo bảng kiểu dữ liệu; không được thay đổi giá trị.
- Nếu một giá trị không xuất hiện trong message và không được hai rule normalize trên cho phép, không được điền.
```

## Prompt này làm gì?

Prompt yêu cầu LLM hoạt động như một parser có rule, thay vì trả lời tự do. Mục tiêu là biến nội dung `message` thành JSON ổn định để có thể thống kê, lọc và đưa vào pipeline phía sau.

1. **Vai trò và giới hạn:** LLM chỉ được đọc trường `message`. Các trường khác của log như `service`, `level` hay `timestamp` không được dùng để suy đoán kết quả. Điều này giúp kiểm tra đúng khả năng trích xuất từ văn bản và giảm nguy cơ model điền thông tin theo ngữ cảnh.

2. **Kiểm tra input:** nếu input không phải JSON object, thiếu `message` hoặc `message` không phải chuỗi, prompt yêu cầu trả một output cố định với `parse_status="unparsed"`. Nhờ vậy downstream luôn nhận được JSON đúng schema, kể cả khi dữ liệu đầu vào hỏng.

3. **Schema đầu ra:** `event_category` cho biết nhóm sự kiện; `event_name` là tên sự kiện đã chuẩn hóa; `component` là thành phần liên quan; `parameters` chứa các giá trị đã biết và đúng kiểu. `message_raw` giữ nguyên nội dung gốc để audit và kiểm tra lại kết quả.

4. **Mapping và kiểu dữ liệu:** các cách viết khác nhau được đưa về cùng một tên, ví dụ `retry=3` thành `retry_count: 3`, còn `upstream=payment-api` thành `component: "payment-api"`. Những key chưa biết vẫn được giữ nguyên trong `extra_parameters` dưới dạng chuỗi để không mất dữ liệu khi format log thay đổi.

5. **Precedence và pattern:** precedence giải quyết trường hợp một message khớp nhiều nhóm. Ví dụ `Slow login 900ms uid=u7882` có yếu tố đăng nhập nhưng được xếp vào `performance`, vì nội dung chính đang mô tả độ trễ. Các dòng trong category rules là pattern tổng quát có phần thay đổi `<...>`, không phải danh sách câu phải khớp nguyên văn.

6. **Mức độ parse:** `parsed` nghĩa là đã nhận diện được pattern và lấy đủ dữ liệu có cấu trúc; `partial` nghĩa là nhận diện được sự kiện nhưng còn thiếu giá trị bắt buộc; `unparsed` nghĩa là chưa có rule phù hợp. Đây là tín hiệu để xác định kết quả nào cần con người kiểm tra.

7. **Chống hallucination:** mọi giá trị trong `component`, `parameters` và `extra_parameters` phải xuất hiện trong message gốc. LLM chỉ được chuẩn hóa `event_name` và chuyển chuỗi số sang đúng kiểu dữ liệu theo rule; không được tự thêm service, nguyên nhân lỗi hoặc tham số không có trong input.

Ví dụ, với `Request completed path=/report in 554ms`, prompt xác định đây là `performance`, chuẩn hóa tên thành `request_completed`, lấy `/report` vào `path`, đổi `554ms` thành `response_time_ms: 554`, và giữ nguyên message trong `message_raw` để đối chiếu.

## Bộ test 5 message từ data pack và expect output

### Test 1 - error và component

Input: `ERR HTTP 502 upstream=payment-api path=/checkout`

```json
{
  "message_raw": "ERR HTTP 502 upstream=payment-api path=/checkout",
  "parse_status": "parsed",
  "event_category": "error",
  "event_name": "HTTP 502",
  "component": "payment-api",
  "parameters": {
    "error_code": "HTTP 502",
    "http_status": 502,
    "path": "/checkout"
  },
  "extra_parameters": {},
  "missing_information": []
}
```

### Test 2 - pattern phổ biến nhất

Input: `Request completed path=/report in 554ms`

```json
{
  "message_raw": "Request completed path=/report in 554ms",
  "parse_status": "parsed",
  "event_category": "performance",
  "event_name": "request_completed",
  "component": null,
  "parameters": {
    "path": "/report",
    "response_time_ms": 554
  },
  "extra_parameters": {},
  "missing_information": []
}
```

### Test 3 - business event

Input: `Payment processed txn=t419149 amount=990000`

```json
{
  "message_raw": "Payment processed txn=t419149 amount=990000",
  "parse_status": "parsed",
  "event_category": "business",
  "event_name": "payment_processed",
  "component": null,
  "parameters": {
    "txn": "t419149",
    "amount": 990000
  },
  "extra_parameters": {},
  "missing_information": []
}
```

### Test 4 - ca mơ hồ giữa performance và auth

Input: `Slow login 900ms uid=u7882`

```json
{
  "message_raw": "Slow login 900ms uid=u7882",
  "parse_status": "parsed",
  "event_category": "performance",
  "event_name": "slow_login",
  "component": null,
  "parameters": {
    "response_time_ms": 900,
    "uid": "u7882"
  },
  "extra_parameters": {},
  "missing_information": []
}
```

### Test 5 - operational health

Input: `Queue depth high depth=2656`

```json
{
  "message_raw": "Queue depth high depth=2656",
  "parse_status": "parsed",
  "event_category": "health",
  "event_name": "queue_depth_high",
  "component": null,
  "parameters": {
    "depth": 2656
  },
  "extra_parameters": {},
  "missing_information": []
}
```

## B3 - Cách đánh giá prompt trên khoảng 3.000 dòng thật

Em không cần đọc thủ công cả 3.000 dòng. Em sẽ kiểm tra tự động toàn bộ output, sau đó chọn khoảng 200-300 message đại diện và tự viết đáp án đúng trước khi xem kết quả LLM. Bộ đáp án này được dùng làm chuẩn để so sánh.

### 1. Tiêu chí đo (metrics)

**JSON và schema:** dùng code kiểm tra output có phải JSON hợp lệ, có đủ key và đúng kiểu dữ liệu hay không. Ví dụ, `response_time_ms` phải là số nguyên và `parameters` phải là object.

```text
JSON validity rate      = số output đọc được bằng JSON parser / tổng output
Schema compliance rate = số output đúng schema / tổng output
```

**Độ chính xác theo field:** so sánh riêng `event_category`, `event_name`, `component` và từng parameter với đáp án chuẩn.

- Precision trả lời câu hỏi: trong các field LLM đã điền, bao nhiêu field đúng?
- Recall trả lời câu hỏi: trong các field cần lấy, LLM lấy được bao nhiêu?
- F1 kết hợp Precision và Recall thành một chỉ số để so sánh các phiên bản prompt.

**Exact-match rate:** tính tỷ lệ JSON khớp toàn bộ đáp án chuẩn sau khi chuẩn hóa thứ tự key. Chỉ cần thiếu hoặc sai một field thì record không được tính đúng.

**Kiểm tra `parse_status`:** đếm số dòng được gán `parsed` nhưng thực tế còn thiếu hoặc sai field. Những dòng này đáng lẽ phải là `partial`; tỷ lệ cao cho thấy prompt đang đánh giá kết quả quá lạc quan.

**Ma trận nhầm category:** ghi lại category đúng và category LLM dự đoán để xem lỗi tập trung ở đâu. Ví dụ, nếu nhiều message `auth` bị xếp thành `business`, em sẽ kiểm tra lại precedence và rule liên quan đến `uid`.

### 2. Phát hiện hallucination

**Đối chiếu tự động với message gốc:** code kiểm tra `message_raw` có giống input và mọi giá trị trong `component`, `parameters`, `extra_parameters` có được lấy từ message hay không. Ngoại lệ chỉ là `event_name` được chuẩn hóa và số được đổi kiểu theo rule.

Không chỉ kiểm tra giá trị có xuất hiện hay không mà còn phải kiểm tra đúng field. Ví dụ, message có `uid=u7882` thì `u7882` có thể nằm ở `parameters.uid`, nhưng không có căn cứ để dùng làm `component`.

**Kiểm tra số:** với field integer/number, code đối chiếu chuỗi số trong message với giá trị sau khi chuyển kiểu. Làm tròn, đổi dấu hoặc thay đổi giá trị đều bị đánh dấu sai.

**Đối chiếu tay trên tập mẫu:** người kiểm tra đọc 200-300 message đã chọn cùng output tương ứng để phát hiện trường hợp code bỏ sót. Mẫu được chia theo pattern phổ biến, hiếm và mơ hồ, không chỉ chọn ngẫu nhiên các dòng dễ.

**Test cố tình thiếu thông tin:** thêm một số message gần giống pattern nhưng thiếu component hoặc tham số để kiểm tra LLM có trả `partial`/`null` hay tự điền dữ liệu không có trong input.

### 3. Khi nào cần người kiểm tra

- Output là `partial`, `unparsed`, sai schema, có `missing_information` hoặc không đối chiếu được với message gốc.
- Xuất hiện format message mới hoặc số lượng `unknown` tăng bất thường.
- Kiểm tra ngẫu nhiên 1-2% nhóm `parsed` để bắt trường hợp LLM trả đúng cấu trúc nhưng hiểu sai nội dung.
- Mỗi lần sửa prompt, chạy lại cùng bộ đáp án chuẩn và các test thiếu thông tin để xem kết quả tốt lên hay phát sinh lỗi cũ.

## B4 - Chạy thử bằng ChatGPT và Claude

Em đã chạy thử prompt trên cùng 5 message từ data pack bằng ChatGPT và Claude, sau đó đối chiếu từng field giữa hai model.

Các message đã dùng:

1. `ERR ConnTimeout db-primary after 30s retry=3`
2. `ERR HTTP 502 upstream=payment-api path=/checkout`
3. `Daily report job finished rows=1001`
4. `Email sent uid=u3328`
5. `Clock sync failed`

### Kết quả Claude

```json
[
  {
    "message_raw": "ERR ConnTimeout db-primary after 30s retry=3",
    "parse_status": "parsed",
    "event_category": "error",
    "event_name": "ConnTimeout",
    "component": "db-primary",
    "parameters": {
      "error_code": "ConnTimeout",
      "retry_count": 3
    },
    "extra_parameters": {},
    "missing_information": []
  },
  {
    "message_raw": "ERR HTTP 502 upstream=payment-api path=/checkout",
    "parse_status": "parsed",
    "event_category": "error",
    "event_name": "HTTP 502",
    "component": "payment-api",
    "parameters": {
      "error_code": "HTTP 502",
      "http_status": 502,
      "path": "/checkout"
    },
    "extra_parameters": {},
    "missing_information": []
  },
  {
    "message_raw": "Daily report job finished rows=1001",
    "parse_status": "parsed",
    "event_category": "job",
    "event_name": "daily_report_finished",
    "component": null,
    "parameters": {
      "rows": 1001
    },
    "extra_parameters": {},
    "missing_information": []
  },
  {
    "message_raw": "Email sent uid=u3328",
    "parse_status": "parsed",
    "event_category": "notification",
    "event_name": "email_sent",
    "component": null,
    "parameters": {
      "uid": "u3328"
    },
    "extra_parameters": {},
    "missing_information": []
  },
  {
    "message_raw": "Clock sync failed",
    "parse_status": "parsed",
    "event_category": "health",
    "event_name": "clock_sync_failed",
    "component": null,
    "parameters": {},
    "extra_parameters": {},
    "missing_information": []
  }
]
```

### Kết quả ChatGPT

```json
[
  {
    "message_raw": "ERR ConnTimeout db-primary after 30s retry=3",
    "parse_status": "parsed",
    "event_category": "error",
    "event_name": "ConnTimeout",
    "component": "db-primary",
    "parameters": {
      "retry_count": 3
    },
    "extra_parameters": {},
    "missing_information": []
  },
  {
    "message_raw": "ERR HTTP 502 upstream=payment-api path=/checkout",
    "parse_status": "parsed",
    "event_category": "error",
    "event_name": "HTTP 502",
    "component": "payment-api",
    "parameters": {
      "error_code": "HTTP 502",
      "http_status": 502,
      "path": "/checkout"
    },
    "extra_parameters": {},
    "missing_information": []
  },
  {
    "message_raw": "Daily report job finished rows=1001",
    "parse_status": "parsed",
    "event_category": "job",
    "event_name": "daily_report_finished",
    "component": null,
    "parameters": {
      "rows": 1001
    },
    "extra_parameters": {},
    "missing_information": []
  },
  {
    "message_raw": "Email sent uid=u3328",
    "parse_status": "parsed",
    "event_category": "notification",
    "event_name": "email_sent",
    "component": null,
    "parameters": {
      "uid": "u3328"
    },
    "extra_parameters": {},
    "missing_information": []
  },
  {
    "message_raw": "Clock sync failed",
    "parse_status": "parsed",
    "event_category": "health",
    "event_name": "clock_sync_failed",
    "component": null,
    "parameters": {},
    "extra_parameters": {},
    "missing_information": []
  }
]
```

### Nhận xét sau khi chạy thử

- Hai model xử lý giống nhau ở test 2, 4 và 5.
- Ở test 1, cả hai đều bỏ sót `timeout_seconds=30`; ChatGPT còn bỏ sót `error_code="ConnTimeout"`. Điều này cho thấy prompt chưa có rule rõ cho `after <n>s`, đồng thời model vẫn có thể bỏ qua rule đã nêu.
- Ở test 3, hai model trả cùng category, event name và parameters.
- Em không coi output của model là đáp án đúng mặc định mà so sánh từng field với expected output và dùng lỗi quan sát được để chỉnh prompt.

## Tài liệu tham khảo cho mục đánh giá prompt

- [OpenAI - Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
- [OpenAI - Graders](https://developers.openai.com/api/docs/guides/graders)
- [scikit-learn - F1 score](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.f1_score.html)
- [spaCy - Scorer](https://spacy.io/api/scorer)
- [NIST - Sample sizes required](https://www.itl.nist.gov/div898/handbook/prc/section2/prc242.htm)
