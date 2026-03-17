---
name: article-plug-classicLines
description: 当用户要求基于知识库（金句库/文章库）润色文章、或需要智能插入高质量金句时应使用此技能。
---

# Article Plug Classic Lines

## 概述
基于本地知识库（金句库37,420条、文章库~4,000篇）进行智能润色。通过RAG检索最相关的金句，以自然嵌入的方式整合到原文中，同时优化语言表达。核心规范见 `references/prompt.md`。

## 何时使用
- 用户要求润色/优化文章
- 用户提及知识库、金句库、智能插入金句
- 用户希望提升文章说服力和感染力

## 工作流程
1. 读取用户提供的文章文件（默认为markdown格式）
2. 提取核心概念：主题词、关键词、段落主题
3. 调用 llamaindex RAG检索：
   - 从 `/Users/wisewong/Documents/Developer/auto-write/金句库/` 检索
   - 语义相似度检索 + 关键词匹配
   - 质量过滤：quality_score.overall > 5.0
4. 评分排序并选择top N条（默认2条）
5. 自然嵌入金句：
   - 优先替换段落末尾相似表述
   - 次优：段落间插入，保持流畅性
6. 优化表达：
   - 精简冗余表述
   - 增强逻辑连接
   - 调整节奏
7. 保存到输出路径（默认：`runs/xxx/platform/04_polished.md`）
8. 返回润色结果 + 匹配金句来源信息

## 输入参数
| 参数 | 必填 | 说明 |
|------|------|------|
| `file_path` | 是 | 待润色文章的文件路径（md格式） |
| `output_path` | 否 | 输出路径，默认为同目录下的 `04_polished.md` |
| `quote_count` | 否 | 需要插入的金句数量，默认为2 |
| `style` | 否 | 润色风格，默认为 `natural`（自然嵌入） |

## 输出格式
```markdown
<!-- 知识库润色结果 -->
<!-- 匹配金句：2条 -->

[润色后的文章内容...]

---

## 金句来源说明
| 金句 | 来源账号 | 来源文章 | 质量分 |
|------|---------|---------|--------|
| xxx | 刘润 | xxx | 6.0 |
| xxx | 糕左罗 | xxx | 5.8 |
```

## 输出落盘协议

**输入：**
- `run_dir`: orchestrator 提供的运行目录
- `input_file`: 待润色的文件路径（如 `wechat/01_draft.md`）
- `quote_count`: 需要插入的金句数量（可选）

**输出（必须落盘）：**
- `wechat/03_polished.md` - 金句润色后的文章
- `wechat/03_handoff.yaml` - 交接文件
- `wechat/03_retrieval_snippets.md` - 检索证据片段（RAG 弱检索）

**handoff.yaml 模板：**
```yaml
step_id: "03_polish"
inputs:
  - "wechat/01_draft.md"
  - "wechat/03_retrieval_snippets.md"
outputs:
  - "wechat/03_polished.md"
  - "wechat/03_handoff.yaml"
summary: "基于知识库检索和金句润色文章"
next_instructions:
  - "只能引用 snippets 中的内容，不得杜撰来源"
  - "保持文章事实点和结构不变"
open_questions: []
```

**更新 run_context.yaml：**
```python
update_step_state("03_polish", "DONE", [
    "wechat/03_polished.md",
    "wechat/03_handoff.yaml",
    "wechat/03_retrieval_snippets.md"
])
```

## RAG 弱检索（P0）

**检索流程：**
1. 使用 rg（ripgrep）对文章库和金句库进行关键词检索
2. 从 `input_file` 中提取关键词（主题、标题、关键段落）
3. 合并检索结果，生成 `wechat/03_retrieval_snippets.md`
4. 在润色时明确要求 LLM 只能引用这些 snippets

**检索证据格式（03_retrieval_snippets.md）：**
```markdown
## 检索证据

### 来源：文章库
<!-- 来源：/path/to/article.md 行号：123-456 -->[匹配片段]-->

### 来源：金句库
<!-- 来源：金句库/quote.json 作者：刘润 质量：6.0 -->[金句内容]-->
```

## 依赖
- **llamaindex**：RAG检索后端，支持向量索引+BM25混合检索（P1，可选）

## 资源
- `references/prompt.md`：完整提示词与润色规范

## 使用方式

### CLI 直接调用
```bash
python3 polisher.py <file_path> [-o output] [-n count] [-q quality]

# 示例
python3 polisher.py article.md -n 3 -o polished.md
```

### 参数说明
- `file_path`: 待润色文章文件路径（必填）
- `-o, --output`: 输出文件路径（可选，默认：同目录/03_polished.md）
- `-n, --count`: 需要插入的金句数量（可选，默认2）
- `-q, --quality`: 金句质量分阈值（可选，默认5.0）

## 输出文件
执行后会在同目录生成以下文件：
- `03_polished.md` - 润色后的文章
- `03_retrieval_snippets.md` - 检索证据片段
- `03_handoff.yaml` - 交接文件（供后续步骤使用）

## 注意事项
- 金句库路径：`/Users/wisewong/Documents/Developer/auto-write/金句库/golden_sentences.jsonl`
- 当前实现为基础版本，金句直接附在文末，完整智能嵌入需调用LLM
- llamaindex 向量检索为 P1 可选功能，当前使用关键词匹配
- 索引路径：`/Users/wisewong/Documents/Developer/auto-write/.index/golden_quotes/`（预留）
