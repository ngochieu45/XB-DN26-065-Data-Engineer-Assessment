from __future__ import annotations

import argparse
import json
from pathlib import Path

from .builder import DEFAULT_DB_PATH, search


DEFAULT_EVAL_PATH = Path("kb/eval_questions.json")
DEFAULT_OUTPUT_DIR = Path("kb/output")


def load_eval_cases(eval_path: Path) -> list[dict[str, object]]:
    return json.loads(eval_path.read_text(encoding="utf-8"))


def evaluate_cases(eval_path: Path, db_path: Path, output_dir: Path, top_k: int = 3) -> list[dict[str, object]]:
    cases = load_eval_cases(eval_path)
    results: list[dict[str, object]] = []

    for case in cases:
        query = str(case["question"])
        retrieved = search(db_path, query, top_k=top_k)
        expected_sources = set(case["expected_sources"])
        top_sources = [row["source_file"] for row in retrieved]
        if not expected_sources:
            retrieval_hit = None
            status = "MANUAL"
        elif case["type"] == "multi-source":
            retrieval_hit = expected_sources.issubset(set(top_sources))
            status = "PASS" if retrieval_hit else "FAIL"
        else:
            retrieval_hit = bool(expected_sources.intersection(top_sources))
            status = "PASS" if retrieval_hit else "FAIL"

        result = {
            "id": case["id"],
            "type": case["type"],
            "question": query,
            "expected_sources": list(expected_sources),
            "retrieval_hit": retrieval_hit,
            "status": status,
            "top_sources": top_sources,
            "top_sections": [row["section"] for row in retrieved],
            "manual_groundedness_check": case["groundedness_criterion"],
            "expected_answer": case["expected_answer"],
        }
        results.append(result)

    write_eval_outputs(results, output_dir)
    return results


def write_eval_outputs(results: list[dict[str, object]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "eval_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    retrieval_cases = [result for result in results if result["retrieval_hit"] is not None]
    passed = sum(1 for result in retrieval_cases if result["retrieval_hit"])
    lines = [
        "# Kết quả eval KB",
        "",
        "Lần chạy eval này kiểm tra retrieval hit cho 10 câu hỏi đã chuẩn bị. Groundedness vẫn là bước kiểm tra thủ công bằng cách đối chiếu câu trả lời mong đợi với các source chunks được retrieve.",
        "",
        f"- Số case đã chạy: {len(results)}",
        f"- Số case kiểm tra retrieval: {len(retrieval_cases)}",
        f"- Retrieval hit PASS: {passed}",
        f"- Retrieval hit FAIL: {len(retrieval_cases) - passed}",
        f"- Số case out-of-scope cần kiểm tra thủ công: {len(results) - len(retrieval_cases)}",
        "",
        "| ID | Loại câu hỏi | Retrieval | Source mong đợi | Top source retrieve được |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in results:
        expected_sources = ", ".join(result["expected_sources"])  # type: ignore[arg-type]
        top_sources = ", ".join(result["top_sources"])  # type: ignore[arg-type]
        status = str(result["status"])
        lines.append(f"| {result['id']} | {result['type']} | {status} | `{expected_sources}` | `{top_sources}` |")

    (output_dir / "eval_results.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run retrieval eval for the mini KB.")
    parser.add_argument("--eval-file", type=Path, default=DEFAULT_EVAL_PATH)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    results = evaluate_cases(args.eval_file, args.db, args.output_dir, args.top_k)
    retrieval_cases = [result for result in results if result["retrieval_hit"] is not None]
    passed = sum(1 for result in retrieval_cases if result["retrieval_hit"])
    print(f"Eval retrieval hit: {passed}/{len(retrieval_cases)}; manual checks: {len(results) - len(retrieval_cases)}")


if __name__ == "__main__":
    main()
