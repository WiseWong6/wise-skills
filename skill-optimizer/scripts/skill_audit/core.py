#!/usr/bin/env python3
"""Public audit core for one Skill directory."""

from __future__ import annotations

import argparse
import codecs
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import unquote

from skill_audit.lifecycle import inspect_lifecycle, parse_agent_entry
from skill_audit.model import add_finding, count_findings, sort_findings
from skill_audit.reachability import inspect_reachability
from skill_audit.schema import (
    SCHEMA_PROFILE_CHOICES,
    effective_schema_profile,
    validate_frontmatter_schema,
)
from skill_audit.structure import inspect_structure
from skill_audit.test_system import inspect_test_system


MAX_IN_MEMORY_TEXT_BYTES = 1024 * 1024
# 兼容既有测试和外部导入；语义从“忽略上限”改为“整文件载入上限”。
MAX_TEXT_BYTES = MAX_IN_MEMORY_TEXT_BYTES
MIN_DUPLICATE_CHARS = 40
MAX_LEGACY_SIGNALS = 80
ARTIFACT_FILE_WARNING = 100
ARTIFACT_BYTES_WARNING = 2 * 1024 * 1024
EXECUTABLE_FILE_WARNING = 512 * 1024
EXECUTABLE_TOTAL_WARNING = 1024 * 1024
GENERATED_REVIEW_BLOCK = 1024 * 1024
PROFILE_CHOICES = ("auto", "general", "review")
EXECUTABLE_SUFFIXES = {".js", ".mjs", ".cjs", ".py", ".sh", ".ps1", ".cmd", ".bat"}
FONT_SUFFIXES = {".ttf", ".otf", ".woff", ".woff2"}
DATA_SUFFIXES = {".json", ".jsonl", ".csv", ".tsv", ".yaml", ".yml", ".toml"}
MEDIA_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf", ".mp4", ".mov", ".mp3", ".wav"}
GENERATED_NAME_PARTS = ("vendor-", ".min.", "bundle", "chunk-")
ADVANCED_UNDICI_APIS = (
    "agent",
    "proxyagent",
    "mockagent",
    "dispatcher",
    "pool",
    "client",
    "setglobaldispatcher",
    "getglobaldispatcher",
    "upgrade",
)
COMMON_METAFILE_NAMES = (
    "metafile.json",
    "meta.json",
    "bundle-metafile.json",
    ".wise-ppt-metafile.json",
    "bin/.wise-ppt-metafile.json",
)
SKIP_DIRS = {
    ".git",
    ".cache",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}
HUMAN_DOC_NAMES = {
    "CHANGELOG.md",
    "INSTALLATION_GUIDE.md",
    "QUICK_REFERENCE.md",
    "README.md",
    "README_EN.md",
}
LEGAL_ARTIFACT_PREFIXES = ("license", "copying")
LEGAL_SUPPORT_PREFIXES = ("notice", "attribution", "third_party")
SHOWCASE_PARTS = ("example", "examples", "sample", "samples", "showcase")
SURFACE_CHOICES = ("auto", "source", "release", "installed")
SKIP_ORPHAN_PREFIXES = ("test/", "tests/")
FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", re.DOTALL)
TOP_LEVEL_YAML_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):(?:\s*(.*))?$")
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
BACKTICK_PATH_RE = re.compile(
    r"`([A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-]+)+)`"
)
HTML_LINK_RE = re.compile(
    r"\b(?:href|src)\s*=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
LEGACY_RE = re.compile(
    r"旧逻辑|旧版|历史版本|兼容(?:旧|历史)?|迁移(?:说明|路径|入口)?|回滚|"
    r"\blegacy\b|\bdeprecated\b|\bfallback\b",
    re.IGNORECASE,
)
ACTIVE_LEGACY_RE = re.compile(
    r"保留.{0,24}(?:旧逻辑|旧版|历史版本)|"
    r"(?:继续|仍然|同时).{0,16}(?:使用|调用|加载|支持).{0,16}(?:旧逻辑|旧版|历史版本)|"
    r"兼容(?:旧版|历史版本|旧逻辑)|"
    r"(?:\blegacy\b|\bdeprecated\b)\s+(?:path|mode|contract|implementation|entry|workflow|schema|api)\b|"
    r"(?:\bkeep\b|\bretain\b|\bsupport\b|\bload\b|\brun\b|\buse\b).{0,32}(?:\blegacy\b|\bdeprecated\b)|"
    r"\bfallback\s+(?:to|path|mode|contract|implementation|entry|workflow|schema|api)\b",
    re.IGNORECASE,
)
INACTIVE_LEGACY_RE = re.compile(
    r"(?:不|未|没有|不得|禁止)(?:再|继续)?(?:保留|使用|支持|加载|调用).{0,24}(?:旧逻辑|旧版|历史版本|\blegacy\b|\bdeprecated\b|\bfallback\b)|"
    r"\bnot\b.{0,24}(?:evidence|keep|retain|use|load|run|support).{0,32}(?:\blegacy\b|\bdeprecated\b|\bfallback\b)",
    re.IGNORECASE,
)
CJK_RE = re.compile(
    "["
    "\u3400-\u4dbf"
    "\u4e00-\u9fff"
    "\uf900-\ufaff"
    "\u3040-\u30ff"
    "\uac00-\ud7af"
    "]"
)
SHELL_COMMAND_RE = re.compile(r"\bcommand\s+-v\s+([A-Za-z0-9._+-]+)")
JS_SPAWN_RE = re.compile(
    r"\b(?:spawn|spawnSync|execFile|execFileSync)\s*\(\s*['\"]([^'\"]+)['\"]"
)
PYTHON_SUBPROCESS_RE = re.compile(
    r"\bsubprocess\.(?:run|Popen|call|check_call|check_output)\s*\(\s*"
    r"(?:\[|\()\s*['\"]([^'\"]+)['\"]"
)
PYTHON_WHICH_RE = re.compile(r"\bshutil\.which\s*\(\s*['\"]([^'\"]+)['\"]")
SHEBANG_RE = re.compile(r"^#!\s*(?:/usr/bin/env\s+)?([^\s/]+|/[^\s]+)")
DEVELOPER_SCRIPT_PREFIXES = ("build_", "build-", "check_", "check-", "dump_", "dump-", "test_", "test-")
DEPENDENCY_MANIFEST_NAMES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "pipfile",
    "pipfile.lock",
    "poetry.lock",
}
KNOWN_AGENTS = ("codex", "claude", "cursor", "kimi", "zcode")
NODE_IMPORT_RE = re.compile(
    r"(?:\bfrom\s+|\bimport\s*\(\s*|\brequire\s*\(\s*)['\"]([^'\"]+)['\"]"
)
NODE_DOC_FLOOR_RE = re.compile(
    r"\bNode(?:\.js)?\b[^\n\d]{0,32}(?:>=|≥)?\s*v?(\d{1,3})(?:\.\d+(?:\.\d+)?)?\s*(?:\+|及以上|或更高|LTS)",
    re.IGNORECASE,
)
NODE_CODE_FLOOR_RE = re.compile(
    r"\b(?:MIN(?:IMUM)?_NODE_(?:MAJOR|VERSION)|NODE_MIN_VERSION|minimumNodeMajor|required_node_(?:major|version))\s*(?:=|:)\s*['\"]?v?(\d{1,3})\b",
    re.IGNORECASE,
)
CHROME_DOC_FLOOR_RE = re.compile(
    r"\b(?:Google\s+)?Chrome\b[^\n\d]{0,32}(?:>=|≥)?\s*v?(\d{2,3})\s*(?:\+|及以上|或更高)",
    re.IGNORECASE,
)
CHROME_CODE_FLOOR_RE = re.compile(
    r"\b(?:MIN(?:IMUM)?_CHROME_(?:MAJOR|VERSION)|CHROME_MIN_VERSION|minimumChromeMajor|required_chrome_(?:major|version))\s*(?:=|:)\s*['\"]?v?(\d{2,3})\b",
    re.IGNORECASE,
)
NETWORK_CALL_RE = re.compile(
    r"\bfetch\s*\(|\bhttps?\.(?:get|request)\s*\(|^\s*(?:command\s+)?(?:curl|wget)\s+",
    re.IGNORECASE | re.MULTILINE,
)


def is_within(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def rel_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def estimate_tokens(text: str) -> int:
    """Estimate tokens: one per CJK char, one per four other characters."""

    compact = re.sub(r"\s+", "", text)
    cjk = len(CJK_RE.findall(compact))
    other = max(0, len(compact) - cjk)
    return cjk + math.ceil(other / 4)


def strip_yaml_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_frontmatter(
    content: str, findings: List[Dict[str, Any]]
) -> Tuple[Dict[str, str], str, str]:
    match = FRONTMATTER_RE.match(content)
    if not match:
        add_finding(
            findings,
            "error",
            "frontmatter-invalid",
            "SKILL.md 缺少完整的 YAML frontmatter。",
            "SKILL.md",
            1,
        )
        return {}, "", content

    raw = match.group(1)
    values = {}  # type: Dict[str, str]
    seen = set()  # type: Set[str]
    for index, line in enumerate(raw.splitlines(), start=2):
        if not line or line[0].isspace() or line.lstrip().startswith("#"):
            continue
        key_match = TOP_LEVEL_YAML_KEY_RE.match(line)
        if not key_match:
            add_finding(
                findings,
                "error",
                "frontmatter-syntax",
                "frontmatter 含有无法识别的顶层语句。",
                "SKILL.md",
                index,
                line.strip(),
            )
            continue
        key, value = key_match.group(1), key_match.group(2) or ""
        if key in seen:
            add_finding(
                findings,
                "error",
                "frontmatter-duplicate-key",
                "frontmatter 重复定义了 {}。".format(key),
                "SKILL.md",
                index,
            )
        seen.add(key)
        values[key] = strip_yaml_scalar(value)

    for required in ("name", "description"):
        value = values.get(required, "").strip()
        if not value or "TODO" in value:
            add_finding(
                findings,
                "error",
                "frontmatter-required",
                "frontmatter 缺少有效的 {}。".format(required),
                "SKILL.md",
            )

    return values, raw, content[match.end() :].lstrip("\r\n")


def package_name_from_path(value: str) -> Optional[str]:
    normalized = value.replace("\\", "/")
    marker = "node_modules/"
    if marker not in normalized:
        return None
    remainder = normalized.split(marker, 1)[1]
    parts = [part for part in remainder.split("/") if part]
    if not parts:
        return None
    if parts[0].startswith("@") and len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]


def has_generated_signature(text: str) -> bool:
    return bool(
        re.search(
            r"(?im)^\s*(?://|/\*+|\*)[^\n]{0,160}(?:generated\s+by\s+(?:esbuild|rollup)|node_modules/|webpackbootstrap)",
            text,
        )
        or re.search(r"\b(?:var|const)\s+__commonjs\s*=", text)
    )


