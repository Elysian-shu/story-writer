#!/usr/bin/env python3
"""Local, source-backed writing ledger. Python 3.10+, no external dependencies."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import zipfile

VERSION = "0.1.0"
DIMENSIONS = ["结构", "人物与关系", "情节因果", "信息披露", "线索伏笔", "节奏张力", "读者承诺", "文风表达"]
KINDS = {"unit", "entity", "clue", "timeline", "knowledge", "promise", "style", "rule", "theme", "outline"}
ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")


class Invalid(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise Invalid(message)


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else packed(value)).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def stamp():
    return datetime.now(timezone.utc).isoformat()


def under(root, relative):
    p = Path(relative)
    need(not p.is_absolute() and ".." not in p.parts, "只允许书仓内相对路径")
    target = (root / p).resolve()
    need(target.is_relative_to(root), "路径或符号链接越出书仓")
    return target


def put(path, content):
    """Atomic file replacement. Caller holds book lock for mutable files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = content if isinstance(content, bytes) else content.encode("utf-8")
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def put_json(path, data):
    put(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


@contextmanager
def lock(root):
    p = under(root, ".故事/写锁")
    try:
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as e:
        raise Invalid("书仓正在写入或有中断遗留写锁；核对写入进程后再处理写锁") from e
    try:
        os.write(fd, packed({"pid": os.getpid(), "created": stamp()}))
        os.close(fd)
        yield
    finally:
        p.unlink(missing_ok=True)


def config(root):
    return load(under(root, ".故事/项目.json"))


def accepted(root):
    """Accepted directory bundles are the sole canonical ledger."""
    base = under(root, "定稿/事务")
    records, parent = [], None
    for path in sorted(base.iterdir()):
        need(path.is_dir() and not path.is_symlink(), "事务目录存在非预期文件或符号链接")
        checked = under(root, str(path.relative_to(root)))
        item = load(checked / "事务.json")
        body = {k: v for k, v in item.items() if k != "hash"}
        need(item.get("hash") == digest(body), f"事务哈希损坏：{path.name}")
        need(item["seq"] == len(records) + 1 and item["parent"] == parent, "事务链断裂")
        need(path.name == f'{item["seq"]:06d}-{item["hash"][:12]}', "事务目录与记录不符")
        for name, sha in item.get("files", {}).items():
            f = under(checked, name)
            need(f.is_file() and digest(f.read_bytes()) == sha, f"定稿工件已改动：{name}")
        records.append(item)
        parent = item["hash"]
    return records


def facts_from(records):
    result = {}
    history_ids = set()
    for record in records:
        for fact in record.get("facts", []):
            need(fact["id"] not in history_ids, "事实编号重复；历史修订须使用新编号")
            history_ids.add(fact["id"])
            if fact.get("supersedes"):
                need(fact["supersedes"] in result, "修订引用不存在或已失效的事实")
                del result[fact["supersedes"]]
            result[fact["id"]] = fact
    return result


def checked_source(root, source_id):
    need(ID.fullmatch(source_id), "资料编号无效")
    meta = load(under(root, f"原始资料/{source_id}.json"))
    need(meta.get("source_id") == source_id and source_id == "S-" + meta["sha256"][:20], "来源元数据编号不符")
    data = under(root, f"原始资料/{source_id}.txt").read_bytes()
    need(digest(data) == meta["sha256"], "原始资料已改动；请作为新版本重新导入")
    original = under(root, f"原始资料/{source_id}.original").read_bytes()
    need(digest(original) == meta["original_sha256"], "来源原件已改动")
    return data.decode("utf-8"), meta


def validate_facts(facts, text, source_id=None, existing=None):
    need(isinstance(facts, list) and facts, "事实列表不能为空")
    seen, slots = set(), set()
    for f in facts:
        need(isinstance(f, dict), "事实须为对象")
        need(set(["id", "kind", "entity", "key", "value", "unit", "reveal_at", "known_since", "quote"]).issubset(f), "事实字段不完整，见数据规范")
        need(isinstance(f["id"], str) and ID.fullmatch(f["id"]) and f["id"] not in seen, "事实编号非法或重复")
        seen.add(f["id"])
        need(f["kind"] in KINDS, "未知事实类型")
        need(type(f["unit"]) is int and f["unit"] >= 1, "单元号须为正整数")
        for key in ("entity", "key", "value", "quote"):
            need(isinstance(f[key], str) and f[key].strip(), f"{key} 不能为空")
        need(f["quote"] in text, f'引文未出现在原文：{f["id"]}')
        need(f["reveal_at"] is None or type(f["reveal_at"]) is int and f["reveal_at"] > 0, "披露章须为正整数或 null（作者机密）")
        need(isinstance(f["known_since"], dict), "知情范围须为人物到章号的映射")
        need(all(isinstance(k, str) and k.strip() and type(v) is int and v > 0 for k, v in f["known_since"].items()), "知情时间不合法")
        slot = (f["kind"], f["entity"], f["key"])
        need(slot not in slots, "同批事实存在重复属性，先拆分或裁决")
        slots.add(slot)
        if source_id is not None:
            need(f.get("source_id") == source_id, "事实资料编号不符")
        if f.get("supersedes"):
            need(source_id is not None, "历史修订必须走来源提案，不可混入正文定稿")
            need(isinstance(f.get("change_reason"), str) and f["change_reason"].strip(), "修订须说明原因")
            if existing is not None:
                need(f["supersedes"] in existing, "修订引用不存在或已失效的事实")
                old = existing[f["supersedes"]]
                need((old["kind"], old["entity"], old["key"]) == slot, "修订只能替换同一属性")
        if existing is not None:
            need(f["id"] not in existing, f'事实已存在：{f["id"]}')
            for old in existing.values():
                need((old["kind"], old["entity"], old["key"]) != slot or f.get("supersedes") == old["id"], f'属性已有事实 {old["id"]}；新增状态请使用带时间/章号的 key，设定冲突先裁决')


def append_bundle(root, body, files=None):
    records = accepted(root)
    body = dict(body, seq=len(records) + 1, parent=records[-1]["hash"] if records else None, created=stamp())
    files = files or {}
    body["files"] = {name: digest(data) for name, data in files.items()}
    body["hash"] = digest(body)
    stage_base = under(root, ".故事/暂存")
    stage_base.mkdir(exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="bundle-", dir=stage_base))
    try:
        for name, data in files.items():
            put(under(stage, name), data)
        put_json(stage / "事务.json", body)
        target = under(root, f'定稿/事务/{body["seq"]:06d}-{body["hash"][:12]}')
        os.rename(stage, target)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return body


