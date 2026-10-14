# 数据协议 v1

编码 UTF-8。脚本保存 JSON，作者与 GPT 用自然语言操作；技术字段无需写进正文。保留未知的事实/合同字段，但它们不会自动产生约束。协议中的 chapter 指通用段落编号（章/场/节），unit 指组织单元（卷/幕/案等）。

## 作品配置

`.故事/项目.json` 保存名称、单元数、形式与 label。`configure --file 配置更新.json` 只更新给出的允许字段，例如：

```json
{
  "format": "剧本",
  "profile": "人物关系",
  "unit_label": "幕",
  "segment_label": "场",
  "length": {"metric": "characters", "min": 800, "target": 1000, "max": 1400}
}
```

篇幅不设默认上限/下限。`metric` 可为 `hanzi`（汉字数）、`words`（空格分词数）、`characters`（非空白字符数），范围为作者约定。计数包含保存文本中的标题，不剔除 Markdown 标记；不在稿文件中附加事实 JSON 或流程说明。中文一般用 hanzi/characters，不以 words 衡量。`length: null` 清除范围。

## 来源与事实提案

`import-source --file /path/source.md --unit 1 --label "作者构想-版本1"` 返回内容编号 S-...。引擎保存原始字节 `.original` 与 UTF-8 规范化文本 `.txt`；原件与规范化文本各有 SHA-256。相同规范化内容不重复登记，原文件仍由作者保留。

`propose` 的 facts 文件为数组。示例均为合成素材，不属于任何用户作品：

```json
[
  {
    "id": "U-001",
    "kind": "unit",
    "entity": "第一篇",
    "key": "故事目标",
    "value": "少年决定找回失去的声音",
    "unit": 1,
    "reveal_at": 1,
    "known_since": {"少年": 1},
    "quote": "少年决定找回失去的声音",
    "source_id": "S-请替换为真实资料编号"
  }
]
```

- `id`：字母开头，ASCII 字母、数字、短横或下划线，1–64 字符。全书唯一，历史已用 ID 不能重复。
- `kind`：unit（单元定位）、entity（人物/地点/组织）、clue（线索）、timeline（时序事件）、knowledge（信息差）、promise（承诺/伏笔）、style（文风）、rule（规则）、theme（主题意图）、outline（规划）。类型是分类标签，特定题材的附加约束由 GPT 审读，不假装脚本已自动识别。
- `entity/key/value`：对象、属性、事实或作者意图内容；均为非空字符串。同一 kind/entity/key 不重复写新事实；状态变化用带时间/段号的 key，例如“第3场后位置”。同一时间点的矛盾先裁决。
- `unit`：1 至作品单元数。跨单元关系可增加 `related_units` 说明，但本版不自动消费此扩展字段。全书共享设定可归入第一单元，并由后续合同按 ID 引用。
- `quote`：必须逐字出现在来源文本中。来源编号定位原件；行号可扩展为 `locator` 供人读，本版只强制校验原句，不自动验证行号。
- `reveal_at`：从哪一段起读者可知；`null` 为作者机密，非“尚未填写”。明示提前披露必须进入章合同 reveal_fact_ids。
- `known_since`：人物→开始知情段号。`{}` 表示尚未登记任何人物知情。不自动推断在场者全部知道，也不把知情登记当披露证据；语义审读核查其实际获得途径。

引文存在不等于引文支持 value。GPT/作者必须验证语义。证词示例可用 entity=证人甲、key=第2章证词，value=他声称看到红车；不能直接登记“真凶驾驶红车”。计划同样保存为 outline，不误报已发生事实。

## 显式修订

用新资料、新 ID、同一个 kind/entity/key，另加：

```json
{
  "supersedes": "旧事实ID",
  "change_reason": "作者改变该设定，或原资料版本被纠正"
}
```

propose 显示替换 ID 与保守的定稿复核范围。确认后有效视图使用新事实，history 保留全部旧事务。不能用直接改定稿或改账本 JSON 来实现修订。

## 章合同

```json
{
  "chapter": 1,
  "unit": 1,
  "title": "出发",
  "pov": "少年",
  "goals": ["让少年选择出发，并显示选择的代价"],
  "required_fact_ids": ["U-001"],
  "reveal_fact_ids": [],
  "allowed_new_entities": ["渡口"],
  "author_basis": "填写作者本次任务的真实依据"
}
```

`required_fact_ids` 不为空，引用当前有效事实。至少一条当前单元的 unit 事实存在才能规划写作合同。`reveal_fact_ids` 必须是 required_fact_ids 的子集。其他未来信息不进入备料正文。`allowed_new_entities` 控制新事实能登记哪些实体；脚本不自动发现正文未登记的专名，该问题由语义审读负责。

合同保存不自动批准未授权的核心剧情。goals 的实现需要真实语义审读，脚本不会凭“正文非空”认定目标达成。

## 八维语义审读

先 check 获得当前 fingerprint。以下只展示格式，不能作为真实通过报告照抄：

```json
{
  "fingerprint": "实际 check 输出的 64 位哈希",
  "reviewer": "实际审读者/模型轮次说明",
  "dimensions": {
    "结构": {
      "verdict": "pass",
      "evidence": ["本稿中支持判断的完整原句"],
      "note": "解释该句如何体现本段结构与合同目标",
      "issues": []
    }
  }
}
```

完整报告必须恰好包含八个键：结构、人物与关系、情节因果、信息披露、线索伏笔、节奏张力、读者承诺、文风表达。每维 verdict=`pass/block/unknown`，note 非空，evidence 至少一条本稿原句，issues 为数组。问题格式 `{"status":"open","detail":"具体问题"}` 或 `{"status":"resolved","detail":"本稿如何解决"}`。任何 unknown、block 或 open 都阻止定稿。没有该形式的伏笔也可 pass，但 note 需说明不适用理由并引用相关段落，不能误造悬疑要求。

fingerprint 绑定稿件内容与路径、合同、项目配置及当前正史链头。输入任一变化需重读并生成新报告。review 输出 blocking 列表并落盘；它只验证格式、证据存在与当前版本，不认证质量评分，也不证明审读者身份。

## 定稿

事实变化数组沿用事实字段，但不带外部 `source_id`，quote 必须来自本稿，unit 必须匹配本段合同；新增知情与披露章不能倒填过去。不允许在本章变化中塞入 supersedes 修订。没有新事实可为 `[]`，不机械要求每章新增人物或伏笔。

定稿事务目录：`定稿/事务/000001-哈希前缀/`，包含 `事务.json` 和（正文事务的）正文.md、章合同.json、审读.json。事务 JSON 保存事实、摘要、决策、父事务哈希及工件哈希。目录只在完整工件准备好后一次入档；事务不存在时草稿仍是草稿。

文本导出不带作者机密账本；书仓备份含全部原件、候选、草稿、审读及定稿，默认是作者私人文件。restore 只向新目录写入，拒绝逃逸、符号链接、重复路径与超过 200MB/20000 文件的包，不执行书仓代码。
