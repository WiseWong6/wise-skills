"""Role-aware file/dependency reachability and conservative deadweight candidates."""

from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .model import add_finding


CODE_SUFFIXES = {".js", ".mjs", ".cjs", ".py", ".sh", ".ps1", ".cmd", ".bat"}
RUNTIME_PREFIXES = ("scripts/", "bin/", "runtime/", "assets/")
DEVELOPER_PREFIXES = ("test/", "tests/", ".github/", ".devcontainer/")
ARCHIVE_PREFIXES = ("archive/", "archives/", "badcase/", "badcases/", "legacy/")
HUMAN_NAMES = {
    "readme.md",
    "readme_en.md",
    "changelog.md",
    "installation_guide.md",
    "quick_reference.md",
}
LEGAL_PREFIXES = ("license", "copying", "notice", "attribution", "third_party")
SHOWCASE_PARTS = {"example", "examples", "sample", "samples", "showcase"}
INTEGRITY_NAMES = {
    "bundle-manifest.json",
    "_release-manifest.json",
    "release-manifest.json",
}
LOCAL_JS_IMPORT_RE = re.compile(
    r"(?:\bfrom\s+|\bimport\s*\(\s*|\brequire\s*\(\s*)['\"](\.{1,2}/[^'\"]+)['\"]"
)
PYTHON_RELATIVE_IMPORT_RE = re.compile(
    r"^\s*from\s+(\.+[A-Za-z0-9_.]*)\s+import\s+", re.MULTILINE
)
PYTHON_FROM_IMPORT_RE = re.compile(
    r"^\s*from\s+([A-Za-z_][A-Za-z0-9_.]*)\s+import\s+([^\n#]+)", re.MULTILINE
)
PYTHON_IMPORT_RE = re.compile(
    r"^\s*import\s+([A-Za-z_][A-Za-z0-9_.]*)", re.MULTILINE
)
DYNAMIC_LOADER_RE = re.compile(
    r"\b(?:glob|rglob|globSync|readdir|readdirSync|listdir|walk)\s*\(|"
    r"\b(?:import|require)\s*\(\s*[^'\"\s]",
    re.IGNORECASE,
)
QUOTED_PATH_RE = re.compile(r"['\"]([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+/?)['\"]")


def _is_human_or_legal(path: str) -> bool:
    name = Path(path).name.lower()
    return name in HUMAN_NAMES or name.startswith(LEGAL_PREFIXES)


def _is_showcase(path: str) -> bool:
    return any(part.lower() in SHOWCASE_PARTS for part in Path(path).parts)


def _is_developer(path: str) -> bool:
    lower = path.lower()
    name = Path(lower).name
    return (
        lower.startswith(DEVELOPER_PREFIXES)
        or name.startswith(("requirements-dev", "test_", "test-", "build_", "build-"))
    )


def _is_archive(path: str) -> bool:
    return path.lower().startswith(ARCHIVE_PREFIXES)


def _is_integrity_source(path: str) -> bool:
    lower = path.lower()
    name = Path(lower).name
    return name in INTEGRITY_NAMES or "manifest" in name


def _edge_key(edge: Mapping[str, Any]) -> Tuple[str, str, str]:
    return str(edge["from"]), str(edge["to"]), str(edge["kind"])


def _resolve_known(root: Path, source: str, raw: str, known: Set[str]) -> Optional[str]:
    source_parent = (root / source).parent
    base = (source_parent / raw).resolve(strict=False)
    candidates = [base]
    if base.suffix == "":
        candidates.extend(Path(str(base) + suffix) for suffix in (".js", ".mjs", ".cjs", ".json", ".py"))
        candidates.extend(base / ("index" + suffix) for suffix in (".js", ".mjs", ".cjs", ".py"))
    for candidate in candidates:
        try:
            relative = candidate.relative_to(root).as_posix()
        except ValueError:
            continue
        if relative in known:
            return relative
    return None


def _known_python_module(module: str, known: Set[str]) -> Optional[str]:
    module_path = module.replace(".", "/")
    endings = (module_path + ".py", module_path + "/__init__.py")
    matches = sorted(
        candidate
        for candidate in known
        if any(candidate == ending or candidate.endswith("/" + ending) for ending in endings)
    )
    return matches[0] if len(matches) == 1 else None