def init(root, title, units=1, unit_label="卷", story_format="小说", profile="通用", segment_label="章"):
    need(isinstance(title, str) and title.strip(), "作品名不能为空")
    need(type(units) is int and units > 0, "单元数须为正整数")
    need(all(isinstance(x, str) and x.strip() for x in (unit_label, story_format, profile, segment_label)), "作品格式字段不能为空")
    need(not (root / ".故事/项目.json").exists(), "书仓已初始化，不覆盖现有内容")
    need(not root.exists() or not any(root.iterdir()), "初始化需要空目录，避免混入既有作品")
    root.mkdir(parents=True, exist_ok=True)
    for folder in [".故事/暂存", "原始资料", "工作区/候选", "工作区/章合同", "工作区/草稿", "工作区/审读", "工作区/备料", "定稿/事务", "导出", "世界书", "故事单元"]:
        under(root, folder).mkdir(parents=True, exist_ok=True)
    put_json(root / ".故事/项目.json", {"schema_version": 1, "title": title, "units": units, "unit_label": unit_label, "format": story_format, "profile": profile, "segment_label": segment_label, "plugin_version": VERSION, "length": None})
    put(root / "作品契约.md", f"# 《{title}》作品契约（待确认）\n\n形式：{story_format}；审读侧重：{profile}。\n题材、主题、叙事视角、人物弧线、文风和篇幅均待作者设定或现有资料确定。\n本文件是作者说明；运行时约束由已确认事实与段落合同承载。\n不能从书名或单元编号推断既定剧情。\n")
    for i in range(1, units + 1):
        put(under(root, f"故事单元/单元{i:02d}/单元卡.md"), f"# 第{i}{unit_label} · 待确认\n\n目标、范围、人物选择、因果链、信息披露、读者承诺、回收计划等待作者构想或既有资料。\n本文件为整理模板，不能作为已确认设定。\n")
    put(root / "世界书/接入说明.md", "# 世界书\n\n角色、组织、地点、规则、人物关系须从来源提案入档。\nMarkdown 整理笔记不自动成为正史；query 返回已确认账本。\n")
    return {"status": "initialized", "book": str(root), "units": units, "canonical": False}


