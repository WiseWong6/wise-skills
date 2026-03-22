# Prompt Frameworks Library (2025 优化版)

## 使用说明

- 优先选 1 个主框架；必要时再加 1 个辅助框架
- 框架用于"结构化提示词"，不要机械堆叠
- 按任务复杂度 → 输出类型 → 特殊需求自动匹配
- 若已完整覆盖核心字段，框架可跳过

## 去重后的核心字段（建议优先填）

- **角色/能力**（Role/Persona）
- **目标/任务**（Goal/Task）
- **背景/上下文**（Context）
- **受众与语气**（Audience/Tone）
- **输入数据**（Input）
- **输出格式**（Format）
- **约束条件**（Constraints/Do-Not）
- **步骤/流程**（Steps/Process）
- **示例/参考**（Examples）
- **成功标准**（Criteria）

---

## 自动推荐逻辑（3 个维度）

### 维度 1：任务复杂度
```
简单任务（一步到位）
  → RTF, TAG, APE, BAB

中等任务（需要结构）
  → RACE, TRACE, CARE, RISE, COAST

复杂任务（多步推理）
  → CRISPE, CREATE, RISEN, Tree of Thought
```

### 维度 2：输出类型
```
内容创作（营销/文案/博客）
  → BAB, TRACE, BLOG, SPARK, COSTAR

技术任务（代码/文档/分析）
  → RTF, RISE, CIDI, GRADE

教育培训（教程/说明）
  → Five S, ELI5, SCAMPER
```

### 维度 3：特殊需求
```
需要语气/受众控制
  → COSTAR, CRAFT, CLEAR

需要推理/验证
  → Tree of Thought, Self-Consistency, PROMPT

需要创新/探索
  → SCAMPER, CRISPE, P-I-V-O
```

---

## 核心框架库（30-35 个）

### 【简单任务】一步到位

#### APE（Action-Purpose-Expectation）
- **Action 行动**：定义要完成的具体行动
- **Purpose 目的**：说明问题或任务的目标
- **Expectation 期望**：描述期望的结果

> **版本说明**：采用 Action-Purpose-Expectation 定义（用户截图版）
> 另一版本 Ask-Plan-Execute 已合并到 techniques.md 的 Plan-and-Solve 技巧

#### RTF（Role-Task-Format）
- **Role 角色**：指定 AI 扮演的角色
- **Task 任务**：定义要完成的任务
- **Format 格式**：指定输出格式

**最佳场景**：快速任务、简单查询、格式化输出

#### TAG（Task-Action-Goal）
- **Task 任务**：定义要完成的任务
- **Action 行动**：描述要做的事情
- **Goal 目标**：解释最终目标

**最佳场景**：日常任务、目标导向工作

#### BAB（Before-After-Bridge）
- **Before 当前状态**：描述问题或现状
- **After 期望状态**：描述理想结果
- **Bridge 解决方案**：连接现状与理想的方案

**最佳场景**：营销文案、说服性内容、问题解决

---

### 【中等任务】需要结构

#### RACE（Role-Action-Context-Expectation）
- **Role 角色**：指定 AI 角色
- **Action 行动**：说明要完成的行动
- **Context 上下文**：提供背景信息
- **Expectation 期望**：描述期望结果

**最佳场景**：快速分析、专业建议

#### TRACE（Task-Request-Action-Context-Example）
- **Task 任务**：定义需要什么
- **Request 请求**：描述具体要求
- **Action 行动**：说明需要的操作
- **Context 上下文**：提供背景说明
- **Example 示例**：给出样例

**最佳场景**：营销文案、创意内容、品牌对齐

#### CARE（Context-Action-Result-Example）
- **Context 上下文**：给出请求或问题背景
- **Action 行动**：描述想做什么
- **Result 结果**：说明希望的结果
- **Example 示例**：给出样例

**最佳场景**：场景化内容、客户沟通

#### RISE（Role-Input-Steps-Expectation）
- **Role 角色**：指定 AI 角色
- **Input 输入**：提供信息或资源
- **Steps 步骤**：说明推理步骤
- **Expectation 期望**：描述结果

**最佳场景**：编辑、数据分析、流程任务

#### COAST（Context-Objective-Actions-Scenario-Task）
- **Context 上下文**：提供背景
- **Objective 目标**：说明目标
- **Actions 行动**：列出具体步骤
- **Scenario 场景**：描述情境
- **Task 任务**：落地任务

**最佳场景**：项目规划、战略制定

---

### 【复杂任务】多步推理

#### CRISPE（Capacity-Role-Insight-Statement-Personality-Experiment）
- **Capacity/Role 能力/角色**：指定 AI 角色和能力
- **Insight 见解**：陈述背景
- **Statement 声明**：解释 AI 要做什么
- **Personality 个性**：指定 AI 个性
- **Experiment 实验**：要求 AI 探索多种可能

