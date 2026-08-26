import json
import sys
import tempfile
import unittest
from pathlib import Path

# record_skill_usage.py는 아직 존재하지 않는다 — 이 import는 실패해야 한다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from record_skill_usage import record_skill_usage


class RecordSkillUsageTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.stats_path = Path(self.tmpdir.name) / "skill-stats.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_first_call_creates_entry_with_count_1(self):
        payload = {"tool_input": {"skill": "claude-api"}}
        stats = record_skill_usage(payload, self.stats_path)
        self.assertEqual(stats, {"claude-api": 1})

    def test_second_call_increments_existing_entry(self):
        payload = {"tool_input": {"skill": "claude-api"}}
        record_skill_usage(payload, self.stats_path)
        stats = record_skill_usage(payload, self.stats_path)
        self.assertEqual(stats, {"claude-api": 2})

    def test_different_skills_tracked_separately(self):
        record_skill_usage({"tool_input": {"skill": "claude-api"}}, self.stats_path)
        stats = record_skill_usage({"tool_input": {"skill": "skill-stat"}}, self.stats_path)
        self.assertEqual(stats, {"claude-api": 1, "skill-stat": 1})

    def test_missing_skill_name_does_not_crash_or_write(self):
        payload = {"tool_input": {}}
        stats = record_skill_usage(payload, self.stats_path)
        self.assertEqual(stats, {})
        self.assertFalse(self.stats_path.exists())

    def test_stats_persisted_to_file(self):
        record_skill_usage({"tool_input": {"skill": "claude-api"}}, self.stats_path)
        on_disk = json.loads(self.stats_path.read_text())
        self.assertEqual(on_disk, {"claude-api": 1})

    def test_corrupt_existing_file_is_treated_as_empty(self):
        self.stats_path.write_text("not json")
        stats = record_skill_usage({"tool_input": {"skill": "claude-api"}}, self.stats_path)
        self.assertEqual(stats, {"claude-api": 1})


if __name__ == "__main__":
    unittest.main()