def ingest(root, path, unit, label):
    need(type(unit) is int and 1 <= unit <= config(root)["units"], "单元号超出作品范围")
    source = Path(path).resolve()
    need(source.is_file(), "资料文件不存在")
    need(source.suffix.lower() in {".md", ".txt"}, "当前支持 UTF-8 Markdown/TXT；其他格式先保留原件并转换")
    raw = source.read_bytes()
    text = raw.decode("utf-8-sig")
    need(text.strip(), "资料为空")
    data = text.encode("utf-8")
    sid = "S-" + digest(data)[:20]
    with lock(root):
        meta_path = under(root, f"原始资料/{sid}.json")
        if meta_path.exists():
            _, old = checked_source(root, sid)
            need(old["unit"] == unit, "相同原文已归入其他单元；跨单元信息请在提案中标明，不重复导入")
            return dict(status="already_imported", source_id=sid)
        put(under(root, f"原始资料/{sid}.txt"), data)
        put(under(root, f"原始资料/{sid}.original"), raw)
        put_json(meta_path, {"source_id": sid, "unit": unit, "label": label or source.name, "sha256": digest(data), "original_sha256": digest(raw), "created": stamp()})
    return {"status": "imported", "source_id": sid, "canonical": False}


def propose(root, sid, path):
    with lock(root):
        text, meta = checked_source(root, sid)
        facts = load(path)
        validate_facts(facts, text, sid, facts_from(accepted(root)))
        need(all(f["unit"] <= config(root)["units"] for f in facts), "事实单元号超出作品范围")
        prior_ids = {f["id"] for r in accepted(root) for f in r.get("facts", [])}
        need(not prior_ids.intersection(f["id"] for f in facts), "事实编号曾使用，不能复用历史编号")
        proposal = {"source_id": sid, "source_sha256": meta["sha256"], "original_sha256": meta["original_sha256"], "facts": facts}
        pid = "P-" + digest(proposal)[:20]
        target = under(root, f"工作区/候选/{pid}.json")
        if not target.exists():
            put_json(target, proposal)
    revisions = [f.get("supersedes") for f in facts if f.get("supersedes")]
    impacted = [r["chapter"] for r in accepted(root) if r["type"] == "chapter"] if revisions else []
    return {"status": "proposed", "proposal_id": pid, "canonical": False, "replaces": revisions, "chapters_to_recheck": impacted, "note": "修订影响保守列出所有定稿，不会自动重写历史" if revisions else "等作者确认"}


def decision(author, note):
    need(author and author.strip() and note and note.strip(), "需记录真实作者裁决人及其指令依据，不能代作者批准")
    return {"author": author, "note": note}


def accept(root, pid, author, note):
    need(ID.fullmatch(pid), "提案编号无效")
    approval = decision(author, note)
    with lock(root):
        for record in accepted(root):
            if record.get("proposal_id") == pid:
                return {"status": "already_accepted", "hash": record["hash"]}
        proposal = load(under(root, f"工作区/候选/{pid}.json"))
        need(pid == "P-" + digest(proposal)[:20], "候选已改动，须重新提交提案")
        text, meta = checked_source(root, proposal["source_id"])
        need(meta["sha256"] == proposal["source_sha256"], "提案来源版本已变")
        need(meta["original_sha256"] == proposal["original_sha256"], "提案来源原件已变")
        records = accepted(root)
        prior_ids = {f["id"] for r in records for f in r.get("facts", [])}
        need(not prior_ids.intersection(f["id"] for f in proposal["facts"]), "事实编号曾使用")
        validate_facts(proposal["facts"], text, proposal["source_id"], facts_from(accepted(root)))
        need(all(f["unit"] <= config(root)["units"] for f in proposal["facts"]), "提案引用超出当前配置的单元")
        item = append_bundle(root, {"type": "canon", "proposal_id": pid, **proposal, "decision": approval})
    return {"status": "accepted", "hash": item["hash"]}


def validate_contract(root, c):
    need(isinstance(c, dict), "章合同须为对象")
    required = {"chapter", "unit", "title", "pov", "goals", "required_fact_ids", "reveal_fact_ids", "allowed_new_entities", "author_basis"}
    need(required <= set(c), "章合同字段不完整")
    need(type(c["chapter"]) is int and c["chapter"] > 0 and type(c["unit"]) is int and c["unit"] >= 1, "章号或单元号无效")
    for key in ("title", "pov", "author_basis"):
        need(isinstance(c[key], str) and c[key].strip(), f"合同 {key} 不能为空")
    for key in ("goals", "required_fact_ids", "reveal_fact_ids", "allowed_new_entities"):
        need(isinstance(c[key], list) and all(isinstance(x, str) and x.strip() for x in c[key]), f"合同 {key} 格式无效")
        need(len(c[key]) == len(set(c[key])), f"合同 {key} 重复")
    need(c["goals"], "合同必须包含本章目标")
    need(c["unit"] <= config(root)["units"], "合同单元号超出作品范围")
    facts = facts_from(accepted(root))
    need(any(f["kind"] == "unit" and f["unit"] == c["unit"] for f in facts.values()), "本单元缺少已确认的单元定位事实，不能凭空开写")
    need(c["required_fact_ids"], "合同需绑定已确认资料")
    for fid in c["required_fact_ids"] + c["reveal_fact_ids"]:
        need(fid in facts, f"合同引用未知事实：{fid}")
    need(set(c["reveal_fact_ids"]) <= set(c["required_fact_ids"]), "披露事实必须进入本章资料范围")
    return facts


