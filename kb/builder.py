from __future__ import annotations

import argparse
import json
import re
import sqlite3
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_DOCS_DIR = Path("Xbrain_Assessment_DE_DataPack/data/docs")
DEFAULT_OUTPUT_DIR = Path("kb/output")
DEFAULT_DB_PATH = DEFAULT_OUTPUT_DIR / "kb.sqlite"
DEFAULT_CHUNKS_PATH = DEFAULT_OUTPUT_DIR / "chunks.jsonl"
DEFAULT_REPORT_PATH = DEFAULT_OUTPUT_DIR / "build_report.md"


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source_file: str
    doc_id: str
    title: str
    section: str
    version: str | None
    issued_or_updated_date: str | None
    owner: str | None
    is_superseded: bool
    supersedes_previous: bool
    text: str


def parse_doc_metadata(path: Path, text: str) -> dict[str, str | bool | None]:
    lines = text.splitlines()
    title_line = next((line for line in lines if line.startswith("# ")), "")
    title = title_line.lstrip("# ").strip() or path.stem

    doc_id = path.stem.split("_", 1)[0]
    if title:
        doc_id = title.split("—", 1)[0].strip() or doc_id

    metadata_line = next((line for line in lines if "Phiên bản" in line or "Ban hành:" in line or "Cập nhật:" in line), "")

    version_match = re.search(r"Phiên bản\s+([0-9.]+)", metadata_line)
    issued_match = re.search(r"(?:Ban hành|Cập nhật):\s*([0-9]{2}/[0-9]{4})", metadata_line)
    owner_match = re.search(r"\*\*(.+?)\*\*", metadata_line)

    owner = None
    if owner_match:
        owner_parts = [part.strip() for part in owner_match.group(1).split("—")]
        owner = owner_parts[-1] if owner_parts else None

    return {
        "source_file": path.name,
        "doc_id": doc_id,
        "title": title,
        "version": version_match.group(1) if version_match else None,
        "issued_or_updated_date": issued_match.group(1) if issued_match else None,
        "owner": owner,
        "supersedes_previous": "Thay thế phiên bản trước" in metadata_line,
    }


def split_markdown_sections(text: str) -> list[tuple[str, str]]:
    lines = text.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_heading = "Tổng quan"
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_lines:
                sections.append((current_heading, current_lines))
            current_heading = line.lstrip("# ").strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_heading, current_lines))

    cleaned: list[tuple[str, str]] = []
    for heading, body_lines in sections:
        body = "\n".join(body_lines).strip()
        if body:
            cleaned.append((heading, body))
    return cleaned


def _version_key(value: str | None) -> tuple[int, ...]:
    if not value:
        return (0,)
    return tuple(int(part) for part in re.findall(r"\d+", value)) or (0,)


def load_chunks(docs_dir: Path) -> list[Chunk]:
    raw_docs: list[tuple[dict[str, str | bool | None], list[tuple[str, str]]]] = []
    for path in sorted(docs_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        raw_docs.append((parse_doc_metadata(path, text), split_markdown_sections(text)))

    latest_by_doc_id: dict[str, tuple[int, ...]] = {}
    doc_ids_with_replacement: set[str] = set()
    for metadata, _sections in raw_docs:
        doc_id = str(metadata["doc_id"])
        latest_by_doc_id[doc_id] = max(latest_by_doc_id.get(doc_id, (0,)), _version_key(metadata["version"]))  # type: ignore[arg-type]
        if metadata["supersedes_previous"]:
            doc_ids_with_replacement.add(doc_id)

    chunks: list[Chunk] = []
    for metadata, sections in raw_docs:
        doc_id = str(metadata["doc_id"])
        version = metadata["version"]
        is_superseded = bool(doc_id in doc_ids_with_replacement and _version_key(version) < latest_by_doc_id[doc_id])  # type: ignore[arg-type]
        source_stem = Path(str(metadata["source_file"])).stem

        for index, (section, section_text) in enumerate(sections, start=1):
            chunk_id = f"{source_stem}-{index:02d}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    source_file=str(metadata["source_file"]),
                    doc_id=doc_id,
                    title=str(metadata["title"]),
                    section=section,
                    version=version if isinstance(version, str) else None,
                    issued_or_updated_date=(
                        metadata["issued_or_updated_date"] if isinstance(metadata["issued_or_updated_date"], str) else None
                    ),
                    owner=metadata["owner"] if isinstance(metadata["owner"], str) else None,
                    is_superseded=is_superseded,
                    supersedes_previous=bool(metadata["supersedes_previous"]),
                    text=section_text,
                )
            )
    return chunks


