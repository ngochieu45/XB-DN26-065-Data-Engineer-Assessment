from __future__ import annotations

import argparse
import json
from pathlib import Path

from .processing import process_jsonl
from .reporting import write_reports


DEFAULT_INPUT = Path("Xbrain_Assessment_DE_DataPack/data/app_logs_7days.jsonl")
DEFAULT_OUTPUT = Path("pipeline/output")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate, clean, and report on the seven-day application log dataset."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input JSONL file")
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT, help="Output directory"
    )
    return parser


def run(input_path: Path, output_dir: Path) -> dict:
    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    result = process_jsonl(input_path)

    result.clean.to_parquet(
        output_dir / "clean_logs.parquet", index=False, engine="pyarrow"
    )
    with (output_dir / "rejected_records.jsonl").open("w", encoding="utf-8") as stream:
        for item in result.rejected:
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")

    (output_dir / "data_quality_report.json").write_text(
        json.dumps(result.quality, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = write_reports(result.clean, result.quality, output_dir)
    return {"quality": result.quality, "analysis": summary}


def main() -> None:
    args = build_parser().parse_args()
    result = run(args.input, args.output)
    counts = result["quality"]["counts"]
    analysis = result["analysis"]
    print(
        f"Pipeline complete: {counts['clean_records']} clean, "
        f"{counts['rejected_records']} rejected/deduplicated."
    )
    print(
        "Most error-prone service: "
        f"{analysis['service_with_most_errors']} "
        f"({analysis['highest_service_error_count']} ERROR records)."
    )
    print(f"Outputs: {args.output.resolve()}")


if __name__ == "__main__":
    main()
