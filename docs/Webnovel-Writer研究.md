# Webnovel Writer 工作流与结构研究

研究日期：2026-10-14。直接读取官方 Git 仓库源码和文档；没有仅凭项目名称猜测功能。

## 版本与来源

| 分支 | 本次读取的提交 | 形态 | 已阅读依据 |
|---|---|---|---|
| master / v6 | `0af0c0b2fc2e4104e8a12c1d62136c6595a6a983` | Claude Code 插件 6.2.1 | README、架构、plugin.json、webnovel-write 与初始化技能 |
| v8 | `a0bdd2d4e2f39bc3de32fc5cbfe605067b5b486b` | DSH Scriptor 8.2.2 / DeepSeek Harness | README、book-format、workflows、novel-review、novel-settle |

主仓库：[lingfengQAQ/webnovel-writer](https://github.com/lingfengQAQ/webnovel-writer)。

- [v6 架构](https://github.com/lingfengQAQ/webnovel-writer/blob/0af0c0b2fc2e4104e8a12c1d62136c6595a6a983/docs/architecture/overview.md)
- [v6 写章流程](https://github.com/lingfengQAQ/webnovel-writer/blob/0af0c0b2fc2e4104e8a12c1d62136c6595a6a983/webnovel-writer/skills/webnovel-write/SKILL.md)
- [v8 工作台介绍](https://github.com/lingfengQAQ/webnovel-writer/blob/a0bdd2d4e2f39bc3de32fc5cbfe605067b5b486b/README.md)
- [v8 文件边界](https://github.com/lingfengQAQ/webnovel-writer/blob/a0bdd2d4e2f39bc3de32fc5cbfe605067b5b486b/docs/book-format.md)
- [v8 审读](https://github.com/lingfengQAQ/webnovel-writer/blob/a0bdd2d4e2f39bc3de32fc5cbfe605067b5b486b/packages/bundle/skills/novel-review/SKILL.md)
- [v8 定稿](https://github.com/lingfengQAQ/webnovel-writer/blob/a0bdd2d4e2f39bc3de32fc5cbfe605067b5b486b/packages/bundle/skills/novel-settle/SKILL.md)

v7 书仓草案已冻结，仅供比较；本包没有把它当已发布、可直接迁移的产品。原项目没有经验证的 v6/v7→v8 自动迁移，故本包也不声称与其账本格式直接兼容。

## 共同核心

1. **持续一致性**：长篇事实须不断沉淀；不是一次性生成文本。
2. **真源纪律**：作者意图、已接受事实与派生视图区分。大纲约束创作、设定约束世界、新实体登记。
3. **完整闭环**：预检与备料→起草→审读→修改→提取事实→提交→验证/备份。
4. **审读有证据**：稿或材料变化使旧报告失效；不能空审、伪造通过或仅替换指纹。
5. **恢复依赖文件**：进度取自实际工件和记录，不依赖聊天窗口记忆。
6. **作者掌舵**：具体方案和工件先呈现，再作事实取舍与定稿裁决。

## 插件组织

v6 用 `.claude-plugin/plugin.json` 定义插件；`skills/` 提供八个作者入口，`agents/` 拆备料、写后提取、审读等职责，`scripts/` 统一 CLI，`references/` 按任务加载写法，`hooks/` 守运行边界。Story System 主链负责合同、accepted CHAPTER_COMMIT 与事件；状态、索引和摘要是投影；Dashboard 是只读展示。

v8 用 DSH 插件包提供写作工作台；作品设计和逐章闭环分开，草稿/真源/定稿三区有写入边界。确定性检查加八维语义审读，定稿准备包呈现正文、事实、时间线、账本、摘要和记忆，再经作者裁决与事务入档。其宿主接口、代理机制和原生写入服务不能直接当 ChatGPT 工具调用。

## 本包的移植决策

| 原思想/能力 | 本包实现 | 取舍 |
|---|---|---|
| 合同优先 | 来源确认 + 通用段落合同 | 卷/幕/案均适用，不限网文 |
| 防设定漂移 | 引文、来源版本、显式 supersedes | 保留历史，不自动改旧正文 |
| 人物与读者信息差 | known_since / reveal_at / 披露白名单 | 起草包遮蔽机密，语义泄密需真实审读 |
| 多代理分工 | 明确设计/起草/审读职责与独立轮次 | ChatGPT 单对话无真正上下文隔离，不冒充多代理 |
| 提交与恢复 | 单目录原子事务 + 幂等 + 全书 ZIP | 不自动写 Git，不依赖托管服务 |
| 检索 | 分类与关键词查询 | 不需要 embedding API，向量能力留为后续可选 |
| Dashboard | 私人静态 HTML 账本 | 无公开端口、无远程服务 |
| 宿主插件 | ChatGPT 自定义 GPT 包 + 可选 Codex 原生清单 | 不谎称直接安装 Claude 插件到 ChatGPT |

原项目的固定 Strand 比例和商业网文追读指标并非所有故事的规则。保留“管理期待与推进”的思想，把具体标准交给作品形式与作者契约。

管理引擎为本次独立实现；未复制原项目运行脚本、代理或 Dashboard。研究所依据的原项目为 GPL-3.0；本包代码亦以 GPL-3.0-only 提供，保留来源说明。私人使用不要求对外发布；本包未公开分发到市场或仓库。
