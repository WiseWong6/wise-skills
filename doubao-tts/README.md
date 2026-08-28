# Doubao TTS · 豆包中文配音

用豆包 V3 HTTP SSE 和复刻音色生成中文短视频配音。支持语速、音量、音调、复刻还原、实验性风格提示，以及长稿自动分段和 MP3 拼接。

## 快速开始

配置会写入 Skill 外部的 `~/.config/doubao-tts/config.json`，权限为 `0600`：

```bash
python3 scripts/doubao_tts.py configure \
  --api-key-stdin \
  --speaker '<复刻音色 ID>'
```

合成中文配音：

```bash
python3 scripts/doubao_tts.py synthesize \
  --text '今天，我们聊聊怎样让表达更有力量。' \
  --output ./voiceover.mp3 \
  --speech-rate 0 \
  --pitch 0 \
  --loudness-rate 0 \
  --tone-fidelity
```

长稿使用 `--text-file`。风格提示属于复刻 2.0 实验能力：

```bash
python3 scripts/doubao_tts.py synthesize \
  --text-file ./script.txt \
  --output ./voiceover.mp3 \
  --style-prompt '用自然、克制、有亲和力的短视频旁白语气演绎'
```

脚本只依赖 Python 标准库；长稿拼接需要 FFmpeg，音频时长校验需要 ffprobe。所有命令返回 JSON，API Key 和完整个人音色 ID 不会进入输出。

详细用法和 Agent 工作流见 [SKILL.md](SKILL.md)，接口能力边界见 [references/capabilities.md](references/capabilities.md)。

License: [MIT](LICENSE) © 2026 Wise Wong