def _absolute_python_imports(text: str, known: Set[str]) -> Set[str]:
    """Resolve absolute imports only when they uniquely name files in this Skill."""

    resolved = set()  # type: Set[str]
    for match in PYTHON_IMPORT_RE.finditer(text):
        target = _known_python_module(match.group(1), known)
        if target:
            resolved.add(target)
    for match in PYTHON_FROM_IMPORT_RE.finditer(text):
        module = match.group(1)
        target = _known_python_module(module, known)
        if target:
            resolved.add(target)
        imported = match.group(2).strip()
        if imported.startswith("("):
            imported = imported[1:]
        for raw_name in imported.rstrip(")").split(","):
            name = raw_name.strip().split(" as ", 1)[0].strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                continue
            child = _known_python_module(module + "." + name, known)
            if child:
                resolved.add(child)
    return resolved


def _iter_manifest_paths(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _iter_manifest_paths(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_manifest_paths(item)


def _package_entrypoints(root: Path, texts: Mapping[str, str], known: Set[str]) -> List[str]:
    raw = texts.get("package.json")
    if not raw:
        return []
    try:
        package = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(package, dict):
        return []
    values = []  # type: List[str]
    for key in ("main", "module", "browser", "bin", "exports", "imports"):
        values.extend(_iter_manifest_paths(package.get(key)))
    scripts = package.get("scripts")
    if isinstance(scripts, dict):
        for name, command in scripts.items():
            if name in {"start", "serve", "doctor", "run"} and isinstance(command, str):
                values.append(command)
    result = set()  # type: Set[str]
    for value in values:
        cleaned = value.lstrip("./")
        for candidate in known:
            if candidate == cleaned or candidate in value:
                result.add(candidate)
    return sorted(result)


def _functional_edges(
    root: Path,
    texts: Mapping[str, str],
    known: Set[str],
) -> Tuple[List[Dict[str, str]], Set[str]]:
    edges = []  # type: List[Dict[str, str]]
    dynamic_paths = set()  # type: Set[str]

    for source, text in sorted(texts.items()):
        suffix = Path(source).suffix.lower()
        for match in LOCAL_JS_IMPORT_RE.finditer(text):
            target = _resolve_known(root, source, match.group(1), known)
            if target:
                edges.append({"from": source, "to": target, "kind": "functional"})
        if suffix == ".py":
            for match in PYTHON_RELATIVE_IMPORT_RE.finditer(text):
                raw = match.group(1)
                level = len(raw) - len(raw.lstrip("."))
                module = raw[level:].replace(".", "/")
                parent = Path(source).parent
                for _ in range(max(0, level - 1)):
                    parent = parent.parent
                candidates = [parent / (module + ".py"), parent / module / "__init__.py"]
                for candidate in candidates:
                    target = candidate.as_posix()
                    if target in known:
                        edges.append({"from": source, "to": target, "kind": "functional"})
                        break
            for target in sorted(_absolute_python_imports(text, known)):
                edges.append({"from": source, "to": target, "kind": "functional"})

        if DYNAMIC_LOADER_RE.search(text):
            matched_directory = False
            for match in QUOTED_PATH_RE.finditer(text):
                raw_path = match.group(1).rstrip("/")
                for candidate in known:
                    if candidate == raw_path or candidate.startswith(raw_path + "/"):
                        dynamic_paths.add(candidate)
                        matched_directory = True
            if not matched_directory:
                for candidate in known:
                    if candidate.startswith(("assets/", "data/", "catalog/", "runtime/")):
                        dynamic_paths.add(candidate)

        if source == "package.json" or _is_integrity_source(source):
            continue
        for target in known:
            if target == source or target not in text:
                continue
            if source == "SKILL.md" and target.startswith(RUNTIME_PREFIXES):
                kind = "functional"
            elif suffix in CODE_SUFFIXES or suffix in {".html", ".htm", ".css", ".json"}:
                kind = "functional"
            else:
                kind = "documentation"
            edges.append({"from": source, "to": target, "kind": kind})

    for entry in _package_entrypoints(root, texts, known):
        edges.append({"from": "package.json", "to": entry, "kind": "functional"})
    return edges, dynamic_paths


def _walk(starts: Iterable[str], graph: Mapping[str, Sequence[str]]) -> Set[str]:
    visited = set(starts)  # type: Set[str]
    queue = deque(sorted(visited))  # type: Deque[str]
    while queue:
        source = queue.popleft()
        for target in graph.get(source, []):
            if target not in visited:
                visited.add(target)
                queue.append(target)
    return visited


def inspect_reachability(
    root: Path,
    texts: Mapping[str, str],
    records: Sequence[Mapping[str, Any]],
    reference_graph: Mapping[str, Sequence[str]],
    surface: str,
    dependency_analysis: Mapping[str, Any],
    metafile: Mapping[str, Any],
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Classify files by actual role; static evidence never confirms deletion safety."""

    sizes = {str(record["file"]): int(record["bytes"]) for record in records}
    known = set(sizes)
    edges = []  # type: List[Dict[str, str]]
    for source, targets in reference_graph.items():
        for target in targets:
            edges.append({"from": source, "to": target, "kind": "documentation"})

    functional, dynamic_paths = _functional_edges(root, texts, known)
    edges.extend(functional)

    for source, text in sorted(texts.items()):
        if not _is_integrity_source(source):
            continue
        kind = "provenance" if "provenance" in Path(source).name.lower() else "integrity"
        for target in known:
            if target != source and target in text:
                edges.append({"from": source, "to": target, "kind": kind})

    deduplicated = []  # type: List[Dict[str, str]]
    seen_edges = set()  # type: Set[Tuple[str, str, str]]
    for edge in edges:
        marker = _edge_key(edge)
        if marker not in seen_edges:
            seen_edges.add(marker)
            deduplicated.append(edge)
    edges = sorted(deduplicated, key=lambda item: (item["from"], item["to"], item["kind"]))

    active_graph = defaultdict(list)  # type: Dict[str, List[str]]
    developer_graph = defaultdict(list)  # type: Dict[str, List[str]]
    inbound = defaultdict(list)  # type: Dict[str, List[Dict[str, str]]]
    for edge in edges:
        inbound[edge["to"]].append(edge)
        if edge["kind"] in {"functional", "documentation", "packaging", "legal"}:
            active_graph[edge["from"]].append(edge["to"])
        if _is_developer(edge["from"]):
            developer_graph[edge["from"]].append(edge["to"])

    package_entries = _package_entrypoints(root, texts, known)
    runtime_roots = {path for path in ("SKILL.md", "agents/openai.yaml") if path in known}
    runtime_roots.update(package_entries)
    runtime_roots.update(
        path
        for path in known
        if Path(path).name.lower()
        in {"package.json", "pyproject.toml", "requirements.txt"}
    )
    integrity_roots = {path for path in known if _is_integrity_source(path)}
    user_roots = {path for path in known if _is_human_or_legal(path) or _is_showcase(path)}
    developer_roots = {path for path in known if _is_developer(path)}
    archive_roots = {path for path in known if _is_archive(path)}

    runtime_reachable = _walk(runtime_roots, active_graph)
    user_reachable = _walk(user_roots, active_graph)
    developer_reachable = _walk(developer_roots, active_graph)
    classifications = []  # type: List[Dict[str, Any]]
    candidates = []  # type: List[Dict[str, Any]]
    total_bytes = sum(sizes.values()) or 1

    for path in sorted(known):
        path_inbound = sorted(
            inbound.get(path, []), key=lambda item: (item["kind"], item["from"])
        )
        if path in integrity_roots:
            status, reason, confidence = "required", "发行完整性或来源清单本身承担明确职责", "high"
        elif path in runtime_reachable:
            status, reason, confidence = "required", "从运行或 Skill 入口可达", "high"
        elif path in user_reachable or _is_human_or_legal(path) or _is_showcase(path):
            status, reason, confidence = "user-envelope", "用户说明、法律声明或既有展示职责", "high"
        elif path in developer_reachable or _is_developer(path):
            status, reason, confidence = "development-only", "开发、测试或仓库自动化职责", "high"
        elif path in archive_roots or _is_archive(path):
            status, reason, confidence = "archive-only", "明确归档职责；应留在源码而非用户发行包", "high"
        elif path in dynamic_paths or int(sizes[path]) > 1024 * 1024:
            status, reason, confidence = "dynamic-unresolved", "存在动态加载或静态读取证据不足", "low"
        elif surface in {"release", "installed"}:
            status, reason, confidence = "deadweight-candidate", "没有功能、文档或明确发行职责的有效入边", "medium"
        else:
            status, reason, confidence = "dynamic-unresolved", "源码/自动载体不允许仅凭零入边给删除建议", "low"

        item = {
            "path": path,
            "status": status,
            "bytes": sizes[path],
            "share": round(sizes[path] / total_bytes, 6),
            "inbound_edges": path_inbound,
            "reason": reason,
            "confidence": confidence,
            "verification_required": (
                "隔离副本移除、重生成 manifest、测试/doctor/代表构建、新 Agent 真实调用和用户结果对比"
                if status == "deadweight-candidate"
                else None
            ),
        }
        classifications.append(item)
        if status == "deadweight-candidate":
            candidates.append(item)

    if candidates:
        candidate_bytes = sum(int(item["bytes"]) for item in candidates)
        add_finding(
            findings,
            "warning",
            "deadweight-candidate",
            "发现 {} 个静态零有效入边候选，共 {} 字节；候选不等于已确认可删。".format(
                len(candidates), candidate_bytes
            ),
            evidence="、".join(item["path"] for item in candidates[:12]),
            surface=surface,
            kind="candidate",
            confidence="medium",
            bytes=candidate_bytes,
            verification="隔离删除并完成 manifest、回归和新 Agent 真实调用后再由用户确认",
        )

    dependency_roles = []  # type: List[Dict[str, Any]]
    metafile_provided = metafile.get("status") in {"provided", "parsed", "ok"} or bool(
        metafile.get("packages")
    )
    for dependency in dependency_analysis.get("dependencies", []):
        if not isinstance(dependency, dict):
            continue
        imported = dependency.get("imported_by") or []
        phase = str(dependency.get("phase", ""))
        if phase == "development":
            status = "development-only"
            confidence = "high"
        elif imported or dependency.get("bundled") or dependency.get("external"):
            status = "required"
            confidence = "high"
        elif metafile_provided and phase in {"runtime", "optional-runtime"}:
            status = "deadweight-candidate"
            confidence = "medium"
            add_finding(
                findings,
                "warning",
                "unused-dependency-candidate",
                "直接运行依赖 {} 未出现在源码 import 或构建归因中；仍需排除动态加载后再处理。".format(
                    dependency.get("name")
                ),
                evidence=json.dumps(dependency, ensure_ascii=False),
                surface="runtime",
                kind="candidate",
                confidence=confidence,
            )
        else:
            status = "dynamic-unresolved"
            confidence = "low"
        dependency_roles.append(
            {
                "name": dependency.get("name"),
                "status": status,
                "phase": phase,
                "confidence": confidence,
                "verification_required": status in {"deadweight-candidate", "dynamic-unresolved"},
            }
        )

    edge_counts = {
        kind: sum(1 for edge in edges if edge["kind"] == kind)
        for kind in ("functional", "documentation", "packaging", "integrity", "provenance", "legal")
    }
    return {
        "edge_kinds": {
            "functional": "运行调用、代码 import 或公开脚本入口",
            "documentation": "SKILL/README/引用文档的读取入口",
            "packaging": "显式发行 include/preserve 职责",
            "integrity": "manifest 哈希或库存声明；不能单独证明运行使用",
            "provenance": "来源或生成记录；不能单独证明运行使用",
            "legal": "许可证和署名职责",
        },
        "edges": edges,
        "edge_counts": edge_counts,
        "roots": {
            "runtime": sorted(runtime_roots),
            "user_envelope": sorted(user_roots),
            "development": sorted(developer_roots),
            "archive": sorted(archive_roots),
            "integrity": sorted(integrity_roots),
        },
        "files": classifications,
        "candidates": candidates,
        "candidate_bytes": sum(int(item["bytes"]) for item in candidates),
        "dependencies": dependency_roles,
        "confirmation_policy": "静态审计只产生 candidate；不得输出 confirmed-deadweight 或自动删除。",
    }