def save_contract(root, path):
    with lock(root):
        c = load(path)
        validate_contract(root, c)
        need(not any(r.get("chapter") == c["chapter"] for r in accepted(root)), "该章已定稿，不能替换章合同")
        put_json(under(root, f'工作区/章合同/{c["chapter"]:04d}.json'), c)
    return {"status": "contract_saved", "chapter": c["chapter"]}


def contract(root, chapter):
    c = load(under(root, f"工作区/章合同/{chapter:04d}.json"))
    validate_contract(root, c)
    return c


def visible(f, c):
    return f["id"] in c["reveal_fact_ids"] or f["reveal_at"] is not None and f["reveal_at"] <= c["chapter"]


def brief(root, chapter):
    with lock(root):
        c = contract(root, chapter)
        facts = facts_from(accepted(root))
        cfg = config(root)
        text = [f'# 第{chapter}{cfg["segment_label"]}《{c["title"]}》写作任务书', f'单元号：{c["unit"]}；视角：{c["pov"]}', "## 目标"]
        text.insert(2, f'作品形式：{cfg["format"]}；审读侧重：{cfg["profile"]}')
        text.extend("- " + x for x in c["goals"])
        text.append("## 可用于本章的事实（读者可知不等于视角人物可知）")
        for fid in c["required_fact_ids"]:
            f = facts[fid]
            if visible(f, c):
                knows = f["known_since"].get(c["pov"])
                status = "已知" if knows is not None and knows <= chapter else "未登记为已知；须在正文安排获得途径"
                text.append(f'- {fid} | {f["entity"]} / {f["key"]}：{f["value"]}；视角状态：{status}')
            else:
                text.append(f"- {fid}：作者机密，内容不进入起草包；禁止提前披露")
        text.append("## 连续性补料")
        text.append("为避免旧摘要泄露尚未披露的事实，本版不自动混入自由文本摘要。审读时读取完整账本；起草仅使用本合同可披露事实。")
        text.extend(["## 写作纪律", "新增人物只可使用合同允许名单；新增事实先留候选。", "先分清真实事实、人物判断与叙述信息；人物必须有合理的知情途径。", "依据作品形式与本段目标安排事件、人物和主题；不强制高潮或机械套用 60/20/20 比例。", "此备料包已遮蔽作者机密；语义审读另读完整账本，禁止把 query 的全部机密复制给起草。"])
        out = under(root, f"工作区/备料/{chapter:04d}.md")
        put(out, "\n\n".join(text) + "\n")
    return {"status": "brief_saved", "path": str(out)}


def snapshot(root, chapter, draft):
    doctor(root)
    c = contract(root, chapter)
    records = accepted(root)
    text = under(root, draft).read_bytes().decode("utf-8")
    need(text.strip(), "草稿为空")
    identity = {"chapter": chapter, "draft": draft, "draft_sha256": digest(text.encode()), "contract_sha256": digest(c), "ledger_head": records[-1]["hash"] if records else None, "config_sha256": digest(config(root))}
    return c, records, text, identity, digest(identity)


def mechanical(root, chapter, draft):
    c, records, text, identity, fp = snapshot(root, chapter, draft)
    blocks = []
    if re.search(r"TODO|待补充|待填写|\{\{.+?\}\}", text):
        blocks.append("草稿包含未完成标记")
    for f in facts_from(records).values():
        if not visible(f, c) and len(f["value"]) >= 4 and f["value"] in text:
            blocks.append(f'可能提前披露 {f["id"]}；更改披露安排须有作者依据')
    count = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\U00020000-\U0002FA1F]", text))
    length = config(root).get("length")
    if length is not None:
        need(isinstance(length, dict) and all(type(length.get(k)) is int and length[k] > 0 for k in ("min", "target", "max")) and length["min"] <= length["target"] <= length["max"], "篇幅配置错误")
        metric = length.get("metric", "hanzi")
        need(metric in {"hanzi", "words", "characters"}, "篇幅口径须为 hanzi/words/characters")
        measured = {"hanzi": count, "words": len(text.split()), "characters": len(re.sub(r"\s", "", text))}[metric]
        if not length["min"] <= measured <= length["max"]:
            blocks.append("草稿篇幅不在作者约定范围内")
    return {"fingerprint": fp, "identity": identity, "counts": {"hanzi": count, "words": len(text.split()), "characters": len(re.sub(r"\s", "", text))}, "length_configured": length is not None, "blocking": blocks, "semantic_dimensions": DIMENSIONS, "limits": "仅精确文本泄密和结构检查；语义因果、OOC、公平推理必须另行审读。空格分词不适合无空格语言，改用 characters/hanzi"}