def build_index(chunks: Iterable[Chunk], db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE chunks (
                id INTEGER PRIMARY KEY,
                chunk_id TEXT NOT NULL UNIQUE,
                source_file TEXT NOT NULL,
                doc_id TEXT NOT NULL,
                title TEXT NOT NULL,
                section TEXT NOT NULL,
                version TEXT,
                issued_or_updated_date TEXT,
                owner TEXT,
                is_superseded INTEGER NOT NULL,
                supersedes_previous INTEGER NOT NULL,
                text TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE VIRTUAL TABLE chunks_fts USING fts5(
                chunk_id UNINDEXED,
                searchable_text,
                tokenize = 'unicode61'
            )
            """
        )

        for chunk in chunks:
            insert_cursor = conn.execute(
                """
                INSERT INTO chunks (
                    chunk_id, source_file, doc_id, title, section, version,
                    issued_or_updated_date, owner, is_superseded,
                    supersedes_previous, text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.chunk_id,
                    chunk.source_file,
                    chunk.doc_id,
                    chunk.title,
                    chunk.section,
                    chunk.version,
                    chunk.issued_or_updated_date,
                    chunk.owner,
                    int(chunk.is_superseded),
                    int(chunk.supersedes_previous),
                    chunk.text,
                ),
            )
            original_text = f"{chunk.title}\n{chunk.section}\n{chunk.text}"
            searchable_text = f"{original_text}\n{normalize_for_search(original_text)}"
            conn.execute(
                "INSERT INTO chunks_fts(rowid, chunk_id, searchable_text) VALUES (?, ?, ?)",
                (insert_cursor.lastrowid, chunk.chunk_id, searchable_text),
            )
            insert_cursor.close()
        conn.commit()
    finally:
        conn.close()


def write_chunks(chunks: list[Chunk], chunks_path: Path) -> None:
    chunks_path.parent.mkdir(parents=True, exist_ok=True)
    with chunks_path.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(asdict(chunk), ensure_ascii=False, sort_keys=True) + "\n")


