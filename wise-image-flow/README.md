# Wise Image Flow · 配图全流程 Skill

一个 skill 打通「**内容 → 提示词 → 生图 → 拼版交付（PDF/HTML）**」全链路：把文章、模块或 PPT 大纲转成统一风格、少字高可读的信息图，批量出图，最后可一键拼成可翻阅的自包含 PDF/HTML。

## 核心能力

- **场景自动定比例**：小红书 3:4 ｜ 公众号封面 21:9、正文 16:9 ｜ 纯 PPT 16:9；明说→直接用，可推断→复述确认，未说明→询问
- **10 种风格**：奶油纸手绘、小红书卡通、方格纸手绘、极简手绘笔记、社论全景、奶油手账、社论纸艺等（出处见 SKILL.md 致谢表）
- **生图通道自动判定**：宿主内置生图（Codex / 网页版 GPT、Gemini）→ MCP 生图工具 → API 兜底（火山 Ark Doubao Seedream / Gemini 3 Pro Image）
- **5 阶段配图流程**：需求澄清 → 配图规划 → 风格选择（阻塞确认）→ 文案定稿 → 提示词封装；另有 PPT 大纲快速通道（3 阶段）
- **全图最多 2 种字体**：层级靠字号、字重与颜色深浅，不靠换字体
- **拼版交付**：小红书与 PPT 场景生成 ≥2 张后，可拼成自包含 PDF/HTML（图片 base64 内嵌、双击即开；Ghostscript/Pillow 压缩，缺依赖优雅降级）

## 安装

```bash
npx skills add WiseWong6/wise-image-flow
```

或手动克隆到你的 skills 目录（如 `~/.claude/skills/`、`~/.agents/skills/`）：

```bash
git clone https://github.com/WiseWong6/wise-image-flow.git ~/.claude/skills/wise-image-flow
```

## 快速使用

给四项就能开始：① 要配图的内容 ② 用在哪个场景（小红书 / 公众号 / PPT / 海报）③ 谁来看 ④ 少字清爽还是信息密度高。

直接生图（API 通道）：

```bash
python scripts/generate_image.py \
  --prompt "星际穿越，黑洞，复古列车，电影大片感" \
  --model "doubao-seedream-5-0-260128" --size "2K"
```

拼版成 PDF/HTML：

```bash
python scripts/generate_html.py ./my_images 输出名            # 竖版合集
python scripts/generate_html.py ./my_images 演示 --orientation landscape  # PPT 横版
```

## 环境变量（API 通道）

| 变量 | 用途 |
|---|---|
| `ARK_API_KEY` | 火山 Ark（Doubao Seedream） |
| `GEMINI_API_KEY` | Gemini 3 Pro Image |

宿主自带生图 / MCP 生图工具可用时无需任何 Key。

## 致谢

风格库参考整理自社区创作者的公开分享：@云舒的AI实践笔记、@宝玉、@松果先森、@Aki聊AI、@歸藏；奶油手账、社论纸艺与拼版交付能力来自 [@歪斯Wise](https://github.com/WiseWong6)。完整致谢表见 [SKILL.md](SKILL.md)。

## License

[MIT](LICENSE)
