# Prompt Optimizer · 提示词优化器

对现有提示词做局部诊断、最小修改和版本化，重点检查冲突、冗余、歧义、示例污染与输出合同，不重写无关内容。

默认先交付完整提示词；顶部作者、模型、更新说明和版本等信息没填就省略，不写占位，交付后再询问是否需要补充。保存和版本管理按用户要求执行。

在 Agent 中调用 `$prompt-optimizer`；权威版本确认、修改边界与验证方式见 [SKILL.md](SKILL.md)。

License: [MIT](LICENSE) © 2026 Wise Wong
