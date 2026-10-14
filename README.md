# Story Writer · 私人故事写作管理包

版本 0.1.0。面向 ChatGPT 写作，适配长篇、短篇、剧本、漫画脚本及其他叙事作品；各类作品共用资料与定稿流程，审读标准按作品形式调整。

这是自定义 GPT 配置包、Python 管理引擎与可选 Codex 插件的组合。不能将本地文件直接安装为 ChatGPT 网页版的原生插件。本包用于私人交付，不公开发布到插件市场，不部署外部服务。

## 从私人 GitHub 仓库下载

登录有仓库访问权限的 GitHub 账号后，打开 `Elysian-shu/story-writer`。可点击 **Code → Download ZIP** 下载源码和配置；或打开 `releases/Story-Writer-0.1.0-private.zip`，使用文件页的下载按钮获取完整工具包。私有仓库链接不公开开放，请保持仓库 Private，不创建公开镜像。

工具包只含代码、说明与合成测试，不含作者稿件、API 密钥或书仓数据。书仓应与源码目录分开；`.gitignore` 也排除了常见书仓目录和本地凭据文件。

## 用于 ChatGPT

1. 解压工具包。创建自定义 GPT，把 [GPT 指令](chatgpt/GPT指令.md) 全文粘贴到 Instructions。
2. 启用“代码解释器与数据分析”（界面名称可能不同）。把 `chatgpt/知识库.md` 与 `plugins/story-writer/references/` 中的文档加入 Knowledge。
3. 保存时选择 **仅我可见**。不添加 GPT Actions，不启用公开分享；写作不需要联网搜索。
4. 在与该 GPT 的对话里上传完整工具包 ZIP。说明：**“请解压工具包，在数据分析环境验证引擎可运行，再按 Story Writer 流程管理我的作品。书名是……，现在先做立项。”**
5. 每次离开前要求生成并下载“书仓备份 ZIP”。新对话上传工具包和最新书仓 ZIP，要求“核验备份并继续”。

源码放入 Knowledge 并不保证模型能把它当可执行文件使用，因此第 4 步明确要求会话上传 ZIP。对话中的执行环境和上传文件不保证永久保留；最新书仓备份才是恢复依据。没有数据分析能力时可使用文字版流程，但不能宣称文件已写入、脚本已执行或跨会话记忆已保存。

如果不创建自定义 GPT，也可在具备数据分析能力的普通 ChatGPT 对话中粘贴指令并上传工具包、书仓 ZIP。自定义 GPT 的创建与可见性尚未在你的账号中操作或验证。

## 你可以直接这样说

- “帮我建立一部短篇，先整理人物、冲突和结局方向，建议放在候选里。”
- “导入这些既有章节，区分已写事实、原计划、证词和冲突项。”
- “准备下一场戏，主角只能知道他已经得到的信息。”
- “审读这一章，重点看人物动机和伏笔；没有核验的维度写未知。”
- “列出本卷未兑现承诺，给我修改建议。”
- “把刚才这个改动作为修订提案，说明会影响哪些已定稿内容。”
- “暂停，导出最新书仓，下次继续。”

设定取舍、核心大纲改动及定稿入档先给出具体结果，再由作者确认。普通查询、备料、起草和检查在既有授权范围内继续推进。

## 本地运行

Python 3.10+，无第三方依赖、无模型 API、无网络请求。

```bash
python plugins/story-writer/scripts/story.py --book /path/to/我的故事 init \
  --title "我的故事" --units 1 --format "短篇" --unit-label "篇" --segment-label "节"
python plugins/story-writer/scripts/story.py --book /path/to/我的故事 doctor
python -m unittest discover -s tests -v
```

`init` 只接受空目录；不改动已有作品。书仓与插件代码分开。开始新故事可先把作者构想保存为 UTF-8 TXT/Markdown，再执行 `import-source → propose → 作者确认 → accept`；没有既有稿件也能使用。

## 可选 Codex 原生入口

本包提供 `.agents/plugins/marketplace.json` 和 `.codex-plugin/plugin.json`。本地目录作为私人插件源，**不会上传公开市场**。

```bash
codex plugin marketplace add /absolute/path/to/story-writer
codex plugin add story-writer@story-writer-local
```

这两个步骤需要宿主允许写入其本地配置。已核对当前 Codex CLI 的命令与源码格式；没有更改你的 Codex 全局配置。ChatGPT 不使用这些命令。

## 内容与交付边界

- 已实现：来源原件与引文核验、提案及显式修订、按需备料、八维报告校验、审读过期检测、原子定稿、幂等重试、完整备份恢复、作者账本看板、定稿导出。
- 模型负责：写作、事实提取、角色动机和语义一致性审读。脚本检查报告完整性及证据是否出现在稿件中，不能证明模型判断正确。
- 未实现：外部数据库、GPT Actions、自动向量检索、实时多人协作、云端自动持久化、ChatGPT 账号内自动安装。
- 现有《献生》一至四案资料尚未提供；本包没有凭空创建这些资料。通用系统可将其配置为四个“案”单元，资料提供后按同一接入流程处理。

完整方案见 [实施方案](docs/实施方案.md)，来源研究见 [Webnovel Writer 研究](docs/Webnovel-Writer研究.md)，验证见 [验证报告](docs/验证报告.md)。