def write_build_report(chunks: list[Chunk], docs_dir: Path, db_path: Path, report_path: Path) -> None:
    by_file: dict[str, int] = {}
    missing_counts = {"version": 0, "issued_or_updated_date": 0, "owner": 0}
    superseded_chunks = 0

    for chunk in chunks:
        by_file[chunk.source_file] = by_file.get(chunk.source_file, 0) + 1
        superseded_chunks += int(chunk.is_superseded)
        for field in missing_counts:
            if getattr(chunk, field) is None:
                missing_counts[field] += 1

    lines = [
        "# Báo cáo build KB",
        "",
        "## Tóm tắt",
        "",
        f"- Thư mục tài liệu nguồn: `{docs_dir.as_posix()}`",
        f"- SQLite index: `{db_path.as_posix()}`",
        f"- Số tài liệu đọc được: {len(by_file)}",
        f"- Số chunk tạo ra: {len(chunks)}",
        f"- Số chunk thuộc tài liệu đã bị thay thế: {superseded_chunks}",
        "",
        "## Quyết định chunking",
        "",
        "KB dùng structure-based chunking. Mỗi tài liệu Markdown được chia theo heading/section để từng phần SOP, policy, FAQ, guide và runbook vẫn giữ đủ ngữ cảnh khi được retrieve độc lập.",
        "",
        "## Số chunk thiếu metadata",
        "",
        "| Trường | Số chunk thiếu |",
        "| --- | ---: |",
    ]
    for field, count in missing_counts.items():
        lines.append(f"| `{field}` | {count} |")

    lines.extend(["", "## Số chunk theo tài liệu nguồn", "", "| Tài liệu nguồn | Số chunk |", "| --- | ---: |"])
    for source_file, count in sorted(by_file.items()):
        lines.append(f"| `{source_file}` | {count} |")

    lines.extend(
        [
            "",
            "## Xử lý mâu thuẫn tài liệu",
            "",
            "`POL-01_chinh_sach_backup_v2.md` được đánh dấu là chính sách backup hiện hành vì là phiên bản 2.0, ban hành 05/2026 và ghi rõ thay thế phiên bản trước. Các chunk từ `POL-01_chinh_sach_backup_v1.md` vẫn được giữ để audit nhưng được đánh dấu `is_superseded=true` để search ưu tiên bản hiện hành.",
            "",
        ]
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def normalize_for_search(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    without_marks = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return without_marks.lower()


def tokenize_query(query: str) -> list[str]:
    query = normalize_for_search(query)
    tokens = re.findall(r"[a-zA-Z0-9_]+", query)
    stopwords = {
        "neu",
        "va",
        "thi",
        "can",
        "the",
        "nao",
        "hoac",
        "duoc",
        "co",
        "la",
        "gi",
        "trong",
        "cho",
        "cua",
    }
    return [token for token in tokens if len(token) > 1 and token not in stopwords]


def build_fts_query(query: str) -> str:
    tokens = tokenize_query(query)
    expanded_tokens = []
    for token in tokens:
        expanded_tokens.append(token)
        lowered = token.lower()
        if lowered == "escalate":
            expanded_tokens.extend(["escalation", "p1", "p2", "muc", "su", "co"])
        if lowered == "escalation":
            expanded_tokens.extend(["p1", "p2", "muc", "su", "co"])
        if lowered == "restart":
            expanded_tokens.extend(["khoi", "dong"])
    tokens = expanded_tokens
    if not tokens:
        return '""'
    return " OR ".join(f'"{token}"' for token in tokens)


def search(db_path: Path, query: str, top_k: int = 3) -> list[dict[str, object]]:
    fts_query = build_fts_query(query)
    candidate_limit = max(top_k * 5, top_k)
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT
                c.chunk_id,
                c.source_file,
                c.doc_id,
                c.title,
                c.section,
                c.version,
                c.issued_or_updated_date,
                c.owner,
                c.is_superseded,
                c.text,
                bm25(chunks_fts) AS lexical_score
            FROM chunks_fts
            JOIN chunks c ON c.id = chunks_fts.rowid
            WHERE chunks_fts MATCH ?
            ORDER BY c.is_superseded ASC, lexical_score ASC
            LIMIT ?
            """,
            (fts_query, candidate_limit),
        )
        rows = cursor.fetchall()
        candidates = [dict(row) for row in rows]
        cursor.close()
    finally:
        conn.close()
    return diversify_sources(candidates, top_k)


def diversify_sources(candidates: list[dict[str, object]], top_k: int) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    seen_sources: set[object] = set()

    for candidate in candidates:
        source_file = candidate["source_file"]
        if source_file in seen_sources:
            continue
        selected.append(candidate)
        seen_sources.add(source_file)
        if len(selected) == top_k:
            return selected

    for candidate in candidates:
        if candidate in selected:
            continue
        selected.append(candidate)
        if len(selected) == top_k:
            break

    return selected


def build_kb(docs_dir: Path, output_dir: Path) -> list[Chunk]:
    chunks = load_chunks(docs_dir)
    db_path = output_dir / "kb.sqlite"
    build_index(chunks, db_path)
    write_chunks(chunks, output_dir / "chunks.jsonl")
    write_build_report(chunks, docs_dir, db_path, output_dir / "build_report.md")
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and query the Part B mini knowledge base.")
    subparsers = parser.add_subparsers(dest="command")

    build_parser = subparsers.add_parser("build", help="Build chunks and SQLite FTS index.")
    build_parser.add_argument("--docs-dir", type=Path, default=DEFAULT_DOCS_DIR)
    build_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)

    query_parser = subparsers.add_parser("query", help="Search the SQLite FTS index.")
    query_parser.add_argument("query")
    query_parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    query_parser.add_argument("--top-k", type=int, default=3)

    args = parser.parse_args()

    if args.command in (None, "build"):
        chunks = build_kb(args.docs_dir, args.output_dir)
        print(f"Built KB with {len(chunks)} chunks from {args.docs_dir}")
        return

    if args.command == "query":
        for index, result in enumerate(search(args.db, args.query, args.top_k), start=1):
            print(f"{index}. {result['source_file']} | {result['section']} | superseded={bool(result['is_superseded'])}")
            print(str(result["text"]).replace("\n", " ")[:350])
            print()


if __name__ == "__main__":
    main()