def validate_semantic(report, fp, text):
    need(isinstance(report, dict), "审读须为 JSON 对象")
    need(report.get("fingerprint") == fp, "审读输入已变化或缺少指纹，须重新审读")
    need(isinstance(report.get("reviewer"), str) and report["reviewer"].strip(), "须记录实际审读者")
    modules = report.get("dimensions", {})
    need(isinstance(modules, dict), "审读维度须为对象")
    need(set(modules) == set(DIMENSIONS), "八维审读必须齐全，不得以机检替代")
    blocking = []
    for name, item in modules.items():
        need(isinstance(item, dict), f"{name} 须为对象")
        need(item.get("verdict") in {"pass", "block", "unknown"}, f"{name} 审读结论不合法")
        evidence = item.get("evidence")
        need(isinstance(evidence, list) and evidence and all(isinstance(q, str) and q.strip() and q in text for q in evidence), f"{name} 需有本稿原句证据")
        need(isinstance(item.get("note"), str) and item["note"].strip(), f"{name} 需说明判断依据")
        issues = item.get("issues")
        need(isinstance(issues, list) and all(isinstance(x, dict) and x.get("status") in {"resolved", "open"} and isinstance(x.get("detail"), str) and x["detail"].strip() for x in issues), f"{name} 问题格式无效")
        if item["verdict"] != "pass" or any(x["status"] == "open" for x in issues):
            blocking.append(name)
    return blocking


def review(root, chapter, draft, report_path):
    with lock(root):
        check = mechanical(root, chapter, draft)
        text = under(root, draft).read_bytes().decode("utf-8")
        semantic = load(report_path)
        blocked = validate_semantic(semantic, check["fingerprint"], text)
        record = {"mechanical": check, "semantic": semantic, "blocking": check["blocking"] + blocked, "created": stamp()}
        put_json(under(root, f"工作区/审读/{chapter:04d}.json"), record)
    return {"status": "blocked" if record["blocking"] else "reviewed", "blocking": record["blocking"], "fingerprint": check["fingerprint"]}


def settle(root, chapter, draft, changes_path, summary, author, note):
    approval = decision(author, note)
    need(isinstance(summary, str) and summary.strip(), "须提供真实章节摘要")
    need(Path(draft).parts[:2] == ("工作区", "草稿"), "定稿正文只能来自工作区/草稿")
    changes = load(changes_path)
    need(isinstance(changes, list), "事实变更须为列表，可以为空")
    with lock(root):
        records = accepted(root)
        old = [r for r in records if r.get("chapter") == chapter]
        if old:
            expected = old[0]["request"]
            current = {"draft_sha256": digest(under(root, draft).read_bytes()), "facts_sha256": digest(changes), "summary": summary}
            need(expected == current, "章节已定稿，拒绝用不同工件覆盖历史")
            return {"status": "already_settled", "hash": old[0]["hash"]}
        last = max([r["chapter"] for r in records if r["type"] == "chapter"], default=0)
        need(chapter == last + 1, "定稿章号须连续；已有正文须按章导入与审读")
        c, records, text, _, fp = snapshot(root, chapter, draft)
        check = mechanical(root, chapter, draft)
        report = load(under(root, f"工作区/审读/{chapter:04d}.json"))
        need(report["mechanical"]["fingerprint"] == fp, "旧审读已失效，重新审读当前稿")
        blocks = validate_semantic(report["semantic"], fp, text)
        need(not check["blocking"] and not report["blocking"] and not blocks, "有未解决或未知问题，不能定稿")
        facts = facts_from(records)
        if changes:
            validate_facts(changes, text, existing=facts)
            prior_ids = {f["id"] for r in records for f in r.get("facts", [])}
            need(not prior_ids.intersection(f["id"] for f in changes), "本段事实复用了历史编号")
            entities = {f["entity"] for f in facts.values()} | set(c["allowed_new_entities"])
            for f in changes:
                need("source_id" not in f, "本章事实须引用草稿，不能冒充外部资料")
                need(f["unit"] == c["unit"], "本段新增事实单元号与合同不符；跨单元内容先更新合同")
                need(f["entity"] in entities, "新增实体不在允许名单中")
                need(f["reveal_at"] is None or f["reveal_at"] >= chapter, "新增事实不能倒填早于本章的披露时间")
                need(all(v >= chapter for v in f["known_since"].values()), "新增知情时间不能倒填历史")
        files = {"正文.md": text.encode(), "章合同.json": packed(c), "审读.json": packed(report)}
        item = append_bundle(root, {"type": "chapter", "chapter": chapter, "unit": c["unit"], "title": c["title"], "facts": changes, "summary": summary, "decision": approval, "request": {"draft_sha256": digest(text.encode()), "facts_sha256": digest(changes), "summary": summary}}, files)
    return {"status": "settled", "hash": item["hash"], "chapter": chapter}


