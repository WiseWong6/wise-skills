# Wise Skills

AI 编程助手技能集合，提升编程与内容创作效率。兼容 [Claude Code](https://claude.ai/code)、[OpenAI Codex CLI](https://github.com/openai/codex) 等 AI 编程工具。

<p>
  <img src="https://img.shields.io/github/stars/WiseWong6/wise-skills?style=flat-square&logo=github&label=Wise%20Skills" alt="Wise Skills Stars">
  <a href="https://star-history.com/#WiseWong6/blue-poster&Date"><img src="https://img.shields.io/github/stars/WiseWong6/blue-poster?style=flat-square&logo=github&label=Blue%20Poster" alt="Blue Poster Stars"></a>
</p>

---

## 前置要求

- AI 编程工具（任选其一）：
  - [Claude Code](https://claude.ai/code) CLI
  - [OpenAI Codex CLI](https://github.com/openai/codex)
  - 其他支持 skill 指令的 AI 编程助手
- Python 3.8+（wise-image-flow、image-to-pages、mac-cleanup 需要）
- 相关 API Key（见环境配置）

---

## 安装方法

### 方法一：npx 一键安装

```bash
npx skills add WiseWong6/wise-skills
```

### 方法二：手动复制

**Claude Code：**
```bash
git clone https://github.com/WiseWong6/wise-skills.git
cp -R wise-skills/<skill-name> ~/.claude/skills/
```

**Codex CLI：**
```bash
git clone https://github.com/WiseWong6/wise-skills.git
# 全局安装
cp -R wise-skills/<skill-name> ~/.codex/skills/
# 或项目级安装
cp -R wise-skills/<skill-name> .codex/skills/
```

### 方法三：单技能安装

```bash
npx skills add WiseWong6/wise-skills --skill image-to-pages
```

仓库中的每个顶层 Skill 目录都是可直接安装的用户发行载荷；开发测试、展示素材和发布说明统一放在仓库级 `tests/`、`docs/`。完整边界和发布前检查见 [Skill 源码与发行合同](docs/release-contract.md)。

`wise-image-flow` 是例外：唯一权威源码位于独立仓库，本仓库只保存由 `python3 scripts/manage_release.py sync` 生成的发行镜像，禁止手改镜像。

---

## Skills 列表

### 📄 image-to-pages

**图片排版转 HTML + PDF**

将图片自动拼接成 3:4 比例页面，同时输出 HTML 和 PDF 文件。

- **双模式排版**：`auto`（任意比例自动拼成 3:4）和 `full`（3:4 图片直接排列）
- **自动 PDF 生成**：检测系统 Chrome/Chromium，headless 渲染输出 PDF
- **打印白边优化**：页面尺寸 150mm × 200mm，PDF 无 A4 白边
- **渐进依赖**：基础 HTML 能力只需 Python；Pillow 用于图片压缩，Ghostscript 用于可选 PDF 二次压缩

```bash
# 基本用法
python3 scripts/generate_html.py ./my_images

# 3:4 图片直接排列
python3 scripts/generate_html.py ./my_images output --mode full

# 只生成 HTML
python3 scripts/generate_html.py ./my_images --no-pdf
```

---

### 🟦 blue-poster（蓝色光波）

**把一张原图，变成光学实验版画海报**

根据主体结构、透视、材质、氛围、动静关系与留白需求，从 `S01–S11` 自动选择一个视觉程序；默认直接生成完整全图，完成后可继续生成同风格的上下 1:1 对照版，或浏览其他风格。

- **11 套语义风格**：蓝晒、摩尔纹、套印、材料构造、气象错版与克制留白
- **完整全图优先**：第一次调用不做分屏，不恢复两阶段母版流程
- **参考图隔离**：风格图册只供浏览，永不作为生成输入
- **严格验收**：精确 3:4、单一效果程序、版本递增、提示词 sidecar
- **Codex 原生生图**：只使用宿主内置 `image_gen.imagegen`，无需第三方图片 API Key

```text
$blue-poster
把这张图做成完整 3:4 蓝色光波海报；风格由你根据原图语义选择。
```

查看完整双模式示例、11 风格目录、安装与验证说明：
[Blue Poster 独立仓库](https://github.com/WiseWong6/blue-poster)。如果它对你有帮助，欢迎点一个 [Star](https://github.com/WiseWong6/blue-poster/stargazers)。

---

### 🎨 wise-image-flow

**配图全流程：内容 → 提示词 → 生图 → 拼版 PDF/HTML**

- 场景自动定比例：小红书 3:4 / 公众号封面 21:9、正文 16:9 / PPT 16:9
- 10 种风格（奶油手账、极简手绘、社论全景等，出处见 Skill 内致谢表）
- 生图通道自动判定：宿主内置生图（Codex / 网页版 GPT、Gemini）→ MCP 生图工具 → API 兜底（火山 Ark Doubao Seedream / Gemini 3 Pro Image）
- 批量生成 + 多线程并行、图片编辑、多图合成（最多14张）
- 小红书与 PPT 场景生成后可拼成自包含 PDF/HTML（内置 image-to-pages 能力）

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
| PPT | 全部 | 16:9 |

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

### 🧹 skill-optimizer

**用人话诊断并精简现有 Skill**

先确定唯一现行合同，再检查 MECE、冲突、矛盾、冗余、重复、旧逻辑、上下文成本和交付闭环。审计请求保持只读；优化请求先说明保留、删除与影响，确认后才修改。

- **不兼容旧逻辑**：历史只留在 Git，运行时只保留当前合同
- **确定性审计**：检查断链、孤儿文件、重复段落、元数据和上下文体积
- **交付优先**：完成后提供成品路径、验证结果、成本对比与失败信号
- **零第三方依赖**：审计脚本仅使用 Python 标准库

```text
/skill-optimizer 检查这个 Skill，先用通俗中文说明问题，等我确认后再修改。
```

---

### 🧹 mac-cleanup

**Mac 清理、性能诊断与残留治理**

固定走“取证 → 按风险分层报告 → 用户拍板 → 执行 → 复查”：

- 覆盖性能、磁盘、进程端口、启动项、应用和 CLI 工具
- 每项都说明来源、删除风险、建议和体积
- 个人机器档案保存在 Skill 目录外，不进入公开发行包
- 本机清理与诊断统一由本 Skill 维护

---

### 🖥️ optimize-system-performance

**远端保留的 Mac / Windows 低权限性能诊断 Skill**

继续留在仓库供原有用户独立安装；本机不再安装它。该 Skill 偏跨平台只读诊断，`mac-cleanup` 则是当前本机的完整清理入口。

---

### 🧩 ppt-component-atlas

**查询并导出 Wise PPT 组件**

根据版式、内容结构和组件编号查询组件目录，必要时导出自包含 HTML。运行时只携带组件数据和导出脚本，不夹带开发测试或发布资料。

---

## 使用方式

**Claude Code：** 在对话中使用 `/skill-name` 触发：
```
/image-to-pages /path/to/images 帮我做成打印页面
/wise-image-flow 生成一张星际穿越主题的图片
$blue-poster 把这张图做成完整 3:4 蓝色光波海报
/prompt-creator 帮我创建一个代码审查提示词
/skill-optimizer 优化这个 Skill，先用通俗中文说明问题，等我确认后再修改
/ppt-speech-creator 帮我准备年终总结 PPT
/mac-cleanup 诊断当前电脑的 CPU、内存、发热、磁盘、网络和后台占用
```

**Codex CLI：** 将 skill 目录放入 `~/.codex/skills/` 或项目 `.codex/skills/`，在指令中描述需求即可触发。

---

## 环境配置

### wise-image-flow API Key 配置

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

`image-to-pages` 在没有 Pillow 时会回退为原图嵌入；没有 Ghostscript 时保留浏览器直接生成的 PDF。需要默认压缩能力时安装：

```bash
python3 -m pip install pillow
brew install ghostscript
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
