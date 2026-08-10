import tempfile
import unittest
from pathlib import Path

from kb.builder import build_kb, load_chunks, search


DOCS_DIR = Path("Xbrain_Assessment_DE_DataPack/data/docs")


class KnowledgeBaseTest(unittest.TestCase):
    def test_loads_all_docs_and_chunks_by_structure(self):
        chunks = load_chunks(DOCS_DIR)
        sources = {chunk.source_file for chunk in chunks}

        self.assertEqual(len(sources), 8)
        self.assertGreaterEqual(len(chunks), 20)
        self.assertIn("Quy định", {chunk.section for chunk in chunks})

    def test_marks_old_backup_policy_as_superseded(self):
        chunks = load_chunks(DOCS_DIR)
        v1_chunks = [chunk for chunk in chunks if chunk.source_file == "POL-01_chinh_sach_backup_v1.md"]
        v2_chunks = [chunk for chunk in chunks if chunk.source_file == "POL-01_chinh_sach_backup_v2.md"]

        self.assertTrue(v1_chunks)
        self.assertTrue(v2_chunks)
        self.assertTrue(all(chunk.is_superseded for chunk in v1_chunks))
        self.assertTrue(all(not chunk.is_superseded for chunk in v2_chunks))

    def test_search_prefers_current_backup_policy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            build_kb(DOCS_DIR, output_dir)

            results = search(output_dir / "kb.sqlite", "chính sách backup hiện hành sao lưu giữ bao lâu", top_k=3)

        self.assertTrue(results)
        self.assertEqual(results[0]["source_file"], "POL-01_chinh_sach_backup_v2.md")
        self.assertFalse(bool(results[0]["is_superseded"]))

    def test_search_finds_conn_timeout_faq(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            build_kb(DOCS_DIR, output_dir)

            results = search(output_dir / "kb.sqlite", "ERR ConnTimeout db-primary restart service", top_k=3)

        self.assertTrue(any(result["source_file"] == "FAQ-01_loi_thuong_gap.md" for result in results))


if __name__ == "__main__":
    unittest.main()

