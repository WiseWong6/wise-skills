---
name: research-review
description: 调研报告审计 + 成品文章事实核查技能。支持两种模式：1) 审计调研报告完整性、质量、逻辑；2) 对成品文章进行联网事实核查。评审/核查结果追加到原文件或生成独立报告。
version: "1.2.0"
author: "Wise Wong"
category: "Content & Media"
tags: [research, audit, quality-control, fact-checking, article-verification]
config:
  output_path: "same_as_input"
  format: "markdown"
  encoding: "utf-8"
  handoff_required: false
---

# research-review - 调研报告审计 + 文章事实核查技能

## 职责定位

你是内容质量的审计者。`research-workflow` 负责搜集信息，你负责检查它的工作质量。同时，你也可以对成品文章进行事实核查。

**核心原则**：
- 只读不改原内容，评审结果追加到文件末尾（或生成独立报告）
- 评审失败**警告但继续**，不阻塞下游流程
- 实用主义：检查真实问题，不搞学术审计

---

## 两种使用模式

### 模式一：调研报告审计（原有功能）

对 `research-workflow` 生成的调研报告进行完整性、质量、逻辑检查。

```bash
/research-review --input /path/to/00_research.md
```

**期望输入格式**：`research-workflow` 生成的标准调研报告 Markdown 文件。

### 模式二：成品文章事实核查（新增功能）

对成品文章进行联网事实核查，验证关键声明的准确性。

```bash
/research-review --input /path/to/article.md --article
```

**期望输入格式**：任何 Markdown 格式的成品文章。

**输出**：独立的 `{原文件名}.fact_check.md` 文件，包含核查明细和数据来源时间标注。

---

## 模式对比

| 特性 | 调研报告审计 | 文章事实核查 |
|------|-------------|-------------|
| 输入 | `00_research.md` | `article.md` |
| 参数 | `--input` | `--input --article` |
| 输出位置 | 追加到原文件 | 独立 `.fact_check.md` 文件 |
| 检查重点 | 完整性、来源质量、置信度标签 | 事实准确性、数据时效性 |
| 联网核查 | 按需触发（低置信度时） | 主动核查所有提取的事实 |

---

## 调研报告审计（模式一）

### 评审维度（核心三维度）

为避免过度设计，先实现以下三个核心维度：

为避免过度设计，先实现以下三个核心维度：

### 1. 完整性检查

检查项：
- [ ] 核心论点是否覆盖
- [ ] 反面观点是否提及
- [ ] 数据来源是否明确

输出：`PASS` / `WARN` / `FAIL` + 缺失项列表

### 2. 覆盖质量评估

检查项：
- 来源分布（官方文档、权威来源、普通来源）
- 时效性（最新发布时间）
- 交叉验证（同一事实是否有多个来源）

输出：评分（0-10）+ 统计摘要

### 3. 联网核查（按需）

触发条件：
- 置信度低于 0.7 的数据点
- 引用链接可疑
- 日期超过 6 个月的权威数据

输出：验证结果（通过/失败）+ 更新建议

---

## AI 调用流程

### Step 1: 读取调研报告

```python
# 伪代码
research_file = Path(input_path)
content = research_file.read_text(encoding='utf-8')
```

### Step 2: 解析结构

提取：
- 元数据（主题、时间、置信度）
- 核心发现列表
- 来源统计
- 置信度低于阈值的数据点

### Step 3: 执行评审

#### 3.1 完整性检查

```
检查逻辑：
1. 扫描 ## 核心发现 部分
2. 统计反面观点出现次数
3. 检查每个事实是否有来源引用
```

#### 3.2 覆盖质量评估

```
计算逻辑：
1. 解析 ## 来源统计 表格
2. 计算 official + high 占比
3. 检查最新来源时间
4. 交叉验证覆盖率 = 有多个来源的事实数 / 总事实数
```

#### 3.3 联网核查

```
触发条件：
- 置信度 < 0.7
- 引用 URL 返回 404
- 关键数据缺乏验证

核查方式（推荐顺序）：
- 优先使用 `firecrawl_scrape` 获取页面内容
- Firecrawl 失败/限额时，使用 Tavily（MCP/SDK）进行搜索与抓取
- Tavily 不可用时，降级到 `web.run` 搜索并核对权威来源
- 验证关键数据点
```

