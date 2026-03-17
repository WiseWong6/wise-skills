# 文章创作工作流 - 项目状态

## 项目信息
- **项目名称**: article-workflow
- **项目路径**: `/Users/wisewong/.claude/skills/article-workflow/`
- **最后更新**: 2026-01-24
- **当前状态**: ✅ 成熟稳定（纯技能链架构）

---

## 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| **4.1.1** | 2026-01-24 | 修复阶段12输入来源：image-prompter 现在从阶段9（article-rewrite）的输出读取 |
| **4.1.0** | 2026-01-23 | 新增阶段9（article-rewrite 专业重写）：调整流程顺序，HKR+四步爆款法在选标题后执行 |
| **4.0.0** | 2026-01-15 | 新标准流程：新增 article-outliner（提纲生成）和 article-writer（根据提纲写作） |
| **3.3.0** | 2026-01-14 | wechat-uploadimg 独立成正式步骤（10_upload_images），新增扁平化输出 |
| **3.2.0** | 2026-01-13 | 新增 wechat-uploadimg 集成，图片自动上传到微信 CDN |
| **3.1.0** | 2026-01-12 | 新增 Handoff 串联协议、Canonicalize 映射、端到端 Doctor 校验 |
| **3.0.0** | 2026-01-12 | 新增 RAG 写作流程（article-create-rag + title-gen + 用户选择标题） |
| **2.0.0** | 2026-01-11 | 重构为纯技能链架构，移除所有适配器层 |
| **1.0.0** | 2025-01-10 | 初始版本，带适配器层（模拟实现） |

---

## 当前架构（v4.1.1）

### 17 个阶段的工作流（新标准流程）

| 阶段 | 技能 | 产物 |
|------|------|------|
| 00_init | 初始化 | run_context.yaml |
| 01_research | research-workflow | 00_research.md |
| 02_outliner | article-outliner | 02_outlines/ |
| 03_select_outline | 用户选择 | 03_outline_selected.md |
| 04_writer | article-writer | 04_draft.md |
| 05_rag_enhance | article-create-rag | 05_enhanced.md |
| 06_titles | title-gen | 06_titles.md |
| 07_select_title | 用户选择 | 07_title_selected.md |
| 08_apply_title | 应用标题 | 08_with_title.md |
| 09_rewrite | article-rewrite | 09_rewritten.md |
| 10_polish | article-plug-classicLines | 10_polished.md |
| 11_formatted | article-formatted | 11_final_final.md |
| 12_prompts | image-prompter | 12_prompts.md |
| 13_images | image-gen | 13_images/ |
| 14_upload_images | wechat-uploadimg | 14_image_mapping.json |
| 15_wx_html | md-to-wxhtml | 15_article.html |
| 16_draftbox | wechat-draftbox | 16_draft.json |

### 并行优化

- **并行链路 1**：12_prompts（基于 09_rewritten）与 11_formatted 可并行启动

---

## 技能依赖

| 技能 | 用途 | 版本 |
|------|------|------|
| `research-workflow` | 趋势分析、竞品缺口、深度搜索 | v2.4.0 |
| `article-create-rag` | 基于本地文章库的 RAG 内容生成 | - |
| `title-gen` | 生成多组爆款标题方案 | - |
| `article-rewrite` | 活人感文章创作（四步爆款法+5层思考） | v2.1.0 |
| `article-plug-classicLines` | 知识库检索与金句润色 | - |
| `article-formatted` | 文本去机械化 | v4.1.0 |
| `image-prompter` | 图片提示词生成（5种风格，五阶段流程） | v7.0.0 |
| `image-gen` | Ark Doubao 图片生成 | - |
| `wechat-uploadimg` | 上传图片到微信 CDN | - |
| `md-to-wxhtml` | Markdown 转微信 HTML | - |
| `wechat-draftbox` | 微信草稿箱上传 | - |

---

## 设计原则

### 1. 零适配器层（Zero Abstraction）

**坏设计（已删除）：**
```python
ContentResearchAdapter().execute(topic)
HumanTouchAdapter().execute(research_file)
```

**好设计（当前）：**
```text
直接通过 Claude Code 技能调用链：
→ /research-workflow
→ /article-create-rag
→ /title-gen
→ /article-rewrite
...
```

### 2. 技能同步（Skill Sync）

- 依赖技能更新时，本技能自动同步
- 无需中间代码维护
- 消除"中间层过时"问题

### 3. SSOT 架构

- **run_context.yaml**：运行状态的单一事实源
- **workflow.yaml**：步骤定义的单一事实源
- **handoff.yaml**：跨步骤数据传递的协议

### 4. 向后兼容（Backward Compatibility）

- 旧版 run_context.yaml 自动迁移
- 输出目录结构保持不变
- 文件命名约定保持不变

---

## 环境变量

| 变量 | 必需 | 用途 |
|------|------|------|
| `ARK_API_KEY` | ✅ | 火山 Ark API 密钥 |
| `WECHAT_APPID` | ✅ | 微信公众号 AppID |
| `WECHAT_APPSECRET` | ✅ | 微信公众号 AppSecret |

**出网 IP 白名单：** 确保 `wechat-draftbox` 请求来源 IP 在微信白名单中。

---

## 相关文件

- **SKILL.md**: 主技能文档（36.7 KB，v3.3.0）
- **README.md**: 快速开始指南（4.1 KB，v3.3.0）
- **TEST_RESULTS.md**: 唯一验收口径（27.7 KB，v1.3）
- **workflow.yaml**: 步骤定义 SSOT（1.6 KB，v3.3.0）
- **scripts/workflow_doctor.py**: 端到端校验脚本
