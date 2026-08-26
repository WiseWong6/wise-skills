#!/usr/bin/env python3
"""Read-only structural and context-cost audit for one Skill directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import unquote


MAX_TEXT_BYTES = 1024 * 1024
MIN_DUPLICATE_CHARS = 40
MAX_LEGACY_SIGNALS = 80
SKIP_DIRS = {
    ".git",
    ".cache",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
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
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
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


def add_finding(
    findings: List[Dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    file: Optional[str] = None,
    line: Optional[int] = None,
    evidence: Optional[str] = None,
) -> None:
    item = {"severity": severity, "code": code, "message": message}  # type: Dict[str, Any]
    if file is not None:
        item["file"] = file
    if line is not None:
        item["line"] = line
    if evidence is not None:
        item["evidence"] = evidence
    findings.append(item)


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

    unexpected = sorted(set(values) - {"name", "description"})
    if unexpected:
        add_finding(
            findings,
            "warning",
            "frontmatter-extra-keys",
            "frontmatter 含有额外字段，请确认它们属于当前平台合同："
            + "、".join(unexpected),
            "SKILL.md",
        )

    name = values.get("name", "").strip()
    if name and not NAME_RE.fullmatch(name):
        add_finding(
            findings,
            "error",
            "skill-name-invalid",
            "Skill 名称必须使用小写字母、数字和单连字符。",
            "SKILL.md",
        )

    return values, raw, content[match.end() :].lstrip("\r\n")


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
            records.append({"file": rel, "bytes": size})
            if size > MAX_TEXT_BYTES:
                skipped.append(
                    {"file": rel, "reason": "超过 {} 字节上限".format(MAX_TEXT_BYTES)}
                )
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
                texts[rel] = data.decode("utf-8-sig")
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


def inspect_legacy_signals(texts: Dict[str, str], findings: List[Dict[str, Any]]) -> None:
    count = 0
    for file, text in sorted(texts.items()):
        for line_number, line in enumerate(text.splitlines(), start=1):
            match = LEGACY_RE.search(line)
            if not match:
                continue
            add_finding(
                findings,
                "info",
                "legacy-signal",
                "发现可能与旧合同有关的线索；需结合当前合同判断，不自动删除。",
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

    return {
        "managed": True,
        "root": str(git_root),
        "head": run_git(git_root, ["rev-parse", "HEAD"]),
        "branch": run_git(git_root, ["branch", "--show-current"]),
        "upstream_snapshot": upstream,
        "ahead_of_upstream_snapshot": ahead,
        "behind_upstream_snapshot": behind,
        "dirty_entry_count": len(status_text.splitlines()) if status_text else 0,
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


def compare_trees(target: Path, source: Path) -> Dict[str, Any]:
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
    return {
        "status": "in-sync" if not source_only and not target_only and not changed else "drift",
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
    }


def audit_skill(
    target: Path,
    source: Optional[Path] = None,
    surface: str = "auto",
) -> Tuple[Dict[str, Any], int]:
    if surface not in SURFACE_CHOICES:
        raise ValueError(
            "目标载体必须是 {} 之一：{}".format("、".join(SURFACE_CHOICES), surface)
        )
    input_path = Path(os.path.abspath(str(target.expanduser())))
    root = input_path.resolve(strict=False)
    if not root.exists() or not root.is_dir():
        raise ValueError("目标不是可读取的 Skill 目录：{}".format(target))

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
    if skill_name and root.name != skill_name:
        add_finding(
            findings,
            "error",
            "skill-name-directory-mismatch",
            "frontmatter 名称 {} 与目录名 {} 不一致。".format(skill_name, root.name),
            "SKILL.md",
        )

    _, depths = build_reference_graph(root, texts, findings)
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
    if source is not None:
        source_input = Path(os.path.abspath(str(source.expanduser())))
        source_root = source_input.resolve(strict=False)
        if not source_root.exists() or not source_root.is_dir():
            raise ValueError("权威源码不是可读取的 Skill 目录：{}".format(source))
        source_comparison = compare_trees(root, source_root)
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

    release_envelope = inspect_release_envelope(
        records,
        surface,
        findings,
        source_paths=source_paths,
    )

    severity_order = {"error": 0, "warning": 1, "info": 2}
    findings.sort(
        key=lambda item: (
            severity_order[item["severity"]],
            item.get("file", ""),
            item.get("line", 0),
            item["code"],
        )
    )

    reachable_refs = sorted(path for path, depth in depths.items() if depth > 0)
    conditional_text = "\n".join(texts[path] for path in reachable_refs if path in texts)
    target_text = "\n".join(texts[path] for path in sorted(texts))
    declared_context = "\n".join((frontmatter, body, conditional_text))
    total_bytes = sum(int(record["bytes"]) for record in records)
    largest_files = sorted(records, key=lambda item: (-int(item["bytes"]), str(item["file"])))[:12]
    metrics = {
        "file_count": len(records),
        "text_file_count": len(texts),
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

    counts = {
        severity: sum(1 for item in findings if item["severity"] == severity)
        for severity in ("error", "warning", "info")
    }
    exit_code = 1 if counts["error"] else 0
    result = {
        "target": str(input_path),
        "resolved_target": str(root),
        "summary": dict(counts, exit_code=exit_code),
        "metrics": metrics,
        "surfaces": {
            "target_surface": surface,
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
        },
        "files": {
            "text": sorted(texts),
            "reachable_references": reachable_refs,
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
        "- 权威源码：{}".format(surfaces["authoritative_source"]["status"]),
        "- 用户发行包：{}".format(surfaces["release_artifact"]["status"]),
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
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        result, exit_code = audit_skill(
            Path(args.skill_directory),
            source=Path(args.source) if args.source else None,
            surface=args.surface,
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
