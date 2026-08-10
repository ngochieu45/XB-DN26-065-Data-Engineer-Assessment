from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from pipeline.processing import extract_error_type, process_jsonl
from pipeline.reporting import build_report_frames


class ProcessingTests(unittest.TestCase):
    def test_validation_normalization_and_deduplication(self) -> None:
        records = [
            {
                "timestamp": "2026-08-01T00:00:00Z",
                "service": "payment-api",
                "level": "ERROR",
                "message": "ERR ConnTimeout db-primary retry=3",
                "request_id": "r1",
            },
            "{broken-json",
            {
                "timestamp": "2026-08-01T01:00:00Z",
                "service": "auth-service",
                "message": "ERR AuthTokenExpired uid=u1",
                "request_id": "r2",
            },
            {
                "timestamp": "not-a-date",
                "service": "auth-service",
                "level": "ERROR",
                "message": "ERR AuthTokenExpired uid=u2",
                "request_id": "r3",
            },
            {
                "timestamp": "2026-08-01T00:00:00Z",
                "service": "payment-api",
                "level": "ERROR",
                "message": "ERR ConnTimeout db-primary retry=3",
                "request_id": "r1",
            },
            {
                "timestamp": "2026-08-02T07:00:00+07:00",
                "service": "auth-service",
                "level": "INFO",
                "message": "Login succeeded uid=u3",
                "request_id": "r4",
                "trace_id": "t4",
            },
        ]

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.jsonl"
            with source.open("w", encoding="utf-8") as stream:
                for record in records:
                    if isinstance(record, str):
                        stream.write(record + "\n")
                    else:
                        stream.write(json.dumps(record) + "\n")

            result = process_jsonl(source)

        self.assertEqual(result.quality["counts"]["total_lines"], 6)
        self.assertEqual(result.quality["counts"]["clean_records"], 2)
        self.assertEqual(result.quality["counts"]["rejected_records"], 4)
        self.assertEqual(
            result.quality["rejected_by_reason"],
            {
                "duplicate_request_id": 1,
                "invalid_timestamp": 1,
                "malformed_json": 1,
                "missing_required_field": 1,
            },
        )
        normalized = result.clean.loc[result.clean["request_id"] == "r4"].iloc[0]
        self.assertEqual(normalized["timestamp"].isoformat(), "2026-08-02T00:00:00+00:00")
        self.assertEqual(normalized["trace_id"], "t4")

    def test_error_type_ignores_changing_parameters(self) -> None:
        self.assertEqual(
            extract_error_type("ERR PaymentDeclined txn=t123 code=51"),
            "PaymentDeclined",
        )
        self.assertEqual(
            extract_error_type("ERR HTTP 502 upstream=payment-api path=/checkout"),
            "HTTP 502",
        )
        self.assertIsNone(extract_error_type("Login succeeded uid=u1"))


class ReportingTests(unittest.TestCase):
    def test_iqr_marks_a_clear_daily_spike(self) -> None:
        rows = []
        for day, count in enumerate([1, 1, 1, 1, 1, 1, 10], start=1):
            for index in range(count):
                rows.append(
                    {
                        "event_date": f"2026-08-{day:02d}",
                        "service": "payment-api",
                        "level": "ERROR",
                        "error_type": "ConnTimeout",
                        "request_id": f"r-{day}-{index}",
                    }
                )
        clean = pd.DataFrame(rows)

        services, daily, top_errors, summary = build_report_frames(clean)

        self.assertEqual(services.iloc[0]["service"], "payment-api")
        self.assertEqual(summary["high_anomaly_dates"], ["2026-08-07"])
        self.assertTrue(bool(daily.iloc[-1]["is_high_anomaly"]))
        self.assertEqual(top_errors.iloc[0]["error_type"], "ConnTimeout")


if __name__ == "__main__":
    unittest.main()