def extract_network_urls(text: str) -> List[str]:
    urls = set()  # type: Set[str]
    direct_patterns = (
        r"\bfetch\s*\(\s*['\"](https?://[^'\"]+)",
        r"\bhttps?\.(?:get|request)\s*\(\s*['\"](https?://[^'\"]+)",
        r"^\s*(?:command\s+)?(?:curl|wget)\b[^\n]*(https?://\S+)",
    )
    for pattern in direct_patterns:
        urls.update(re.findall(pattern, text, re.IGNORECASE | re.MULTILINE))
    assignments = {
        name: url
        for name, url in re.findall(
            r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*['\"](https?://[^'\"]+)",
            text,
            re.IGNORECASE,
        )
    }
    for name, url in assignments.items():
        if re.search(
            r"\b(?:fetch|https?\.(?:get|request))\s*\(\s*{}\b".format(
                re.escape(name)
            ),
            text,
            re.IGNORECASE,
        ):
            urls.add(url)
    return sorted(url.rstrip(");,\"") for url in urls)


def analyze_text_content(path: str, text: str) -> Dict[str, Any]:
    lower = text.lower()
    lines = text.splitlines()
    max_line = max((len(line) for line in lines), default=0)
    whitespace = sum(1 for char in text if char.isspace())
    whitespace_ratio = whitespace / max(1, len(text))
    name = Path(path).name.lower()
    minified = max_line >= 20000 and whitespace_ratio < 0.12
    obfuscation_signals = [
        signal
        for signal, present in (
            ("eval", bool(re.search(r"\beval\s*\(", text))),
            ("hex-escapes", len(re.findall(r"\\x[0-9a-fA-F]{2}", text)) >= 20),
            ("string-array", bool(re.search(r"\b_0x[0-9a-fA-F]{4,}\b", text))),
        )
        if present
    ]
    modules = []  # type: List[str]
    if "node_modules/" in text:
        modules = sorted(
            {
                package
                for package in (
                    package_name_from_path("node_modules/" + match.group(1))
                    for match in re.finditer(
                        r"node_modules/(@?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?)",
                        text,
                    )
                )
                if package
            }
        )
    generated = (
        any(part in name for part in GENERATED_NAME_PARTS)
        or has_generated_signature(text)
        or bool(modules)
    )
    return {
        "textual": True,
        "line_count": text.count("\n") + (1 if text else 0),
        "max_line_length": max_line,
        "whitespace_ratio": round(whitespace_ratio, 4),
        "generated": generated,
        "minified": minified,
        "suspected_obfuscation": minified and len(obfuscation_signals) >= 2,
        "obfuscation_signals": obfuscation_signals,
        "source_map": "sourcemappingurl=" in lower or path.lower().endswith(".map"),
        "license_marker": bool(
            re.search(r"@license|\blicen[sc]e\b|copyright|third[-_ ]party", lower)
        ),
        "module_markers": modules[:40],
        "network_call": bool(NETWORK_CALL_RE.search(text)),
        "remote_url_count": len(extract_network_urls(text)),
    }


def stream_text_profile(path: Path, relative: str) -> Dict[str, Any]:
    decoder = codecs.getincrementaldecoder("utf-8-sig")("strict")
    line_count = 0
    current_line = 0
    max_line = 0
    chars = 0
    whitespace = 0
    tail = ""
    generated_signature = False
    source_map = False
    license_marker = False
    modules = set()  # type: Set[str]
    obfuscation_counts = {"eval": 0, "hex-escapes": 0, "string-array": 0}
    remote_url_count = 0
    network_call = False
    saw_text = False
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(64 * 1024), b""):
                if b"\x00" in chunk:
                    return {"textual": False, "reason": "二进制文件"}
                decoded = decoder.decode(chunk)
                saw_text = saw_text or bool(decoded)
                combined = tail + decoded
                chars += len(decoded)
                whitespace += sum(1 for char in decoded if char.isspace())
                parts = decoded.split("\n")
                if len(parts) == 1:
                    current_line += len(decoded)
                else:
                    line_count += len(parts) - 1
                    max_line = max(max_line, current_line + len(parts[0]))
                    if len(parts) > 2:
                        max_line = max(max_line, max(len(part) for part in parts[1:-1]))
                    current_line = len(parts[-1])
                lower_combined = combined.lower()
                generated_signature = generated_signature or has_generated_signature(combined)
                source_map = source_map or "sourcemappingurl=" in lower_combined
                license_marker = license_marker or bool(
                    re.search(
                        r"@license|\blicen[sc]e\b|copyright|third[-_ ]party",
                        lower_combined,
                    )
                )
                network_call = network_call or bool(NETWORK_CALL_RE.search(combined))
                remote_url_count += len(extract_network_urls(combined))
                obfuscation_counts["eval"] += len(re.findall(r"\beval\s*\(", combined))
                obfuscation_counts["hex-escapes"] += len(
                    re.findall(r"\\x[0-9a-fA-F]{2}", combined)
                )
                obfuscation_counts["string-array"] += len(
                    re.findall(r"\b_0x[0-9a-fA-F]{4,}\b", combined)
                )
                if "node_modules/" in combined:
                    for match in re.finditer(
                        r"node_modules/(@?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?)",
                        combined,
                    ):
                        package = package_name_from_path(
                            "node_modules/" + match.group(1)
                        )
                        if package:
                            modules.add(package)
                tail = combined[-2048:]
            decoded = decoder.decode(b"", final=True)
    except UnicodeDecodeError:
        return {"textual": False, "reason": "非 UTF-8 文本或二进制文件"}
    except OSError as exc:
        return {"textual": False, "reason": "无法读取：{}".format(exc)}

    if decoded:
        chars += len(decoded)
        whitespace += sum(1 for char in decoded if char.isspace())
        current_line += len(decoded)
    max_line = max(max_line, current_line)
    if saw_text:
        line_count += 1
    whitespace_ratio = whitespace / max(1, chars)
    name = Path(relative).name.lower()
    generated = (
        any(part in name for part in GENERATED_NAME_PARTS)
        or generated_signature
        or bool(modules)
    )
    minified = max_line >= 20000 and whitespace_ratio < 0.12
    obfuscation_signals = []  # type: List[str]
    if obfuscation_counts["eval"]:
        obfuscation_signals.append("eval")
    if obfuscation_counts["hex-escapes"] >= 20:
        obfuscation_signals.append("hex-escapes")
    if obfuscation_counts["string-array"]:
        obfuscation_signals.append("string-array")
    return {
        "textual": True,
        "streamed": True,
        "line_count": line_count,
        "max_line_length": max_line,
        "whitespace_ratio": round(whitespace_ratio, 4),
        "generated": generated,
        "minified": minified,
        "suspected_obfuscation": minified and len(obfuscation_signals) >= 2,
        "obfuscation_signals": obfuscation_signals,
        "source_map": source_map or relative.lower().endswith(".map"),
        "license_marker": license_marker,
        "module_markers": sorted(modules)[:40],
        "network_call": network_call,
        "remote_url_count": remote_url_count,
    }


def collect_text_files(
    root: Path, findings: List[Dict[str, Any]]
) -> Tuple[Dict[str, str], List[Dict[str, str]], List[Dict[str, Any]]]:
    texts = {}  # type: Dict[str, str]
    skipped = []  # type: List[Dict[str, str]]
    records = []  # type: List[Dict[str, Any]]

    for dirpath, dirnames, filenames in os.walk(str(root), followlinks=False):
        current = Path(dirpath)
        kept_dirs = []  # type: List[str]
        for dirname in sorted(dirnames):
            child = current / dirname
            rel = rel_posix(child, root)
            if dirname in SKIP_DIRS:
                skipped.append({"file": rel + "/", "reason": "缓存或构建目录"})
                continue
            if child.is_symlink():
                try:
                    resolved = child.resolve(strict=True)
                except OSError:
                    add_finding(
                        findings,
                        "error",
                        "symlink-invalid",
                        "目录符号链接无法解析，已跳过。",
                        rel,
                    )
                    skipped.append({"file": rel + "/", "reason": "无效符号链接"})
                    continue
                code = "symlink-outside" if not is_within(root, resolved) else "symlink-directory"
                severity = "error" if code == "symlink-outside" else "info"
                add_finding(
                    findings,
                    severity,
                    code,
                    "目录符号链接指向 Skill 外部，已跳过。"
                    if code == "symlink-outside"
                    else "目录符号链接未递归跟随，避免循环读取。",
                    rel,
                )
                skipped.append({"file": rel + "/", "reason": "目录符号链接"})
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            path = current / filename
            rel = rel_posix(path, root)

            if path.is_symlink():
                try:
                    resolved = path.resolve(strict=True)
                except OSError:
                    add_finding(
                        findings,
                        "error",
                        "symlink-invalid",
                        "文件符号链接无法解析，已跳过。",
                        rel,
                    )
                    skipped.append({"file": rel, "reason": "无效符号链接"})
                    continue
                if not is_within(root, resolved):
                    add_finding(
                        findings,
                        "error",
                        "symlink-outside",
                        "文件符号链接指向 Skill 外部，已跳过。",
                        rel,
                    )
                    skipped.append({"file": rel, "reason": "越界符号链接"})
                    continue

            try:
                size = path.stat().st_size
            except OSError as exc:
                add_finding(
                    findings,
                    "error",
                    "file-unreadable",
                    "无法读取文件信息：{}".format(exc),
                    rel,
                )
                continue
            record = {"file": rel, "bytes": size}  # type: Dict[str, Any]
            records.append(record)
            if size > MAX_IN_MEMORY_TEXT_BYTES:
                profile = stream_text_profile(path, rel)
                record["text_profile"] = profile
                if not profile.get("textual"):
                    skipped.append({"file": rel, "reason": str(profile.get("reason"))})
                continue

            try:
                data = path.read_bytes()
            except OSError as exc:
                add_finding(
                    findings,
                    "error",
                    "file-unreadable",
                    "无法读取文件：{}".format(exc),
                    rel,
                )
                continue
            if b"\x00" in data:
                skipped.append({"file": rel, "reason": "二进制文件"})
                continue
            try:
                text = data.decode("utf-8-sig")
                texts[rel] = text
                record["text_profile"] = analyze_text_content(rel, text)
            except UnicodeDecodeError:
                skipped.append({"file": rel, "reason": "非 UTF-8 文本或二进制文件"})

    return texts, skipped, records


def clean_link_target(raw: str) -> Optional[str]:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        value = value[1 : value.index(">")]
    else:
        value = re.split(r"\s+[\"']", value, maxsplit=1)[0].strip()
    if not value or value.startswith(("#", "http://", "https://", "mailto:", "data:")):
        return None
    value = unquote(value).split("#", 1)[0].split("?", 1)[0]
    return value or None


def build_reference_graph(
    root: Path,
    texts: Dict[str, str],
    findings: List[Dict[str, Any]],
) -> Tuple[Dict[str, List[str]], Dict[str, int]]:
    graph = defaultdict(list)  # type: Dict[str, List[str]]
    for source, text in sorted(texts.items()):
        if not source.lower().endswith(".md"):
            continue
        source_path = root / source
        in_fence = False
        for line_number, line_text in enumerate(text.splitlines(), start=1):
            stripped = line_text.lstrip()
            if stripped.startswith(("```", "~~~")):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for pattern in (MARKDOWN_LINK_RE, HTML_LINK_RE):
                for match in pattern.finditer(line_text):
                    target_text = clean_link_target(match.group(1))
                    if target_text is None:
                        continue
                    candidate = (source_path.parent / target_text).resolve(strict=False)
                    if not is_within(root, candidate):
                        add_finding(
                            findings,
                            "error",
                            "link-outside",
                            "相对链接指向 Skill 目录外部。",
                            source,
                            line_number,
                            target_text,
                        )
                        continue
                    if not candidate.exists():
                        add_finding(
                            findings,
                            "error",
                            "link-broken",
                            "相对链接目标不存在。",
                            source,
                            line_number,
                            target_text,
                        )
                        continue
                    if candidate.is_file():
                        target = rel_posix(candidate, root)
                        if target in texts:
                            graph[source].append(target)
            # 反引号内联路径（如 `references/stages/01-brief.md`）只计入可达性，
            # 不做 broken/outside 报错：行内代码常含版本号、工具名等非路径文本。
            # 路径按惯例相对 Skill 根目录书写，故同时尝试相对根目录与相对本文档两种解析。
            for match in BACKTICK_PATH_RE.finditer(line_text):
                for base in (root, source_path.parent):
                    candidate = (base / match.group(1)).resolve(strict=False)
                    if not (is_within(root, candidate) and candidate.is_file()):
                        continue
                    target = rel_posix(candidate, root)
                    if target in texts:
                        graph[source].append(target)

    depths = {"SKILL.md": 0}  # type: Dict[str, int]
    queue = deque(["SKILL.md"])  # type: Deque[str]
    while queue:
        source = queue.popleft()
        for target in graph.get(source, []):
            next_depth = depths[source] + 1
            if target not in depths or next_depth < depths[target]:
                depths[target] = next_depth
                queue.append(target)

    deep = sorted(path for path, depth in depths.items() if depth > 1)
    if deep:
        add_finding(
            findings,
            "warning",
            "reference-depth",
            "存在二级或更深引用；将必要引用直接挂到 SKILL.md 可减少查找成本："
            + "、".join(deep[:10]),
        )

    return graph, depths


