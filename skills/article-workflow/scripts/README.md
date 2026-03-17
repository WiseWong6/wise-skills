# Article Workflow 执行引擎

解决"文档写了很多但执行容易遗漏"的问题。

## 核心问题

1. **目录重命名遗漏**：阶段7选标题后，AI 容易忘记重命名目录
2. **image-prompter 流程违规**：AI 直接生成提示词文件，跳过5阶段流程

## 解决方案：代码强制 + 声明式状态

### 脚本清单

| 脚本 | 用途 |
|:---|:---|
| `stage_manager.py` | 阶段管理 + 自动重命名 + 状态标记 |
| `skill_invoker.py` | image-prompter 契约调用 + 阶段验证 |
| `workflow_guardian.py` | 执行前强制检查，阻断违规操作 |

### 使用方式

#### 1. 阶段7后自动重命名

```bash
# 用户选择标题后，立即执行
python3 stage_manager.py \
  --project-dir "/path/to/project" \
  --rename "用户选择的标题"

# 验证
python3 workflow_guardian.py --project-dir "/path/to/project" --before-stage 08
```

#### 2. 阶段12契约模式

```bash
# 初始化契约模板
python3 skill_invoker.py --project-dir "/path/to/project" --init

# 用户完成 image-prompter 5阶段后，验证契约
python3 skill_invoker.py --project-dir "/path/to/project" --validate

# 如果验证失败，打印清单
python3 skill_invoker.py --project-dir "/path/to/project" --checklist
```

#### 3. 阶段13前置检查

```bash
# 执行前强制检查
python3 workflow_guardian.py --project-dir "/path/to/project" --before-stage 13

# 检查通过返回 0，失败返回 1 并输出错误信息
```

## 契约标记格式

### 07_图片提示词.md 必须包含：

```yaml
---
image_prompter:
  version: "1.0"
  stages:
    brief:
      status: "done"
      confirmed_by: "user"
      timestamp: "2026-02-26T10:00:00"
    plan:
      status: "done"
      ...
    style:
      status: "done"
      ...
    copy:
      status: "done"
      ...
    prompts:
      status: "done"
      ...
  style_selected: "minimalist-sketch"
  image_count: 6
  copy_spec_confirmed: true
---
```

### 主文件 frontmatter 必须包含：

```yaml
---
steps:
  selected_title:
    status: "done"
    rename_completed: true  # 阶段7后自动设置
  prompts:
    status: "done"
---
```

## 阻断规则

| 检查点 | 阻断条件 | 错误信息 |
|:---|:---|:---|
| 阶段8前 | 目录含 `__` 且 `rename_completed: false` | 目录未重命名 |
| 阶段13前 | `07_图片提示词.md` 不存在 | 文件不存在 |
| 阶段13前 | 缺少 `image_prompter:` frontmatter | 未通过技能生成 |
| 阶段13前 | 有未完成的 stage | 5阶段未完成 |
| 阶段13前 | `style_selected` 为空 | 未选择风格 |
| 阶段13前 | `copy_spec_confirmed: false` | 文案未确认 |

## 集成到 SKILL.md

更新后的 article-workflow 技能会：

1. 阶段7后**强制**调用重命名脚本
2. 阶段12明确标记为"契约模式"，必须通过技能执行
3. 阶段13前**自动**运行 guardian 检查