def query(root, unit=None, term=None):
    records = accepted(root)
    facts = list(facts_from(records).values())
    if unit is not None:
        facts = [f for f in facts if f["unit"] == unit]
    if term:
        facts = [f for f in facts if term in json.dumps(f, ensure_ascii=False)]
    return {"title": config(root)["title"], "facts": facts, "chapters": [{"chapter": r["chapter"], "unit": r["unit"], "title": r["title"], "summary": r["summary"]} for r in records if r["type"] == "chapter"], "warning": "作者视图含机密，不直接用作读者视图或起草包"}


def doctor(root):
    records = accepted(root)
    facts = facts_from(records)
    sources = []
    for p in sorted(under(root, "原始资料").glob("S-*.json")):
        _, meta = checked_source(root, p.stem)
        sources.append(meta)
    for r in records:
        if r["type"] == "canon":
            text, meta = checked_source(root, r["source_id"])
            need(meta["sha256"] == r["source_sha256"], "已确认来源版本被改动")
            need(meta["original_sha256"] == r["original_sha256"], "已确认来源原件版本被改动")
            validate_facts(r["facts"], text, r["source_id"])
    units = {str(i): {"sources": sum(s["unit"] == i for s in sources), "facts": sum(f["unit"] == i for f in facts.values()), "premise_confirmed": any(f["kind"] == "unit" and f["unit"] == i for f in facts.values())} for i in range(1, config(root)["units"] + 1)}
    chapters = [r["chapter"] for r in records if r["type"] == "chapter"]
    need(chapters == list(range(1, len(chapters) + 1)), "定稿段号不连续")
    pending = sorted(p.name for p in under(root, ".故事/暂存").iterdir())
    return {"integrity": "ok", "transactions": len(records), "units": units, "writing_ready": any(c["premise_confirmed"] for c in units.values()), "all_units_integrated": all(c["premise_confirmed"] for c in units.values()), "staging_leftovers": pending, "limits": "完整事实语义与故事质量需作者/模型核验；writing_ready 仅指至少一单元具备备料前提"}


def export(root, relative):
    with lock(root):
        out = under(root, relative)
        need(not out.exists(), "导出目标已存在，拒绝覆盖")
        records = [r for r in accepted(root) if r["type"] == "chapter"]
        need(records, "没有定稿可导出")
        result = []
        for r in records:
            folder = under(root, f'定稿/事务/{r["seq"]:06d}-{r["hash"][:12]}')
            result.append(f'# 第{r["chapter"]}{config(root)["segment_label"]} {r["title"]}\n\n' + (folder / "正文.md").read_text(encoding="utf-8"))
        put(out, "\n\n---\n\n".join(result) + "\n")
    return {"status": "exported", "chapters": len(records), "path": str(out), "sha256": digest(out.read_bytes())}


def dashboard(root, relative):
    with lock(root):
        data = query(root)
        out = under(root, relative)
        need(not out.exists(), "看板目标已存在，拒绝覆盖")
        rows = []
        for f in data["facts"]:
            values = [str(f["unit"]), f["id"], f["kind"], f["entity"], f["key"], f["value"], str(f["reveal_at"]), json.dumps(f["known_since"], ensure_ascii=False)]
            rows.append('<tr data-unit="' + str(f["unit"]) + '">' + ''.join('<td>' + html.escape(x) + '</td>' for x in values) + '</tr>')
        page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>故事 · 故事单元账本</title>