> **版本说明**：采用 OpenAI 版本定义（Capacity-Role-Insight-Statement-Personality-Experiment）
> 来源：最初由 OpenAI 内部开发，后公开使用

**最佳场景**：创意探索、头脑风暴、复杂问题解决

#### CREATE（Character-Request-Examples-Adjustment-Type-Extras）
- **Character 角色**：指定身份与视角
- **Request 请求**：明确任务
- **Examples 示例**：给出样例
- **Adjustment 调整**：补充细节、约束或偏好
- **Type 输出类型**：指定格式
- **Extras 附加**：补充背景或限制

**最佳场景**：高细节内容、可控输出

#### RISEN（Role-Instructions-Steps-Expectations-Novelry）
- **Role 角色**：指定 AI 角色
- **Instructions 指令**：说明要做什么
- **Steps 步骤**：给出步骤
- **Expectations 期望**：明确最终结果或验收标准
- **Novelty 创新**：强调创新或收敛范围

**最佳场景**：需要创新的复杂任务

#### Tree of Thought（ToT）⭐ 新增 2025
- **Thought Nodes**：生成多个思考分支
- **Evaluation**：评估每个分支
- **Backtracking**：回溯和探索其他路径
- **Decision**：选择最优路径

**最佳场景**：技术故障排查、逻辑密集任务、复杂规划
**来源**：[Parloa 2025](https://www.parloa.com/knowledge-hub/prompt-engineering-frameworks/)

---

### 【内容创作】营销/文案/博客

#### BLOG（Background-Logic-Outline-Goal）⭐ 新增 2025
- **Background 背景**：文章背景和主题
- **Logic 逻辑**：核心论点和逻辑
- **Outline 大纲**：文章结构
- **Goal 目标**：写作目标

**最佳场景**：博客文章、长篇内容、SEO 优化
**来源**：Juuzt.ai

#### SPARK（Situation-Problem-Aspiration-Result-Kismet）⭐ 新增 2025
- **Situation 情境**：当前状况
- **Problem 问题**：面临挑战
- **Aspiration 愿景**：期望目标
- **Result 结果**：具体成果
- **Kismet 运气/惊喜**：意外价值

**最佳场景**：创意问题解决、产品开发、营销策略
**来源**：Juuzt.ai

#### COSTAR（Context-Objective-Style-Tone-Audience-Response）⭐ 新增 2025
- **Context 上下文**：提供背景
- **Objective 目标**：说明目标
- **Style 风格**：说明表达风格
- **Tone 语调**：指定语气
- **Audience 受众**：指定目标受众
- **Response 回应**：明确输出形式或字数

**最佳场景**：客户服务、品牌沟通、需要语气控制的商业场景
**来源**：新加坡 GPT-4 Prompt Engineering 竞赛冠军框架

---

### 【技术任务】代码/文档/分析

#### CIDI（Context-Instructions-Details-Input）
- **Context 上下文**：提供背景
- **Instructions 指令**：说明要做什么
- **Details 细节**：补充关键细节或约束
- **Input 输入**：提供输入内容

**最佳场景**：结构化任务、技术文档

#### GRADE（Goal-Request-Action-Details-Example）⭐ 新增 2025
- **Goal 目标**：明确目标
- **Request 请求**：具体请求
- **Action 行动**：采取的行动
- **Details 细节**：相关细节
- **Example 示例**：参考样例

**最佳场景**：项目管理、任务跟踪、工作流优化
**来源**：Juuzt.ai

---

### 【教育培训】教程/说明

#### Five S Model（Set Scene-Specify Task-Simplify-Structure-Share）⭐ 新增 2025
- **Set the Scene**：设定场景和背景
- **Specify Task**：明确任务
- **Simplify Language**：简化语言
- **Structure Response**：结构化输出
- **Share Feedback**：分享反馈

**最佳场景**：培训材料、教程、内部文档、教育内容
**来源**：[Parloa 2025](https://www.parloa.com/knowledge-hub/prompt-engineering-frameworks/)

#### ELI5（Explain Like I'm 5）
- **Explain**：像给 5 岁孩子解释一样
- **Simplify**：用简单语言
- **Avoid Jargon**：避免术语

**最佳场景**：复杂概念解释、技术文档简化

#### SCAMPER（Substitute-Combine-Adapt-Modify-Put to other use-Eliminate-Reverse）⭐ 新增 2025
- **Substitute 替换**：什么可以替换？
- **Combine 组合**：什么可以组合？
- **Adapt 改编**：什么可以改编？
- **Modify 修改**：什么可以修改？
- **Put to other use**：其他用途？
- **Eliminate 消除**：什么可以消除？
- **Reverse 反转**：什么可以反转？

**最佳场景**：创新思维、产品改进、创意头脑风暴、问题解决
**来源**：经典创新工具，应用于 AI 提示词工程

---

### 【语气/受众控制】

#### CRAFT（Context-Role-Audience-Format-Tone）
- **Context 上下文**：提供背景
- **Role 角色**：指定 AI 角色
- **Audience 受众**：目标读者
- **Format 格式**：输出格式
- **Tone 语调**：语气风格

**最佳场景**：需要精确受众定位的内容

#### CLEAR（Context-Language-Examples-Audience-Request）
- **Context 上下文**：提供背景
- **Language 语言**：语言风格
- **Examples 示例**：参考样例
- **Audience 受众**：目标读者
- **Request 请求**：具体请求

**最佳场景**：多语言、跨文化沟通

---

### 【推理/验证】

#### PROMPT（Precision-Relevance-Objectivity-Method-Provenance-Timeliness）⭐ 新增 2025
- **Precision 精确性**：信息准确
- **Relevance 相关性**：与主题相关
- **Objectivity 客观性**：无偏见
- **Method 方法**：方法论合理
- **Provenance 来源**：来源可靠
- **Timeliness 时效性**：信息及时

**最佳场景**：研究、新闻、数据分析、信息质量评估
**来源**：Juuzt.ai

#### Self-Consistency
- 生成多个方案
- 比较并选择最佳
- 提高可靠性

**最佳场景**：需要高可靠性的任务

---

### 【创新/探索】

#### RACEF（Rephrase-Append-Contextualize-Examples-Follow-up）⭐ 新增 2025
- **Rephrase 重述**：重述需求
- **Append 追加**：补充信息
- **Contextualize 情境化**：提供情境
- **Examples 示例**：参考样例
- **Follow-up 跟进**：迭代优化

**最佳场景**：需要反复优化的任务、迭代式内容创作
**来源**：Juuzt.ai

#### P-I-V-O（Problem-Insights-Voice-Outcome）⭐ 新增 2025
- **Problem 问题**：定义问题
- **Insights 洞察**：提供洞察
- **Voice 声音**：视角和语气
- **Outcome 结果**：期望结果

**最佳场景**：商业策略、问题解决、战略建议
**来源**：Medium 2025

#### RHODES（Role-Objective-Details-Examples-Sense Check）⭐ 新增 2025
- **Role 角色**：指定角色
- **Objective 目标**：明确目标
- **Details 细节**：详细说明
- **Examples 示例**：参考样例
- **Sense Check 检查**：质量检查

**最佳场景**：创意对齐、品牌内容、质量把控
**来源**：Juuzt.ai

---

## 其他实用框架

### BROKE（Background-Role-Objectives-Key Result-Evolve）
- **Background 背景**：说明背景
- **Role 角色**：提供角色
- **Objectives 目标**：说明目标
- **Key Result 关键结果**：成功标准
- **Evolve 改进**：提升建议

### CO-STAR（Context-Objective-Style-Tone-Audience-Response）
- 与 COSTAR 相同，不同来源的命名变体

### ROSES（Role-Objective-Scenario-Expected Solution-Steps）
- **Role 角色**：指定角色
- **Objective 目标**：描述目标
- **Scenario 场景**：描述情境
- **Expected Solution 期望方案**：定义结果
- **Steps 步骤**：列出步骤

### RASE（Role-Action-Scenario-Example）
- **Role 角色**：指定角色
- **Action 行动**：说明操作
- **Scenario 场景**：具体情境
- **Example 示例**：参考样例

### ICIO（Instruction-Context-Input Data-Output Indicator）
- **Instruction 指令**：具体行动
- **Context 背景**：目标信息
- **Input Data 输入数据**：处理数据
- **Output Indicator 输出引导**：输出类型

---

## 框架选择决策树

```
开始
  ↓
任务复杂度？
  ├─ 简单 → RTF / TAG / APE / BAB
  ├─ 中等 → 输出类型？
  │        ├─ 内容创作 → TRACE / BAB / COSTAR
  │        ├─ 技术任务 → RACE / RISE / CIDI
  │        └─ 教育培训 → Five S / CARE
  └─ 复杂 → 特殊需求？
           ├─ 推理验证 → Tree of Thought / PROMPT
           ├─ 创新探索 → SCAMPER / CRISPE / RACEF
           └─ 通用复杂 → CRISPE / CREATE / RISEN
```

---

## 来源与参考

- **Parloa**: [Prompt Engineering Frameworks 2025](https://www.parloa.com/knowledge-hub/prompt-engineering-frameworks/)
- **Medium**: [15 Best ChatGPT Prompt Frameworks in 2025](https://medium.com/@amdadAI/15-best-chatgpt-prompt-frameworks-in-2025-get-every-output-right-31903350e39b)
- **Juuzt.ai**: [57 AI Prompt Frameworks](https://juuzt.ai/knowledge-base/prompt-frameworks/)
- **PromptBuilder**: [Best Prompt Frameworks in 2025](https://promptbuilder.cc/blog/prompt-frameworks-2025/)
