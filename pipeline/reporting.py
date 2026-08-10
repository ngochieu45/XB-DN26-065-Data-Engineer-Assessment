from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def _daily_error_report(clean: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    all_dates = sorted(clean["event_date"].dropna().unique())
    errors = clean.loc[clean["level"] == "ERROR"]
    counts = errors.groupby("event_date").size().reindex(all_dates, fill_value=0)
    daily = counts.rename("error_count").reset_index()

    q1 = float(daily["error_count"].quantile(0.25)) if not daily.empty else 0.0
    q3 = float(daily["error_count"].quantile(0.75)) if not daily.empty else 0.0
    iqr = q3 - q1
    upper_bound = q3 + 1.5 * iqr
    daily["is_high_anomaly"] = daily["error_count"] > upper_bound
    return daily, {"q1": q1, "q3": q3, "iqr": iqr, "upper_bound": upper_bound}


def build_report_frames(
    clean: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    errors = clean.loc[clean["level"] == "ERROR"].copy()

    service_counts = (
        errors.groupby("service")
        .size()
        .rename("error_count")
        .sort_values(ascending=False)
        .reset_index()
    )
    service_counts.insert(0, "rank", range(1, len(service_counts) + 1))

    daily_counts, anomaly_threshold = _daily_error_report(clean)

    pair_counts = (
        errors.dropna(subset=["error_type"])
        .groupby(["error_type", "service"])
        .size()
        .rename("count")
        .reset_index()
    )
    top_rows: list[dict[str, Any]] = []
    if not pair_counts.empty:
        totals = (
            pair_counts.groupby("error_type")["count"]
            .sum()
            .sort_values(ascending=False)
            .head(3)
        )
        for rank, (error_type, total) in enumerate(totals.items(), start=1):
            services = pair_counts.loc[pair_counts["error_type"] == error_type].sort_values(
                ["count", "service"], ascending=[False, True]
            )
            breakdown = ", ".join(
                f"{row.service} ({int(row.count)})" for row in services.itertuples()
            )
            top_rows.append(
                {
                    "rank": rank,
                    "error_type": error_type,
                    "error_count": int(total),
                    "services": breakdown,
                }
            )
    top_errors = pd.DataFrame(
        top_rows, columns=["rank", "error_type", "error_count", "services"]
    )

    summary = {
        "total_clean_records": int(len(clean)),
        "total_error_records": int(len(errors)),
        "service_with_most_errors": (
            service_counts.iloc[0]["service"] if not service_counts.empty else None
        ),
        "highest_service_error_count": (
            int(service_counts.iloc[0]["error_count"]) if not service_counts.empty else 0
        ),
        "high_anomaly_dates": daily_counts.loc[
            daily_counts["is_high_anomaly"], "event_date"
        ].tolist(),
        "anomaly_method": "High outlier above Q3 + 1.5 * IQR",
        "anomaly_threshold": anomaly_threshold,
        "top_error_types": top_errors.to_dict(orient="records"),
    }
    return service_counts, daily_counts, top_errors, summary


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No data._"
    columns = list(frame.columns)
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    rows = []
    for values in frame.itertuples(index=False, name=None):
        rendered = [str(value).lower() if isinstance(value, bool) else str(value) for value in values]
        rows.append("| " + " | ".join(rendered) + " |")
    return "\n".join([header, separator, *rows])


def write_reports(
    clean: pd.DataFrame, quality: dict[str, Any], output_dir: str | Path
) -> dict[str, Any]:
    destination = Path(output_dir)
    service_counts, daily_counts, top_errors, summary = build_report_frames(clean)

    service_counts.to_csv(destination / "errors_by_service.csv", index=False)
    daily_counts.to_csv(destination / "errors_by_day.csv", index=False)
    top_errors.to_csv(destination / "top_error_types.csv", index=False)
    (destination / "analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    rejected = quality["counts"]["rejected_records"]
    reason_rows = pd.DataFrame(
        [
            {"reason": reason, "record_count": count}
            for reason, count in quality["rejected_by_reason"].items()
        ]
    )
    transformation_rows = pd.DataFrame(
        [
            {"transformation": name, "record_count": count}
            for name, count in quality["transformations"].items()
        ]
    )
    anomaly_dates = ", ".join(summary["high_anomaly_dates"]) or "None"
    report = f"""# Log Analysis Report

## Data quality

- Input lines: {quality['counts']['total_lines']}
- Clean records: {quality['counts']['clean_records']}
- Rejected or deduplicated records: {rejected}

{_markdown_table(reason_rows)}

## 1. Service with the most errors

**{summary['service_with_most_errors']}** has the most ERROR records: **{summary['highest_service_error_count']}**.

{_markdown_table(service_counts)}

## 2. Error count by day

High anomalies use the IQR rule: a count above `Q3 + 1.5 * IQR`.

High-anomaly date(s): **{anomaly_dates}**.

{_markdown_table(daily_counts)}

## 3. Top three error types

Messages are grouped by the stable error name after `ERR`; changing parameters such as `txn`, `uid`, and `code` are not part of the error type.

{_markdown_table(top_errors)}

## 4. Removed or normalized records

**{rejected}** records were rejected or deduplicated. They are written to `rejected_records.jsonl` with the source line number, reason, and original content.

{_markdown_table(reason_rows)}

Accepted records also received these normalization operations:

{_markdown_table(transformation_rows)}

Transformation counts are operation counts and may overlap: one accepted record can have both its timezone normalized and its missing optional `trace_id` filled with null.
"""
    (destination / "analysis_report.md").write_text(report, encoding="utf-8")
    return summary
