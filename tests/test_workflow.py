"""Synthetic stories only. No user manuscript or real review is simulated here."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ENGINE = Path(__file__).parents[1] / "plugins/story-writer/scripts/story.py"
spec = importlib.util.spec_from_file_location("story", ENGINE)
story = importlib.util.module_from_spec(spec)
spec.loader.exec_module(story)


class Workflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.book = self.base / "中文作品"
        story.init(self.book, "测试故事", units=6, unit_label="幕", story_format="剧本", segment_label="场")
        self.source = self.base / "作者构想.md"
        self.source.write_text("第一幕：林舟寻找失踪的姐姐。\n林舟在码头拿到旧船票。\n秘密：姐姐是夜航船船长。", encoding="utf-8")
        self.sid = story.ingest(self.book, self.source, 1, "合成构想")["source_id"]
        self.initial = [
            self.fact("U-001", "unit", "第一幕", "目标", "林舟寻找失踪的姐姐", "林舟寻找失踪的姐姐"),
            self.fact("E-001", "entity", "林舟", "初始线索", "旧船票", "旧船票"),
            self.fact("K-001", "knowledge", "姐姐", "身份", "姐姐是夜航船船长", "姐姐是夜航船船长", reveal=None),
        ]
        self.proposal = self.write("facts.json", self.initial)
        self.pid = story.propose(self.book, self.sid, self.proposal)["proposal_id"]

    def write(self, name, data):
        path = self.base / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def fact(self, fid, kind, entity, key, value, quote, reveal=1):
        return {"id": fid, "kind": kind, "entity": entity, "key": key, "value": value, "unit": 1, "reveal_at": reveal, "known_since": {"林舟": 1} if reveal else {}, "quote": quote, "source_id": self.sid}

    def prepare(self, draft="林舟把旧船票放在桌上，决定去码头寻找姐姐。"):
        story.accept(self.book, self.pid, "测试作者", "测试夹具批准")
        c = {"chapter": 1, "unit": 1, "title": "旧船票", "pov": "林舟", "goals": ["前往码头"], "required_fact_ids": ["U-001", "E-001", "K-001"], "reveal_fact_ids": [], "allowed_new_entities": ["码头"], "author_basis": "测试夹具的任务授权"}
        self.cpath = self.write("contract.json", c)
        story.save_contract(self.book, self.cpath)
        self.draft = "工作区/草稿/0001.md"
        (self.book / self.draft).write_text(draft, encoding="utf-8")
        self.changes = self.write("changes.json", [])
        self.semantic_review()

    def semantic_review(self, verdict="pass", missing=False):
        text = (self.book / self.draft).read_text(encoding="utf-8")
        check = story.mechanical(self.book, 1, self.draft)
        dimensions = {name: {"verdict": verdict, "evidence": [text], "note": "仅为合成测试，用于校验流程，不代表真实质量审读。", "issues": []} for name in story.DIMENSIONS}
        if missing:
            del dimensions[story.DIMENSIONS[-1]]
        report = {"fingerprint": check["fingerprint"], "reviewer": "合成测试审读者", "dimensions": dimensions}
        self.rpath = self.write("semantic.json", report)
        return story.review(self.book, 1, self.draft, self.rpath)

    def settle(self):
        return story.settle(self.book, 1, self.draft, self.changes, "林舟携旧船票去码头。", "测试作者", "合成夹具批准")

    def test_candidates_do_not_pollute_canon(self):
        self.assertEqual(story.query(self.book)["facts"], [])
        self.assertFalse(story.doctor(self.book)["writing_ready"])
        with self.assertRaises(story.Invalid):
            story.accept(self.book, self.pid, "", "")
        story.accept(self.book, self.pid, "测试作者", "合成夹具批准")
        self.assertEqual(len(story.query(self.book)["facts"]), 3)

    def test_no_source_no_writing_contract(self):
        c = {"chapter": 1, "unit": 1, "title": "x", "pov": "x", "goals": ["x"], "required_fact_ids": ["U-001"], "reveal_fact_ids": [], "allowed_new_entities": [], "author_basis": "test"}
        with self.assertRaisesRegex(story.Invalid, "单元定位"):
            story.save_contract(self.book, self.write("c.json", c))

    def test_rejects_fabricated_quote(self):
        self.initial[0]["quote"] = "原文根本没有的内容"
        with self.assertRaisesRegex(story.Invalid, "引文"):
            story.propose(self.book, self.sid, self.write("bad.json", self.initial))

    def test_stale_draft_review_blocks_settle(self):
        self.prepare()
        (self.book / self.draft).write_text("林舟转身离开，船票留在桌上。", encoding="utf-8")
        with self.assertRaisesRegex(story.Invalid, "旧审读"):
            self.settle()
        self.assertEqual(len(story.accepted(self.book)), 1)

    def test_stale_contract_review_blocks_settle(self):
        self.prepare()
        c = json.loads(self.cpath.read_text())
        c["goals"] = ["先留在原地"]
        story.save_contract(self.book, self.write("new-c.json", c))
        with self.assertRaisesRegex(story.Invalid, "旧审读"):
            self.settle()

    def test_missing_or_unknown_semantic_review_blocks(self):
        self.prepare()
        with self.assertRaisesRegex(story.Invalid, "八维"):
            self.semantic_review(missing=True)
        result = self.semantic_review(verdict="unknown")
        self.assertEqual(len(result["blocking"]), 8)
        with self.assertRaisesRegex(story.Invalid, "未知"):
            self.settle()

    def test_open_issue_blocks_even_pass_verdict(self):
        self.prepare()
        report = json.loads(self.rpath.read_text())
        report["dimensions"][story.DIMENSIONS[0]]["issues"] = [{"status": "open", "detail": "转场缺少依据"}]
        story.review(self.book, 1, self.draft, self.write("open.json", report))
        with self.assertRaises(story.Invalid):
            self.settle()

    def test_secret_redacted_from_brief_and_scan_blocks(self):
        self.prepare()
        result = story.brief(self.book, 1)
        text = Path(result["path"]).read_text(encoding="utf-8")
        self.assertNotIn("姐姐是夜航船船长", text)
        self.assertIn("作者机密", text)
        (self.book / self.draft).write_text("林舟说：姐姐是夜航船船长。", encoding="utf-8")
        self.assertTrue(story.mechanical(self.book, 1, self.draft)["blocking"])

    def test_import_dedup_and_original_integrity(self):
        again = story.ingest(self.book, self.source, 1, None)
        self.assertEqual(again["status"], "already_imported")
        (self.book / f"原始资料/{self.sid}.original").write_text("偷偷改原件", encoding="utf-8")
        with self.assertRaisesRegex(story.Invalid, "原件"):
            story.doctor(self.book)

    def test_atomic_commit_idempotence_and_export(self):
        self.prepare()
        result = self.settle()
        self.assertEqual(result["status"], "settled")
        self.assertEqual(self.settle()["status"], "already_settled")
        self.assertEqual(len(story.accepted(self.book)), 2)
        exported = story.export(self.book, "导出/正文.md")
        self.assertEqual(exported["chapters"], 1)
        self.assertIn("第1场", Path(exported["path"]).read_text(encoding="utf-8"))
        with self.assertRaises(story.Invalid):
            story.export(self.book, "导出/正文.md")

    def test_failed_transaction_leaves_no_partial_canon(self):
        self.prepare()
        original = story.os.rename
        def fail_stage(src, dst):
            if "bundle-" in str(src):
                raise OSError("合成磁盘故障")
            return original(src, dst)
        with patch.object(story.os, "rename", side_effect=fail_stage):
            with self.assertRaises(OSError):
                self.settle()
        self.assertEqual(len(story.accepted(self.book)), 1)
        self.assertEqual(list((self.book / ".故事/暂存").iterdir()), [])
        self.assertTrue((self.book / self.draft).exists())
        self.settle()

    def test_source_version_revision_does_not_rewrite_history(self):
        self.prepare()
        self.settle()
        original = story.accepted(self.book)[1]["hash"]
        new = self.base / "修订.md"
        new.write_text("作者修订：姐姐是夜航船医师。", encoding="utf-8")
        sid = story.ingest(self.book, new, 1, "作者修订")["source_id"]
        f = self.fact("K-002", "knowledge", "姐姐", "身份", "姐姐是夜航船医师", "姐姐是夜航船医师", reveal=None)
        f.update(source_id=sid, supersedes="K-001", change_reason="作者改变未揭示的身份")
        proposal = story.propose(self.book, sid, self.write("rev.json", [f]))
        self.assertEqual(proposal["chapters_to_recheck"], [1])
        story.accept(self.book, proposal["proposal_id"], "测试作者", "批准合成修订")
        facts = story.query(self.book)["facts"]
        self.assertIn("K-002", [x["id"] for x in facts])
        self.assertNotIn("K-001", [x["id"] for x in facts])
        self.assertEqual(story.accepted(self.book)[1]["hash"], original)

    def test_backup_restores_complete_book_without_chat_memory(self):
        self.prepare()
        self.settle()
        result = story.backup(self.book, "导出/书仓.zip")
        new_root = self.base / "恢复后的中文书仓"
        story.restore(new_root, result["path"])
        self.assertEqual(story.query(self.book), story.query(new_root))
        self.assertEqual(story.doctor(new_root)["integrity"], "ok")
        self.assertEqual(len(story.accepted(new_root)), 2)
        with self.assertRaises(story.Invalid):
            story.restore(new_root, result["path"])

    def test_malicious_archive_rejected_without_partial_restore(self):
        bad = self.base / "坏包.zip"
        with zipfile.ZipFile(bad, "w") as z:
            z.writestr("../escape.txt", "x")
        target = self.base / "target"
        with self.assertRaisesRegex(story.Invalid, "相对路径"):
            story.restore(target, bad)
        self.assertFalse(target.exists())
        self.assertFalse((self.base / "escape.txt").exists())

    def test_more_than_four_units_and_dashboard_html_escaping(self):
        self.prepare()
        result = story.dashboard(self.book, "导出/账本.html")
        content = Path(result["path"]).read_text(encoding="utf-8")
        self.assertIn("<option>6</option>", content)
        cfg = self.write("config.json", {"title": "<script>alert(1)</script>"})
        story.configure(self.book, cfg)
        result = story.dashboard(self.book, "导出/账本2.html")
        self.assertIn("&lt;script&gt;", Path(result["path"]).read_text(encoding="utf-8"))

    def test_length_metric_and_config_invalidates_review(self):
        self.prepare()
        story.configure(self.book, self.write("cfg.json", {"length": {"metric": "characters", "min": 1, "target": 25, "max": 200}}))
        with self.assertRaisesRegex(story.Invalid, "旧审读"):
            self.settle()
        self.semantic_review()
        self.settle()

    def test_tampered_final_draft_detected(self):
        self.prepare()
        self.settle()
        draft = next((self.book / "定稿/事务").glob("*/正文.md"))
        draft.write_text("改过的定稿", encoding="utf-8")
        with self.assertRaisesRegex(story.Invalid, "定稿工件已改动"):
            story.doctor(self.book)

    def test_path_and_symlink_escape_rejected(self):
        with self.assertRaises(story.Invalid):
            story.under(self.book, "../../etc/passwd")
        (self.book / "外部").symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(story.Invalid):
            story.under(self.book, "外部/作者构想.md")


if __name__ == "__main__":
    unittest.main()
