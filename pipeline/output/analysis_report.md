# Log Analysis Report

## Data quality

- Input lines: 2923
- Clean records: 2839
- Rejected or deduplicated records: 84

| reason | record_count |
| --- | --- |
| duplicate_request_id | 28 |
| invalid_timestamp | 20 |
| malformed_json | 18 |
| missing_required_field | 18 |

## 1. Service with the most errors

**payment-api** has the most ERROR records: **139**.

| rank | service | error_count |
| --- | --- | --- |
| 1 | payment-api | 139 |
| 2 | web-portal | 41 |
| 3 | batch-report | 37 |
| 4 | auth-service | 35 |
| 5 | notification-worker | 35 |

## 2. Error count by day

High anomalies use the IQR rule: a count above `Q3 + 1.5 * IQR`.

High-anomaly date(s): **2026-07-30**.

| event_date | error_count | is_high_anomaly |
| --- | --- | --- |
| 2026-07-27 | 19 | false |
| 2026-07-28 | 27 | false |
| 2026-07-29 | 29 | false |
| 2026-07-30 | 140 | true |
| 2026-07-31 | 17 | false |
| 2026-08-01 | 24 | false |
| 2026-08-02 | 31 | false |

## 3. Top three error types

Messages are grouped by the stable error name after `ERR`; changing parameters such as `txn`, `uid`, and `code` are not part of the error type.

| rank | error_type | error_count | services |
| --- | --- | --- | --- |
| 1 | ConnTimeout | 114 | payment-api (114) |
| 2 | HTTP 502 | 41 | web-portal (41) |
| 3 | NullPointer | 37 | batch-report (37) |

## 4. Removed or normalized records

**84** records were rejected or deduplicated. They are written to `rejected_records.jsonl` with the source line number, reason, and original content.

| reason | record_count |
| --- | --- |
| duplicate_request_id | 28 |
| invalid_timestamp | 20 |
| malformed_json | 18 |
| missing_required_field | 18 |

Accepted records also received these normalization operations:

| transformation | record_count |
| --- | --- |
| missing_optional_trace_id_filled_null | 1674 |
| timezone_offset_normalized_to_utc | 588 |

Transformation counts are operation counts and may overlap: one accepted record can have both its timezone normalized and its missing optional `trace_id` filled with null.
