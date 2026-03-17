# Prompt 技巧库（去框架化增强层）

## 使用原则

- 先用“核心字段”把任务讲清楚，技巧只在必要时使用。
- 一次只叠加 1-2 个技巧，优先解决最主要的问题（偏离/不可靠/太平庸）。
- 避免要求模型输出完整 Chain-of-Thought，可改为“简要理由/核对清单”。

## 基础技巧

- 指令无歧义：明确动词与对象，避免“分析下这个”。
- 正向指令优先：说清“要什么”，避免“不要什么”当核心目标。
- “不要”用于边界：限制范围、排除禁区。
- 补足上下文：提供背景、数据、前情与关键约束。
- 指定受众：决定语言深度、术语与风格。
- 角色设定：稳定语气与专业视角。
- 分隔符：用 ``` / <tag> / ### 区分指令、资料、示例。
- 输出格式：明确 Markdown / JSON / 表格 / 列表。
- 输出启动：给开头模板或代码块提示。
- Zero-shot：适合简单明确任务。
- Few-shot：有固定格式/风格时使用示例。
- Batch Prompting：批量生成多方案，便于筛选。

## 迭代与管理

- 迭代优化：测试 → 观察问题 → 局部调整 → 复测。
- 缺陷定位：幻觉/重复/模糊/前后不一致分别处理。
- 提示词当代码：版本号、占位符、A/B 测试。
- 只改核心问题：避免无关重写。

## 推理与结构化

- Chain-of-Thought（内部推理）：复杂推理任务可要求“简要理由”。
- Zero-shot CoT：要求模型先做简短推理再回答。
- Plan-and-Solve：先输出计划，再给结果。
- Step-Back：先抽象问题，再解决细节。
- Self-Ask：先列子问题，再逐个回答。
- Program-of-Thoughts：适合计算/逻辑/结构化任务。
- Tabular CoT：用表格组织推理步骤（若需要）。
- Tree of Thoughts：多路径探索+自评+回溯，适合复杂规划。

## 可靠性与校验

- Self-Consistency：生成多解并投票/融合。
- Chain-of-Verification：先答，再列验证点并修正。
- Self-Refine：先出草案，再按清单改写。
- Rephrase-and-Respond：改写问题后再次回答，降低偏差。
- Generated Knowledge：先回忆/列出关键知识，再生成结果。
- RAG：检索权威资料后再生成，降低幻觉。

## 创造与探索

- Analogical Prompting：用跨域类比激发新解。
- Divergent Expansion：要求多方案、多视角。
- Meta-Prompting：让模型先产出更好的提示词，再执行。

## 行动与工具

- ReAct：思考 → 行动 → 观察的工具调用循环。
- Reflexion：失败后反思并记录改进策略。
- PAL：把推理转成可执行代码，交给解释器计算。
- ART：自动复用“工具调用示例库”，降低提示成本。

## 跨语种与转换

- Cross-Lingual Prompting：使用最熟悉语言思考，再输出目标语言。
- Chain-of-Translation：多次翻译对照，降低歧义。

## 组合与工作流

- Prompt Chaining：将复杂任务拆成多段提示串联。
- Graph Prompting：用图结构/三元组组织关系再推理。
- APE（自动提示工程）：生成多候选提示词并评估择优。
- Active-Prompt：挑不确定样本优先补示例。
- DSP：先用小模型生成“方向盘前缀”，再交给大模型。

## 风格与输出控制

- 明确语气与视角（如第一人称/专业体）。
- 禁用冗余装饰（如 emoji、空洞强调词）。
- 需要一致性时，强制引用范围与风格约束。

## 选择建议（极简规则）

- 容易跑偏/不稳定：Step-Back + Few-shot
- 逻辑或计算密集：Plan-and-Solve + Program-of-Thoughts
- 需要高可靠：Self-Consistency + Verification
- 需要高创意：Analogical + Divergent
- 需要统一风格：Role Prompting + Few-shot
- 需要知识更新：RAG + Verification
- 复杂长流程：Prompt Chaining + 质量检查清单

## 来源

- Prompt Engineering Techniques Hub：https://github.com/KalyanKS-NLP/Prompt-Engineering-Techniques-Hub
- Prompt Engineering Guide：https://github.com/dair-ai/Prompt-Engineering-Guide
- 用户提供的「32 个提示词技巧」摘要