<style>body{font-family:system-ui;max-width:1400px;margin:30px auto;padding:0 20px;background:#f9f7f1;color:#292826}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:10px;text-align:left}input,select{padding:10px;margin:10px}td{white-space:pre-wrap}</style>
<h1>BOOK_TITLE · 作者账本</h1><p>静态快照，含作者机密。只展示已确认事实；资料变化后生成新快照。</p>
<label>单元号 <select id="unit"><option value="">全部</option>UNIT_OPTIONS</select></label>
<label>查询 <input id="term" placeholder="人物、线索、时间线、伏笔"></label><p id="count"></p>
<table><thead><tr><th>单元</th><th>编号</th><th>类型</th><th>对象</th><th>属性</th><th>事实</th><th>披露位置</th><th>知情时间</th></tr></thead><tbody>'''+ ''.join(rows)+'''</tbody></table>
<script>const filter=()=>{let n=0;for(const row of document.querySelectorAll('tbody tr')){const show=(!document.getElementById('unit').value||row.dataset.unit===document.getElementById('unit').value)&&row.textContent.includes(document.getElementById('term').value);row.hidden=!show;if(show)n++;}document.getElementById('count').textContent='当前显示 '+n+' 条已确认事实';};document.querySelectorAll('input,select').forEach(x=>x.addEventListener('input',filter));filter();</script></html>'''
        page = page.replace("UNIT_OPTIONS", "".join(f"<option>{i}</option>" for i in range(1, config(root)["units"] + 1)))
        page = page.replace("BOOK_TITLE", html.escape(config(root)["title"]))
        put(out, page)
    return {"status": "dashboard_saved", "path": str(out), "facts": len(data["facts"])}


def backup(root, relative):
    with lock(root):
        health = doctor(root)
        out = under(root, relative)
        need(not out.exists(), "备份目标已存在，拒绝覆盖")
        need(out.suffix == ".zip", "备份文件须为 .zip")
        out.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix="backup-", dir=out.parent)
        os.close(fd)
        tmp = Path(tmp)
        count = 0
        try:
            with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as z:
                for path in sorted(root.rglob("*")):
                    need(not path.is_symlink(), "书仓含符号链接，先转换为实际文件再备份")
                    if not path.is_file() or path == tmp or path == out:
                        continue
                    rel = path.relative_to(root)
                    if str(rel) == ".故事/写锁" or rel.parts[:2] == (".故事", "暂存") or path.suffix == ".zip" and rel.parts[0] == "导出":
                        continue
                    z.write(path, str(rel))
                    count += 1
            os.replace(tmp, out)
        finally:
            tmp.unlink(missing_ok=True)
    return {"status": "backed_up", "path": str(out), "files": count, "integrity": health["integrity"], "sha256": digest(out.read_bytes())}


def restore(root, archive):
    """Restore only into a new directory; never execute files from book archives."""
    need(not root.exists(), "恢复目标须为尚不存在的新目录，禁止覆盖书仓")
    archive = Path(archive).resolve()
    need(archive.is_file(), "书仓压缩包不存在")
    root.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="restore-", dir=root.parent))
    try:
        with zipfile.ZipFile(archive) as z:
            names = set()
            total = 0
            for item in z.infolist():
                need("\\" not in item.filename and ":" not in item.filename, "压缩包路径不合法")
                target = under(stage, item.filename)
                need(target != stage, "压缩包存在空路径")
                need(item.filename not in names, "压缩包存在重复路径")
                names.add(item.filename)
                need((item.external_attr >> 16) & 0o170000 != 0o120000, "压缩包包含符号链接")
                total += item.file_size
                need(total <= 200 * 1024 * 1024 and len(names) <= 20000, "书仓超过恢复限制（200MB / 20000 文件）")
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    put(target, z.read(item))
        need(not (stage / ".故事/写锁").exists(), "压缩包含活动写锁，请核对导出方式")
        config(stage)
        (stage / ".故事/暂存").mkdir(parents=True, exist_ok=True)
        health = doctor(stage)
        os.rename(stage, root)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {"status": "restored", "book": str(root), "integrity": health["integrity"]}


def configure(root, file):
    update = load(file)
    need(isinstance(update, dict) and set(update) <= {"title", "units", "unit_label", "format", "profile", "segment_label", "length"}, "只允许更新作品配置字段")
    with lock(root):
        cfg = config(root)
        cfg.update(update)
        need(all(isinstance(cfg.get(k), str) and cfg[k].strip() for k in ("title", "unit_label", "format", "profile", "segment_label")), "作品配置缺少有效名称")
        need(type(cfg["units"]) is int and cfg["units"] > 0, "单元数须为正整数")
        used = [f["unit"] for r in accepted(root) for f in r.get("facts", [])]
        used += [load(p)["unit"] for p in under(root, "工作区/章合同").glob("*.json")]
        used += [load(p)["unit"] for p in under(root, "原始资料").glob("S-*.json")]
        need(not used or cfg["units"] >= max(used), "不能移除已有资料引用的单元")
        length = cfg["length"]
        if length is not None:
            need(isinstance(length, dict) and length.get("metric", "hanzi") in {"hanzi", "words", "characters"} and all(type(length.get(k)) is int and length[k] > 0 for k in ("min", "target", "max")) and length["min"] <= length["target"] <= length["max"], "篇幅配置无效")
        put_json(under(root, ".故事/项目.json"), cfg)
    return {"status": "configured", "config": cfg, "note": "已有审读指纹随配置修改失效；不改写定稿"}


def parser():
    p = argparse.ArgumentParser(description="故事 Writer：故事单元写作管理（作者裁决由调用者核实）")
    p.add_argument("--book", required=True, help="书仓根目录，与插件代码分开")
    sub = p.add_subparsers(dest="command", required=True)
    q = sub.add_parser("init")
    q.add_argument("--title", required=True)
    q.add_argument("--units", type=int, default=1)
    q.add_argument("--unit-label", default="卷")
    q.add_argument("--format", default="小说")
    q.add_argument("--profile", default="通用")
    q.add_argument("--segment-label", default="章")
    q = sub.add_parser("restore")
    q.add_argument("--file", required=True)
    q = sub.add_parser("configure")
    q.add_argument("--file", required=True)
    q = sub.add_parser("import-source")
    q.add_argument("--file", required=True)
    q.add_argument("--unit", type=int, required=True)
    q.add_argument("--label")
    q = sub.add_parser("propose")
    q.add_argument("--source-id", required=True)
    q.add_argument("--facts", required=True)
    q = sub.add_parser("accept")
    q.add_argument("--proposal", required=True)
    q.add_argument("--author", required=True)
    q.add_argument("--note", required=True)
    q = sub.add_parser("contract")
    q.add_argument("--file", required=True)
    q = sub.add_parser("brief")
    q.add_argument("--chapter", type=int, required=True)
    for name in ("check", "review", "settle"):
        q = sub.add_parser(name)
        q.add_argument("--chapter", type=int, required=True)
        q.add_argument("--draft", required=True, help="书仓内相对路径")
        if name == "review":
            q.add_argument("--semantic", required=True)
        if name == "settle":
            q.add_argument("--facts", required=True)
            q.add_argument("--summary", required=True)
            q.add_argument("--author", required=True)
            q.add_argument("--note", required=True)
    q = sub.add_parser("query")
    q.add_argument("--unit", type=int)
    q.add_argument("--term")
    sub.add_parser("doctor")
    sub.add_parser("history")
    for name in ("export", "dashboard", "backup"):
        q = sub.add_parser(name)
        q.add_argument("--out", required=True, help="新建的书仓内相对输出路径")
    return p


def main():
    p = parser()
    a = p.parse_args()
    root = Path(a.book).resolve()
    try:
        if a.command not in {"init", "restore"}:
            config(root)
        command = a.command
        if command == "init":
            result = init(root, a.title, a.units, a.unit_label, a.format, a.profile, a.segment_label)
        elif command == "restore":
            result = restore(root, a.file)
        elif command == "configure":
            result = configure(root, a.file)
        elif command == "import-source":
            result = ingest(root, a.file, a.unit, a.label)
        elif command == "propose":
            result = propose(root, a.source_id, a.facts)
        elif command == "accept":
            result = accept(root, a.proposal, a.author, a.note)
        elif command == "contract":
            result = save_contract(root, a.file)
        elif command == "brief":
            result = brief(root, a.chapter)
        elif command == "check":
            result = mechanical(root, a.chapter, a.draft)
        elif command == "review":
            result = review(root, a.chapter, a.draft, a.semantic)
        elif command == "settle":
            result = settle(root, a.chapter, a.draft, a.facts, a.summary, a.author, a.note)
        elif command == "query":
            result = query(root, a.unit, a.term)
        elif command == "doctor":
            result = doctor(root)
        elif command == "history":
            result = {"transactions": accepted(root)}
        elif command == "backup":
            result = backup(root, a.out)
        elif command == "export":
            result = export(root, a.out)
        else:
            result = dashboard(root, a.out)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get("blocking") else 0
    except (Invalid, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
