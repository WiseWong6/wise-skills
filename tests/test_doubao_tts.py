from __future__ import annotations

import base64
import contextlib
import importlib.util
import io
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "doubao-tts/scripts/doubao_tts.py"
SPEC = importlib.util.spec_from_file_location("doubao_tts", MODULE_PATH)
assert SPEC and SPEC.loader
doubao_tts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(doubao_tts)


class FakeResponse:
    def __init__(self, lines, headers=None):
        self.lines = lines
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def __iter__(self):
        return iter(self.lines)


class DoubaoTTSTests(unittest.TestCase):
    def test_parameter_boundaries(self) -> None:
        self.assertEqual(doubao_tts.validate_range("speech-rate", -50, -50, 100), -50)
        self.assertEqual(doubao_tts.validate_range("speech-rate", 100, -50, 100), 100)
        self.assertEqual(doubao_tts.validate_range("pitch", -12, -12, 12), -12)
        self.assertEqual(doubao_tts.validate_range("pitch", 12, -12, 12), 12)
        with self.assertRaises(doubao_tts.CliError):
            doubao_tts.validate_range("speech-rate", 101, -50, 100)
        with self.assertRaises(doubao_tts.CliError):
            doubao_tts.validate_range("pitch", -13, -12, 12)

    def test_config_permissions_environment_override_and_masking(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            path = Path(temporary_name) / "nested/config.json"
            doubao_tts.save_config(
                {
                    "api_key": "secret-api-key",
                    "speaker": "speaker-123456",
                    "resource_id": "seed-icl-2.0",
                    "model": "seed-tts-2.0-standard",
                },
                path,
            )
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with mock.patch.dict(
                os.environ,
                {"DOUBAO_TTS_API_KEY": "temporary-key", "DOUBAO_TTS_SPEAKER": "env-speaker"},
                clear=False,
            ):
                config = doubao_tts.resolved_credentials(path)
            self.assertEqual(config["api_key"], "temporary-key")
            self.assertEqual(config["speaker"], "env-speaker")
            self.assertNotIn("secret-api-key", doubao_tts.mask_identifier("secret-api-key"))
            self.assertNotIn(
                "secret-api-key",
                doubao_tts.redact("failed with secret-api-key", ("secret-api-key",)),
            )

    def test_insecure_config_permissions_are_rejected(self) -> None:
        if os.name != "posix":
            self.skipTest("POSIX permissions only")
        with tempfile.TemporaryDirectory() as temporary_name:
            path = Path(temporary_name) / "config.json"
            path.write_text('{"api_key":"secret","speaker":"voice"}', encoding="utf-8")
            os.chmod(path, 0o644)
            with self.assertRaises(doubao_tts.ConfigError):
                doubao_tts.load_config(path)

    def test_request_body_maps_numeric_and_clone_fields(self) -> None:
        body = doubao_tts.build_request_body(
            text="你好",
            speaker="voice",
            model="seed-tts-2.0-standard",
            speech_rate=10,
            pitch=-2,
            loudness_rate=5,
            tone_fidelity=True,
            section_id="shared-section",
            style_prompt="自然克制",
        )
        params = body["req_params"]
        self.assertEqual(params["audio_params"]["speech_rate"], 10)
        self.assertEqual(params["audio_params"]["loudness_rate"], 5)
        additions = json.loads(params["additions"])
        self.assertEqual(additions["post_process"]["pitch"], -2)
        self.assertEqual(additions["section_id"], "shared-section")
        self.assertTrue(additions["tone_fidelity"])
        self.assertEqual(additions["context_texts"], ["自然克制"])

    def test_sse_audio_chunks_are_concatenated(self) -> None:
        first = base64.b64encode(b"abc").decode("ascii")
        second = base64.b64encode(b"def").decode("ascii")
        response = FakeResponse(
            [
                'event: message\n',
                'data: {"code":0,"data":"%s"}\n' % first,
                '\n',
                'data: {"code":20000000,"data":"%s"}\n' % second,
                'data: [DONE]\n',
            ],
            {"X-Tt-Logid": "log-123"},
        )

        audio, log_id = doubao_tts.synthesize_segment(
            endpoint="https://example.invalid/tts",
            api_key="secret",
            resource_id="resource",
            request_id="request-123",
            body={"demo": True},
            timeout=1,
            opener=lambda request, timeout: response,
        )
        self.assertEqual(audio, b"abcdef")
        self.assertEqual(log_id, "log-123")

    def test_service_error_is_redacted_and_keeps_ids(self) -> None:
        secret = "never-print-this-key"
        response = FakeResponse(
            ['data: {"code":3001,"message":"bad never-print-this-key"}\n'],
            {"X-Tt-Logid": "log-error"},
        )
        with self.assertRaises(doubao_tts.ServiceError) as captured:
            doubao_tts.synthesize_segment(
                endpoint="https://example.invalid/tts",
                api_key=secret,
                resource_id="resource",
                request_id="request-error",
                body={"demo": True},
                timeout=1,
                opener=lambda request, timeout: response,
            )
        self.assertNotIn(secret, str(captured.exception))
        self.assertEqual(captured.exception.request_id, "request-error")
        self.assertEqual(captured.exception.log_id, "log-error")

    def test_chinese_segmentation_preserves_text_and_byte_limit(self) -> None:
        text = "第一句很短。第二句稍微长一点，适合测试中文标点分段！" * 20
        chunks = doubao_tts.split_chinese_text(text, max_bytes=90)
        self.assertGreater(len(chunks), 1)
        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(len(chunk.encode("utf-8")) <= 90 for chunk in chunks))

        no_punctuation = "中" * 80
        hard_chunks = doubao_tts.split_chinese_text(no_punctuation, max_bytes=30)
        self.assertEqual("".join(hard_chunks), no_punctuation)
        self.assertTrue(all(len(chunk.encode("utf-8")) <= 30 for chunk in hard_chunks))

    def test_failure_leaves_no_output_or_staging_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            output = root / "voice.mp3"
            args = doubao_tts.build_parser().parse_args(
                ["synthesize", "--text", "这是一段测试。", "--output", str(output)]
            )
            with mock.patch.object(doubao_tts, "require_program", return_value="tool"), mock.patch.object(
                doubao_tts,
                "resolved_credentials",
                return_value={
                    "api_key": "secret",
                    "speaker": "voice",
                    "resource_id": "seed-icl-2.0",
                    "model": "seed-tts-2.0-standard",
                    "endpoint": "https://example.invalid",
                },
            ), mock.patch.object(
                doubao_tts,
                "synthesize_segment",
                side_effect=doubao_tts.ServiceError("simulated failure"),
            ):
                with self.assertRaises(doubao_tts.ServiceError):
                    doubao_tts.synthesize(args)
            self.assertFalse(output.exists())
            self.assertEqual(list(root.iterdir()), [])

    def test_multi_segment_success_uses_atomic_final_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            root = Path(temporary_name)
            output = root / "voice.mp3"
            args = doubao_tts.build_parser().parse_args(
                [
                    "synthesize",
                    "--text",
                    "第一句。第二句。第三句。",
                    "--segment-max-bytes",
                    "16",
                    "--output",
                    str(output),
                ]
            )

            def fake_concat(segment_paths, destination, ffmpeg):
                destination.write_bytes(b"joined-audio")

            request_bodies = []

            def fake_synthesize_segment(**kwargs):
                request_bodies.append(kwargs["body"])
                return b"segment", "log-id"

            with mock.patch.object(doubao_tts, "require_program", return_value="tool"), mock.patch.object(
                doubao_tts,
                "resolved_credentials",
                return_value={
                    "api_key": "secret",
                    "speaker": "voice",
                    "resource_id": "seed-icl-2.0",
                    "model": "seed-tts-2.0-standard",
                    "endpoint": "https://example.invalid",
                },
            ), mock.patch.object(
                doubao_tts, "synthesize_segment", side_effect=fake_synthesize_segment
            ), mock.patch.object(
                doubao_tts, "concatenate_mp3", side_effect=fake_concat
            ) as concatenate, mock.patch.object(
                doubao_tts, "probe_duration", return_value=1.25
            ):
                result = doubao_tts.synthesize(args)

            self.assertEqual(result["status"], "ok")
            self.assertGreater(result["segments"], 1)
            self.assertEqual(output.read_bytes(), b"joined-audio")
            concatenate.assert_called_once()
            self.assertEqual([path.name for path in root.iterdir()], ["voice.mp3"])
            section_ids = {
                json.loads(body["req_params"]["additions"])["section_id"]
                for body in request_bodies
            }
            self.assertEqual(len(section_ids), 1)

    def test_main_returns_json_without_api_key(self) -> None:
        stream = io.StringIO()
        secret = "api-key-must-not-appear"
        with mock.patch.object(
            doubao_tts, "run", side_effect=doubao_tts.ServiceError("bad " + secret)
        ), mock.patch.dict(os.environ, {"DOUBAO_TTS_API_KEY": secret}), contextlib.redirect_stdout(
            stream
        ):
            code = doubao_tts.main([])
        self.assertEqual(code, 1)
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["status"], "error")
        self.assertNotIn(secret, payload["error"]["message"])


if __name__ == "__main__":
    unittest.main()
