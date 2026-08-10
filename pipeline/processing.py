from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


REQUIRED_FIELDS = ("timestamp", "service", "level", "message", "request_id")
ALLOWED_LEVELS = {"INFO", "WARN", "ERROR"}
ERROR_TYPE_PATTERN = re.compile(r"^ERR\s+(HTTP\s+\d{3}|[A-Za-z][A-Za-z0-9_]*)\b")
PARAMETER_PATTERN = re.compile(r"\b([A-Za-z_][A-Za-z0-9_-]*)=([^\s]+)")


@dataclass
class ProcessingResult:
    clean: pd.DataFrame
    rejected: list[dict[str, Any]]
    quality: dict[str, Any]


def parse_timestamp_utc(value: str) -> datetime:
    """Parse an ISO-8601 timestamp and require an explicit timezone."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp has no timezone")
    return parsed.astimezone(timezone.utc)


def extract_message_parameters(message: str) -> dict[str, str]:
    return {key: value for key, value in PARAMETER_PATTERN.findall(message)}


def extract_error_type(message: str) -> str | None:
    match = ERROR_TYPE_PATTERN.search(message.strip())
    return match.group(1) if match else None


def _reject(
    rejected: list[dict[str, Any]],
    reasons: Counter[str],
    *,
    line_number: int,
    reason: str,
    raw_line: str,
    details: Any = None,
    record: dict[str, Any] | None = None,
) -> None:
    item: dict[str, Any] = {
        "line_number": line_number,
        "reason": reason,
        "raw_line": raw_line,
    }
    if details is not None:
        item["details"] = details
    if record is not None:
        item["record"] = record
    rejected.append(item)
    reasons[reason] += 1


def process_jsonl(input_path: str | Path) -> ProcessingResult:
    """Read, validate, normalize, and deduplicate a JSON Lines log file."""
    source = Path(input_path)
    rejected: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    rejection_reasons: Counter[str] = Counter()
    schema_variants: Counter[str] = Counter()
    observed_fields: Counter[str] = Counter()
    transformations: Counter[str] = Counter()
    seen_request_ids: dict[str, int] = {}
    total_lines = 0
    parsed_json_values = 0

    with source.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            total_lines += 1
            raw_line = line.rstrip("\r\n")

            try:
                record = json.loads(raw_line)
                parsed_json_values += 1
            except json.JSONDecodeError as exc:
                _reject(
                    rejected,
                    rejection_reasons,
                    line_number=line_number,
                    reason="malformed_json",
                    raw_line=raw_line,
                    details={"message": exc.msg, "column": exc.colno},
                )
                continue

            if not isinstance(record, dict):
                _reject(
                    rejected,
                    rejection_reasons,
                    line_number=line_number,
                    reason="json_not_object",
                    raw_line=raw_line,
                    record={"value": record},
                )
                continue

            fields = sorted(record)
            schema_variants["|".join(fields)] += 1
            observed_fields.update(fields)

            missing_fields = [
                field
                for field in REQUIRED_FIELDS
                if field not in record or record[field] is None or record[field] == ""
            ]
            if missing_fields:
                _reject(
                    rejected,
                    rejection_reasons,
                    line_number=line_number,
                    reason="missing_required_field",
                    raw_line=raw_line,
                    details={"fields": missing_fields},
                    record=record,
                )
                continue

            invalid_types = [
                field for field in REQUIRED_FIELDS if not isinstance(record[field], str)
            ]
            if invalid_types:
                _reject(
                    rejected,
                    rejection_reasons,
                    line_number=line_number,
                    reason="invalid_field_type",
                    raw_line=raw_line,
                    details={"fields": invalid_types},
                    record=record,
                )
                continue

            level = record["level"].strip().upper()
            if level not in ALLOWED_LEVELS:
                _reject(
                    rejected,
                    rejection_reasons,
                    line_number=line_number,
                    reason="invalid_level",
                    raw_line=raw_line,
                    details={"value": record["level"]},
                    record=record,
                )
                continue
            if level != record["level"]:
                transformations["level_normalized"] += 1

            try:
                timestamp_utc = parse_timestamp_utc(record["timestamp"])
            except (TypeError, ValueError):
                _reject(
                    rejected,
                    rejection_reasons,
                    line_number=line_number,
                    reason="invalid_timestamp",
                    raw_line=raw_line,
                    details={"value": record["timestamp"]},
                    record=record,
                )
                continue

            request_id = record["request_id"]
            if request_id in seen_request_ids:
                _reject(
                    rejected,
                    rejection_reasons,
                    line_number=line_number,
                    reason="duplicate_request_id",
                    raw_line=raw_line,
                    details={"first_seen_line": seen_request_ids[request_id]},
                    record=record,
                )
                continue
            seen_request_ids[request_id] = line_number

            timestamp_raw = record["timestamp"]
            if not timestamp_raw.endswith("Z"):
                transformations["timezone_offset_normalized_to_utc"] += 1

            if "trace_id" not in record:
                transformations["missing_optional_trace_id_filled_null"] += 1

            parameters = extract_message_parameters(record["message"])
            clean_record = dict(record)
            clean_record.update(
                {
                    "timestamp_raw": timestamp_raw,
                    "timestamp": timestamp_utc,
                    "event_date": timestamp_utc.date().isoformat(),
                    "level": level,
                    "trace_id": record.get("trace_id"),
                    "error_type": extract_error_type(record["message"]),
                    "error_code": parameters.get("code"),
                    "message_parameters": json.dumps(
                        parameters, ensure_ascii=False, sort_keys=True
                    ),
                    "source_line_number": line_number,
                }
            )
            accepted.append(clean_record)

    clean = pd.DataFrame(accepted)
    preferred_columns = [
        "timestamp",
        "timestamp_raw",
        "event_date",
        "service",
        "level",
        "message",
        "request_id",
        "trace_id",
        "error_type",
        "error_code",
        "message_parameters",
        "source_line_number",
    ]
    if clean.empty:
        clean = pd.DataFrame(columns=preferred_columns)
    else:
        extra_columns = [column for column in clean.columns if column not in preferred_columns]
        clean = clean[preferred_columns + sorted(extra_columns)]
        clean = clean.sort_values(["timestamp", "request_id"], kind="stable").reset_index(
            drop=True
        )

    quality = {
        "input_file": str(source),
        "policy": {
            "malformed_json": "quarantine",
            "missing_required_field": "quarantine",
            "invalid_timestamp": "quarantine",
            "duplicate_request_id": "keep first valid occurrence",
            "timestamp": "normalize valid timezone-aware values to UTC",
            "trace_id": "optional; fill missing values with null",
        },
        "counts": {
            "total_lines": total_lines,
            "parsed_json_values": parsed_json_values,
            "clean_records": len(clean),
            "rejected_records": len(rejected),
        },
        "rejected_by_reason": dict(sorted(rejection_reasons.items())),
        "transformations": dict(sorted(transformations.items())),
        "schema_variants": dict(sorted(schema_variants.items())),
        "observed_fields": dict(sorted(observed_fields.items())),
    }
    return ProcessingResult(clean=clean, rejected=rejected, quality=quality)
