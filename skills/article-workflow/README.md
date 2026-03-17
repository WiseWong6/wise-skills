# 保险文章创作流水线

## 快速开始

### 1. 新建运行

```bash
python3 scripts/orchestrator.py --topic "你的文章话题"
```

这将创建一个新的运行目录，开始从调研到草稿箱上传的完整流程。

### 2. 查看进度

```bash
# 进入已有运行目录
cd /Users/wisewong/Documents/Developer/auto-write/runs/20260114__your-topic__abc123

# 查看当前状态
python3 ../../scripts/orchestrator.py --resume --status
```

**输出包含**：
- 工作流基本信息（话题、状态、当前步骤）
- 所有步骤的状态表（PENDING/RUNNING/DONE）
- 每步产物是否存在
- 如卡在 Gate，显示阻塞原因和确认状态
- 预测下一步（确认后将进入哪个步骤）

### 3. 查看执行计划

```bash
python3 scripts/orchestrator.py --resume --plan
```

**输出包含**：
- 剩余待执行步骤列表
- 每步的 runner 类型（skill 或 script）
- 步骤依赖关系
- 预期产物路径

### 4. 继续执行

中断后继续运行：

```bash
python3 scripts/orchestrator.py --resume
```

## Gate 交互说明

### Gate A: 公众号账号选择

**问题**：选择发布到哪个公众号账号

**回答示例**：
```
main
```
或
```
sub
```

### Gate B: 图片配置确认

**问题**：请确认配图方向和张数

### 阶段 10：上传图片到微信 CDN（新增扁平化输出）

**技能**：`wechat-uploadimg`

**输入**：
- 图片目录：`wechat/09_images/`
- 公众号：`decisions.wechat.account`

**输出**：
- `wechat/10_image_mapping.json`（嵌套结构，保留兼容性）
- `wechat/10_image_mapping_flat.json`（新增：扁平结构）

### 阶段 11：Markdown → 微信 HTML

**前置操作**：在 Markdown 中插入图片引用（使用扁平化的映射）

**输入**：
- Markdown 文件：`wechat/07_final_final.md`
- 图片映射：`wechat/10_image_mapping_flat.json`（使用扁平版本）

**AI 执行**：
```text
1. 在 wechat/07_final_final.md 中按语义插入图片引用
2. 图片路径必须是相对路径：`poster_01_4x3.jpg`（不带 09_images/ 前缀）
3. 必须使用 `<!--RAW-->...<!--/RAW-->` 块包装图片 HTML
4.（推荐）使用标准 Markdown 语法：`![alt](url)` 而不是 `<img>` 标签
5. 调用 /md-to-wxhtml 技能：
   - 传入 `--image-mapping wechat/10_image_mapping_flat.json`
```

**注意**：`md-to-wxhtml` 只处理 Markdown 标准图片语法 `![alt](url)`，不处理 HTML `<img>` 标签

**回答示例**：
```
横屏，4张
```

**可选参数**：
- 方向：`横屏` / `竖屏` / `landscape` / `portrait`
- 张数：`4张` / `5幅` / 直接数字（如 `4`）
- 封面比例：`封面16:9`
- 正文比例：`正文3:4` / `正文21:9`

**完整示例**：
```
横屏，4张，封面16:9，正文3:4
```

**回车确认**：如想保持当前值，直接回车即可。

## 产物路径约定

```
运行目录/
├── run_context.yaml        # 唯一真实来源（SSOT）
├── we_/
│   ├── 00_research.md       # 调研内容
│   ├── 01_draft.md          # 初稿
│   ├── 03_polished.md       # 润色后
│   ├── 04_final.md          # 去机械化后
│   ├── 05_prompts.md        # 图片提示词
│   ├── 06_images/           # 生成的图片
│   │   ├── cover_16_9.jpg
    # └── poster_01_16_9.jpg
│   ├── 10_image_mapping.json       # 图片映射（嵌套结构）- 用于向后兼容
│   ├── 10_image_mapping_flat.json  # 图片映射（扁平结构）- 用于 md-to-wxhtml
│   ├── 11_article.html      # 转换后的 HTML
│   ├── 12_draft.json        # 草稿箱上传结果
│   └── *_handoff.yaml       # 每步交接文件
└── _log/                   # 步骤日志
    └── step_*.log
```

## 手册与验收

- **唯一验收口径**：`TEST_RESULTS.md`（包含所有功能验证和代码行为说明）
- **CLI 命令参考**：见 `TEST_RESULTS.md` 的 "30 秒重启可自证验收用例" 章节

## 版本信息

- **当前版本**：v3.3.0
- **最后更新**：2026-01-23
- **向后兼容**：旧版 `run_context.yaml` 会自动迁移到新结构
