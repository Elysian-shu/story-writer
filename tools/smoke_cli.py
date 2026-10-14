"""Exercise the actual CLI in a fresh synthetic book, including ZIP restoration."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).parents[1]
ENGINE = ROOT / "plugins/story-writer/scripts/story.py"


def main():
    with tempfile.TemporaryDirectory(prefix="story-smoke-") as temp:
        base = Path(temp)
        book = base / "合成短篇"
        calls = []
        def run(*args, target=book, expected=0):
            p = subprocess.run([sys.executable, str(ENGINE), "--book", str(target), *args], capture_output=True, text=True, encoding="utf-8")
            assert p.returncode == expected, (args, p.returncode, p.stderr, p.stdout)
            calls.append(args[0])
            return json.loads(p.stdout if p.stdout else p.stderr)
        def write(name, data):
            p = base / name
            p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return str(p)

        run("init", "--title", "合成短篇", "--format", "短篇", "--units", "1", "--unit-label", "篇", "--segment-label", "节")
        source = base / "作者构想.md"
        source.write_text("主人公阿宁要把寄错的信送回。", encoding="utf-8")
        sid = run("import-source", "--file", str(source), "--unit", "1")["source_id"]
        fact = {"id": "U-001", "kind": "unit", "entity": "阿宁", "key": "目标", "value": "把寄错的信送回", "unit": 1, "reveal_at": 1, "known_since": {"阿宁": 1}, "quote": "把寄错的信送回", "source_id": sid}
        pid = run("propose", "--source-id", sid, "--facts", write("facts.json", [fact]))["proposal_id"]
        assert not run("query")["facts"]
        run("accept", "--proposal", pid, "--author", "合成测试作者", "--note", "测试模拟批准，不是实际用户授权")
        c = {"chapter": 1, "unit": 1, "title": "寄错的信", "pov": "阿宁", "goals": ["决定送信"], "required_fact_ids": ["U-001"], "reveal_fact_ids": [], "allowed_new_entities": [], "author_basis": "仅测试合成任务"}
        run("contract", "--file", write("contract.json", c))
        brief = run("brief", "--chapter", "1")
        assert "第1节" in Path(brief["path"]).read_text(encoding="utf-8")
        draft = "工作区/草稿/0001.md"
        body = "阿宁没有拆信。他把信封放进口袋，循着寄件人的地址走出门。"
        (book / draft).write_text(body, encoding="utf-8")
        check = run("check", "--chapter", "1", "--draft", draft)
        dimensions = ["结构", "人物与关系", "情节因果", "信息披露", "线索伏笔", "节奏张力", "读者承诺", "文风表达"]
        report = {"fingerprint": check["fingerprint"], "reviewer": "合成测试轮次", "dimensions": {d: {"verdict": "pass", "evidence": [body], "note": "合成测试结构，非文学质量评价。", "issues": []} for d in dimensions}}
        run("review", "--chapter", "1", "--draft", draft, "--semantic", write("review.json", report))
        changes = write("changes.json", [])
        result = run("settle", "--chapter", "1", "--draft", draft, "--facts", changes, "--summary", "阿宁选择按地址送回信件。", "--author", "合成作者", "--note", "合成测试批准")
        assert result["status"] == "settled"
        assert run("doctor")["integrity"] == "ok"
        assert len(run("history")["transactions"]) == 2
        run("dashboard", "--out", "导出/账本.html")
        text = run("export", "--out", "导出/定稿.md")
        assert body in Path(text["path"]).read_text(encoding="utf-8")
        package = run("backup", "--out", "导出/最新书仓.zip")
        recovered = base / "新会话恢复"
        run("restore", "--file", package["path"], target=recovered)
        assert run("query") == run("query", target=recovered)
        # Preserve the true runner exit outcome for a real blocked review.
        (recovered / draft).write_text("TODO 待补充", encoding="utf-8")
        assert run("check", "--chapter", "1", "--draft", draft, target=recovered, expected=2)["blocking"]
        print(json.dumps({"status": "passed", "cli_invocations": len(calls), "commands": sorted(set(calls)), "materials": "synthetic_only", "real_story_quality_reviewed": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