### Step 4: 生成评审报告

```markdown
---
## 调研评审报告

### 评审元数据
- **评审时间**: 2026-01-23T12:00:00Z
- **评审状态**: ✅ PASS / ⚠️ WARN / ❌ FAIL

### 评审摘要
- **完整性**: 8/10
- **覆盖质量**: 7/10
- **综合评分**: 7.5/10

### 1. 完整性检查
- [✅] 核心论点覆盖
- [❌] 反面观点覆盖
- [✅] 数据来源充分性

**缺失项**:
- 缺少对立观点：[具体描述]

### 2. 覆盖质量评估
#### 来源分布
| 类型 | 数量 | 占比 |
|------|------|------|
| official | 3 | 75% |
| high | 1 | 25% |

**时效性**: 最新来源 2025-12-15
**交叉验证**: 60% 事实有多个来源

### 3. 联网核查结果
- 核查项目数：2
- 验证通过：2
- 发现问题：0

### 4. 改进建议
1. [高优先级] 补充反面观点
2. [中优先级] 增加第三方验证

---
```

### Step 5: 追加到原文件

```python
# 伪代码
review_report = generate_review_report(...)
research_file.write_text(content + "\n\n" + review_report, encoding='utf-8')
```

---

## 输出格式

评审报告追加到 `00_research.md` 末尾，格式见 Step 4。

---

## 容错处理

### 调研报告审计模式

| 场景 | 处理方式 |
|------|---------|
| 输入文件不存在 | 抛出错误 |
| 输入格式不符合 | 尝试解析，失败则报告格式错误 |
| 联网核查失败 | 标记为"未验证"，不阻塞评审 |
| 评审失败 | 输出警告，返回 WARN 状态 |

### 文章事实核查模式

| 场景 | 处理方式 |
|------|---------|
| 输入文件不存在 | 抛出错误 |
| 未提取到事实声明 | 输出警告，退出码 1 |
| 用户取消确认 | 正常退出，不生成报告 |
| 联网搜索失败 | 标记为"核查失败"，继续其他事实 |
| 部分事实核查失败 | 生成报告，包含已核查结果 |

---

## 使用示例

### 调研报告审计

```bash
# 基础用法
/research-review --input ./run_dir/wechat/00_research.md

# 查看评审报告
cat ./run_dir/wechat/00_research.md | tail -50
```

### 文章事实核查

```bash
# 基础用法
/research-review --input ./11_final_final.md --article

# 查看核查报告
cat ./11_final_final.fact_check.md
```

---

## 与 article-workflow 集成

在 `workflow.yaml` 中定位：
```yaml
research:
  id: "01_research"
  fn: "step_research"
  deps: ["init"]

review:  # 新增步骤
  id: "01b_review"
  fn: "step_review"
  deps: ["research"]

rag:
  id: "02_rag"
  deps: ["review"]  # 更新依赖
```

在 `orchestrator.py` 中实现 `step_review()` 方法调用本技能。

---

## 文章事实核查（模式二）

### 功能概述

对成品文章进行系统性事实核查，提取关键声明并通过联网搜索验证其准确性。

### 核查流程

```
Step 1: 提取事实声明
    ↓ 使用启发式规则提取
Step 2: 展示预览
    ↓ 用户确认/编辑列表
Step 3: 联网核查
    ↓ 对每个事实进行 Web Search
Step 4: 生成报告
    ↓ 输出到 .fact_check.md
Step 5: 完成
```

### 事实类型识别

| 类型 | 识别规则 | 示例 |
|------|---------|------|
| 财务数据 | 数字+货币单位/百分比 | "估值约1万亿美元", "营收150亿美元" |
| 时间/日期 | 年份/日期模式 | "2025年12月", "截至2025年" |
| 人物/公司 | 实体+声明动词 | "马斯克表示", "SpaceX宣布" |
| 预测/推测 | 预测性关键词 | "预计", "将", "有望" |

### 核查结果标记

| 标记 | 含义 | 说明 |
|------|------|------|
| ✅ 准确 | verified | 搜索确认该声明准确 |
| ❌ 错误 | disputed | 发现矛盾或错误信息 |
| ⚠️ 需核实 | unverified | 无法确认或信息不足 |
| ❓ 核查失败 | error | 搜索过程出错 |

