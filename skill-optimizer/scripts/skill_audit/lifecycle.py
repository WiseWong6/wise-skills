"""Lifecycle topology, release provenance, and version-coordinate inspection."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .model import add_finding


AGENT_LABEL_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
SKIP_TREE_DIRS = {
    ".git",
    ".cache",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}


def absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(str(path.expanduser())))


def parse_agent_entry(value: str) -> Tuple[str, Path]:
    if "=" not in value:
        raise ValueError("--agent-entry 必须使用 agent=/absolute/path 形式。")
    agent, raw_path = value.split("=", 1)
    agent = agent.strip()
    raw_path = raw_path.strip()
    if not agent or not AGENT_LABEL_RE.fullmatch(agent):
        raise ValueError("--agent-entry 的 agent 名只能包含字母、数字、点、下划线和连字符。")
    if not raw_path:
        raise ValueError("--agent-entry 缺少路径。")
    return agent, absolute_path(Path(raw_path))


def _lexists(path: Path) -> bool:
    return os.path.lexists(str(path))


def _within(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def trace_entry(path: Path) -> Dict[str, Any]:
    """Trace explicit symlink hops without letting Path.resolve hide cycles."""

    start = absolute_path(path)
    current = start
    seen = set()  # type: Set[str]
    hops = []  # type: List[Dict[str, Any]]

    if not _lexists(current):
        return {
            "input": str(start),
            "status": "missing",
            "hops": hops,
            "hop_count": 0,
            "final_path": None,
        }

    while current.is_symlink():
        marker = str(current)
        if marker in seen:
            return {
                "input": str(start),
                "status": "cycle",
                "hops": hops,
                "hop_count": len(hops),
                "cycle_at": marker,
                "final_path": None,
            }
        seen.add(marker)
        try:
            raw_target = os.readlink(str(current))
        except OSError as exc:
            return {
                "input": str(start),
                "status": "unreadable",
                "hops": hops,
                "hop_count": len(hops),
                "error": str(exc),
                "final_path": None,
            }
        target = Path(raw_target)
        if not target.is_absolute():
            target = absolute_path(current.parent / target)
        else:
            target = absolute_path(target)
        hops.append(
            {
                "path": str(current),
                "raw_target": raw_target,
                "target": str(target),
                "relative": not Path(raw_target).is_absolute(),
            }
        )
        current = target
        if not _lexists(current):
            return {
                "input": str(start),
                "status": "broken",
                "hops": hops,
                "hop_count": len(hops),
                "broken_at": str(current),
                "final_path": None,
            }

    marker = str(current)
    if marker in seen:
        return {
            "input": str(start),
            "status": "cycle",
            "hops": hops,
            "hop_count": len(hops),
            "cycle_at": marker,
            "final_path": None,
        }
    try:
        final = current.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        return {
            "input": str(start),
            "status": "unreadable",
            "hops": hops,
            "hop_count": len(hops),
            "error": str(exc),
            "final_path": None,
        }
    return {
        "input": str(start),
        "status": "resolved" if final.is_dir() else "not-directory",
        "hops": hops,
        "hop_count": len(hops),
        "final_path": str(final),
    }


def _iter_tree_entries(root: Path) -> Iterable[Tuple[str, Path]]:
    for dirpath, dirnames, filenames in os.walk(str(root), followlinks=False):
        current = Path(dirpath)
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_TREE_DIRS)
        linked_directories = [name for name in dirnames if (current / name).is_symlink()]
        dirnames[:] = [name for name in dirnames if name not in linked_directories]
        for name in linked_directories:
            path = current / name
            try:
                relative = path.relative_to(root).as_posix()
            except ValueError:
                continue
            yield relative, path
        for name in sorted(filenames):
            path = current / name
            try:
                relative = path.relative_to(root).as_posix()
            except ValueError:
                continue
            yield relative, path


def tree_digest(root: Optional[Path]) -> Optional[str]:
    if root is None or not root.exists() or not root.is_dir():
        return None
    digest = hashlib.sha256()
    try:
        for relative, path in _iter_tree_entries(root):
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            if path.is_symlink():
                digest.update(b"LINK\0")
                digest.update(os.readlink(str(path)).encode("utf-8", "surrogateescape"))
            else:
                with path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
            digest.update(b"\0")
    except OSError:
        return None
    return digest.hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _declared_skill_name(root: Optional[Path]) -> Optional[str]:
    if root is None:
        return None
    contract = root / "SKILL.md"
    try:
        if not contract.is_file() or contract.stat().st_size > 512 * 1024:
            return None
        text = contract.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    match = re.match(r"^---\s*\n(.*?)\n---(?:\s*\n|$)", text, re.DOTALL)
    if not match:
        return None
    for line in match.group(1).splitlines():
        field = re.match(r"^name\s*:\s*['\"]?([^'\"#]+?)['\"]?\s*$", line)
        if field:
            return field.group(1).strip()
    return None


def _source_commit(data: Any, skill_name: str) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    direct = data.get("source_commit")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    metadata = data.get("metadata")
    if isinstance(metadata, dict):
        value = metadata.get("source_commit")
        if isinstance(value, str) and value.strip():
            return value.strip()
    external = data.get("external_sources")
    if isinstance(external, dict):
        state = external.get(skill_name)
        if isinstance(state, dict):
            value = state.get("commit") or state.get("source_commit")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _hash_entries(data: Any) -> Dict[str, str]:
    if not isinstance(data, dict):
        return {}
    for key in ("sha256", "hashes"):
        value = data.get(key)
        if isinstance(value, dict):
            return {
                str(path): str(digest)
                for path, digest in value.items()
                if isinstance(path, str) and isinstance(digest, str)
            }
    files = data.get("files")
    if isinstance(files, dict):
        return {
            str(path): str(digest)
            for path, digest in files.items()
            if isinstance(path, str) and isinstance(digest, str)
        }
    if isinstance(files, list):
        result = {}  # type: Dict[str, str]
        for item in files:
            if not isinstance(item, dict):
                continue
            path = item.get("path") or item.get("file")
            digest = item.get("sha256") or item.get("hash")
            if isinstance(path, str) and isinstance(digest, str):
                result[path] = digest
        return result
    return {}


def _safe_relative(value: str) -> Optional[Path]:
    normalized = value.replace("\\", "/")
    path = Path(normalized)
    if path.is_absolute() or re.match(r"^[A-Za-z]:", normalized):
        return None
    parts = [part for part in path.parts if part not in ("", ".")]
    if not parts or ".." in parts:
        return None
    return Path(*parts)


def inspect_release_manifest(
    manifest_path: Optional[Path],
    root: Path,
    skill_name: str,
    source_git: Optional[Mapping[str, Any]],
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if manifest_path is None:
        return {"status": "not-provided", "path": None}
    path = absolute_path(manifest_path)
    if not path.exists() or not path.is_file():
        add_finding(
            findings,
            "error",
            "release-manifest-missing",
            "显式提供的发行 manifest 不存在或不是文件。",
            evidence=str(path),
            surface="release",
            kind="fact",
            confidence="high",
        )
        return {"status": "missing", "path": str(path)}
    try:
        if path.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("manifest 超过 32 MiB 安全读取上限")
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        add_finding(
            findings,
            "error",
            "release-manifest-invalid",
            "发行 manifest 无法安全解析：{}".format(exc),
            evidence=str(path),
            surface="release",
            kind="fact",
            confidence="high",
        )
        return {"status": "invalid", "path": str(path), "error": str(exc)}

    source_commit = _source_commit(data, skill_name)
    hashes = _hash_entries(data)
    declared_skills = data.get("skills", []) if isinstance(data, dict) else []
    skill_declared = isinstance(declared_skills, list) and skill_name in declared_skills
    scoped_manifest = any(
        (_safe_relative(raw_name) or Path()).parts[:1] == (skill_name,)
        for raw_name in hashes
    )
    checked = []  # type: List[Dict[str, Any]]
    unsafe = []  # type: List[str]
    relevant = 0
    mismatches = 0
    missing = 0

    for raw_name, expected in sorted(hashes.items()):
        relative = _safe_relative(raw_name)
        if relative is None:
            unsafe.append(raw_name)
            continue
        parts = list(relative.parts)
        if parts and parts[0] == skill_name:
            parts = parts[1:]
            skill_declared = True
        elif scoped_manifest:
            # A repository-level manifest may contain root files whose names happen
            # to exist inside a Skill. Once skill-prefixed entries exist, only that
            # explicit namespace is authoritative for this target Skill.
            continue
        candidate_relative = Path(*parts) if parts else None
        if candidate_relative is None:
            continue
        candidate = root / candidate_relative
        if not candidate.exists() and not raw_name.startswith(skill_name + "/"):
            continue
        relevant += 1
        if not candidate.exists() or not candidate.is_file():
            missing += 1
            checked.append(
                {
                    "file": candidate_relative.as_posix(),
                    "status": "missing",
                    "expected_sha256": expected,
                }
            )
            add_finding(
                findings,
                "error",
                "release-manifest-file-missing",
                "发行 manifest 声明的文件在目标载荷中不存在。",
                candidate_relative.as_posix(),
                surface="release",
                kind="fact",
                confidence="high",
            )
            continue
        actual = _file_digest(candidate)
        status = "match" if actual.lower() == expected.lower() else "mismatch"
        mismatches += int(status == "mismatch")
        checked.append(
            {
                "file": candidate_relative.as_posix(),
                "status": status,
                "expected_sha256": expected,
                "actual_sha256": actual,
            }
        )
        if status == "mismatch":
            add_finding(
                findings,
                "error",
                "release-manifest-hash-mismatch",
                "发行文件哈希与 manifest 不一致。",
                candidate_relative.as_posix(),
                evidence="expected={} actual={}".format(expected, actual),
                surface="release",
                kind="fact",
                confidence="high",
            )

    for raw_name in unsafe:
        add_finding(
            findings,
            "error",
            "release-manifest-path-unsafe",
            "发行 manifest 包含绝对路径、盘符或越界路径。",
            evidence=raw_name,
            surface="release",
            kind="fact",
            confidence="high",
        )

    source_head = source_git.get("head") if source_git else None
    if source_commit and source_head and not str(source_head).startswith(source_commit) and not source_commit.startswith(str(source_head)):
        add_finding(
            findings,
            "warning",
            "release-source-commit-divergence",
            "发行 manifest 的 source_commit 与当前显式权威源码 HEAD 不同；可能是旧发行，也可能是错误权威关系。",
            evidence="manifest={} source={}".format(source_commit, source_head),
            surface="release",
            kind="candidate",
            confidence="high",
        )

    return {
        "status": "verified" if not (unsafe or mismatches or missing) else "invalid",
        "path": str(path),
        "source_commit": source_commit,
        "skill_declared": skill_declared,
        "hash_entry_count": len(hashes),
        "relevant_hash_count": relevant,
        "checked": checked,
        "unsafe_paths": unsafe,
        "mismatch_count": mismatches,
        "missing_count": missing,
    }


def inspect_lifecycle(
    target_input: Path,
    target_root: Path,
    values: Mapping[str, str],
    target_git: Mapping[str, Any],
    findings: List[Dict[str, Any]],
    source_input: Optional[Path] = None,
    source_root: Optional[Path] = None,
    source_git: Optional[Mapping[str, Any]] = None,
    release_manifest: Optional[Path] = None,
    agent_entries: Sequence[Tuple[str, Path]] = (),
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Build one evidence graph without claiming that static resolution is runtime proof."""

    skill_name = values.get("name", "").strip() or target_root.name
    nodes = [
        {
            "id": "target",
            "kind": "target",
            "input": str(target_input),
            "realpath": str(target_root),
        }
    ]
    edges = []  # type: List[Dict[str, Any]]
    if source_root is not None:
        nodes.append(
            {
                "id": "source",
                "kind": "authoritative-source",
                "input": str(source_input or source_root),
                "realpath": str(source_root),
            }
        )
        edges.append({"from": "source", "to": "target", "kind": "explicit-authority"})

    manifest = inspect_release_manifest(
        release_manifest, target_root, skill_name, source_git, findings
    )
    if manifest.get("status") != "not-provided":
        nodes.append(
            {
                "id": "release-manifest",
                "kind": "release-manifest",
                "path": manifest.get("path"),
            }
        )
        edges.append({"from": "release-manifest", "to": "target", "kind": "integrity"})

    entry_paths = {agent: absolute_path(path) for agent, path in agent_entries}
    traces = []  # type: List[Dict[str, Any]]
    for agent, path in sorted(entry_paths.items()):
        trace = trace_entry(path)
        trace["agent"] = agent
        final = Path(str(trace["final_path"])) if trace.get("final_path") else None
        trace["declared_skill_name"] = _declared_skill_name(final)
        trace["tree_sha256"] = tree_digest(final)
        cross_agent = []  # type: List[str]
        for hop in trace.get("hops", []):
            target_path = Path(str(hop["target"]))
            for other_agent, other_path in entry_paths.items():
                if other_agent == agent:
                    continue
                if target_path == other_path or _within(other_path, target_path):
                    cross_agent.append(other_agent)
        trace["cross_agent_targets"] = sorted(set(cross_agent))
        traces.append(trace)
        node_id = "agent:{}".format(agent)
        nodes.append(
            {
                "id": node_id,
                "kind": "agent-entry",
                "agent": agent,
                "input": str(path),
                "realpath": trace.get("final_path"),
                "status": trace.get("status"),
            }
        )
        edges.append(
            {
                "from": node_id,
                "to": "target" if trace.get("final_path") == str(target_root) else "unresolved",
                "kind": "install-entry",
                "hop_count": trace.get("hop_count"),
            }
        )

        status = trace.get("status")
        if status in {"broken", "cycle", "unreadable", "not-directory"}:
            add_finding(
                findings,
                "error",
                "agent-entry-{}".format(status),
                "{} 的 Skill 安装入口无法形成有效目录链。".format(agent),
                evidence=json.dumps(trace, ensure_ascii=False),
                surface="installed",
                kind="fact",
                confidence="high",
            )
        elif status == "missing":
            add_finding(
                findings,
                "error",
                "agent-entry-missing",
                "显式提供的 {} 安装入口不存在。".format(agent),
                evidence=str(path),
                surface="installed",
                kind="fact",
                confidence="high",
            )
        elif status == "resolved" and trace.get("declared_skill_name") != skill_name:
            add_finding(
                findings,
                "error",
                "agent-entry-target-mismatch",
                "{} 安装入口解析到了另一个 Skill 或缺少有效 SKILL.md。".format(agent),
                evidence="expected={} actual={} realpath={}".format(
                    skill_name, trace.get("declared_skill_name"), trace.get("final_path")
                ),
                surface="installed",
                kind="fact",
                confidence="high",
            )
        if int(trace.get("hop_count", 0)) > 1:
            add_finding(
                findings,
                "warning",
                "agent-entry-multi-hop",
                "{} 安装入口经过 {} 跳软链；当前可能可用，但传播链不够直接。".format(
                    agent, trace.get("hop_count")
                ),
                evidence=json.dumps(trace.get("hops"), ensure_ascii=False),
                surface="installed",
                kind="candidate",
                confidence="high",
            )
        if trace["cross_agent_targets"]:
            add_finding(
                findings,
                "warning",
                "agent-entry-cross-agent-upstream",
                "{} 安装入口借道其他 Agent 的安装目录：{}。".format(
                    agent, "、".join(trace["cross_agent_targets"])
                ),
                evidence=json.dumps(trace.get("hops"), ensure_ascii=False),
                surface="installed",
                kind="candidate",
                confidence="high",
            )

    resolved = [trace for trace in traces if trace.get("status") == "resolved"]
    realpath_groups = {}  # type: Dict[str, List[str]]
    for trace in resolved:
        realpath_groups.setdefault(str(trace["final_path"]), []).append(str(trace["agent"]))
    shared_targets = [
        {"realpath": path, "agents": sorted(agents)}
        for path, agents in sorted(realpath_groups.items())
        if len(agents) > 1
    ]
    for item in shared_targets:
        add_finding(
            findings,
            "info",
            "agent-entries-shared-target",
            "多个 Agent 入口解析到同一实体；这是共享源码，不是多个可独立验证的副本。",
            evidence=json.dumps(item, ensure_ascii=False),
            surface="installed",
            kind="fact",
            confidence="high",
        )

    independent = {}  # type: Dict[str, List[Dict[str, Any]]]
    for trace in resolved:
        digest = trace.get("tree_sha256")
        if digest:
            independent.setdefault(str(digest), []).append(trace)
    duplicate_copies = []  # type: List[Dict[str, Any]]
    for digest, group in independent.items():
        paths = sorted({str(item["final_path"]) for item in group})
        if len(paths) > 1:
            item = {
                "sha256": digest,
                "paths": paths,
                "agents": sorted(str(entry["agent"]) for entry in group),
            }
            duplicate_copies.append(item)
            add_finding(
                findings,
                "warning",
                "agent-entry-duplicate-copy",
                "多个 Agent 使用内容相同但可独立漂移的实体副本。",
                evidence=json.dumps(item, ensure_ascii=False),
                surface="installed",
                kind="candidate",
                confidence="high",
            )

    distinct_digests = {str(trace.get("tree_sha256")) for trace in resolved if trace.get("tree_sha256")}
    if len(distinct_digests) > 1:
        add_finding(
            findings,
            "warning",
            "agent-entry-content-drift",
            "不同 Agent 安装入口解析到内容不一致的 Skill 实体。",
            evidence=json.dumps(
                [
                    {
                        "agent": trace["agent"],
                        "realpath": trace["final_path"],
                        "sha256": trace.get("tree_sha256"),
                    }
                    for trace in resolved
                ],
                ensure_ascii=False,
            ),
            surface="installed",
            kind="fact",
            confidence="high",
        )

    distribution_status = "not-observed"
    if manifest.get("skill_declared"):
        distribution_status = "installed-observed" if traces else "usage-unverified"
        if not traces:
            add_finding(
                findings,
                "info",
                "distribution-usage-unverified",
                "目标 Skill 被发行清单携带，但没有提供安装入口或真实调用证据；这不是已确认死重。",
                surface="release",
                kind="candidate",
                confidence="low",
            )

    lifecycle = {
        "authority": {
            "status": "explicit" if source_root is not None else "not-provided",
            "source": str(source_root) if source_root is not None else None,
            "rule": "只有显式 --source 或发行 manifest 才建立权威关系，不按目录名猜测。",
        },
        "nodes": nodes,
        "edges": edges,
        "agent_entries": traces,
        "shared_targets": shared_targets,
        "duplicate_copies": duplicate_copies,
        "release_manifest": manifest,
        "distribution_usage": {
            "status": distribution_status,
            "rule": "发行清单存在但无安装或运行证据时只标记未验证，不能直接称为死重。",
        },
    }
    versions = {
        "source": {
            "git_head": source_git.get("head") if source_git else None,
            "git_dirty": source_git.get("dirty") if source_git else None,
            "dirty_entry_count": source_git.get("dirty_entry_count") if source_git else None,
            "tree_sha256": tree_digest(source_root),
        },
        "target": {
            "git_head": target_git.get("head"),
            "git_dirty": target_git.get("dirty"),
            "dirty_entry_count": target_git.get("dirty_entry_count"),
            "tree_sha256": tree_digest(target_root),
        },
        "release": {
            "source_commit": manifest.get("source_commit"),
            "manifest_status": manifest.get("status"),
            "manifest_path": manifest.get("path"),
        },
        "frontmatter": {"version": values.get("version") or None},
        "installed": [
            {
                "agent": trace["agent"],
                "realpath": trace.get("final_path"),
                "tree_sha256": trace.get("tree_sha256"),
                "status": trace.get("status"),
            }
            for trace in traces
        ],
        "rule": "Git SHA、发行来源提交、文件哈希、frontmatter 语义版本和平台线上版本是不同坐标，不做跨类型字符串等同。",
    }
    runtime = {
        "status": "not-run",
        "evidence": [],
        "required": True,
        "note": "路径解析和静态审计不能证明 Agent 已发现、加载并完成真实任务；需在新会话单独验证。",
    }
    return lifecycle, versions, runtime
