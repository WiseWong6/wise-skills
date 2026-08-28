#!/usr/bin/env python3
"""Chinese short-video TTS through Volcengine Doubao V3 HTTP SSE."""

from __future__ import annotations

import argparse
import base64
import binascii
import getpass
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union
from urllib import error as urlerror
from urllib import request as urlrequest


DEFAULT_ENDPOINT = "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse"
DEFAULT_RESOURCE_ID = "seed-icl-2.0"
DEFAULT_MODEL = "seed-tts-2.0-standard"
DEFAULT_LANGUAGE = "zh-cn"
DEFAULT_SAMPLE_RATE = 24000
DEFAULT_BIT_RATE = 64000
DEFAULT_SEGMENT_BYTES = 900
CONFIG_ENV = "DOUBAO_TTS_CONFIG"


class DoubaoTTSError(RuntimeError):
    """Base error carrying a stable machine-readable code."""

    code = "runtime_error"

    def __init__(
        self,
        message: str,
        *,
        request_id: Optional[str] = None,
        log_id: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.request_id = request_id
        self.log_id = log_id


class CliError(DoubaoTTSError):
    code = "invalid_arguments"


class ConfigError(DoubaoTTSError):
    code = "missing_config"


class DependencyError(DoubaoTTSError):
    code = "dependency_missing"


class ServiceError(DoubaoTTSError):
    code = "service_error"


class OutputError(DoubaoTTSError):
    code = "output_error"


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliError(message)


def default_config_path() -> Path:
    override = os.environ.get(CONFIG_ENV)
    return Path(override).expanduser() if override else Path.home() / ".config/doubao-tts/config.json"


def emit_json(payload: Mapping[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def mask_identifier(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return "{}…{}".format(value[:2], value[-2:])


def redact(message: object, secrets: Sequence[str] = ()) -> str:
    text = str(message)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text[:2000]


def runtime_secrets() -> List[str]:
    secrets = [os.environ.get("DOUBAO_TTS_API_KEY", "")]
    try:
        secrets.append(load_config().get("api_key", ""))
    except DoubaoTTSError:
        pass
    return [secret for secret in secrets if secret]


def save_config(config: Mapping[str, str], path: Optional[Path] = None) -> Path:
    destination = (path or default_config_path()).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(destination.parent, 0o700)
    except OSError:
        pass

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".config-", suffix=".json", dir=str(destination.parent)
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(dict(config), stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        os.chmod(destination, 0o600)
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise
    return destination


def load_config(path: Optional[Path] = None) -> Dict[str, str]:
    source = (path or default_config_path()).expanduser().resolve()
    if not source.is_file():
        return {}
    if os.name == "posix":
        mode = stat.S_IMODE(source.stat().st_mode)
        if mode & 0o077:
            raise ConfigError("配置文件权限不安全，应为 0600：{}".format(source))
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError("无法读取配置文件：{}".format(redact(exc))) from exc
    if not isinstance(data, dict):
        raise ConfigError("配置文件必须是 JSON 对象")
    return {str(key): str(value) for key, value in data.items() if value is not None}


def resolved_credentials(path: Optional[Path] = None) -> Dict[str, str]:
    config = load_config(path)
    resolved = {
        "api_key": os.environ.get("DOUBAO_TTS_API_KEY", config.get("api_key", "")),
        "speaker": os.environ.get("DOUBAO_TTS_SPEAKER", config.get("speaker", "")),
        "resource_id": os.environ.get(
            "DOUBAO_TTS_RESOURCE_ID", config.get("resource_id", DEFAULT_RESOURCE_ID)
        ),
        "model": os.environ.get("DOUBAO_TTS_MODEL", config.get("model", DEFAULT_MODEL)),
        "endpoint": os.environ.get("DOUBAO_TTS_ENDPOINT", config.get("endpoint", DEFAULT_ENDPOINT)),
    }
    missing = [name for name in ("api_key", "speaker") if not resolved[name]]
    if missing:
        raise ConfigError("缺少配置字段：{}".format(", ".join(missing)))
    return resolved


def validate_range(name: str, value: int, minimum: int, maximum: int) -> int:
    if value < minimum or value > maximum:
        raise CliError("{} 必须在 [{}, {}] 范围内".format(name, minimum, maximum))
    return value


def _split_units(text: str, boundaries: Set[str]) -> List[str]:
    units: List[str] = []
    buffer: List[str] = []
    for character in text:
        buffer.append(character)
        if character in boundaries:
            units.append("".join(buffer))
            buffer = []
    if buffer:
        units.append("".join(buffer))
    return units


def _hard_split_utf8(text: str, max_bytes: int) -> List[str]:
    chunks: List[str] = []
    buffer: List[str] = []
    size = 0
    for character in text:
        encoded_size = len(character.encode("utf-8"))
        if encoded_size > max_bytes:
            raise CliError("单个字符超过分段字节上限")
        if buffer and size + encoded_size > max_bytes:
            chunks.append("".join(buffer))
            buffer = []
            size = 0
        buffer.append(character)
        size += encoded_size
    if buffer:
        chunks.append("".join(buffer))
    return chunks


def _fit_unit(unit: str, max_bytes: int) -> List[str]:
    if len(unit.encode("utf-8")) <= max_bytes:
        return [unit]
    secondary = _split_units(unit, set("，,、：:\t "))
    if len(secondary) == 1:
        return _hard_split_utf8(unit, max_bytes)
    fitted: List[str] = []
    for item in secondary:
        if len(item.encode("utf-8")) <= max_bytes:
            fitted.append(item)
        else:
            fitted.extend(_hard_split_utf8(item, max_bytes))
    return fitted


def split_chinese_text(text: str, max_bytes: int = DEFAULT_SEGMENT_BYTES) -> List[str]:
    if max_bytes < 16:
        raise CliError("segment-max-bytes 不能小于 16")
    normalized = text.strip()
    if not normalized:
        raise CliError("配音文本不能为空")
    if len(normalized.encode("utf-8")) <= max_bytes:
        return [normalized]

    units: List[str] = []
    for unit in _split_units(normalized, set("。！？!?；;\n")):
        units.extend(_fit_unit(unit, max_bytes))

    chunks: List[str] = []
    current = ""
    for unit in units:
        candidate = current + unit
        if current and len(candidate.encode("utf-8")) > max_bytes:
            chunks.append(current)
            current = unit
        else:
            current = candidate
    if current:
        chunks.append(current)
    return [chunk for chunk in chunks if chunk.strip()]


def build_request_body(
    *,
    text: str,
    speaker: str,
    model: str,
    speech_rate: int,
    pitch: int,
    loudness_rate: int,
    tone_fidelity: bool,
    section_id: str,
    style_prompt: Optional[str],
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    bit_rate: int = DEFAULT_BIT_RATE,
) -> Dict[str, Any]:
    additions: Dict[str, Any] = {
        "explicit_language": DEFAULT_LANGUAGE,
        "section_id": section_id,
        "tone_fidelity": tone_fidelity,
        "post_process": {"pitch": pitch},
    }
    if style_prompt:
        additions["context_texts"] = [style_prompt]
    return {
        "user": {"uid": "doubao-tts-skill"},
        "req_params": {
            "text": text,
            "speaker": speaker,
            "model": model,
            "audio_params": {
                "format": "mp3",
                "sample_rate": sample_rate,
                "bit_rate": bit_rate,
                "speech_rate": speech_rate,
                "loudness_rate": loudness_rate,
            },
            "additions": json.dumps(additions, ensure_ascii=False, separators=(",", ":")),
        },
    }


def parse_sse_payloads(lines: Iterable[Union[bytes, str]]) -> Iterable[Dict[str, Any]]:
    for raw_line in lines:
        line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else raw_line
        stripped = line.strip()
        if not stripped or stripped.startswith(":") or not stripped.startswith("data:"):
            continue
        serialized = stripped[5:].strip()
        if not serialized or serialized == "[DONE]":
            continue
        try:
            payload = json.loads(serialized)
        except json.JSONDecodeError as exc:
            raise ServiceError("服务端返回了无效 SSE JSON") from exc
        if not isinstance(payload, dict):
            raise ServiceError("服务端 SSE 数据不是 JSON 对象")
        yield payload


def synthesize_segment(
    *,
    endpoint: str,
    api_key: str,
    resource_id: str,
    request_id: str,
    body: Mapping[str, Any],
    timeout: float,
    opener: Any = None,
) -> Tuple[bytes, Optional[str]]:
    request = urlrequest.Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Api-Key": api_key,
            "X-Api-Resource-Id": resource_id,
            "X-Api-Request-Id": request_id,
        },
    )
    open_request = opener or urlrequest.urlopen
    try:
        with open_request(request, timeout=timeout) as response:
            log_id = response.headers.get("X-Tt-Logid") or response.headers.get("X-Tt-LogId")
            audio = bytearray()
            for payload in parse_sse_payloads(response):
                code = payload.get("code", 0)
                if code not in (0, 20000000, "0", "20000000", None):
                    message = payload.get("message") or payload.get("msg") or "语音服务返回业务错误"
                    raise ServiceError(
                        redact(message, (api_key,)), request_id=request_id, log_id=log_id
                    )
                encoded = payload.get("data")
                if encoded:
                    try:
                        audio.extend(base64.b64decode(encoded, validate=True))
                    except (binascii.Error, ValueError) as exc:
                        raise ServiceError(
                            "服务端返回了无效音频数据", request_id=request_id, log_id=log_id
                        ) from exc
            if not audio:
                raise ServiceError("服务端未返回音频数据", request_id=request_id, log_id=log_id)
            return bytes(audio), log_id
    except urlerror.HTTPError as exc:
        log_id = exc.headers.get("X-Tt-Logid") if exc.headers else None
        body_text = exc.read(4096).decode("utf-8", errors="replace")
        raise ServiceError(
            "HTTP {}：{}".format(exc.code, redact(body_text or exc.reason, (api_key,))),
            request_id=request_id,
            log_id=log_id,
        ) from exc
    except urlerror.URLError as exc:
        raise ServiceError(
            "网络请求失败：{}".format(redact(exc.reason, (api_key,))), request_id=request_id
        ) from exc


def require_program(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise DependencyError("缺少系统命令：{}".format(name))
    return path


def _concat_file_line(path: Path) -> str:
    return "file '{}'\n".format(str(path.resolve()).replace("'", "'\\''"))


def concatenate_mp3(segment_paths: Sequence[Path], output: Path, ffmpeg: str) -> None:
    list_path = segment_paths[0].parent / "concat.txt"
    list_path.write_text("".join(_concat_file_line(path) for path in segment_paths), encoding="utf-8")
    process = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c",
            "copy",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        raise OutputError("FFmpeg 拼接失败：{}".format(redact(process.stderr)))


def probe_duration(path: Path, ffprobe: str) -> float:
    process = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        raise OutputError("ffprobe 检查失败：{}".format(redact(process.stderr)))
    try:
        duration = float(process.stdout.strip())
    except ValueError as exc:
        raise OutputError("ffprobe 未返回有效时长") from exc
    if duration <= 0:
        raise OutputError("生成音频时长必须大于 0")
    return duration


def _staging_path(output: Path) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=".{}-".format(output.stem), suffix=output.suffix, dir=str(output.parent)
    )
    os.close(descriptor)
    path = Path(name)
    path.unlink()
    return path


def configure(args: argparse.Namespace) -> Dict[str, Any]:
    if sys.stdin.isatty():
        api_key = getpass.getpass("API Key: ").strip()
    else:
        api_key = sys.stdin.readline().strip()
    if not api_key:
        raise CliError("stdin 中没有 API Key")
    config = {
        "api_key": api_key,
        "speaker": args.speaker.strip(),
        "resource_id": args.resource_id.strip(),
        "model": args.model.strip(),
        "endpoint": args.endpoint.strip(),
    }
    if not config["speaker"]:
        raise CliError("speaker 不能为空")
    path = save_config(config)
    return {
        "status": "ok",
        "action": "configured",
        "config_path": str(path),
        "permissions": "0600",
        "speaker": mask_identifier(config["speaker"]),
        "resource_id": config["resource_id"],
        "model": config["model"],
    }


def read_input_text(args: argparse.Namespace) -> str:
    if args.text is not None:
        return args.text
    path = Path(args.text_file).expanduser().resolve()
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CliError("无法读取 UTF-8 稿件：{}".format(redact(exc))) from exc


def synthesize(args: argparse.Namespace) -> Dict[str, Any]:
    validate_range("speech-rate", args.speech_rate, -50, 100)
    validate_range("loudness-rate", args.loudness_rate, -50, 100)
    validate_range("pitch", args.pitch, -12, 12)
    if args.timeout <= 0:
        raise CliError("timeout 必须大于 0")

    text = read_input_text(args)
    segments = split_chinese_text(text, args.segment_max_bytes)
    output = Path(args.output).expanduser().resolve()
    if output.suffix.lower() != ".mp3":
        raise CliError("首版输出文件必须使用 .mp3 扩展名")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not args.force:
        raise OutputError("输出已存在；确认目标后使用 --force：{}".format(output))

    ffprobe = require_program("ffprobe")
    ffmpeg = require_program("ffmpeg") if len(segments) > 1 else None
    credentials = resolved_credentials()
    section_id = str(uuid.uuid4())
    request_ids: List[str] = []
    log_ids: List[str] = []
    staging = _staging_path(output)

    try:
        with tempfile.TemporaryDirectory(prefix="doubao-tts-") as temporary_name:
            temporary = Path(temporary_name)
            segment_paths: List[Path] = []
            for index, segment in enumerate(segments, start=1):
                request_id = str(uuid.uuid4())
                request_ids.append(request_id)
                body = build_request_body(
                    text=segment,
                    speaker=credentials["speaker"],
                    model=credentials["model"],
                    speech_rate=args.speech_rate,
                    pitch=args.pitch,
                    loudness_rate=args.loudness_rate,
                    tone_fidelity=args.tone_fidelity,
                    section_id=section_id,
                    style_prompt=args.style_prompt,
                )
                audio, log_id = synthesize_segment(
                    endpoint=credentials["endpoint"],
                    api_key=credentials["api_key"],
                    resource_id=credentials["resource_id"],
                    request_id=request_id,
                    body=body,
                    timeout=args.timeout,
                )
                segment_path = temporary / "segment-{:03d}.mp3".format(index)
                segment_path.write_bytes(audio)
                segment_paths.append(segment_path)
                if log_id:
                    log_ids.append(log_id)

            if len(segment_paths) == 1:
                shutil.copyfile(segment_paths[0], staging)
            else:
                assert ffmpeg is not None
                concatenate_mp3(segment_paths, staging, ffmpeg)
            duration = probe_duration(staging, ffprobe)
            os.replace(staging, output)
    except Exception:
        staging.unlink(missing_ok=True)
        raise

    return {
        "status": "ok",
        "action": "synthesized",
        "output_path": str(output),
        "duration_seconds": round(duration, 3),
        "segments": len(segments),
        "parameters": {
            "language": DEFAULT_LANGUAGE,
            "format": "mp3",
            "sample_rate": DEFAULT_SAMPLE_RATE,
            "bit_rate": DEFAULT_BIT_RATE,
            "speech_rate": args.speech_rate,
            "pitch": args.pitch,
            "loudness_rate": args.loudness_rate,
            "tone_fidelity": args.tone_fidelity,
            "style_prompt": bool(args.style_prompt),
            "speaker": mask_identifier(credentials["speaker"]),
            "resource_id": credentials["resource_id"],
            "model": credentials["model"],
        },
        "request_ids": request_ids,
        "log_ids": log_ids,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(description="豆包中文短视频配音")
    subparsers = parser.add_subparsers(dest="command", required=True)

    configure_parser = subparsers.add_parser("configure", help="写入仓库外个人配置")
    configure_parser.add_argument("--api-key-stdin", action="store_true", required=True)
    configure_parser.add_argument("--speaker", required=True)
    configure_parser.add_argument("--resource-id", default=DEFAULT_RESOURCE_ID)
    configure_parser.add_argument("--model", default=DEFAULT_MODEL)
    configure_parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)

    synthesize_parser = subparsers.add_parser("synthesize", help="合成中文 MP3")
    text_group = synthesize_parser.add_mutually_exclusive_group(required=True)
    text_group.add_argument("--text")
    text_group.add_argument("--text-file")
    synthesize_parser.add_argument("--output", required=True)
    synthesize_parser.add_argument("--speech-rate", type=int, default=0)
    synthesize_parser.add_argument("--pitch", type=int, default=0)
    synthesize_parser.add_argument("--loudness-rate", type=int, default=0)
    synthesize_parser.add_argument("--tone-fidelity", action="store_true")
    synthesize_parser.add_argument("--style-prompt")
    synthesize_parser.add_argument("--segment-max-bytes", type=int, default=DEFAULT_SEGMENT_BYTES)
    synthesize_parser.add_argument("--timeout", type=float, default=120.0)
    synthesize_parser.add_argument("--force", action="store_true")
    return parser


def run(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    args = build_parser().parse_args(argv)
    if args.command == "configure":
        return configure(args)
    if args.command == "synthesize":
        return synthesize(args)
    raise CliError("未知命令")


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        result = run(argv)
        emit_json(result)
        return 0
    except DoubaoTTSError as exc:
        payload: Dict[str, Any] = {
            "status": "error",
            "error": {"code": exc.code, "message": redact(exc, runtime_secrets())},
        }
        if exc.request_id:
            payload["request_id"] = exc.request_id
        if exc.log_id:
            payload["log_id"] = exc.log_id
        emit_json(payload)
        return 1
    except KeyboardInterrupt:
        emit_json({"status": "error", "error": {"code": "interrupted", "message": "用户中断"}})
        return 130
    except Exception as exc:
        emit_json(
            {
                "status": "error",
                "error": {
                    "code": "internal_error",
                    "message": redact(exc, runtime_secrets()),
                },
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
