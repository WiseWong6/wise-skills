# Wise Skills

Claude Code 技能集合，提升 AI 编程与内容创作效率。

---

## 前置要求

- [Claude Code](https://claude.ai/code) CLI 工具
- Python 3.8+（image-gen 需要）
- 相关 API Key（见环境配置）

---

## 安装方法

### 方法一：npx 一键安装

```bash
npx skills add WiseWong6/wise-skills
```

### 方法二：手动复制

```bash
# 克隆仓库
git clone https://github.com/WiseWong6/wise-skills.git

# 复制需要的 skill 到 Claude Code skills 目录
cp -r wise-skills/omega-prompt-forge ~/.claude/skills/
cp -r wise-skills/ppt-speech-creator ~/.claude/skills/
cp -r wise-skills/prompt-version-editor ~/.claude/skills/
cp -r wise-skills/image-gen ~/.claude/skills/
```

### 方法三：单技能安装

```bash
# 只安装需要的 skill
npx skills add WiseWong6/wise-skills image-gen
```

---

## Skills 列表

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

### 🎯 omega-prompt-forge

**从零创建高质量 AI 提示词**

当你需要：
- 设计全新的 Prompt 框架
- 创建任务专用的系统提示词
- 为特定场景定制 AI 行为

**工作流程：**
1. 需求分析 - 收集任务目标、受众、场景、约束
2. 核心字段提取 - 填充角色、目标、背景、输出格式等关键槽位
3. 智能框架推荐 - 根据复杂度自动匹配最佳框架（RTF/RACE/CRISPE 等）
4. 方案确认 - 输出结构化提示词方案供确认
5. 保存输出 - 生成并保存 Markdown 格式提示词

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

### ✏️ prompt-version-editor

**严格变更控制下的提示词版本管理**

当你需要：
- 局部优化现有提示词
- 修复提示词失败问题
- 维护提示词版本历史

**与大改重写的区别：**

| 场景 | 使用工具 |
|-----|---------|
| 局部修订、补丁修复 | prompt-version-editor |
| 大改重写、结构重构 | omega-prompt-forge |

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

## 使用方式

安装后，在 Claude Code 中使用 `/skill-name` 命令触发：

```bash
/image-gen 生成一张星际穿越主题的图片
/omega-prompt-forge 帮我创建一个代码审查提示词
/ppt-speech-creator 帮我准备年终总结 PPT
```

---

## 关于作者

**全网同名：@歪斯Wise**

专注分享：
- 🛠️ **AI 编程实践** - Claude Code 效率技巧、开发工作流
- 🤖 **Agent/Skills 应用** - 用 AI 编程的方式写提示词，知识资产化
- ⚡ **多模型协作** - GPT 当架构师、GLM 当码农，让 Token 更高效
- 📊 **AI 工程化思维** - 产品经理的 AI 护城河

**社交媒体：**
- 小红书：[@歪斯Wise](https://www.xiaohongshu.com/user/profile/wise)
- Twitter/X：[@wise_wong](https://twitter.com/wise_wong)

<img src="qrcode.jpg" width="200" alt="公众号二维码">

**扫码关注公众号 @歪斯Wise**，一起探索「用 AI 编程，早点下班」的实战技巧。

---

## 贡献

欢迎提交 Issue 和 PR，共同完善这些 skills。

---

## License

[MIT License](LICENSE)
