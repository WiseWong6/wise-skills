# 保险文章创作工作流重构 - 进度总结

## 已完成任务

### 1. 创建 run_context.template.yaml
**文件**: `templates/run_context.template.yaml`

创建了 SSOT（单一事实源）模板，包含：
- 运行元数据（run_id, topic, platforms）
- 状态管理（status, current_step）
- 决策记录（decisions.wechat, decisions.image）
- 待确认问题（pending_questions）
- 步骤状态追踪（steps 00_init 到 08_draftbox）

### 2. 更新 insurance-article-creator/SKILL.md
**版本**: 3.0.0

新增内容：
- SSOT 架构设计说明
- run_context.yaml 结构示例
- 状态机设计（PENDING → RUNNING → DONE/FAILED/WAITING）
- 强制确认点（Stage Gates）
  - Gate A: 公众号账号选择
  - Gate B: 图片配置确认
  - Gate C: 草稿箱行为确认
- Resume 机制详细逻辑
- 并行与合流规则（04_humanize 与 05_prompts 并行）
- 阶段 0 初始化详细步骤
- handoff.yaml 模板

### 3. 更新 content-research-workflow/SKILL.md
**版本**: 2.2.0

新增内容：
- 输出落盘协议
- 输入输出规范
- handoff.yaml 模板
- run_context.yaml 更新逻辑

## 待完成任务

### 高优先级（P0）

#### 1. 更新下游 Skills 的 SKILL.md
- [ ] human-touch-content: 添加落盘契约
- [ ] knowledge-polisher: 添加落盘契约 + RAG 弱检索实现
- [ ] text-humanizer: 添加落盘契约
- [ ] insurance-healing-split-prompter: 添加落盘契约

每个 skill 需要：
- 输入规范（从 orchestrator 接收）
- 输出规范（写入固定路径）
- handoff.yaml 模板
- run_context.yaml 更新逻辑

#### 2. 脚本层改造
- [ ] ark-image-gen/scripts/generate_image.py
  - 添加命令行参数（--prompts-file, --out-dir, --cover-ratio, --poster-ratio, --count, --non-interactive）
  - 移除 input() 交互
  - 添加 load_dotenv() 支持
  - 标准化输出文件名

- [ ] wechat-draftbox/scripts/wechat_draftbox.py
  - 添加 --account 参数（main/sub/alias）
  - 添加 --non-interactive 模式
  - 移除 input() 交互
  - 添加 load_dotenv() 支持
  - 可选：支持 config/accounts.yaml

- [ ] md-to-wx-html/scripts/*
  - 确认支持 --input-md 和 --output-html 参数
  - 确保图片路径按 run_dir 相对路径解析

#### 3. 实现 orchestrator 核心逻辑
需要创建新脚本：`scripts/orchestrator.py`

功能：
- [ ] 初始化运行目录和 run_context.yaml
- [ ] 加载和保存 run_context.yaml
- [ ] 实现状态机转换逻辑
- [ ] 实现强制确认点（Stage Gates）
- [ ] 实现 resume 机制
- [ ] 调用下游 skills
- [ ] 并行执行 04_humanize 和 05_prompts
- [ ] 合流前校验（07_wx_html）
- [ ] 日志记录（_log/step_xx.log）

#### 4. RAG 弱检索实现（knowledge-polisher）
- [ ] 使用 rg 检索文章库/金句库
- [ ] 生成 wechat/03_retrieval_snippets.md
- [ ] 限制 LLM 只能引用检索结果

### 中优先级（P1）

#### 5. 环境统一
- [ ] 删除各 skill 子目录的 .venv/
- [ ] 保留根目录 .venv/
- [ ] 创建 requirements.txt 或 pyproject.toml
- [ ] 创建 scripts/install_all.sh

#### 6. 测试和验证
- [ ] P0 验收测试
  - 用户只输入 topic，能创建 run_dir 和 run_context.yaml
  - 执行到确认点时进入 WAITING_FOR_USER 并停止
  - 用户回复确认后能 resume 继续
  - 全链路结束后文件真实存在
  - 任意一步失败标记 FAILED

- [ ] P1 验收测试
  - 脚本无交互 input，缺参报错
  - .env 自动加载
  - 03 步生成 retrieval_snippets.md

## 关键设计决策

### 1. 文件命名规范
```
runs/YYYY-MM-DD__topic-slug__<shortid>/
├── run_context.yaml
├── _log/
│   ├── step_00_init.log
│   ├── step_01_research.log
│   └── ...
└── wechat/
    ├── 00_research.md
    ├── 00_handoff.yaml
    ├── 01_draft.md
    ├── 01_handoff.yaml
    ├── 03_polished.md
    ├── 03_handoff.yaml
    ├── 04_final.md
    ├── 04_handoff.yaml
    ├── 05_prompts.md
    ├── 05_handoff.yaml
    ├── 06_images/
    │   ├── cover_16x9.jpg
    │   └── poster_01_3x4.jpg
    ├── 06_handoff.yaml
    ├── 07_article.html
    ├── 07_handoff.yaml
    └── 09_draft.json
```

### 2. handoff.yaml 最小结构
```yaml
step_id: "01_research"
inputs:
  - "wechat/00_research.md"
outputs:
  - "wechat/01_draft.md"
summary: "基于调研生成公众号初稿"
next_instructions:
  - "下一步只润色，不改变事实点与结构层级"
open_questions: []
```

### 3. 状态转换规则
- PENDING → RUNNING: 步骤开始执行
- RUNNING → DONE: 步骤成功完成（artifacts 已落盘）
- RUNNING → FAILED: 步骤执行失败
- RUNNING → WAITING_FOR_USER: 需要用户确认参数
- WAITING_FOR_USER → RUNNING: 用户确认后继续

### 4. 强制确认点
- **Gate A**: decisions.wechat.account 为 null 时触发
- **Gate B**: decisions.image.count 为 null 时触发
- **Gate C**: 草稿箱行为未明确时触发（可选）

## 下一步建议

1. **立即开始**: 实现 orchestrator 核心逻辑（scripts/orchestrator.py）
2. **并行进行**: 改造 ark-image-gen 和 wechat-draftbox 脚本
3. **逐步更新**: 下游 skills 的 SKILL.md
4. **最后完善**: RAG 弱检索和统一环境

## 风险点

1. **下游 skills 不兼容**: 需要确保所有 skills 都遵循新的落盘协议
2. **Resume 逻辑复杂**: 需要仔细测试各种中断和恢复场景
3. **并行执行**: 04_humanize 和 05_prompts 并行需要处理好同步问题
4. **合流校验**: 07_wx_html 前的校验必须严格，否则会导致后续步骤失败