### 输出格式

事实核查报告输出为独立的 `.fact_check.md` 文件：

```markdown
---

## 事实核查报告

### 核查摘要
- **核查时间**: 2026-02-03T10:00:00Z
- **总声明数**: 12
- **准确**: 8 | **错误**: 1 | **需核实**: 3

### 核查明细

| 原文声明 | 类型 | 结果 | 修正内容 | 数据来源时间 |
|---------|------|------|---------|-------------|
| SpaceX估值约1万亿美元 | 财务数据 | ⚠️ 需核实 | SpaceX估值约8000亿美元 | 2025年12月 |

### 详细核查结果

#### #1 - ✅ 准确
**原文声明**: SpaceX 2025年营收约150亿美元

**类型**: 财务数据

**上下文**: ...

**数据来源时间**: 2025财年

**参考来源**:
- [来源标题](url)

---

### 数据时效性说明

> 📅 **核查基准时间**: 2026年02月03日
>
> 本文事实核查基于公开可获取的最新信息...

---
```

### 时效性要求

**搜索查询必须包含最新日期**：

```python
# 错误示例（可能返回过时信息）
"SpaceX revenue 2025"

# 正确示例（确保获取最新数据）
"SpaceX revenue 2025 2026"
"SpaceX financial results 2026"
```

**数据时效性标注**：
- 每个核查结果必须标注数据来源时间
- 如发现文章数据已过时，在报告中明确提示

### 使用示例

```bash
# 基础用法
/research-review --input ./11_final_final.md --article

# 查看核查报告
cat ./11_final_final.fact_check.md
```

### 依赖工具

- `WebSearch` - 用于联网验证事实
- `WebFetch` - 用于获取具体页面内容核实细节

### 注意事项

1. **半自动流程**：提取事实后会展示预览，用户确认后才进行联网核查
2. **交互式确认**：CLI 环境下会询问用户确认；非交互式环境自动继续
3. **时效性优先**：搜索查询自动附加当前年份，确保获取最新数据

---

## 与 article-workflow 集成（阶段 09b）

### 输出落盘协议

当作为 article-workflow 的阶段 09b 调用时：

**输入：**
- `run_dir`: orchestrator 提供的运行目录
- `input_file`: 待核查的文章路径（如 `wechat/09_rewritten.md`）

**输出（必须落盘）：**
1. `wechat/09b_fact_checked.md` - **修正后的文章**（必须生成）
2. `wechat/09b_fact_check_report.md` - 事实核查报告
3. `wechat/09b_handoff.yaml` - 交接文件

### 生成修正后文章（关键要求）

**必须生成 `09b_fact_checked.md`**：

| 情况 | 操作 |
|------|------|
| 发现事实错误 | 修正错误内容后生成 `09b_fact_checked.md` |
| 无事实错误 | 复制原文为 `09b_fact_checked.md`，在报告中说明"无需修正" |

**禁止**：
- ❌ 只生成核查报告而不生成 `09b_fact_checked.md`
- ❌ 修改原文 `09_rewritten.md`（必须生成新文件）

### handoff.yaml 模板

```yaml
step_id: "09b_fact_check"
inputs:
  - "wechat/09_rewritten.md"
outputs:
  - "wechat/09b_fact_checked.md"
  - "wechat/09b_fact_check_report.md"
  - "wechat/09b_handoff.yaml"
summary: "文章事实核查完成。验证了 N 个核心声明，X 个准确，Y 个需修正。已生成修正后文章。"
next_instructions:
  - "下一步：article-plug-classicLines 基于 09b_fact_checked.md 润色"
  - "禁止：基于 09_rewritten.md 跳过事实核查"
open_questions: []
```

### 更新 run_context.yaml

```python
update_step_state("09b_fact_check", "DONE", [
    "wechat/09b_fact_checked.md",
    "wechat/09b_fact_check_report.md",
    "wechat/09b_handoff.yaml"
])
```

### 下游依赖

- **阶段 10** 必须基于 `09b_fact_checked.md` 而非 `09_rewritten.md`
- **阶段 12**（图片链）也必须基于 `09b_fact_checked.md`

---
