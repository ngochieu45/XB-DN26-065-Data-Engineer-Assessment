# Xbrain Data Engineer POC - Part 1A Log Pipeline

This repository currently contains the local Python pipeline for Part 1A of the Xbrain Data Engineer assessment.

The pipeline processes seven days of simulated application logs from five services. It validates and cleans the source records, stores a structured dataset, and generates the four reports requested by the customer.

The source JSONL file is treated as immutable raw data and is never edited.

## Current repository structure

```text
repo/
|-- README.md
|-- requirements.txt
|-- pipeline/
|   |-- processing.py
|   |-- reporting.py
|   |-- run.py
|   |-- tests/
|   `-- output/
`-- Xbrain_Assessment_DE_DataPack/
    `-- data/
        `-- app_logs_7days.jsonl
```

## Requirements

- Python 3.12+
- pandas 2.2.3
- PyArrow 19.0.1

Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run the pipeline

From the repository root:

```powershell
python -m pipeline
```

The default paths are:

```text
Input:  Xbrain_Assessment_DE_DataPack/data/app_logs_7days.jsonl
Output: pipeline/output/
```

Custom paths can be provided:

```powershell
python -m pipeline `
  --input path\to\app_logs_7days.jsonl `
  --output path\to\output
```

## Processing flow

```text
JSONL input
  -> line-by-line ingestion
  -> validation and quarantine
  -> deduplication
  -> UTC and schema normalization
  -> structured Parquet dataset
  -> operational reports
```

The file is read line by line so one malformed JSON record does not stop the entire batch. Every physical line is assigned to one primary outcome: accepted into the clean dataset or written to `rejected_records.jsonl` with a rejection reason and source line number.

## Ingestion and validation

Validation is applied in this deterministic order:

```text
Parse JSON
  -> require a JSON object
  -> validate required fields and types
  -> validate level
  -> validate the timezone-aware timestamp
  -> deduplicate request_id
  -> accept the record
```

The required fields are `timestamp`, `service`, `level`, `message`, and `request_id`. The optional `trace_id` field is accepted when present and stored as null when absent.

### Raw data profiling method

I did not inspect every record manually. I treated the raw JSONL file as immutable and used a data-engineering profiling workflow: inspect small representative samples by eye, run read-only checks across the full file, then drill into representative examples for each anomaly category before deciding how the pipeline should handle them.

The profiling checks covered:

- Physical line count and sample records from the beginning, end, and random positions in the file.
- JSON parse success and malformed-line samples.
- Field presence, required-field gaps, observed fields, and schema variants.
- Domain values for `level` and `service`.
- Timestamp parseability, timezone awareness, offset variants, and date range.
- Duplicate `request_id` records and whether duplicates appeared to be repeated events.
- Optional `trace_id` coverage.
- Repeated ERROR message patterns and dynamic parameters that should not split one logical error type into many groups.

This separates human judgment from measurement: I decided which issues mattered and how to handle them, while the counts are produced by deterministic checks that can be rerun by the evaluator.

### Findings and decisions

| Finding | Count | Handling decision | Reason |
| --- | ---: | --- | --- |
| Malformed JSON | 18 | Quarantine the original line | The intended fields cannot be inferred safely, and silent skipping would hide data loss. |
| Missing required `level` | 18 | Quarantine without assigning a default | Guessing the level would directly change ERROR-based reports. |
| Invalid timestamp (`not-a-date`) | 20 | Quarantine without guessing a date | An invented timestamp could place an event in the wrong daily bucket. |
| Repeated `request_id` | 28 | Keep the first valid occurrence | Counting exact repeated events would inflate all downstream totals. |
| Mixed `Z` and `+07:00` timestamps | 588 accepted offset records | Preserve `timestamp_raw` and normalize the analytical timestamp to UTC | UTC provides one basis for daily aggregation while retaining traceability. |
| Optional `trace_id` schema drift | Present in only part of the data | Keep the column and store missing values as null | The field is useful metadata but is not required for the requested analysis. |
| Parameterized messages | Multiple dynamic values | Preserve `message`; derive `error_type`, `error_code`, and parameters | Dynamic values such as `txn` and `uid` must not split one logical error into many categories. |

The validation totals reconcile to the physical input:

```text
2,923 input lines
-    18 malformed JSON
-    18 missing required level
-    20 invalid timestamps
-    28 duplicate request IDs
= 2,839 clean records
```

Rejected categories are mutually exclusive under the validation order. Full validation counts and observed schema variants are written to `pipeline/output/data_quality_report.json`.

## Transformation and storage

Accepted records are normalized into a consistent schema containing:

- Original and UTC timestamps.
- UTC event date.
- Service, level, message, and request ID.
- Optional trace ID.
- Normalized error type and error code.
- Extracted message parameters.
- Original source line number.

The clean dataset is stored as **Parquet** because it preserves schema and timezone-aware timestamp types, supports efficient analytical column reads, and is suitable for analytical data-lake workloads.

Rejected records remain in JSONL format because this preserves their record-oriented structure and makes later correction or replay straightforward.

## Report results

All reports are calculated from the clean dataset rather than the raw file.

| Customer question | Result | Method |
| --- | --- | --- |
| Service with the most ERROR records | `payment-api` with 139 | Group clean ERROR records by `service`. |
| Daily error anomaly | `2026-07-30` with 140 | Mark counts above `Q3 + 1.5 * IQR` as high anomalies. |
| Most common error type | `ConnTimeout`, 114, `payment-api` | Group by normalized `error_type`, excluding dynamic parameters. |
| Second most common error type | `HTTP 502`, 41, `web-portal` | Apply the same normalized grouping rule. |
| Third most common error type | `NullPointer`, 37, `batch-report` | Apply the same normalized grouping rule. |
| Removed or deduplicated records | 84 | Reconcile mutually exclusive rejection reasons against all physical lines. |

The complete breakdown is available in `pipeline/output/analysis_report.md`.

## Generated outputs

```text
pipeline/output/
|-- clean_logs.parquet
|-- rejected_records.jsonl
|-- data_quality_report.json
|-- errors_by_service.csv
|-- errors_by_day.csv
|-- top_error_types.csv
|-- analysis_summary.json
`-- analysis_report.md
```

## Tests

Run the automated tests with:

```powershell
python -m unittest discover -s pipeline/tests -v
```

The tests cover malformed JSON, missing fields, invalid timestamps, duplicate request IDs, timezone normalization, optional `trace_id`, stable error-type extraction, and IQR anomaly detection.

## Assumptions and limitations

- `request_id` is treated as unique because repeated IDs in the supplied data are exact duplicated events. A production pipeline should confirm this contract with the source owner.
- The IQR anomaly rule is transparent and suitable for this POC, but seven days is a short baseline. A production detector should use more history and account for weekday or seasonal patterns.
- The current implementation is a local batch pipeline designed for reproducibility and clear decision-making.
