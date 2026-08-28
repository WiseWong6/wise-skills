# 平台 Schema Profile

平台 profile 只描述 metadata 和推荐目录结构。它不改变 Skill 的通用正确性、生命周期证据或真实运行门禁。

## Codex（默认）

`--schema-profile auto` 当前等同 `codex`：

- frontmatter 必须有 `name` 和 `description`。
- `name` 使用小写 ASCII 字母、数字和单连字符；首尾不能是连字符，不能连续连字符。
- `name` 与 Skill 根目录名一致。
- 当前通用合同不要求 `version` 或 `metadata`；额外字段作为政策提醒，避免把其他平台字段误当 Codex 硬合同。
- 常见顶层目录 `scripts/`、`references/`、`assets/` 均按实际职责可选，不要求为空也不要求全部存在。

## RedSkill（显式选择）

只有审计目标明确是 RedSkill 包时才使用 `--schema-profile redskill`：

- `name`、`description` 是基础字段。
- `name` 建议仅用 ASCII 字母、数字和单连字符，不超过 64 字符。
- `version` 建议位于 frontmatter 顶层并使用 `x.y.z`；它与平台线上版本分开记录。
- `metadata` 可用于作者等自定义键值。
- 推荐五件套是根目录 `SKILL.md`，以及可选 `README.md`、`references/`、`scripts/`、`assets/`；自定义运行目录作为结构政策提醒，可考虑归入 `assets/`。

这些是显式平台结构政策，不升级为 Codex/ZCode 的通用硬错误，也不等于平台审核结论。已观察到的平台实践和公开说明可能变化；审计正式发行前应重新核对当前 RedSkill 资料。

## 仍由 redskill-pack 管理

以下规则不属于通用 Skill Optimizer：

- 上传文件白名单或压缩包过滤。
- identifier/slug 与平台记录的对应关系。
- 自动审核阈值、人工复核阈值和审核文案。
- 平台发布按钮、线上状态和线上版本号。
- RedSkill 专用打包或上传流程。

Skill Optimizer 可以报告结构偏差和证据缺口，但不能宣称“已过审”或替代 `redskill-pack` 执行平台发布。
