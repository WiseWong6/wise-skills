# 能力与接口边界

## 首版支持

- 接口：豆包语音合成 V3 HTTP SSE 单向流式接口。
- 资源：复刻 2.0，默认 `seed-icl-2.0`。
- 模型：默认 `seed-tts-2.0-standard`。
- 语言：中文 `zh-cn`。
- 输出：MP3，默认 24 kHz、64 kbps。
- 数值调节：`speech_rate [-50, 100]`、`loudness_rate [-50, 100]`、`pitch [-12, 12]`。
- 复刻还原：`tone_fidelity`。
- 长稿：按 UTF-8 字节数和中文标点自动分段，共用一个 `section_id`，再用 FFmpeg 无重编码拼接。

## 实验能力

`--style-prompt` 会把文本作为 `context_texts` 发送。声音复刻 2.0 最佳实践说明它可增强情感，但 V3 参数页把该字段标注为只支持官方音色，官方说明存在冲突。因此必须以当前账号、当前复刻音色的真实 A/B 请求为准；服务端拒绝时不要把它描述为已支持能力。

## 暂不支持

- 音效生成、参考图片或参考音频生成。
- 声音训练、音色管理。
- 异步十万字长文本。
- SSML。
- WAV、PCM、Ogg Opus 等其他格式。
- 自动评价“像不像本人”或情感是否自然。

## 请求映射

| CLI | V3 请求字段 |
| --- | --- |
| `--speech-rate` | `req_params.audio_params.speech_rate` |
| `--loudness-rate` | `req_params.audio_params.loudness_rate` |
| `--pitch` | `req_params.additions.post_process.pitch` |
| `--tone-fidelity` | `req_params.additions.tone_fidelity` |
| `--style-prompt` | `req_params.additions.context_texts` |
| 自动生成 | `req_params.additions.section_id` |

`additions` 在外层请求中是 JSON 字符串，不是嵌套对象。

## 官方资料

- [豆包语音合成模型 2.0 HTTP V3 接口](https://www.volcengine.com/docs/6561/2528925?lang=zh)
- [声音复刻 2.0 最佳实践](https://www.volcengine.com/docs/6561/2298705?lang=zh)
- [音频生成 HTTP 接口（非本 Skill 能力）](https://www.volcengine.com/docs/6561/2550782?lang=zh)
