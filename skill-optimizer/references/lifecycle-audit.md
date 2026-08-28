# Skill 生命周期审计判据

本文件是按需读取的详细判据。`SKILL.md` 决定流程和确认门禁；本文件定义证据如何分类，不授权自动修改或删除目标 Skill。

## 1. 生命周期证据图

生命周期从权威源码起，依次经过发行载荷和 Agent 安装入口，最终以 Agent 实际加载并完成真实任务收口。

节点和边必须来自显式路径、Git/manifest 数据、文件哈希或真实运行记录。不通过目录名猜“开发仓”“发行仓”；只有显式 `--source`、目标 `--surface source` 或发行 manifest 证据能确立权威关系。

每个 Agent 入口记录：用户提供的原始路径、`lstat` 类型、原始 `readlink` 值、每一跳解析后的绝对目标、最终 `realpath`、状态和内容哈希。检查：

- 不存在、断链、循环、目标不是目录和逃逸的非法入口是确定性阻断。
- 相对软链按该软链父目录逐跳解析；不能按当前 shell 目录猜。
- 多跳和跨 Agent 目录借道是结构耦合警告，即使最终可用。
- 多入口解析到同一权威目录是共享安装事实；不要误报为重复副本。
- 同名入口解析到不同目录时比较内容哈希；独立副本和内容漂移分别报告。
- 同一目录被多个入口重复加载只报告证据；是否导致运行重复由 Agent 实测确认。

若后续获批修复软链，每条操作必须包含 Agent 名、入口、直接目标、期望 `realpath` 和回滚依据，并在执行后逐条 `readlink`/`realpath` 复核。禁止让 shell 通过空格分词批量拼接源和目标。

## 2. 版本坐标

版本不是单一数字。分别记录：

- `source.git_head` 和 `source.git_dirty`：源码提交与工作区状态。
- `release.source_commit`：发行 manifest 声称的源码提交。
- `source.tree_sha256`、`release.tree_sha256`、`installed.tree_sha256`：各载体内容坐标。
- `frontmatter.version`：Skill 自述语义版本，仅在对应平台 profile 有意义。
- 平台线上版本：只能由平台记录证明，静态目录审计不推断。

坐标不一致时报告具体哪两个坐标漂移。不要用 Git SHA 替代语义版本，也不要用 frontmatter version 证明平台已发布该版本。

发行 manifest 至少需要同时校验两向关系：manifest 声明的文件必须存在且哈希一致；发行载荷中应受管理的文件也必须能被 manifest 解释。当前审计器只对已识别格式做静态验证，未知格式标记待验证，不自动执行生成器。

## 3. 引用入边

每条文件关系只属于以下一种主要证据类型：

| 类型 | 能否证明被使用 | 含义 |
| --- | --- | --- |
| `functional` | 是 | 运行调用、代码 import、公开脚本入口 |
| `documentation` | 是 | SKILL/README/按需 reference 的有效读取入口 |
| `packaging` | 仅证明发行职责 | 显式 include/preserve 或用户发行外壳 |
| `integrity` | 否 | manifest 哈希或库存清单 |
| `provenance` | 否 | 来源、生成或追溯记录 |
| `legal` | 证明保留义务 | LICENSE、NOTICE、署名和第三方义务 |

`integrity` 或 `provenance` 入边不能洗白死重；但 `legal` 和既有用户外壳可以形成明确保留职责。动态 import、glob、运行时拼接路径和插件发现无法被静态穷举时，必须降级为 `dynamic-unresolved`，不得当作零入边。

## 4. 文件与依赖分类

- `required`：功能或有效文档入口可达，或根合同本身。
- `user-envelope`：已有 README、安装说明、许可证、NOTICE、署名和面向用户示例。
- `development-only`：测试、生成器、开发配置、CI，只需留在源码。
- `archive-only`：明确归档、旧案例或历史材料，不作为活跃合同。
- `dynamic-unresolved`：可能由动态加载或未提供构建证据使用。
- `deadweight-candidate`：在明确的发行/安装载体中，没有功能、文档或明确发行职责的有效入边，且未命中豁免。

每个候选必须报告：所在载体、字节数、占载体比例、全部入边、豁免检查、置信度和需要补齐的验证。依赖候选还需区分直接/传递、开发/运行、外置/内联和构建归因；没有 metafile 或等价证据时，未见静态 import 的运行依赖通常只能标记 `dynamic-unresolved`。

整个 Skill “被发行清单带着但无人安装或调用”时，只标记 `distribution-usage-unverified`。先单独进入该 Skill 审计，不能直接把整个目录升级为死重候选。

## 5. 确认死重

静态审计永远只产生候选。确认死重必须完成全部步骤：

1. 在隔离发行副本移除候选，不碰权威源码。
2. 重生成 manifest，并校验 manifest 到载荷、载荷到 manifest 两个方向。
3. 重跑静态审计、测试、doctor 和代表性构建。
4. 由新的 Agent 会话从真实安装入口调用并完成代表任务。
5. 对比删除前后的用户可见结果。
6. 用户确认后才能修改权威源码；移除第三方内容时同步复核 LICENSE/NOTICE/署名。

任一步缺失，状态保持 `deadweight-candidate` 或 `dynamic-unresolved`，不得写“确认可删”。

## 6. 结构矩阵

结构质量不折算成总分。逐项输出 `pass / review / fail`、证据和规则：

1. `single-owner`：一个规则、资源、版本坐标只有一个主人。
2. `lifecycle-dag`：安装传播拓扑必须是 DAG；文档引用环需人工收敛。
3. `thin-agent-adapters`：Agent 层只放 metadata/启动适配，不复制共享业务合同，也不借道其他 Agent 安装目录。
4. `surface-separation`：开发、发行、安装和运行证据分别记录。
5. `top-level-explainable`：每个顶层目录都能归入唯一职责；自定义目录给候选提醒，不自动删除。
6. `platform-structure-policy`：平台推荐结构单列，不把“过审”和“结构优秀”混为一谈。

多套活跃 legacy/fallback 合同、重复规则主人、引用循环和跨 Agent 多跳链均需进入结构审查。归档可以保留，但必须与现行合同隔离且不被活跃入口调用。

## 7. Finding 与阻断

- `kind=fact`：可直接复核的事实。
- `kind=candidate`：需要动态或隔离验证的候选。
- `kind=policy`：平台或项目政策，不冒充运行事实。
- `confidence=high|medium|low`：证据强度，不等于严重级别。

断链、软链循环、非法入口、明确的 manifest 哈希破坏等确定性问题导致退出码 `1`。死重候选、未使用依赖候选、结构建议、跨 Agent 借道和平台政策只给 warning/info，退出码仍可为 `0`。参数或审计器运行失败返回 `2`。

## 8. 真实运行

静态工具的 `runtime_verification` 默认为：

```json
{
  "status": "not-run",
  "evidence": [],
  "note": "静态解析不能证明 Agent 已加载并完成真实任务"
}
```

只有真实的新 Agent 会话完成代表任务，才能在人工验收记录中写 `passed`；失败则写 `failed` 并保留输入、入口、错误和输出证据。审计器本身不伪造这两个状态。