def paragraph_locations(text: str, file: str) -> Iterable[Tuple[str, str, int]]:
    lines = text.splitlines()
    start = 1
    current = []  # type: List[str]
    in_fence = False

    def emit() -> Optional[Tuple[str, str, int]]:
        raw = "\n".join(current).strip()
        normalized = re.sub(r"[`*_>#-]", " ", raw)
        normalized = re.sub(r"\s+", " ", normalized).strip().lower()
        if len(normalized) < MIN_DUPLICATE_CHARS:
            return None
        return normalized, raw, start

    for number, line in enumerate(lines, start=1):
        if line.strip().startswith(("```", "~~~")):
            if current:
                item = emit()
                if item:
                    yield item[0], file, item[2]
                current = []
            in_fence = not in_fence
            start = number + 1
            continue
        if in_fence:
            continue
        if not line.strip():
            if current:
                item = emit()
                if item:
                    yield item[0], file, item[2]
                current = []
            start = number + 1
            continue
        if not current:
            start = number
        current.append(line)

    if current:
        item = emit()
        if item:
            yield item[0], file, item[2]


def inspect_duplicates(texts: Dict[str, str], findings: List[Dict[str, Any]]) -> None:
    seen = defaultdict(list)  # type: Dict[str, List[Tuple[str, int]]]
    for file, text in sorted(texts.items()):
        if file.lower().endswith(".md"):
            for normalized, source, line in paragraph_locations(text, file):
                seen[normalized].append((source, line))

    for locations in seen.values():
        if len(locations) < 2:
            continue
        shown = "、".join("{}:{}".format(file, line) for file, line in locations[:6])
        add_finding(
            findings,
            "warning",
            "duplicate-paragraph",
            "发现完全重复的长段落：{}".format(shown),
        )


def is_first_party_semantic_text(path: str, text: str) -> bool:
    lower = path.lower()
    suffix = Path(lower).suffix
    name = Path(lower).name
    if lower.startswith(("vendor/", "third_party/", "third-party/")):
        return False
    if any(part in name for part in GENERATED_NAME_PARTS):
        return False
    if suffix in DATA_SUFFIXES | MEDIA_SUFFIXES | FONT_SUFFIXES:
        return False
    profile = analyze_text_content(path, text)
    return not profile["generated"] and not profile["minified"]


def inspect_legacy_signals(texts: Dict[str, str], findings: List[Dict[str, Any]]) -> None:
    count = 0
    suppressed_files = set()  # type: Set[str]
    suppressed_signals = 0
    for file, text in sorted(texts.items()):
        if not is_first_party_semantic_text(file, text):
            matches = len(LEGACY_RE.findall(text))
            if matches:
                suppressed_files.add(file)
                suppressed_signals += matches
            continue
        lines = text.splitlines()
        for line_number, line in enumerate(lines, start=1):
            stripped = line.lstrip()
            if "(?:" in line and stripped.startswith(("r\"", "r'", "br\"", "br'")):
                # A detector pattern is evidence about what to search for, not
                # evidence that the target keeps that legacy contract active.
                continue
            match = ACTIVE_LEGACY_RE.search(line)
            previous = lines[line_number - 2] if line_number > 1 else ""
            local_context = "{} {}".format(previous, line)
            if not match or INACTIVE_LEGACY_RE.search(local_context):
                continue
            add_finding(
                findings,
                "info",
                "legacy-signal",
                "发现可能仍在运行的旧合同线索；需结合当前合同判断，不自动删除。",
                file,
                line_number,
                match.group(0),
            )
            count += 1
            if count >= MAX_LEGACY_SIGNALS:
                add_finding(
                    findings,
                    "info",
                    "legacy-signal-limit",
                    "旧合同线索已达到 {} 条，停止继续列举。".format(MAX_LEGACY_SIGNALS),
                )
                return
    if suppressed_signals:
        add_finding(
            findings,
            "info",
            "legacy-generated-signals-suppressed",
            "第三方或生成文件中的 legacy/fallback 线索已聚合，不逐行污染报告。",
            evidence="files={} signals={}".format(
                len(suppressed_files), suppressed_signals
            ),
            kind="fact",
            confidence="high",
        )


def yaml_line_value(text: str, key: str) -> Optional[str]:
    match = re.search(r"(?m)^\s*{}:\s*(.*?)\s*$".format(re.escape(key)), text)
    if not match:
        return None
    return strip_yaml_scalar(match.group(1))


def inspect_openai_yaml(
    texts: Dict[str, str], skill_name: str, findings: List[Dict[str, Any]]
) -> None:
    path = "agents/openai.yaml"
    text = texts.get(path)
    if text is None:
        add_finding(
            findings,
            "warning",
            "openai-yaml-missing",
            "缺少 agents/openai.yaml；如需 Codex UI 展示，应补齐并与 SKILL.md 同步。",
        )
        return

    for key in ("display_name", "short_description", "default_prompt"):
        if not yaml_line_value(text, key):
            add_finding(
                findings,
                "warning",
                "openai-yaml-field",
                "agents/openai.yaml 缺少 {}。".format(key),
                path,
            )
    short = yaml_line_value(text, "short_description")
    if short and not 25 <= len(short) <= 64:
        add_finding(
            findings,
            "warning",
            "openai-yaml-description-length",
            "short_description 应为 25–64 个字符。",
            path,
        )
    prompt = yaml_line_value(text, "default_prompt")
    if prompt and skill_name and "${}".format(skill_name) not in prompt:
        add_finding(
            findings,
            "warning",
            "openai-yaml-prompt-name",
            "default_prompt 未显式提到 ${}。".format(skill_name),
            path,
        )


def is_human_or_legal_document(path: str) -> bool:
    name = Path(path).name
    lower = name.lower()
    return (
        name in HUMAN_DOC_NAMES
        or lower.startswith(LEGAL_ARTIFACT_PREFIXES)
        or lower.startswith(LEGAL_SUPPORT_PREFIXES)
    )


def inspect_docs(
    texts: Dict[str, str], depths: Dict[str, int], findings: List[Dict[str, Any]]
) -> None:
    orphans = []
    for path in sorted(texts):
        if path == "SKILL.md" or not path.lower().endswith(".md"):
            continue
        if path.startswith(SKIP_ORPHAN_PREFIXES):
            continue
        if is_human_or_legal_document(path):
            continue
        if path not in depths:
            orphans.append(path)
    if orphans:
        add_finding(
            findings,
            "warning",
            "orphan-doc",
            "以下 Markdown 未从 SKILL.md 的引用链到达：" + "、".join(orphans[:10]),
        )


def summarize_release_envelope(paths: Sequence[str]) -> Dict[str, Any]:
    paths = sorted(paths)
    root_files = [path for path in paths if "/" not in path]
    human_docs = [path for path in paths if Path(path).name in HUMAN_DOC_NAMES]
    license_files = [
        path
        for path in root_files
        if Path(path).name.lower().startswith(LEGAL_ARTIFACT_PREFIXES)
    ]
    legal_support = [
        path
        for path in root_files
        if Path(path).name.lower().startswith(LEGAL_SUPPORT_PREFIXES)
    ]
    showcase = [
        path
        for path in paths
        if any(part.lower() in SHOWCASE_PARTS for part in Path(path).parts)
    ]
    readme_present = "README.md" in root_files
    license_present = bool(license_files)
    return {
        "readme_present": readme_present,
        "license_present": license_present,
        "license_files": license_files,
        "human_documents": human_docs,
        "legal_support": legal_support,
        "showcase_examples": showcase,
    }


def inspect_release_envelope(
    records: Sequence[Dict[str, Any]],
    surface: str,
    findings: List[Dict[str, Any]],
    source_paths: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    target = summarize_release_envelope(
        [str(record["file"]) for record in records]
    )
    source = (
        summarize_release_envelope(source_paths)
        if source_paths is not None
        else None
    )
    checked = surface == "release"
    preservation_checked = checked and source is not None
    readme_removed = bool(
        preservation_checked
        and source["readme_present"]
        and not target["readme_present"]
    )
    license_removed = bool(
        preservation_checked
        and source["license_present"]
        and not target["license_present"]
    )
    removed_legal_support = (
        sorted(set(source["legal_support"]) - set(target["legal_support"]))
        if preservation_checked
        else []
    )

    if readme_removed:
        add_finding(
            findings,
            "error",
            "release-readme-removed",
            "权威源码原有 README.md，但用户发行包将其移除；不能仅因 Agent 不读取而清理。",
            "README.md",
        )
    if license_removed:
        add_finding(
            findings,
            "error",
            "release-license-removed",
            "权威源码原有许可证文件，但用户发行包将其移除。",
            "LICENSE",
        )
    if removed_legal_support:
        add_finding(
            findings,
            "error",
            "release-legal-notice-removed",
            "用户发行包移除了权威源码原有的法律或第三方声明。",
            evidence="、".join(removed_legal_support),
        )

    regression = readme_removed or license_removed or bool(removed_legal_support)

    return {
        "checked": checked,
        "preservation_checked": preservation_checked,
        "status": (
            "not-checked"
            if not checked
            else "observed"
            if not preservation_checked
            else "regressed"
            if regression
            else "preserved"
        ),
        "readme": {
            "required": False,
            "present": target["readme_present"],
            "source_present": source["readme_present"] if source else None,
            "removed": readme_removed,
            "file": "README.md",
        },
        "license": {
            "required": False,
            "present": target["license_present"],
            "source_present": source["license_present"] if source else None,
            "removed": license_removed,
            "files": target["license_files"],
        },
        "human_documents": target["human_documents"],
        "legal_support": target["legal_support"],
        "removed_legal_support": removed_legal_support,
        "showcase_examples": target["showcase_examples"],
        "note": "README 和法律文件不是通用必填项；原本没有不报错，源码原有但发行时移除才报错。除非 SKILL.md 引用，否则不计入声明上下文。",
    }


def run_git(root: Path, arguments: Sequence[str]) -> Optional[str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root)] + list(arguments),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def git_metadata(root: Path) -> Dict[str, Any]:
    git_root_text = run_git(root, ["rev-parse", "--show-toplevel"])
    if not git_root_text:
        return {"managed": False}

    git_root = Path(git_root_text).resolve(strict=False)
    try:
        pathspec = root.relative_to(git_root).as_posix() or "."
    except ValueError:
        return {"managed": False}

    tracked_text = run_git(git_root, ["ls-files", "--", pathspec]) or ""
    untracked_text = run_git(
        git_root, ["ls-files", "--others", "--exclude-standard", "--", pathspec]
    ) or ""
    ignored_text = run_git(
        git_root,
        ["ls-files", "--others", "--ignored", "--exclude-standard", "--", pathspec],
    ) or ""
    status_text = run_git(
        git_root, ["status", "--porcelain=v1", "--untracked-files=all", "--", pathspec]
    ) or ""

    upstream = run_git(
        git_root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"]
    )
    ahead = None  # type: Optional[int]
    behind = None  # type: Optional[int]
    if upstream:
        drift = run_git(git_root, ["rev-list", "--left-right", "--count", "HEAD...@{upstream}"])
        if drift:
            parts = drift.split()
            if len(parts) == 2 and all(part.isdigit() for part in parts):
                ahead, behind = int(parts[0]), int(parts[1])

    tracked_bytes = 0
    for relative in tracked_text.splitlines():
        candidate = git_root / relative
        if candidate.is_file():
            try:
                tracked_bytes += candidate.stat().st_size
            except OSError:
                pass

    dirty_entry_count = len(status_text.splitlines()) if status_text else 0
    return {
        "managed": True,
        "root": str(git_root),
        "head": run_git(git_root, ["rev-parse", "HEAD"]),
        "branch": run_git(git_root, ["branch", "--show-current"]),
        "upstream_snapshot": upstream,
        "ahead_of_upstream_snapshot": ahead,
        "behind_upstream_snapshot": behind,
        "dirty": bool(dirty_entry_count),
        "dirty_entry_count": dirty_entry_count,
        "tracked_file_count": len(tracked_text.splitlines()) if tracked_text else 0,
        "tracked_worktree_bytes": tracked_bytes,
        "untracked_file_count": len(untracked_text.splitlines()) if untracked_text else 0,
        "ignored_file_count": len(ignored_text.splitlines()) if ignored_text else 0,
        "note": "upstream 仅为本地快照；本审计不联网刷新远端。",
    }


def developer_asset_category(path: str) -> Optional[str]:
    lower = path.lower()
    name = Path(lower).name
    if lower.startswith(("tests/", "test/")):
        return "tests"
    if lower.startswith(".github/"):
        return "repository-automation"
    if name.startswith("requirements-dev"):
        return "development-dependencies"
    if lower.startswith("scripts/skill_audit/"):
        # These files are importable parts of the shipped auditor even when a
        # module name describes the subject it validates (for example,
        # test_system.py). Do not classify the runtime package by basename.
        return None
    if lower.startswith("scripts/") and name.startswith(DEVELOPER_SCRIPT_PREFIXES):
        return "development-scripts"
    return None


