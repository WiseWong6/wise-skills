---
name: doubao-tts
description: 使用豆包 V3 HTTP SSE 和复刻音色合成中文短视频配音，支持中文稿件、语速、音量、音调、复刻音色还原、实验性风格提示、长稿自动分段与 MP3 拼接。用户要求中文配音、短视频旁白、豆包 TTS、复刻声音、调语速/音调/音量或把中文稿件生成音频时使用。
---

# Doubao TTS

## 工作流

1. 检查 `python3`、`ffprobe`；稿件超过单段上限时额外检查 `ffmpeg`。
2. 未配置时，让用户在终端执行配置命令；不要索取或回显 API Key。
3. 将用户提供的中文稿保存为 UTF-8 文本，或通过 `--text` 直接传入短句。
4. 调用 `scripts/doubao_tts.py synthesize`。默认保持原始语速、音量和音调；只有用户明确要求时才调整。
5. 检查命令返回的 JSON：`status` 必须为 `ok`，`duration_seconds` 必须大于 0，且输出文件存在。
6. 把音频绝对路径交给用户试听；不要代替用户判断声音是否自然、像本人或情绪是否准确。

## 配置

在 Skill 目录中执行：

```bash
python3 scripts/doubao_tts.py configure \
  --api-key-stdin \
  --speaker '<复刻音色 ID>'
```

命令会把个人配置写入 `~/.config/doubao-tts/config.json` 并设为 `0600`。配置、API Key 和完整个人音色 ID 不得写入 Skill、项目文件、Git、日志或回答。

环境变量 `DOUBAO_TTS_API_KEY`、`DOUBAO_TTS_SPEAKER`、`DOUBAO_TTS_RESOURCE_ID`、`DOUBAO_TTS_MODEL` 可临时覆盖配置。`DOUBAO_TTS_CONFIG` 可覆盖配置文件路径。

## 合成

短文本：

```bash
python3 scripts/doubao_tts.py synthesize \
  --text '这是一段中文短视频配音。' \
  --output ./voiceover.mp3
```

长稿与数值调节：

```bash
python3 scripts/doubao_tts.py synthesize \
  --text-file ./script.txt \
  --output ./voiceover.mp3 \
  --speech-rate 10 \
  --pitch -1 \
  --loudness-rate 5 \
  --tone-fidelity
```

复刻 2.0 风格提示：

```bash
python3 scripts/doubao_tts.py synthesize \
  --text-file ./script.txt \
  --output ./voiceover.mp3 \
  --style-prompt '用自然、克制、有亲和力的短视频旁白语气演绎'
```

`--text` 与 `--text-file` 二选一。输出已存在时默认拒绝覆盖；确认目标正确后使用 `--force`。参数边界：语速和音量 `[-50, 100]`，音调 `[-12, 12]`。

## 失败处理

- `missing_config`：让用户执行配置命令，或临时设置环境变量。
- `dependency_missing`：安装 JSON 中点名的系统命令；不要自动安装依赖。
- `service_error`：记录脱敏错误、请求 ID 和服务端 LogID，不要重试收费请求，除非用户同意。
- `style_prompt` 被服务端拒绝：去掉该参数生成数值调节版本，并说明当前音色不支持实验性风格提示。
- 任意失败后确认最终目标文件未被半成品覆盖；脚本会自动清理临时分段。

能力范围、请求字段与已知冲突见 [references/capabilities.md](references/capabilities.md)。
