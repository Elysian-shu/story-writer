# 运行流程与恢复

## 工作原则

大纲是作者意图约束，设定是连续性约束，模型新发明须登记；文笔、节奏和结构服务于当前作品。保留探索空间，候选与正史区分，不把管理流程变成强迫作者套模板。

## 完整闭环

```text
立项/资料接入 → 作品契约 → 世界书与单元规划
                         ↓
章合同 → 备料 → 草稿 → 机检 → 八维审读 → 修改
                  ↑                    ↓
                  └── 输入变化重审 ────┘
作者核对正文与事实变更 → 原子定稿 → 查询/导出/备份
```

作品契约和世界书 Markdown 是作者可读说明；运行时已确认约束来自来源提案及章合同。两者有差异时先列出差异，不偷偷迁移。

## 在数据分析中调用

解压工具包到专用新目录，例如 `/mnt/data/story-tools`；实际路径由文件检查确定，不假定目录必定存在。书仓放在另外的目录，例如 `/mnt/data/books/当前作品`。读取参数时用列表调用 subprocess：

```python
import json, subprocess, sys
from pathlib import Path
engine = Path('/实际路径/plugins/story-writer/scripts/story.py')
book = Path('/实际书仓路径')
def run(*args):
    completed = subprocess.run([sys.executable, str(engine), '--book', str(book), *args],
                               capture_output=True, text=True, encoding='utf-8')
    if completed.returncode:
        raise RuntimeError(completed.stderr or completed.stdout)
    return json.loads(completed.stdout)
```

退出码：0 已完成且无阻断；2 check/review 已产生结果但有阻断；1 命令失败。审读阻断时仍须保存/读取结果，不以异常处理丢弃发现项。运行环境的下载文件路径和连接由实际产物生成。

## 新故事

`init --title 作品名 --format 短篇 --units 1 --unit-label 篇 --segment-label 节` 创建空书仓。先讨论人物、冲突、主题、结局候选。把作者已确认的构想保存为 UTF-8 Markdown，然后 `import-source --file 构想.md --unit 1`。创建有引文的 facts JSON，`propose --source-id S-... --facts facts.json`。呈现来源与候选后，依作者授权 `accept --proposal P-... --author 作者 --note 真实授权依据`。

至少一条 `kind: unit` 事实用于确认单元定位；可用一句作者已明确的故事目标，不能从模板中制造剧情。其他素材逐步入档，不要求第一天填全世界书。

## 既有作品

按原文件顺序导入，保留章号与版本信息。提案先区分已发生事件、作者计划、角色判断、证词、真假未明信息及冲突；对于“真实事件”和“某角色声称的事件”，使用不同实体/key，不把证词直接转成真相。导入事实不会导入已定稿正文；正文要进入定稿需逐段合同、审读与入档，不能宣称旧稿已经过新审读。

## 一段的命令顺序

1. `contract --file 章合同.json`；普通章节计划可按授权生成，核心偏离先列提案。
2. `brief --chapter N`，生成写作包。起草过程只读可披露包；审读另读完整作者账本。必要的近况以明确事实引用进合同，本版不自动加载可能泄密的自由摘要。
3. 将正文保存为 `工作区/草稿/NNNN-稿A.md`。
4. `check --chapter N --draft 工作区/草稿/NNNN-稿A.md`；保存 fingerprint 和实际计数。
5. 八维审读形成 semantic JSON；`review --chapter N --draft ... --semantic 审读输入.json`。检查每维证据与未解问题。
6. 修改另存新稿并重新执行 check/review；不要替换旧指纹假装重审。
7. 提取本段变化 JSON（无新事实可为 `[]`），摘要与正文一起呈现给作者。作者允许本次入档后 `settle --chapter N --draft ... --facts 变化.json --summary 真实摘要 --author 作者 --note 真实依据`。
8. `doctor`、`query` 确認成果，`backup --out 导出/书仓-新版本.zip`，交付实际文件。

`settle` 将正文、合同快照、审读、事实与作者裁决打包后，在同一文件系统以单次目录重命名入档。失败不会使半成品成为正史；同一正文、事实与摘要重试不重复入档。这里没有 Git 自动提交，不能声称已经推送或备份到 GitHub。

## 历史修订

保存作者新指令为新来源，导入后新事实带 `supersedes: 旧事实ID` 和 `change_reason`。propose 保守列出所有定稿段号供影响核对；真实模型/作者决定哪些正文受影响。明确批准后入档新事实，旧事务仍可从 history 查询。旧正文永不就地改写；必须明确另行修稿和重新审读。本版不自动生成旧正文修订版。

## 恢复

- 书仓 ZIP：`restore --file 书仓.zip` 恢复到新目录，验证链与来源完整性。继续之前运行 doctor。
- 查询 query/history、工作区/章合同、草稿与审读文件。稿在、审读缺：从审读继续。稿或约束已变：重新审读。定稿在：不要重写。备份缺：生成新备份。
- 写锁残留：停止写入，核对进程及暂存目录。确认无活动写入后才处理锁；不要无条件删除锁或暂存工件。
- 完整性损坏：保留坏包，恢复已下载且核验成功的备份，不改哈希使损坏记录“通过”。

## 权限与边界

CLI 的 author/note 是调用者填写的审计字段，不能在技术上认证 ChatGPT 用户或阻止模型撒谎。GPT 流程必须根据真实用户授权使用它们。本版无外部审批平台与身份验证服务。

ChatGPT 新对话不保证自动保有书仓，不能承诺跨会话无上传恢复。Knowledge 是说明文档，上传 ZIP 和真实运行是执行依据。只在同一对话换写作/审读角色没有实现独立上下文；必要时把审读包交给新对话，回传同一 fingerprint 的真实报告。