def inspect_developer_assets(records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    grouped = defaultdict(list)  # type: Dict[str, List[str]]
    for record in records:
        category = developer_asset_category(str(record["file"]))
        if category:
            grouped[category].append(str(record["file"]))
    return {
        "counts": {category: len(paths) for category, paths in sorted(grouped.items())},
        "examples": {
            category: sorted(paths)[:8] for category, paths in sorted(grouped.items())
        },
        "classification": "开发资产候选可留在源码；是否进入发行包需由发布合同决定。",
    }


def inspect_dependency_manifests(records: Sequence[Dict[str, Any]]) -> List[Dict[str, str]]:
    manifests = []  # type: List[Dict[str, str]]
    for record in records:
        path = str(record["file"])
        name = Path(path).name.lower()
        if name.startswith("requirements-dev"):
            phase = "开发/测试"
        elif name.startswith("requirements") and name.endswith((".txt", ".in")):
            phase = "待验证"
        elif name in DEPENDENCY_MANIFEST_NAMES:
            phase = "待验证"
        else:
            continue
        manifests.append({"file": path, "phase": phase})
    return sorted(manifests, key=lambda item: item["file"])


def parse_node_major_spec(spec: str) -> Optional[int]:
    match = re.search(r"(?:>=|>|\^|~)?\s*v?(\d{1,3})(?:\.\d+)?", spec)
    return int(match.group(1)) if match else None


def node_spec_allows_major(spec: str, major: int) -> bool:
    branches = [branch.strip() for branch in spec.split("||") if branch.strip()]
    if not branches:
        return True
    for branch in branches:
        minimum = None  # type: Optional[int]
        maximum = None  # type: Optional[int]
        exact = None  # type: Optional[int]
        for operator, raw in re.findall(r"(>=|<=|>|<|\^|~)?\s*v?(\d{1,3})(?:\.\d+)?(?:\.x)?", branch):
            value = int(raw)
            if operator == ">=":
                minimum = value if minimum is None else max(minimum, value)
            elif operator == ">":
                minimum = value + 1 if minimum is None else max(minimum, value + 1)
            elif operator == "<":
                maximum = value - 1 if maximum is None else min(maximum, value - 1)
            elif operator == "<=":
                maximum = value if maximum is None else min(maximum, value)
            elif operator in {"^", "~"}:
                minimum = value
                maximum = value
            elif re.fullmatch(r"\s*v?{}(?:\.x|(?:\.\d+){{0,2}})?\s*".format(value), branch):
                exact = value
        if exact is not None and major == exact:
            return True
        if exact is None and (minimum is None or major >= minimum) and (
            maximum is None or major <= maximum
        ):
            return True
    return False


def detect_command_major(commands: Sequence[Sequence[str]]) -> Optional[int]:
    for command in commands:
        executable = command[0]
        if os.path.isabs(executable):
            if not Path(executable).exists():
                continue
        elif shutil.which(executable) is None:
            continue
        try:
            completed = subprocess.run(
                list(command),
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                timeout=8,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        match = re.search(r"(?:v|Chrome\s+)(\d{1,3})(?:\.|\b)", completed.stdout)
        if match:
            return int(match.group(1))
    return None


def load_json_file(path: Path, max_bytes: int = 32 * 1024 * 1024) -> Optional[Any]:
    try:
        if path.stat().st_size > max_bytes:
            return None
        with path.open("r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def inspect_runtime_constraints(
    root: Path,
    texts: Dict[str, str],
    supported_node_majors: Sequence[int],
    findings: List[Dict[str, Any]],
    host_node_major: Optional[int] = None,
    host_chrome_major: Optional[int] = None,
) -> Dict[str, Any]:
    package = load_json_file(root / "package.json")
    engine_spec = None  # type: Optional[str]
    if isinstance(package, dict):
        engines = package.get("engines")
        if isinstance(engines, dict) and isinstance(engines.get("node"), str):
            engine_spec = engines["node"].strip()

    claims = []  # type: List[Dict[str, Any]]
    actual_node_gates = []  # type: List[Dict[str, Any]]
    actual_chrome_gates = []  # type: List[Dict[str, Any]]
    tested_node_majors = set()  # type: Set[int]
    for path, text in sorted(texts.items()):
        for match in NODE_DOC_FLOOR_RE.finditer(text):
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            line_text = text[line_start : line_end if line_end >= 0 else len(text)]
            if not re.search(
                r"要求|最低|需要|运行环境|支持版本|requires?|minimum|required|prerequisite",
                line_text,
                re.IGNORECASE,
            ):
                continue
            claim = {"file": path, "minimum": int(match.group(1)), "kind": "document"}
            claims.append(claim)
        for match in CHROME_DOC_FLOOR_RE.finditer(text):
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            line_text = text[line_start : line_end if line_end >= 0 else len(text)]
            if not re.search(
                r"要求|最低|需要|运行环境|支持版本|requires?|minimum|required|prerequisite",
                line_text,
                re.IGNORECASE,
            ):
                continue
            claims.append(
                {"file": path, "minimum": int(match.group(1)), "kind": "chrome-document"}
            )
        lower_path = path.lower()
        if lower_path.startswith((".github/", "tests/", "test/")):
            for match in re.finditer(
                r"(?:node-version|node_version|\bnode\b)\s*:\s*([^\n#]+)",
                text,
                re.IGNORECASE,
            ):
                tested_node_majors.update(
                    int(value)
                    for value in re.findall(r"\b(\d{1,3})(?:\.x|\.\d+)?\b", match.group(1))
                )
        if any(part in lower_path for part in ("doctor", "constant", "check", "test", ".github/")):
            for match in NODE_CODE_FLOOR_RE.finditer(text):
                actual_node_gates.append(
                    {"file": path, "minimum": int(match.group(1)), "kind": "runtime-gate"}
                )
            for match in re.finditer(
                r"\b(?:nodeMajor|node_major|major)\s*<\s*(\d{1,3})\b", text
            ):
                actual_node_gates.append(
                    {"file": path, "minimum": int(match.group(1)), "kind": "runtime-gate"}
                )
            for match in CHROME_CODE_FLOOR_RE.finditer(text):
                actual_chrome_gates.append(
                    {"file": path, "minimum": int(match.group(1)), "kind": "runtime-gate"}
                )

    if engine_spec:
        minimum = parse_node_major_spec(engine_spec)
        if minimum is not None:
            claims.append(
                {"file": "package.json", "minimum": minimum, "kind": "package-engine", "spec": engine_spec}
            )

    documented_node = [
        item for item in claims if item["kind"] in {"document", "package-engine"}
    ]
    documented_chrome = [item for item in claims if item["kind"] == "chrome-document"]
    declared_node_values = {int(item["minimum"]) for item in documented_node}
    actual_node_values = {int(item["minimum"]) for item in actual_node_gates}
    if actual_node_values and declared_node_values and max(actual_node_values) > min(declared_node_values):
        add_finding(
            findings,
            "error",
            "runtime-node-constraint-conflict",
            "Node 版本声明与实际 doctor/校验门槛冲突，按文档安装仍可能无法启动。",
            evidence="declared={} enforced={}".format(
                sorted(declared_node_values), sorted(actual_node_values)
            ),
            surface="runtime",
            kind="fact",
            confidence="high",
        )
    elif len(declared_node_values | actual_node_values) > 1:
        add_finding(
            findings,
            "warning",
            "runtime-node-constraint-divergence",
            "Node 版本线索不一致，请确认较高门槛是否必要并统一合同。",
            evidence="declared={} enforced={}".format(
                sorted(declared_node_values), sorted(actual_node_values)
            ),
            surface="runtime",
            kind="policy",
            confidence="medium",
        )
    if actual_node_values and tested_node_majors and min(tested_node_majors) < max(actual_node_values):
        add_finding(
            findings,
            "error",
            "runtime-node-test-matrix-conflict",
            "测试矩阵包含低于实际 doctor 门槛的 Node 版本，测试支持声明与可启动条件冲突。",
            evidence="tested={} enforced={}".format(
                sorted(tested_node_majors), sorted(actual_node_values)
            ),
            surface="test",
            kind="fact",
            confidence="high",
        )

    effective_node_min = max(declared_node_values | actual_node_values) if (
        declared_node_values or actual_node_values
    ) else None
    if host_node_major is None:
        host_node_major = detect_command_major((("node", "--version"),))
    if effective_node_min is not None and host_node_major is not None and host_node_major < effective_node_min:
        add_finding(
            findings,
            "error",
            "runtime-node-host-incompatible",
            "当前目标环境的 Node {} 低于主路径要求的 Node {}，公开入口无法按声明启动。".format(
                host_node_major, effective_node_min
            ),
            surface="runtime",
            kind="fact",
            confidence="high",
        )

    excluded = []  # type: List[int]
    if engine_spec:
        excluded = [
            major
            for major in supported_node_majors
            if not node_spec_allows_major(engine_spec, major)
            or (effective_node_min is not None and major < effective_node_min)
        ]
    elif effective_node_min is not None:
        excluded = [major for major in supported_node_majors if major < effective_node_min]
    if excluded:
        add_finding(
            findings,
            "warning",
            "runtime-supported-lts-excluded",
            "当前版本门槛排除了仍在目标支持矩阵中的 Node LTS；若无能力证据，应下调最低版本。",
            evidence="excluded={}".format(",".join(str(value) for value in excluded)),
            surface="runtime",
            kind="policy",
            confidence="high",
        )
    if documented_node and not actual_node_gates:
        add_finding(
            findings,
            "warning",
            "runtime-node-doc-only",
            "Node 最低版本只出现在文档或 package engines，实际公开入口未发现对应校验。",
            surface="runtime",
            kind="fact",
            confidence="medium",
        )

    effective_chrome_min = max(
        [int(item["minimum"]) for item in documented_chrome + actual_chrome_gates],
        default=None,
    )
    if host_chrome_major is None and effective_chrome_min is not None:
        host_chrome_major = detect_command_major(
            (
                ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"),
                ("google-chrome", "--version"),
                ("chromium", "--version"),
            )
        )
    if effective_chrome_min is not None and host_chrome_major is not None and host_chrome_major < effective_chrome_min:
        add_finding(
            findings,
            "error",
            "runtime-chrome-host-incompatible",
            "当前目标环境的 Chrome {} 低于主路径要求的 Chrome {}。".format(
                host_chrome_major, effective_chrome_min
            ),
            surface="runtime",
            kind="fact",
            confidence="high",
        )
    if documented_chrome and not actual_chrome_gates:
        add_finding(
            findings,
            "warning",
            "runtime-chrome-doc-only",
            "Chrome 最低版本只在文档中声明，实际 doctor/入口未发现对应校验。",
            surface="runtime",
            kind="fact",
            confidence="medium",
        )

    return {
        "supported_node_majors": list(supported_node_majors),
        "host_node_major": host_node_major,
        "host_chrome_major": host_chrome_major,
        "node_engine_spec": engine_spec,
        "node_claims": documented_node,
        "node_runtime_gates": actual_node_gates,
        "node_test_matrix_majors": sorted(tested_node_majors),
        "chrome_claims": documented_chrome,
        "chrome_runtime_gates": actual_chrome_gates,
        "effective_node_minimum": effective_node_min,
        "effective_chrome_minimum": effective_chrome_min,
    }


def resolve_metafile(
    root: Path,
    source_root: Optional[Path],
    explicit: Optional[Path],
    findings: List[Dict[str, Any]],
) -> Optional[Path]:
    if explicit is not None:
        candidate = explicit.expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        candidate = candidate.resolve(strict=False)
        if not candidate.is_file():
            add_finding(
                findings,
                "error",
                "metafile-missing",
                "显式指定的 esbuild metafile 不存在或不可读取。",
                evidence=str(candidate),
                surface="build",
                kind="fact",
                confidence="high",
            )
            return None
        return candidate
    for base in (root, source_root):
        if base is None:
            continue
        for relative in COMMON_METAFILE_NAMES:
            candidate = base / relative
            if candidate.is_file():
                return candidate.resolve(strict=False)
        matches = sorted(
            path
            for path in base.glob("**/*metafile*.json")
            if not any(part in SKIP_DIRS for part in path.parts)
        )
        if matches:
            return matches[0].resolve(strict=False)
    return None


def inspect_metafile(path: Optional[Path], findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    if path is None:
        return {"status": "not-found", "path": None, "reliable": False}
    payload = load_json_file(path, max_bytes=64 * 1024 * 1024)
    if not isinstance(payload, dict) or not isinstance(payload.get("inputs"), dict):
        add_finding(
            findings,
            "warning",
            "metafile-invalid",
            "metafile 不是可识别的 esbuild 结构，无法据此归因 bundle。",
            evidence=str(path),
            surface="build",
            kind="fact",
            confidence="high",
        )
        return {"status": "invalid", "path": str(path), "reliable": False}

    inputs = payload["inputs"]
    package_bytes = defaultdict(int)  # type: Dict[str, int]
    own_bytes = 0
    total_bytes = 0
    for input_path, detail in inputs.items():
        if not isinstance(detail, dict):
            continue
        size = int(detail.get("bytes", 0) or 0)
        total_bytes += size
        package = package_name_from_path(str(input_path))
        if package:
            package_bytes[package] += size
        else:
            own_bytes += size

    outputs = payload.get("outputs")
    output_entries = []  # type: List[Dict[str, Any]]
    output_package_bytes = defaultdict(int)  # type: Dict[str, int]
    output_own_bytes = 0
    external_packages = set()  # type: Set[str]
    if isinstance(outputs, dict):
        for output_path, detail in outputs.items():
            if not isinstance(detail, dict):
                continue
            output_packages = defaultdict(int)  # type: Dict[str, int]
            output_own = 0
            for input_path, contribution in (detail.get("inputs") or {}).items():
                if not isinstance(contribution, dict):
                    continue
                size = int(contribution.get("bytesInOutput", 0) or 0)
                package = package_name_from_path(str(input_path))
                if package:
                    output_packages[package] += size
                    output_package_bytes[package] += size
                else:
                    output_own += size
                    output_own_bytes += size
            for imported in detail.get("imports") or []:
                if not isinstance(imported, dict) or not imported.get("external"):
                    continue
                package = normalize_import_package(str(imported.get("path", "")))
                if package:
                    external_packages.add(package)
            output_entries.append(
                {
                    "file": str(output_path),
                    "bytes": int(detail.get("bytes", 0) or 0),
                    "entry_point": detail.get("entryPoint"),
                    "own_bytes": output_own,
                    "packages": dict(sorted(output_packages.items())),
                }
            )

    if output_own_bytes + sum(output_package_bytes.values()):
        own_bytes = output_own_bytes
        package_bytes = output_package_bytes
        measurement = "bytes-in-output"
    else:
        measurement = "input-bytes"
    denominator = own_bytes + sum(package_bytes.values())
    return {
        "status": "parsed",
        "path": str(path),
        "reliable": bool(denominator),
        "measurement": measurement,
        "input_count": len(inputs),
        "total_input_bytes": denominator,
        "own_bytes": own_bytes,
        "own_share": round(own_bytes / denominator, 4) if denominator else None,
        "packages": [
            {"name": name, "bytes": size, "share": round(size / denominator, 4)}
            for name, size in sorted(package_bytes.items(), key=lambda item: (-item[1], item[0]))
        ],
        "outputs": output_entries,
        "external_packages": sorted(external_packages),
    }


def normalize_import_package(specifier: str) -> Optional[str]:
    if specifier.startswith((".", "/", "node:", "file:")):
        return None
    parts = specifier.split("/")
    if specifier.startswith("@") and len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0] if parts else None


def entry_runtime(path: str, text: str, package: Optional[Dict[str, Any]]) -> str:
    lower = path.lower()
    if any(part in lower for part in ("browser", "frontend", "client", "web/")):
        return "browser"
    if re.search(r"\b(?:window|document|navigator)\b", text):
        return "browser"
    if isinstance(package, dict) and package.get("browser") and lower == str(package.get("browser")).lstrip("./").lower():
        return "browser"
    return "node"


def inspect_dependencies(
    root: Path,
    texts: Dict[str, str],
    metafile: Dict[str, Any],
    runtime: Dict[str, Any],
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    package = load_json_file(root / "package.json")
    package = package if isinstance(package, dict) else {}
    direct_runtime = set((package.get("dependencies") or {}).keys()) if isinstance(package.get("dependencies"), dict) else set()
    direct_dev = set((package.get("devDependencies") or {}).keys()) if isinstance(package.get("devDependencies"), dict) else set()
    optional = set((package.get("optionalDependencies") or {}).keys()) if isinstance(package.get("optionalDependencies"), dict) else set()

    lock_packages = set()  # type: Set[str]
    lock = load_json_file(root / "package-lock.json")
    if isinstance(lock, dict) and isinstance(lock.get("packages"), dict):
        for lock_path in lock["packages"]:
            package_name = package_name_from_path(str(lock_path))
            if package_name:
                lock_packages.add(package_name)

    imports = defaultdict(list)  # type: Dict[str, List[Dict[str, str]]]
    entries = defaultdict(set)  # type: Dict[str, Set[str]]
    for path, text in sorted(texts.items()):
        if not is_first_party_semantic_text(path, text):
            continue
        runtime_kind = entry_runtime(path, text, package)
        for match in NODE_IMPORT_RE.finditer(text):
            name = normalize_import_package(match.group(1))
            if not name:
                continue
            imports[name].append({"file": path, "runtime": runtime_kind})
            entries[path].add(name)

    metafile_packages = {
        str(item["name"]): item for item in metafile.get("packages", []) if isinstance(item, dict)
    }
    external_packages = set(metafile.get("external_packages", []))
    names = sorted(
        direct_runtime | direct_dev | optional | lock_packages | set(imports) | set(metafile_packages)
    )
    dependencies = []  # type: List[Dict[str, Any]]
    for name in names:
        if name in direct_runtime:
            relation, phase = "direct", "runtime"
        elif name in optional:
            relation, phase = "direct", "optional-runtime"
        elif name in direct_dev:
            relation, phase = "direct", "development"
        else:
            relation, phase = "transitive", "runtime-or-build"
        meta = metafile_packages.get(name, {})
        dependencies.append(
            {
                "name": name,
                "relation": relation,
                "phase": phase,
                "bundled": name in metafile_packages,
                "external": name in external_packages or (
                    name not in metafile_packages and bool(imports.get(name))
                ),
                "bytes": meta.get("bytes"),
                "share": meta.get("share"),
                "imported_by": imports.get(name, [])[:12],
            }
        )

    candidates = []  # type: List[Dict[str, Any]]
    all_names = set(names)
    contract = "\n".join(texts.get(path, "") for path in ("SKILL.md", "README.md"))
    contract_utf8 = bool(
        re.search(
            r"仅(?:接受|支持).*UTF-?8|UTF-?8\s*only|只(?:接受|支持).*UTF-?8",
            contract,
            re.IGNORECASE,
        )
    )
    source_corpus = "\n".join(
        text for path, text in texts.items() if is_first_party_semantic_text(path, text)
    )

    if "undici" in all_names:
        undici_corpus = "\n".join(
            texts.get(item["file"], "") for item in imports.get("undici", [])
        )
        advanced = sorted(
            api
            for api in ADVANCED_UNDICI_APIS
            if re.search(r"\b{}\b".format(api), undici_corpus, re.IGNORECASE)
        )
        node_min = runtime.get("effective_node_minimum")
        qualifies = (
            node_min is not None
            and node_min >= 18
            and not advanced
            and (bool(imports.get("undici")) or "undici" in direct_runtime)
        )
        candidate = {
            "dependency": "undici",
            "candidate": qualifies,
            "reason": (
                "目标 Node 已提供全局 fetch，且未发现 Undici 专有 API。"
                if qualifies
                else "仍使用专有 API 或最低 Node 版本证据不足，不能判定可移除。"
            ),
            "evidence": {"node_minimum": node_min, "advanced_apis": advanced},
        }
        candidates.append(candidate)
        if qualifies:
            add_finding(
                findings,
                "warning",
                "dependency-undici-native-candidate",
                "undici 是无依赖替代候选：当前用途可优先评估 Node 全局 fetch。",
                evidence="Node>={} advanced_apis=none".format(node_min),
                surface="runtime",
                kind="candidate",
                confidence="high",
            )

    if "pako" in all_names:
        usages = imports.get("pako", [])
        browser_use = any(item["runtime"] == "browser" for item in usages)
        qualifies = bool(usages) and not browser_use
        candidates.append(
            {
                "dependency": "pako",
                "candidate": qualifies,
                "reason": (
                    "仅在 Node 入口使用，可回归对照 node:zlib。"
                    if qualifies
                    else "存在浏览器路径或缺少调用路径证据，不能建议替换。"
                ),
                "evidence": {"usages": usages[:12]},
            }
        )
        if qualifies:
            add_finding(
                findings,
                "warning",
                "dependency-pako-native-candidate",
                "pako 是 Node-only 路径的无依赖替代候选，可验证 node:zlib 等价性。",
                surface="runtime",
                kind="candidate",
                confidence="high",
            )

    if "iconv-lite" in all_names:
        relation = next((item["relation"] for item in dependencies if item["name"] == "iconv-lite"), None)
        legacy_encodings = sorted(
            set(re.findall(r"\b(?:cp\d{3,4}|gbk|gb2312|big5|shift[_-]?jis|euc[-_]?jp)\b", source_corpus, re.IGNORECASE))
        )
        qualifies = relation == "transitive" and contract_utf8 and not legacy_encodings
        candidates.append(
            {
                "dependency": "iconv-lite",
                "candidate": qualifies,
                "reason": (
                    "它是传递依赖，输入合同限定 UTF-8，且未发现 legacy 编码用途。"
                    if qualifies
                    else "不是纯传递依赖、合同未限定 UTF-8，或确有多编码用途。"
                ),
                "evidence": {"relation": relation, "utf8_contract": contract_utf8, "legacy_encodings": legacy_encodings},
            }
        )
        if qualifies:
            add_finding(
                findings,
                "warning",
                "dependency-iconv-transitive-candidate",
                "iconv-lite 是可排除候选；需从引入链验证 UTF-8-only 合同不会被破坏。",
                surface="runtime",
                kind="candidate",
                confidence="medium",
            )

    parser_names = {"parse5", "htmlparser2", "cheerio", "jsdom"}
    parser_overlap = []  # type: List[Dict[str, Any]]
    for entry, entry_packages in sorted(entries.items()):
        overlap = sorted(entry_packages & parser_names)
        if len(overlap) >= 2:
            parser_overlap.append({"entry": entry, "packages": overlap})
    if parser_overlap:
        candidates.append(
            {
                "dependency": "html-parser-stack",
                "candidate": True,
                "reason": "同一自有入口直接引入多套 HTML 解析栈，应核对职责是否重叠。",
                "evidence": parser_overlap,
            }
        )
        add_finding(
            findings,
            "warning",
            "dependency-html-parser-overlap-candidate",
            "同一运行入口出现多套 HTML 解析栈；仅在职责重叠时合并。",
            evidence=json.dumps(parser_overlap, ensure_ascii=False),
            surface="runtime",
            kind="candidate",
            confidence="high",
        )

    if "pdf-lib" in all_names:
        meta = metafile_packages.get("pdf-lib", {})
        add_finding(
            findings,
            "info",
            "dependency-pdf-lib-cost",
            "pdf-lib 已计入体积归因；只有 Chrome 导出覆盖全部实际能力并通过回归后，才可建议移除。",
            evidence="bytes={}".format(meta.get("bytes", "unknown")),
            surface="runtime",
            kind="candidate",
            confidence="medium",
        )

    return {
        "manifest": "package.json" if package else None,
        "lockfile": "package-lock.json" if isinstance(lock, dict) else None,
        "dependencies": dependencies,
        "candidates": candidates,
        "policy": "依赖允许存在；先查系统原生能力，再复用已有依赖，最后才新增依赖。候选不等于可自动删除。",
    }


def artifact_category(record: Dict[str, Any]) -> str:
    path = str(record["file"])
    lower = path.lower()
    suffix = Path(lower).suffix
    name = Path(lower).name
    profile = record.get("text_profile") or {}
    if any(part in lower.split("/") for part in SHOWCASE_PARTS):
        return "examples"
    if suffix in FONT_SUFFIXES:
        return "fonts"
    if suffix in {".md", ".txt", ".rst"} or is_human_or_legal_document(path):
        return "docs"
    if lower.startswith(("vendor/", "third_party/", "third-party/")) or profile.get("module_markers") or any(
        part in name for part in ("vendor-", ".min.")
    ):
        return "third_party_code" if suffix in EXECUTABLE_SUFFIXES else "data"
    if suffix in DATA_SUFFIXES or any(
        part in lower
        for part in (
            "catalog-data",
            "registry-data",
            "dataset",
            "assets/data",
            "/catalog/",
            "/registry/",
        )
    ):
        return "data"
    if suffix in EXECUTABLE_SUFFIXES:
        return "own_code"
    return "data"


def inspect_artifact_risk(
    records: Sequence[Dict[str, Any]],
    profile: str,
    surface: str,
    metafile: Dict[str, Any],
    release_envelope: Dict[str, Any],
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    categories = defaultdict(lambda: {"files": 0, "bytes": 0})  # type: Dict[str, Dict[str, int]]
    executable = []  # type: List[Dict[str, Any]]
    generated = []  # type: List[Dict[str, Any]]
    suspected_obfuscated = []  # type: List[Dict[str, Any]]
    source_maps = []  # type: List[str]
    for record in records:
        category = artifact_category(record)
        categories[category]["files"] += 1
        categories[category]["bytes"] += int(record["bytes"])
        suffix = Path(str(record["file"])).suffix.lower()
        text_profile = record.get("text_profile") or {}
        if suffix == ".map":
            source_maps.append(str(record["file"]))
        if (
            category in {"own_code", "third_party_code"}
            and suffix in EXECUTABLE_SUFFIXES
            and text_profile.get("textual")
        ):
            item = {
                "file": record["file"],
                "bytes": int(record["bytes"]),
                "line_count": text_profile.get("line_count"),
                "max_line_length": text_profile.get("max_line_length"),
                "whitespace_ratio": text_profile.get("whitespace_ratio"),
                "classification": (
                    "suspected-obfuscated"
                    if text_profile.get("suspected_obfuscation")
                    else "generated-minified"
                    if text_profile.get("generated") and text_profile.get("minified")
                    else "generated-bundle"
                    if text_profile.get("generated")
                    else "minified-source"
                    if text_profile.get("minified")
                    else "source"
                ),
                "source_map": bool(text_profile.get("source_map")),
                "license_marker": bool(text_profile.get("license_marker")),
                "module_markers": text_profile.get("module_markers", []),
            }
            executable.append(item)
            if text_profile.get("generated") or text_profile.get("minified"):
                generated.append(item)
            if text_profile.get("suspected_obfuscation"):
                suspected_obfuscated.append(item)
            if text_profile.get("source_map"):
                source_maps.append(str(record["file"]))

    total_bytes = sum(int(record["bytes"]) for record in records)
    executable_bytes = sum(item["bytes"] for item in executable)
    generated_bytes = sum(item["bytes"] for item in generated)
    for item in executable:
        if item["bytes"] > EXECUTABLE_FILE_WARNING:
            add_finding(
                findings,
                "warning",
                "artifact-large-executable",
                "单个可执行文本超过 512 KiB，需要说明生成方式、来源和审阅路径。",
                file=str(item["file"]),
                evidence="bytes={} lines={} max_line={}".format(
                    item["bytes"], item["line_count"], item["max_line_length"]
                ),
                surface="release" if surface == "release" else "target",
                kind="policy",
                confidence="high",
            )
    if executable_bytes > EXECUTABLE_TOTAL_WARNING:
        add_finding(
            findings,
            "warning",
            "artifact-executable-budget",
            "可执行代码合计超过 1 MiB，需要给出组件归因和瘦身优先级。",
            evidence="bytes={}".format(executable_bytes),
            surface="release" if surface == "release" else "target",
            kind="policy",
            confidence="high",
        )
    if suspected_obfuscated:
        add_finding(
            findings,
            "warning",
            "artifact-suspected-obfuscation",
            "发现同时具备压缩和多项混淆特征的文件；这是疑似混淆，不等同于已证明恶意。",
            evidence="、".join(str(item["file"]) for item in suspected_obfuscated[:8]),
            surface="release" if surface == "release" else "target",
            kind="fact",
            confidence="medium",
        )

    legal_notice = bool(release_envelope.get("legal_support"))
    provenance = bool(metafile.get("reliable") or source_maps or legal_notice)
    if profile == "review" and generated_bytes > GENERATED_REVIEW_BLOCK and not provenance:
        add_finding(
            findings,
            "error",
            "artifact-generated-provenance-missing",
            "生成代码超过 1 MiB，但缺少 source map、可用 metafile/组件清单或第三方声明，发行审核无法追溯来源。",
            evidence="generated_bytes={}".format(generated_bytes),
            surface="release",
            kind="policy",
            confidence="high",
        )
    if profile == "review" and (
        len(records) > ARTIFACT_FILE_WARNING or total_bytes > ARTIFACT_BYTES_WARNING
    ):
        add_finding(
            findings,
            "warning",
            "artifact-release-budget",
            "发行目录超过解释预算，请按代码、第三方、数据、字体、示例和文档说明组成；大型合法资产不会因此自动判为冗余。",
            evidence="files={} bytes={}".format(len(records), total_bytes),
            surface="release",
            kind="policy",
            confidence="high",
        )
    own_share = metafile.get("own_share")
    if metafile.get("reliable") and isinstance(own_share, (float, int)) and own_share < 0.20:
        add_finding(
            findings,
            "warning",
            "artifact-third-party-dominant",
            "可靠 metafile 显示自有代码低于 20%；第三方主导，优先从系统原生替代和重复依赖入手瘦身。",
            evidence="own_share={:.1%}".format(float(own_share)),
            surface="release" if surface == "release" else "build",
            kind="policy",
            confidence="high",
        )

    category_rows = []  # type: List[Dict[str, Any]]
    for category in ("own_code", "third_party_code", "data", "fonts", "examples", "docs"):
        item = categories[category]
        category_rows.append(
            {
                "category": category,
                "files": item["files"],
                "bytes": item["bytes"],
                "share": round(item["bytes"] / total_bytes, 4) if total_bytes else 0,
            }
        )
    return {
        "profile": profile,
        "file_count": len(records),
        "logical_bytes": total_bytes,
        "categories": category_rows,
        "executable_bytes": executable_bytes,
        "generated_executable_bytes": generated_bytes,
        "executables": sorted(executable, key=lambda item: (-item["bytes"], item["file"])),
        "provenance": {
            "metafile": metafile.get("path"),
            "source_maps": source_maps,
            "third_party_notice": legal_notice,
            "sufficient_for_review": provenance,
        },
    }


def network_phase(path: str) -> str:
    lower = path.lower()
    if lower.startswith(("tests/", "test/", ".github/")) or "fixture" in lower:
        return "test-development"
    if any(part in lower for part in ("build", "release", "publish", "package")):
        return "build-release"
    if any(part in lower for part in ("install", "doctor", "bin/", "cli", "run")):
        return "user-runtime"
    return "unclassified"


def inspect_network_behavior(
    texts: Dict[str, str],
    records: Sequence[Dict[str, Any]],
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    contract = "\n".join(texts.get(path, "") for path in ("SKILL.md", "README.md"))
    strict_offline = bool(
        re.search(r"完全离线|无需联网|不需要联网|禁止联网|fully\s+offline|offline[- ]only", contract, re.IGNORECASE)
    )
    disclosed_optional = bool(
        re.search(r"首次|可选|optional|download|下载|缓存", contract, re.IGNORECASE)
    )
    sha_documented = bool(re.search(r"sha(?:256|512)|校验和|checksum", contract, re.IGNORECASE))
    events = []  # type: List[Dict[str, Any]]
    for path, text in sorted(texts.items()):
        if path.lower().endswith(("package-lock.json", "yarn.lock")):
            continue
        suffix = Path(path).suffix.lower()
        if suffix not in EXECUTABLE_SUFFIXES and not (
            suffix == "" and SHEBANG_RE.match(text.splitlines()[0] if text.splitlines() else "")
        ):
            continue
        if not is_first_party_semantic_text(path, text):
            continue
        calls = list(NETWORK_CALL_RE.finditer(text))
        urls = extract_network_urls(text)
        if not calls and not (urls and re.search(r"download|下载|font|字体|cache|缓存", text, re.IGNORECASE)):
            continue
        phase = network_phase(path)
        shell_network = bool(
            re.search(r"^\s*(?:command\s+)?(?:curl|wget)\s+", text, re.IGNORECASE | re.MULTILINE)
        )
        download_semantics = bool(
            re.search(r"download|下载|remote|远程|font[_ -]?url|字体[^\n]{0,20}(?:url|地址)|cache[_ -]?url", text, re.IGNORECASE)
        )
        events.append(
            {
                "file": path,
                "phase": phase,
                "call_count": len(calls),
                "urls": sorted(set(urls))[:8],
                "remote_evidence": bool(urls) or shell_network,
                "download_semantics": download_semantics,
            }
        )

    for record in records:
        profile = record.get("text_profile") or {}
        path = str(record["file"])
        if path in texts or not profile.get("textual") or not profile.get("network_call"):
            continue
        events.append(
            {
                "file": path,
                "phase": network_phase(path),
                "call_count": 1,
                "urls": [],
                "streamed": True,
                "remote_evidence": bool(profile.get("remote_url_count")),
                "download_semantics": False,
            }
        )

    sha_in_code = any(
        re.search(r"sha(?:256|512)|createHash\s*\(|hashlib\.", text, re.IGNORECASE)
        for text in texts.values()
    )
    checksum = sha_documented or sha_in_code
    dynamic_events = []  # type: List[Dict[str, Any]]
    for event in events:
        phase = event["phase"]
        actionable = bool(event.get("remote_evidence"))
        if not actionable:
            dynamic_events.append(event)
            continue
        if strict_offline and phase in {"user-runtime", "build-release", "unclassified"}:
            add_finding(
                findings,
                "error",
                "network-offline-contract-conflict",
                "合同声明完全离线，但公开运行/构建路径含强制联网行为。",
                file=event["file"],
                evidence="phase={} urls={}".format(phase, ",".join(event["urls"])),
                surface=phase,
                kind="fact",
                confidence="high",
            )
        elif disclosed_optional and checksum:
            add_finding(
                findings,
                "warning",
                "network-optional-download",
                "发现已披露且带校验线索的可选/首次下载；仍需确认失败可解释且不阻断离线路径。",
                file=event["file"],
                evidence="phase={}".format(phase),
                surface=phase,
                kind="policy",
                confidence="medium",
            )
        elif phase not in {"test-development"}:
            add_finding(
                findings,
                "warning",
                "network-behavior-undisclosed",
                "发现联网候选；需要说明阶段、是否强制、缓存位置、失败行为和完整性校验。",
                file=event["file"],
                evidence="phase={} urls={}".format(phase, ",".join(event["urls"])),
                surface=phase,
                kind="fact",
                confidence="medium",
            )

    if dynamic_events:
        add_finding(
            findings,
            "info",
            "network-dynamic-fetch-aggregated",
            "发现没有远端 URL 或下载语义的动态 fetch/HTTP 调用，已聚合为待追踪线索，不逐文件升级为联网风险。",
            evidence="files={}".format(len(dynamic_events)),
            surface="static-analysis",
            kind="fact",
            confidence="low",
        )

    grouped = defaultdict(int)  # type: Dict[str, int]
    for event in events:
        grouped[event["phase"]] += 1
    return {
        "mode": "static-only",
        "executed_target_code": False,
        "strict_offline_claim": strict_offline,
        "download_disclosed": disclosed_optional,
        "checksum_evidence": checksum,
        "events": events,
        "phase_counts": dict(sorted(grouped.items())),
    }


def normalize_command(command: str) -> str:
    return Path(command).name.strip()


def inspect_runtime_commands(texts: Dict[str, str]) -> List[Dict[str, Any]]:
    commands = defaultdict(set)  # type: Dict[str, Set[str]]
    for path, text in sorted(texts.items()):
        for pattern in (SHELL_COMMAND_RE, JS_SPAWN_RE, PYTHON_SUBPROCESS_RE, PYTHON_WHICH_RE):
            for match in pattern.finditer(text):
                command = normalize_command(match.group(1))
                if command and command not in {"true", "false"}:
                    commands[command].add(path)
        first_line = text.splitlines()[0] if text.splitlines() else ""
        match = SHEBANG_RE.match(first_line)
        if match:
            command = normalize_command(match.group(1))
            if command:
                commands[command].add(path)
    return [
        {"command": command, "locations": sorted(locations)[:12]}
        for command, locations in sorted(commands.items())
    ]


def declared_support(texts: Dict[str, str]) -> Dict[str, List[str]]:
    contract_files = ("SKILL.md", "README.md", "agents/openai.yaml")
    corpus = "\n".join(texts.get(path, "") for path in contract_files).lower()
    platforms = []  # type: List[str]
    if re.search(r"\bmacos\b|\bmac\s*os\b", corpus):
        platforms.append("macOS")
    if re.search(r"\bwindows\b", corpus):
        platforms.append("Windows")
    agents = [agent for agent in KNOWN_AGENTS if re.search(r"\b{}\b".format(agent), corpus)]
    return {"platforms": platforms, "agents": agents}


def is_public_shell_entry(path: str, text: str) -> bool:
    first_line = text.splitlines()[0] if text.splitlines() else ""
    if not re.match(r"^#!.*\b(?:sh|bash)\b", first_line):
        return False
    lower = path.lower()
    name = Path(lower).name
    if lower.startswith(("tests/", "test/")):
        return False
    return not name.startswith(DEVELOPER_SCRIPT_PREFIXES)


def inspect_platform_signals(texts: Dict[str, str]) -> Tuple[List[Dict[str, Any]], List[str]]:
    grouped = defaultdict(set)  # type: Dict[str, Set[str]]
    public_shell_entries = []  # type: List[str]
    for path, text in sorted(texts.items()):
        first_line = text.splitlines()[0] if text.splitlines() else ""
        if re.match(r"^#!.*\b(?:sh|bash)\b", first_line):
            grouped["shell-entry"].add(path)
            if is_public_shell_entry(path, text):
                public_shell_entries.append(path)
        if "/Applications/" in text:
            grouped["macos-application-path"].add(path)
        if "/tmp/" in text or "mktemp " in text:
            grouped["posix-temp-path"].add(path)
        if path.lower().endswith((".ps1", ".cmd", ".bat")):
            grouped["windows-entry"].add(path)
        elif Path(path).suffix.lower() in {".sh", ".py", ".js", ".mjs", ".cjs"} and re.search(
            r"(?m)^\s*(?:powershell|pwsh|cmd\.exe)\b", text, re.IGNORECASE
        ):
            grouped["windows-command"].add(path)
        if re.search(r"[A-Za-z]:\\", text):
            grouped["windows-path"].add(path)
    signals = [
        {"signal": signal, "count": len(paths), "examples": sorted(paths)[:8]}
        for signal, paths in sorted(grouped.items())
    ]
    return signals, sorted(public_shell_entries)


def tree_file_map(root: Path) -> Dict[str, Tuple[Path, int]]:
    files = {}  # type: Dict[str, Tuple[Path, int]]
    for dirpath, dirnames, filenames in os.walk(str(root), followlinks=False):
        current = Path(dirpath)
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIRS)
        for filename in sorted(filenames):
            path = current / filename
            if path.is_symlink():
                try:
                    resolved = path.resolve(strict=True)
                except OSError:
                    continue
                if not is_within(root, resolved):
                    continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            files[rel_posix(path, root)] = (path, size)
    return files


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_expected_release_exclusion(path: str) -> bool:
    lower = path.lower()
    name = Path(lower).name
    return bool(
        developer_asset_category(path)
        or lower.startswith((".github/", ".devcontainer/"))
        or name in {".gitignore", ".gitattributes", ".editorconfig"}
    )


def compare_trees(target: Path, source: Path, surface: str = "auto") -> Dict[str, Any]:
    if target == source:
        return {
            "status": "same-tree",
            "source": str(source),
            "target": str(target),
            "source_only_count": 0,
            "target_only_count": 0,
            "changed_count": 0,
            "note": "源码与目标解析到同一目录，不是独立安装副本。",
        }

    target_files = tree_file_map(target)
    source_files = tree_file_map(source)
    target_names = set(target_files)
    source_names = set(source_files)
    source_only = sorted(source_names - target_names)
    target_only = sorted(target_names - source_names)
    changed = []  # type: List[str]
    for path in sorted(source_names & target_names):
        source_path, source_size = source_files[path]
        target_path, target_size = target_files[path]
        if source_size != target_size or sha256_file(source_path) != sha256_file(target_path):
            changed.append(path)
    expected_release_pruning = bool(
        surface == "release"
        and source_only
        and all(is_expected_release_exclusion(path) for path in source_only)
        and not target_only
        and not changed
    )
    return {
        "status": (
            "in-sync"
            if not source_only and not target_only and not changed
            else "expected-release-pruning"
            if expected_release_pruning
            else "drift"
        ),
        "source": str(source),
        "target": str(target),
        "source_file_count": len(source_files),
        "target_file_count": len(target_files),
        "source_only_count": len(source_only),
        "target_only_count": len(target_only),
        "changed_count": len(changed),
        "source_only_examples": source_only[:12],
        "target_only_examples": target_only[:12],
        "changed_examples": changed[:12],
        "expected_release_pruning": expected_release_pruning,
        "note": (
            "发行包缺少开发侧文件属于正常裁剪；仍由发行外壳和入口检查判断是否误删用户资产。"
            if expected_release_pruning
            else None
        ),
    }


def audit_skill(
    target: Path,
    source: Optional[Path] = None,
    surface: str = "auto",
    profile: str = "auto",
    supported_node_majors: Sequence[int] = (22, 24),
    metafile: Optional[Path] = None,
    host_node_major: Optional[int] = None,
    host_chrome_major: Optional[int] = None,
    schema_profile: str = "auto",
    release_manifest: Optional[Path] = None,
    agent_entries: Sequence[Tuple[str, Path]] = (),
    test_system_contract: Optional[Path] = None,
) -> Tuple[Dict[str, Any], int]:
    if surface not in SURFACE_CHOICES:
        raise ValueError(
            "目标载体必须是 {} 之一：{}".format("、".join(SURFACE_CHOICES), surface)
        )
    if profile not in PROFILE_CHOICES:
        raise ValueError(
            "审核 profile 必须是 {} 之一：{}".format("、".join(PROFILE_CHOICES), profile)
        )
    effective_schema_profile(schema_profile)
    labels = [agent for agent, _ in agent_entries]
    if len(labels) != len(set(labels)):
        raise ValueError("--agent-entry 的 agent 名不能重复。")
    normalized_node_majors = sorted({int(value) for value in supported_node_majors})
    if any(value <= 0 for value in normalized_node_majors):
        raise ValueError("supported Node major 必须是正整数。")
    effective_profile = (
        "review" if profile == "auto" and surface == "release" else "general" if profile == "auto" else profile
    )
    input_path = Path(os.path.abspath(str(target.expanduser())))
    root = input_path.resolve(strict=False)
    if not root.exists() or not root.is_dir():
        raise ValueError("目标不是可读取的 Skill 目录：{}".format(target))

    source_input = None  # type: Optional[Path]
    source_root = None  # type: Optional[Path]
    if source is not None:
        source_input = Path(os.path.abspath(str(source.expanduser())))
        source_root = source_input.resolve(strict=False)
        if not source_root.exists() or not source_root.is_dir():
            raise ValueError("权威源码不是可读取的 Skill 目录：{}".format(source))

    findings = []  # type: List[Dict[str, Any]]
    texts, skipped, records = collect_text_files(root, findings)
    skill_content = texts.get("SKILL.md")
    if skill_content is None:
        add_finding(
            findings,
            "error",
            "skill-md-missing",
            "目标目录缺少可读取的 SKILL.md。",
            "SKILL.md",
        )
        values = {}  # type: Dict[str, str]
        frontmatter = ""
        body = ""
    else:
        values, frontmatter, body = parse_frontmatter(skill_content, findings)

    skill_name = values.get("name", "").strip()
    schema_analysis = validate_frontmatter_schema(
        values, root.name, schema_profile, findings
    )

    reference_graph, depths = build_reference_graph(root, texts, findings)
    inspect_docs(texts, depths, findings)
    inspect_duplicates(texts, findings)
    inspect_legacy_signals(texts, findings)
    inspect_openai_yaml(texts, skill_name, findings)

    input_is_symlink = input_path.is_symlink()
    git = git_metadata(root)
    developer_assets = inspect_developer_assets(records)
    dependency_manifests = inspect_dependency_manifests(records)
    runtime_commands = inspect_runtime_commands(texts)
    support = declared_support(texts)
    platform_signals, public_shell_entries = inspect_platform_signals(texts)

    if input_is_symlink:
        add_finding(
            findings,
            "warning" if git.get("managed") else "info",
            "installed-source-symlink",
            "输入路径是符号链接；安装副本与解析后的目录不是两个可独立验证的载体。",
            evidence="{} -> {}".format(input_path, root),
        )
    if developer_assets["counts"]:
        add_finding(
            findings,
            "info",
            "developer-assets-present",
            "发现开发资产候选；它们可以留在源码，但是否进入用户发行包必须单独判断。",
            evidence="、".join(
                "{}={}".format(key, value)
                for key, value in developer_assets["counts"].items()
            ),
        )
    if runtime_commands:
        add_finding(
            findings,
            "info",
            "runtime-command-candidates",
            "发现外部命令候选；需按开发、构建、发布、用户运行或可选能力逐项归类。",
            evidence="、".join(item["command"] for item in runtime_commands[:16]),
        )
    if git.get("untracked_file_count") or git.get("ignored_file_count"):
        add_finding(
            findings,
            "info",
            "local-only-files-present",
            "目标所在本地工作区含未跟踪或忽略文件；它们不能当作远端源码或发行包内容。",
            evidence="untracked={} ignored={}".format(
                git.get("untracked_file_count", 0), git.get("ignored_file_count", 0)
            ),
        )
    if git.get("ahead_of_upstream_snapshot") or git.get("behind_upstream_snapshot"):
        add_finding(
            findings,
            "info",
            "git-upstream-snapshot-drift",
            "本地 HEAD 与本地 upstream 快照不一致；若需要当前远端事实，应另行联网核对。",
            evidence="ahead={} behind={}".format(
                git.get("ahead_of_upstream_snapshot"), git.get("behind_upstream_snapshot")
            ),
        )
    if public_shell_entries and not any(
        item["signal"] == "windows-entry" for item in platform_signals
    ):
        add_finding(
            findings,
            "warning",
            "windows-entrypoint-unverified",
            "发现面向任务的 shell 入口，但未发现 Windows 启动入口；不能据此宣称 Windows 可用。",
            evidence="、".join(public_shell_entries[:8]),
        )

    source_comparison = None  # type: Optional[Dict[str, Any]]
    source_git = None  # type: Optional[Dict[str, Any]]
    source_paths = None  # type: Optional[List[str]]
    if source_root is not None and source_input is not None:
        source_comparison = compare_trees(root, source_root, surface=surface)
        source_comparison["input"] = str(source_input)
        source_git = git_metadata(source_root)
        source_paths = sorted(tree_file_map(source_root))
        if source_comparison["status"] == "drift":
            add_finding(
                findings,
                "warning",
                "source-install-drift",
                "权威源码与目标副本内容不一致；必须先判断哪一侧代表当前合同。",
                evidence="source_only={} target_only={} changed={}".format(
                    source_comparison["source_only_count"],
                    source_comparison["target_only_count"],
                    source_comparison["changed_count"],
                ),
            )
        elif source_comparison["status"] == "same-tree":
            add_finding(
                findings,
                "info",
                "source-install-same-tree",
                "权威源码与目标解析到同一目录；这只能证明当前内容相同，不能代替发行包或干净安装验证。",
            )
        elif source_comparison["status"] == "expected-release-pruning":
            add_finding(
                findings,
                "info",
                "source-release-pruning-expected",
                "发行包仅缺少开发侧文件，按正常裁剪记录，不再误报为安装漂移。",
                evidence="source_only={}".format(source_comparison["source_only_count"]),
                surface="release",
                kind="fact",
                confidence="high",
            )

    release_envelope = inspect_release_envelope(
        records,
        surface,
        findings,
        source_paths=source_paths,
    )

    runtime_constraints = inspect_runtime_constraints(
        root,
        texts,
        normalized_node_majors,
        findings,
        host_node_major=host_node_major,
        host_chrome_major=host_chrome_major,
    )
    metafile_path = resolve_metafile(root, source_root, metafile, findings)
    metafile_analysis = inspect_metafile(metafile_path, findings)
    dependency_analysis = inspect_dependencies(
        root, texts, metafile_analysis, runtime_constraints, findings
    )
    artifact_analysis = inspect_artifact_risk(
        records,
        effective_profile,
        surface,
        metafile_analysis,
        release_envelope,
        findings,
    )
    network_analysis = inspect_network_behavior(texts, records, findings)

    manifest_path = release_manifest
    if manifest_path is not None and not manifest_path.expanduser().is_absolute():
        manifest_path = root / manifest_path
    lifecycle, version_coordinates, runtime_verification = inspect_lifecycle(
        input_path,
        root,
        values,
        git,
        findings,
        source_input=source_input,
        source_root=source_root,
        source_git=source_git,
        release_manifest=manifest_path,
        agent_entries=agent_entries,
    )
    reachability = inspect_reachability(
        root,
        texts,
        records,
        reference_graph,
        surface,
        dependency_analysis,
        metafile_analysis,
        findings,
    )
    test_system = inspect_test_system(
        root,
        skill_name,
        surface,
        git,
        findings,
        contract_path=test_system_contract,
    )
    structure = inspect_structure(
        records,
        texts,
        reference_graph,
        lifecycle,
        str(schema_analysis["effective"]),
        surface,
        findings,
        test_system=test_system,
    )

    sort_findings(findings)

    reachable_refs = sorted(path for path, depth in depths.items() if depth > 0)
    conditional_text = "\n".join(texts[path] for path in reachable_refs if path in texts)
    target_text = "\n".join(texts[path] for path in sorted(texts))
    declared_context = "\n".join((frontmatter, body, conditional_text))
    total_bytes = sum(int(record["bytes"]) for record in records)
    streamed_files = [
        {
            "file": str(record["file"]),
            "bytes": int(record["bytes"]),
            "profile": record.get("text_profile"),
        }
        for record in records
        if (record.get("text_profile") or {}).get("streamed")
    ]
    largest_files = sorted(records, key=lambda item: (-int(item["bytes"]), str(item["file"])))[:12]
    metrics = {
        "file_count": len(records),
        "text_file_count": len(texts),
        "streamed_text_file_count": len(streamed_files),
        "skipped_file_count": len(skipped),
        "metadata_chars": len(frontmatter),
        "metadata_estimated_tokens": estimate_tokens(frontmatter),
        "triggered_body_chars": len(body),
        "triggered_body_estimated_tokens": estimate_tokens(body),
        "conditional_reference_count": len(reachable_refs),
        "conditional_reference_chars": len(conditional_text),
        "conditional_reference_estimated_tokens": estimate_tokens(conditional_text),
        "declared_context_chars": len(declared_context),
        "declared_context_estimated_tokens": estimate_tokens(declared_context),
        "target_text_chars": len(target_text),
        "target_text_estimated_tokens": estimate_tokens(target_text),
        "target_total_bytes": total_bytes,
        "max_reference_depth": max(depths.values()) if depths else 0,
    }

    counts = count_findings(findings)
    exit_code = 1 if counts["error"] else 0
    result = {
        "target": str(input_path),
        "resolved_target": str(root),
        "summary": dict(counts, exit_code=exit_code),
        "metrics": metrics,
        "surfaces": {
            "target_surface": surface,
            "requested_profile": profile,
            "effective_profile": effective_profile,
            "schema_profile": schema_analysis,
            "input_is_symlink": input_is_symlink,
            "git": git,
            "authoritative_source": {
                "status": "provided" if source is not None else "not-provided",
                "comparison": source_comparison,
                "git": source_git,
            },
            "release_artifact": {
                "status": "provided" if surface == "release" else "not-provided",
                "path": str(root) if surface == "release" else None,
                "note": (
                    "目标已按用户发行包检查。"
                    if surface == "release"
                    else "审计器不会把源码或安装目录自动当成用户发行包。"
                ),
            },
            "release_envelope": release_envelope,
            "developer_assets": developer_assets,
            "dependency_manifests": dependency_manifests,
            "runtime_command_candidates": runtime_commands,
            "declared_support": support,
            "platform_signals": platform_signals,
            "public_shell_entries": public_shell_entries,
            "runtime_constraints": runtime_constraints,
            "metafile": metafile_analysis,
            "dependency_analysis": dependency_analysis,
            "artifact_analysis": artifact_analysis,
            "network_analysis": network_analysis,
        },
        "lifecycle": lifecycle,
        "version_coordinates": version_coordinates,
        "runtime_verification": runtime_verification,
        "reachability": reachability,
        "test_system": test_system,
        "structure": structure,
        "files": {
            "text": sorted(texts),
            "reachable_references": reachable_refs,
            "streamed": streamed_files,
            "skipped": skipped,
            "largest": largest_files,
        },
        "findings": findings,
        "token_estimation": "CJK 字符按 1 token，其他非空白字符按每 4 个约 1 token；声明上下文只作前后对比，不等于实际模型账单。",
    }
    return result, exit_code


def format_text(result: Dict[str, Any]) -> str:
    summary = result["summary"]
    metrics = result["metrics"]
    surfaces = result["surfaces"]
    test_system = result["test_system"]
    category_labels = {
        "own_code": "自有代码",
        "third_party_code": "第三方代码",
        "data": "数据/其他资产",
        "fonts": "字体",
        "examples": "示例",
        "docs": "文档",
    }
    category_summary = "、".join(
        "{} {:.1%}".format(category_labels[item["category"]], item["share"])
        for item in surfaces["artifact_analysis"]["categories"]
        if item["bytes"]
    )
    if summary["error"]:
        conclusion = "有 {} 个阻断问题，修复前不应继续改造。".format(summary["error"])
    elif summary["warning"]:
        conclusion = "没有阻断问题，有 {} 项需要人工判断。".format(summary["warning"])
    else:
        conclusion = "没有发现结构性阻断问题。"

    lines = [
        "Skill 审计：{}".format(result["target"]),
        "结论：{}".format(conclusion),
        "",
        "角色与载体：",
        "- 输入路径：{}".format(result["target"]),
        "- 解析目录：{}{}".format(
            result["resolved_target"],
            "（符号链接）" if surfaces["input_is_symlink"] else "",
        ),
        "- 目标载体：{}".format(surfaces["target_surface"]),
        "- 审核 profile：{}".format(surfaces["effective_profile"]),
        "- 平台 schema：{}".format(surfaces["schema_profile"]["effective"]),
        "- 权威源码：{}".format(surfaces["authoritative_source"]["status"]),
        "- 用户发行包：{}".format(surfaces["release_artifact"]["status"]),
        "- Agent 安装入口：{} 个；真实运行：{}".format(
            len(result["lifecycle"]["agent_entries"]),
            result["runtime_verification"]["status"],
        ),
        "- 死重候选：{} 个 / {} 字节（静态候选，不是确认删除）".format(
            len(result["reachability"]["candidates"]),
            result["reachability"]["candidate_bytes"],
        ),
        "- 测试体系：{}（合同={}，机制={}，runner={}，未登记={}）".format(
            test_system["status"],
            test_system["contract"]["status"],
            len(test_system["mechanisms"]),
            len(test_system["runners"]),
            len(test_system["unregistered_files"]),
        ),
        "- 发行外壳：{}（README={}，LICENSE={}）".format(
            surfaces["release_envelope"]["status"],
            "有" if surfaces["release_envelope"]["readme"]["present"] else "缺",
            "有" if surfaces["release_envelope"]["license"]["present"] else "缺",
        ),
        "",
        "声明上下文估算：",
        "- 常驻 metadata：{} token".format(metrics["metadata_estimated_tokens"]),
        "- 触发后正文：{} token".format(metrics["triggered_body_estimated_tokens"]),
        "- 条件引用：{} token（{} 个文件）".format(
            metrics["conditional_reference_estimated_tokens"],
            metrics["conditional_reference_count"],
        ),
        "- 声明可达上限：{} token".format(metrics["declared_context_estimated_tokens"]),
        "",
        "目标载荷：",
        "- 文件：{} 个；字节：{}".format(metrics["file_count"], metrics["target_total_bytes"]),
        "- 可执行代码：{} 字节；生成代码：{} 字节".format(
            surfaces["artifact_analysis"]["executable_bytes"],
            surfaces["artifact_analysis"]["generated_executable_bytes"],
        ),
        "- 分类占比：{}".format(category_summary or "无可分类载荷"),
        "- 目录内全部文本估算：{} token（不是模型上下文）".format(
            metrics["target_text_estimated_tokens"]
        ),
    ]

    labels = {"error": "阻断", "warning": "提醒", "info": "线索"}
    visible_info = 0
    hidden_info = 0
    if result["findings"]:
        lines.extend(["", "发现："])
    for item in result["findings"]:
        if item["severity"] == "info":
            if visible_info >= 12:
                hidden_info += 1
                continue
            visible_info += 1
        location = item.get("file", "")
        if item.get("line"):
            location += ":{}".format(item["line"])
        prefix = "[{}]".format(labels[item["severity"]])
        if location:
            prefix += " {}".format(location)
        lines.append("- {} {}".format(prefix, item["message"]))
    if hidden_info:
        lines.append("- [线索] 另有 {} 条信息级线索未在简洁输出中展开。".format(hidden_info))

    lines.extend(["", "估算说明：{}".format(result["token_estimation"])])
    return "\n".join(lines)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="只读审计一个 Skill 目录")
    parser.add_argument("skill_directory", help="目标 Skill 目录")
    parser.add_argument("--source", help="可选：权威源码 Skill 目录")
    parser.add_argument(
        "--surface",
        choices=SURFACE_CHOICES,
        default="auto",
        help="目标载体；release 配合 --source 检查既有 README 和许可证是否被移除",
    )
    parser.add_argument(
        "--profile",
        choices=PROFILE_CHOICES,
        default="auto",
        help="审核强度；auto 在 release 载体使用 review，其余使用 general",
    )
    parser.add_argument(
        "--schema-profile",
        choices=SCHEMA_PROFILE_CHOICES,
        default="auto",
        help="平台 metadata/结构政策；auto 保持现有 Codex 合同，redskill 仅增加平台政策提醒",
    )
    parser.add_argument(
        "--release-manifest",
        help="可选：发行 manifest；相对路径按目标 Skill 目录解析",
    )
    parser.add_argument(
        "--agent-entry",
        action="append",
        default=[],
        metavar="AGENT=PATH",
        help="可重复：显式提供一个 Agent 的 Skill 安装入口",
    )
    parser.add_argument(
        "--supported-node-majors",
        default="22,24",
        help="由调用方根据当前官方支持矩阵传入，例如 22,24；审计器本身不联网查询",
    )
    parser.add_argument(
        "--metafile",
        help="显式提供 esbuild metafile；相对路径按目标 Skill 目录解析",
    )
    parser.add_argument(
        "--test-system-contract",
        help="可选：源仓测试体系合同；相对路径按 Git 根（非 Git 目标按目标根）解析",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        try:
            supported_node_majors = [
                int(value.strip())
                for value in args.supported_node_majors.split(",")
                if value.strip()
            ]
        except ValueError:
            raise ValueError("--supported-node-majors 必须是逗号分隔的整数。")
        if not supported_node_majors:
            raise ValueError("--supported-node-majors 不能为空。")
        result, exit_code = audit_skill(
            Path(args.skill_directory),
            source=Path(args.source) if args.source else None,
            surface=args.surface,
            profile=args.profile,
            supported_node_majors=supported_node_majors,
            metafile=Path(args.metafile) if args.metafile else None,
            schema_profile=args.schema_profile,
            release_manifest=(
                Path(args.release_manifest) if args.release_manifest else None
            ),
            agent_entries=[parse_agent_entry(value) for value in args.agent_entry],
            test_system_contract=(
                Path(args.test_system_contract) if args.test_system_contract else None
            ),
        )
    except (OSError, ValueError) as exc:
        if args.format == "json":
            print(json.dumps({"error": str(exc), "exit_code": 2}, ensure_ascii=False, indent=2))
        else:
            print("审计失败：{}".format(exc), file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_text(result))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
