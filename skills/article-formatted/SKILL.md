---
name: article-formatted
description: Python 脚本执行 Markdown 格式规范化，处理中英文混排的空格、标点、引号问题
version: "4.1.0"
requires:
  - run_dir (from orchestrator)
  - input_file (e.g., wechat/06_polished.md)
---

# article-formatted

## 概述

这是一个**单步处理**的格式规范化技能，使用 Python 确定性脚本执行 Markdown 文本清洗。

**架构设计：**
```
输入 (06_polished.md)
    │
    ▼ Python 状态机清洗（保护代码块/链接/公式）
    │
    ▼ 07_final.md
输出 (07_handoff.yaml)
```

**为什么是单步？**
- 格式清洗是确定性任务，正则表达式是最佳工具
- LLM 处理格式会产生不确定性
- 简化后速度更快、成本更低、结果更可靠

## 何时使用

- 用户需要 Markdown 格式规范（中英文空格、标点、引号）
- 用户需要保留代码块、链接、图片等 Markdown 结构

## 输出落盘协议

**输入：**
- `run_dir`: orchestrator 提供的运行目录
- `input_file`: 待处理的文件路径（如 `wechat/06_polished.md`）

**输出（必须落盘）：**
- `wechat/07_final.md` - 格式清洗后的最终稿
- `wechat/07_handoff.yaml` - 交接文件

**handoff.yaml 模板：**
```yaml
step_id: "07_format"
inputs:
  - "wechat/06_polished.md"
outputs:
  - "wechat/07_final.md"
  - "wechat/07_handoff.yaml"
summary: "Markdown 格式规范化：空格、标点、引号"
next_instructions:
  - "下一步：image-prompter 生成图片提示词"
  - "保持文章结构和关键信息不变"
open_questions: []
```

**更新 run_context.yaml：**
```python
update_step_state("07_format", "DONE", [
    "wechat/07_final.md",
    "wechat/07_handoff.yaml"
])
```

## 工作流程

**单步处理：Python 格式清洗**

使用 `references/cleaner.py`，执行：
1. **状态机保护**：标记代码块、链接、图片、公式，用占位符替换
2. **破折号转换**：`—` / `——` → 中文标点
3. **引号统一**：删除装饰性弯引号「」『』，统一为直引号
4. **中英文空格**：删除中文字符与英文/数字之间的空格
5. **标点中文化**：`,.!?;()` → `，。！？；（）`
6. **空行规范化**：段落间只保留一个空行
7. **还原受保护区**

输出：`07_final.md`

## 依赖

- Python 3.12+
- 标准库（无需额外安装）：`re`, `typing`

## 文件结构

```
/Users/wisewong/.claude/skills/article-formatted/
├── SKILL.md                    # 本文件
├── references/
│   └── cleaner.py              # 清洗脚本
└── test/
    └── fixtures/               # 测试用例
        ├── basic_case.md
        ├── code_block_test.md
        └── edge_cases.md
```

## 注意事项

- **状态机保护**：代码块、链接、图片、公式在清洗过程中不会被修改
- **确定性输出**：相同输入永远产生相同的清洗结果
- **中间文件**：不再需要，直接输出最终稿

## 测试

```bash
# 测试清洗脚本
cd /Users/wisewong/.claude/skills/article-formatted
python3 references/cleaner.py test/fixtures/basic_case.md
python3 references/cleaner.py test/fixtures/code_block_test.md
python3 references/cleaner.py test/fixtures/edge_cases.md
```

## 版本历史

- **4.1.0** - 修复 `_clean_quotes()`：删除中文环境中的直引号 `""`（去机械化），同时保护代码块/加粗/表格中的引号
- **4.0.0** - 初始版本，支持状态机保护的格式清洗
