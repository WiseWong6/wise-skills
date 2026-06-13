# Wise Skills

AI 编程助手技能集合，提升编程与内容创作效率。兼容 [Claude Code](https://claude.ai/code)、[OpenAI Codex CLI](https://github.com/openai/codex) 等 AI 编程工具。

---

## 前置要求

- AI 编程工具（任选其一）：
  - [Claude Code](https://claude.ai/code) CLI
  - [OpenAI Codex CLI](https://github.com/openai/codex)
  - 其他支持 skill 指令的 AI 编程助手
- Python 3.8+（image-gen、image-to-pages 需要）
- 相关 API Key（见环境配置）

---

## 安装方法

### 方法一：npx 一键安装（Claude Code）

```bash
npx skills add WiseWong6/wise-skills
```

### 方法二：手动复制

**Claude Code：**
```bash
git clone https://github.com/WiseWong6/wise-skills.git
cp -r wise-skills/<skill-name> ~/.claude/skills/
```

**Codex CLI：**
```bash
git clone https://github.com/WiseWong6/wise-skills.git
# 全局安装
cp -r wise-skills/<skill-name> ~/.codex/skills/
# 或项目级安装
cp -r wise-skills/<skill-name> .codex/skills/
```

### 方法三：单技能安装

```bash
npx skills add WiseWong6/wise-skills image-to-pages
```

---

## Skills 列表

### 📄 image-to-pages

**图片排版转 HTML + PDF**

将图片自动拼接成 3:4 比例页面，同时输出 HTML 和 PDF 文件。

- **双模式排版**：`auto`（任意比例自动拼成 3:4）和 `full`（3:4 图片直接排列）
- **自动 PDF 生成**：检测系统 Chrome/Chromium，headless 渲染输出 PDF
- **打印白边优化**：页面尺寸 150mm × 200mm，PDF 无 A4 白边
- **零外部依赖**：纯 Python + 系统浏览器，无需安装额外库

```bash
# 基本用法
python3 scripts/generate_html.py ./my_images

# 3:4 图片直接排列
python3 scripts/generate_html.py ./my_images output --mode full

# 只生成 HTML
python3 scripts/generate_html.py ./my_images --no-pdf
```

---

### 🎨 image-gen

**多提供商图片生成工具**

支持火山 Ark (Doubao Seedream) 和 Gemini 3 Pro Image 两大提供商，具备：
- 批量生成 + 多线程并行
- 图片编辑（单图）
- 多图合成（最多14张）
- 平台智能识别（公众号/小红书自动适配比例）
- Markdown 自动插入

**快速开始：**

```bash
# 火山 Ark 生成
python scripts/generate_image.py \
  --prompt "星际穿越，黑洞，复古列车，电影大片感" \
  --model "doubao-seedream-5-0-260128" \
  --size "2K"

# Gemini 图片编辑
python scripts/generate_image.py \
  --provider gemini \
  --prompt "给这只猫加上墨镜" \
  --input-image ./cat.png \
  --output "./cool-cat.png"
```

**平台智能识别：**
| 平台 | 图片类型 | 比例 |
|------|----------|------|
| 公众号 | 封面图 | 21:9 |
| 公众号 | 正文图 | 16:9 |
| 小红书 | 全部 | 3:4 |

---

### 🎯 prompt-creator

**从零创建 AI 提示词，像写代码一样写提示词**

核心方法论：**提示词 = 函数签名**。不需要记 35 个框架，只需要填 6 个字段。

| 字段 | 含义 | 类比 |
|------|------|------|
| Role | 角色/视角 | function context |
| Task | 做什么 | function name |
| Context | 背景信息 | closure vars |
| Input | 输入数据 | params type |
| Output | 输出格式 | return type |
| Constraints | 边界规则 | type constraints |

**工作流程：**
1. 模式判断 - 目标模型开思考？→ 判断型；不开？→ 执行型
2. 收集字段 - 按需填充 6 字段
3. 自检 - MECE / 冲突 / 冗余 / 模糊
4. 输出保存

---

### 📊 ppt-speech-creator

**自动生成 PPT 结构和配套演讲逐字稿**

当你需要：
- 准备年终总结/述职报告
- 项目复盘演示
- 产品发布/路演

**支持场景：**
- 📅 年终总结：回顾 → 成果 → 问题 → 成长 → 规划
- 📁 项目复盘：背景 → 目标 → 过程 → 结果 → 经验 → 后续
- 🚀 产品发布：痛点 → 方案 → 产品 → 优势 → 市场 → 愿景
- 👔 述职报告：职责 → 业绩 → 亮点 → 不足 → 规划

**智能时长计算：**
- 正常语速 220 字/分钟
- 自动评估页面复杂度
- 边界检查：单页 15 秒 - 5 分钟

---

### ✏️ prompt-optimizer

**诊断式提示词优化 + 版本管理**

4 项自检定位问题：MECE / 冲突 / 冗余 / 模糊。以 diff 形式提出修改，确认后版本号 +1 保存。

| 场景 | 使用工具 |
|-----|---------|
| 局部修订、补丁修复 | prompt-optimizer |
| 从零创建、重写 | prompt-creator |

---

### 🖥️ optimize-system-performance

**Mac / Windows 低权限性能诊断与清理决策助手**

默认只读诊断，不自动清理：
- 跨平台覆盖 CPU、内存、能耗/发热推断、磁盘、网络、启动项/后台项
- Mac 和 Windows 使用独立采样脚本，共用中文报告和候选评分
- 通过 PID、PPID、运行时长、监听端口、命令分组识别可疑 dev server / MCP / node_repl
- 清理动作只生成逐项确认单，不批量执行、不强杀、不禁用启动项
- 深度取证只作为确认后的菜单项，不默认执行

---

### 🖥️ optimize-mac-performance

**Mac 兼容入口**

保留给旧命令使用；安装了 `optimize-system-performance` 时优先走新的跨平台低权限流程。

---

## 使用方式

**Claude Code：** 在对话中使用 `/skill-name` 触发：
```
/image-to-pages /path/to/images 帮我做成打印页面
/image-gen 生成一张星际穿越主题的图片
/prompt-creator 帮我创建一个代码审查提示词
/ppt-speech-creator 帮我准备年终总结 PPT
/optimize-system-performance 诊断当前电脑的 CPU、内存、发热、磁盘、网络和后台占用
```

**Codex CLI：** 将 skill 目录放入 `~/.codex/skills/` 或项目 `.codex/skills/`，在指令中描述需求即可触发。

---

## 环境配置

### image-gen API Key 配置

**火山 Ark（推荐，国内访问稳定）**

1. 访问 [火山引擎控制台](https://console.volcengine.com/ark/region:ark+cn-beijing/model/detail?Id=doubao-seedream-5-0)
2. 注册/登录账号
3. 获取 API Key
4. 配置环境变量：

```bash
export ARK_API_KEY="your-ark-api-key"
```

**Gemini（可选）**

```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

### 依赖安装

```bash
# 火山 Ark
pip install openai python-dotenv pyyaml

# Gemini（可选）
pip install google-genai pillow
```

---

## 社交媒体

<div align="center">
  <p>全网同名：<code>@歪斯Wise</code></p>
  <p>
    <a href="https://www.xiaohongshu.com/user/profile/61f3ea4f000000001000db73">小红书</a> /
    <a href="https://x.com/killthewhys">Twitter(X)</a> /
    扫码关注公众号
  </p>
  <img src="qrcode.jpg" alt="公众号歪斯二维码" width="220" />
</div>

---

## 贡献

欢迎提交 Issue 和 PR，共同完善这些 skills。

---

## License

[MIT License](LICENSE)
