"""Read-only validation for repository-owned test-system contracts."""

from __future__ import annotations

import glob
import json
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .model import add_finding


SCHEMA_VERSION = 1
CASE_MODELS = {"none", "inline", "external"}
RUNNER_MODES = {"shared", "standalone"}
EXECUTABLE_SUFFIXES = {
    ".bat",
    ".cjs",
    ".cmd",
    ".js",
    ".jsx",
    ".mjs",
    ".ps1",
    ".py",
    ".sh",
    ".ts",
    ".tsx",
}
SKIP_PARTS = {
    ".cache",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
    "vendor",
}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
DEFAULT_CANDIDATE_RE = re.compile(
    r"(?:^|[-_.])(test|tests|check|audit|smoke)(?:$|[-_.])", re.IGNORECASE
)
TOP_LEVEL_KEYS = {
    "schema_version",
    "skill",
    "target_root",
    "inventory_patterns",
    "mechanisms",
    "runners",
    "exclusions",
}
MECHANISM_KEYS = {
    "id",
    "rule_owner",
    "case_model",
    "case_sources",
    "rationale",
}
RUNNER_KEYS = {
    "id",
    "boundary",
    "mode",
    "command",
    "files",
    "covers",
    "owner",
    "reason",
    "exit_condition",
}
EXCLUSION_KEYS = {"file", "reason", "owner", "review_when"}


def _within(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _run_git(root: Path, arguments: Sequence[str]) -> Optional[str]:
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


def _git_worktree_files(repository_root: Path) -> Optional[Tuple[Set[str], Set[str]]]:
    tracked_output = _run_git(repository_root, ["ls-files"])
    if tracked_output is None:
        return None
    untracked_output = _run_git(
        repository_root, ["ls-files", "--others", "--exclude-standard"]
    )
    tracked = {line for line in tracked_output.splitlines() if line}
    untracked = {
        line for line in (untracked_output or "").splitlines() if line
    }
    return tracked, untracked


def _has_skipped_part(relative: str) -> bool:
    return any(part in SKIP_PARTS for part in Path(relative).parts)


def _looks_like_test_candidate(relative: str) -> bool:
    path = Path(relative)
    if path.suffix.lower() not in EXECUTABLE_SUFFIXES or _has_skipped_part(relative):
        return False
    if any(part.lower() in {"test", "tests", "test-node", "tests-node"} for part in path.parts[:-1]):
        return True
    return bool(DEFAULT_CANDIDATE_RE.search(path.name))


def _filesystem_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(str(root), followlinks=False):
        dirnames[:] = [name for name in sorted(dirnames) if name not in SKIP_PARTS]
        current = Path(dirpath)
        for filename in sorted(filenames):
            path = current / filename
            if path.is_file() and not path.is_symlink():
                yield path


def _candidate_inventory(
    target_root: Path,
    repository_root: Path,
    skill_name: str,
    eligible: Optional[Set[str]],
) -> Dict[str, Any]:
    scope_roots = [target_root]
    test_directory_names = [skill_name]
    python_directory_name = skill_name.replace("-", "_")
    if python_directory_name not in test_directory_names:
        test_directory_names.append(python_directory_name)
    for name in test_directory_names:
        repository_tests = repository_root / "tests" / name
        if repository_tests.is_dir() and not _within(target_root, repository_tests):
            scope_roots.append(repository_tests)

    files = set()  # type: Set[str]
    for scope_root in scope_roots:
        if eligible is not None:
            try:
                scope_prefix = _relative(scope_root, repository_root)
            except ValueError:
                continue
            prefix = "" if scope_prefix == "." else scope_prefix.rstrip("/") + "/"
            for relative in eligible:
                if (not prefix or relative.startswith(prefix)) and _looks_like_test_candidate(relative):
                    files.add(relative)
        else:
            for path in _filesystem_files(scope_root):
                relative = _relative(path, repository_root)
                if _looks_like_test_candidate(relative):
                    files.add(relative)

    return {
        "basis": "git-worktree" if eligible is not None else "filesystem",
        "scope_roots": [str(path) for path in scope_roots],
        "candidate_count": len(files),
        "candidate_files": sorted(files)[:80],
        "truncated": len(files) > 80,
    }


def _contract_candidates(
    target_root: Path, repository_root: Path, skill_name: str
) -> List[Path]:
    test_directory_names = [skill_name]
    python_directory_name = skill_name.replace("-", "_")
    if python_directory_name not in test_directory_names:
        test_directory_names.append(python_directory_name)
    candidates = [
        repository_root / "tests" / name / "test-system.json"
        for name in test_directory_names
    ]
    if target_root == repository_root:
        candidates.append(target_root / "tests" / "test-system.json")
    unique = []  # type: List[Path]
    seen = set()  # type: Set[str]
    for candidate in candidates:
        key = str(candidate.resolve(strict=False))
        if key not in seen and candidate.is_file():
            seen.add(key)
            unique.append(candidate)
    return unique


def _resolve_contract_path(
    target_root: Path,
    repository_root: Path,
    skill_name: str,
    requested: Optional[Path],
    findings: List[Dict[str, Any]],
) -> Tuple[Optional[Path], str]:
    if requested is not None:
        candidate = requested.expanduser()
        if not candidate.is_absolute():
            candidate = (repository_root / candidate).resolve(strict=False)
            if not _within(repository_root, candidate):
                add_finding(
                    findings,
                    "error",
                    "test-system-contract-path-escape",
                    "相对测试体系合同路径不得越出仓库根。",
                    evidence=str(candidate),
                    surface="source",
                    kind="contract",
                    confidence="high",
                )
                return candidate, "explicit-missing"
        candidate = candidate.resolve(strict=False)
        if not candidate.is_file():
            add_finding(
                findings,
                "error",
                "test-system-contract-unreadable",
                "显式测试体系合同不是可读取文件。",
                evidence=str(candidate),
                surface="source",
                kind="contract",
                confidence="high",
            )
            return candidate, "explicit-missing"
        return candidate, "explicit"

    discovered = _contract_candidates(target_root, repository_root, skill_name)
    if len(discovered) > 1:
        add_finding(
            findings,
            "error",
            "test-system-contract-ambiguous",
            "发现多份测试体系合同；必须用 --test-system-contract 指定唯一规则主人。",
            evidence=json.dumps([str(path) for path in discovered], ensure_ascii=False),
            surface="source",
            kind="contract",
            confidence="high",
        )
        return None, "ambiguous"
    if discovered:
        return discovered[0].resolve(strict=False), "discovered"
    return None, "missing"


def _is_string_list(value: Any, allow_empty: bool = True) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(isinstance(item, str) and bool(item.strip()) for item in value)
    )


def _contract_error(
    findings: List[Dict[str, Any]],
    code: str,
    message: str,
    contract_path: Path,
    evidence: Optional[str] = None,
) -> None:
    add_finding(
        findings,
        "error",
        code,
        message,
        str(contract_path),
        evidence=evidence,
        surface="source",
        kind="contract",
        confidence="high",
    )


def _resolve_declared_file(
    repository_root: Path,
    value: str,
    findings: List[Dict[str, Any]],
    contract_path: Path,
    code: str,
    label: str,
) -> Optional[str]:
    declared = Path(value)
    if declared.is_absolute() or ".." in declared.parts:
        _contract_error(
            findings,
            "test-system-path-escape",
            "{}必须是仓库根内的相对路径。".format(label),
            contract_path,
            value,
        )
        return None
    candidate = (repository_root / declared).resolve(strict=False)
    if not _within(repository_root, candidate):
        _contract_error(
            findings,
            "test-system-path-escape",
            "{}解析后越出仓库根。".format(label),
            contract_path,
            value,
        )
        return None
    if not candidate.is_file():
        _contract_error(
            findings,
            code,
            "{}引用的文件不存在。".format(label),
            contract_path,
            value,
        )
        return None
    return _relative(candidate, repository_root)


def _validate_keys(
    item: Mapping[str, Any],
    allowed: Set[str],
    required: Set[str],
    label: str,
    contract_path: Path,
    findings: List[Dict[str, Any]],
) -> bool:
    valid = True
    unknown = sorted(set(item) - allowed)
    missing = sorted(required - set(item))
    if unknown:
        _contract_error(
            findings,
            "test-system-schema-unknown-field",
            "{}含有未知字段。".format(label),
            contract_path,
            "、".join(unknown),
        )
        valid = False
    if missing:
        _contract_error(
            findings,
            "test-system-schema-required-field",
            "{}缺少必填字段。".format(label),
            contract_path,
            "、".join(missing),
        )
        valid = False
    return valid


def _expand_inventory(
    repository_root: Path,
    patterns: Sequence[str],
    eligible: Optional[Set[str]],
    contract_path: Path,
    findings: List[Dict[str, Any]],
) -> List[str]:
    matched = set()  # type: Set[str]
    for pattern in patterns:
        pattern_path = Path(pattern)
        if pattern_path.is_absolute() or ".." in pattern_path.parts:
            _contract_error(
                findings,
                "test-system-path-escape",
                "inventory_patterns 只能使用仓库根内的相对 glob。",
                contract_path,
                pattern,
            )
            continue
        absolute_pattern = str(repository_root / pattern)
        for value in glob.iglob(absolute_pattern, recursive=True):
            candidate = Path(value).resolve(strict=False)
            if not candidate.is_file() or not _within(repository_root, candidate):
                continue
            relative = _relative(candidate, repository_root)
            if _has_skipped_part(relative):
                continue
            if eligible is not None and relative not in eligible:
                continue
            matched.add(relative)
    return sorted(matched)


def _invalid_result(
    contract_path: Optional[Path],
    discovery: str,
    inventory: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "status": "fail",
        "contract": {
            "status": "invalid",
            "path": str(contract_path) if contract_path else None,
            "discovery": discovery,
            "schema_version": None,
        },
        "inventory": dict(inventory or {}),
        "mechanisms": [],
        "runners": [],
        "exclusions": [],
        "unregistered_files": [],
        "checks": [
            {
                "id": "contract-valid",
                "status": "fail",
                "evidence": {"path": str(contract_path) if contract_path else None},
            }
        ],
        "limitations": [
            "只校验源仓声明与当前文件的一致性，不推断测试业务语义。"
        ],
    }


def inspect_test_system(
    target_root: Path,
    skill_name: str,
    surface: str,
    git: Mapping[str, Any],
    findings: List[Dict[str, Any]],
    contract_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Validate an opt-in repository test-system map without executing target code."""

    if surface in {"release", "installed"}:
        return {
            "status": "not-applicable",
            "contract": {
                "status": "not-applicable",
                "path": None,
                "discovery": "surface-skipped",
                "schema_version": None,
            },
            "inventory": {
                "basis": "not-scanned",
                "candidate_count": 0,
                "candidate_files": [],
            },
            "mechanisms": [],
            "runners": [],
            "exclusions": [],
            "unregistered_files": [],
            "checks": [
                {
                    "id": "source-surface",
                    "status": "not-applicable",
                    "evidence": {"surface": surface},
                }
            ],
            "limitations": ["测试体系属于权威源码职责；发行包和安装载体不据此判定。"],
        }

    repository_root = Path(str(git.get("root"))).resolve(strict=False) if git.get("managed") else target_root
    git_files = _git_worktree_files(repository_root) if git.get("managed") else None
    tracked = git_files[0] if git_files is not None else set()
    untracked = git_files[1] if git_files is not None else set()
    eligible = tracked | untracked if git_files is not None else None
    effective_name = skill_name or target_root.name
    discovery_name = effective_name if ID_RE.match(effective_name) else target_root.name
    candidate_inventory = _candidate_inventory(
        target_root, repository_root, discovery_name, eligible
    )
    selected, discovery = _resolve_contract_path(
        target_root,
        repository_root,
        discovery_name,
        contract_path,
        findings,
    )

    if discovery in {"ambiguous", "explicit-missing"}:
        return _invalid_result(selected, discovery, candidate_inventory)
    if selected is None:
        if candidate_inventory["candidate_count"]:
            add_finding(
                findings,
                "warning",
                "test-system-contract-missing",
                "发现测试/check/audit 文件，但源仓没有声明测试体系合同；只能报告客观盘点，不能判断脚本是否重复。",
                evidence="candidates={}".format(candidate_inventory["candidate_count"]),
                surface="source",
                kind="candidate",
                confidence="high",
            )
            status = "review"
            check_status = "review"
        else:
            status = "not-applicable"
            check_status = "not-applicable"
        return {
            "status": status,
            "contract": {
                "status": "missing",
                "path": None,
                "discovery": discovery,
                "schema_version": None,
            },
            "inventory": candidate_inventory,
            "mechanisms": [],
            "runners": [],
            "exclusions": [],
            "unregistered_files": [],
            "checks": [
                {
                    "id": "contract-present",
                    "status": check_status,
                    "evidence": {
                        "candidate_count": candidate_inventory["candidate_count"]
                    },
                }
            ],
            "limitations": [
                "没有源仓合同，不对文件进行语义聚类，也不建议自动合并或删除。"
            ],
        }

    if git_files is not None and _within(repository_root, selected):
        selected_relative = _relative(selected, repository_root)
        if selected_relative not in eligible:
            _contract_error(
                findings,
                "test-system-contract-ignored",
                "测试体系合同被 Git 忽略，不能作为可传播的源仓规则主人。",
                selected,
                selected_relative,
            )
            return _invalid_result(selected, discovery, candidate_inventory)

    errors_before = sum(1 for item in findings if item.get("severity") == "error")
    try:
        if selected.stat().st_size > 1024 * 1024:
            raise ValueError("合同超过 1 MiB 上限")
        raw = json.loads(selected.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        _contract_error(
            findings,
            "test-system-contract-invalid-json",
            "测试体系合同不是有效的 UTF-8 JSON。",
            selected,
            str(exc),
        )
        return _invalid_result(selected, discovery, candidate_inventory)

    if not isinstance(raw, dict):
        _contract_error(
            findings,
            "test-system-contract-invalid-root",
            "测试体系合同顶层必须是对象。",
            selected,
        )
        return _invalid_result(selected, discovery, candidate_inventory)

    _validate_keys(
        raw,
        TOP_LEVEL_KEYS,
        TOP_LEVEL_KEYS,
        "合同顶层",
        selected,
        findings,
    )
    if raw.get("schema_version") != SCHEMA_VERSION:
        _contract_error(
            findings,
            "test-system-schema-version",
            "测试体系合同 schema_version 必须为 1。",
            selected,
            repr(raw.get("schema_version")),
        )
    if raw.get("skill") != effective_name:
        _contract_error(
            findings,
            "test-system-skill-mismatch",
            "测试体系合同 skill 与目标 SKILL.md 不一致。",
            selected,
            "expected={} actual={}".format(effective_name, raw.get("skill")),
        )

    expected_target_root = _relative(target_root, repository_root) if target_root != repository_root else "."
    if raw.get("target_root") != expected_target_root:
        _contract_error(
            findings,
            "test-system-target-root-mismatch",
            "测试体系合同 target_root 与当前目标不一致。",
            selected,
            "expected={} actual={}".format(expected_target_root, raw.get("target_root")),
        )

    patterns = raw.get("inventory_patterns")
    if not _is_string_list(patterns, allow_empty=False):
        _contract_error(
            findings,
            "test-system-inventory-patterns",
            "inventory_patterns 必须是非空字符串数组。",
            selected,
        )
        patterns = []
    inventory_files = _expand_inventory(
        repository_root, patterns, eligible, selected, findings
    )

    mechanisms_value = raw.get("mechanisms")
    runners_value = raw.get("runners")
    exclusions_value = raw.get("exclusions")
    if not isinstance(mechanisms_value, list):
        _contract_error(findings, "test-system-mechanisms", "mechanisms 必须是数组。", selected)
        mechanisms_value = []
    if not isinstance(runners_value, list):
        _contract_error(findings, "test-system-runners", "runners 必须是数组。", selected)
        runners_value = []
    if not isinstance(exclusions_value, list):
        _contract_error(findings, "test-system-exclusions", "exclusions 必须是数组。", selected)
        exclusions_value = []

    mechanisms = []  # type: List[Dict[str, Any]]
    mechanism_ids = set()  # type: Set[str]
    for index, value in enumerate(mechanisms_value):
        label = "mechanisms[{}]".format(index)
        if not isinstance(value, dict):
            _contract_error(findings, "test-system-mechanism-shape", "{} 必须是对象。".format(label), selected)
            continue
        _validate_keys(
            value,
            MECHANISM_KEYS,
            {"id", "rule_owner", "case_model", "case_sources"},
            label,
            selected,
            findings,
        )
        mechanism_id = value.get("id")
        if not isinstance(mechanism_id, str) or not ID_RE.match(mechanism_id):
            _contract_error(findings, "test-system-mechanism-id", "{} 的 id 格式无效。".format(label), selected, repr(mechanism_id))
            continue
        if mechanism_id in mechanism_ids:
            _contract_error(findings, "test-system-mechanism-duplicate", "测试机制 id 重复。", selected, mechanism_id)
            continue
        mechanism_ids.add(mechanism_id)
        owner = value.get("rule_owner")
        owner_path = None
        if isinstance(owner, str) and owner.strip():
            owner_path = _resolve_declared_file(
                repository_root,
                owner,
                findings,
                selected,
                "test-system-rule-owner-missing",
                "rule_owner",
            )
        else:
            _contract_error(findings, "test-system-rule-owner", "{} 缺少唯一 rule_owner。".format(label), selected)

        case_model = value.get("case_model")
        case_sources = value.get("case_sources")
        if case_model not in CASE_MODELS:
            _contract_error(findings, "test-system-case-model", "{} 的 case_model 无效。".format(label), selected, repr(case_model))
        if not _is_string_list(case_sources):
            _contract_error(findings, "test-system-case-sources", "{} 的 case_sources 必须是字符串数组。".format(label), selected)
            case_sources = []
        resolved_sources = []  # type: List[str]
        for source in case_sources:
            resolved = _resolve_declared_file(
                repository_root,
                source,
                findings,
                selected,
                "test-system-case-source-missing",
                "case_sources",
            )
            if resolved:
                if Path(resolved).suffix.lower() in EXECUTABLE_SUFFIXES:
                    _contract_error(
                        findings,
                        "test-system-external-case-executable",
                        "external case_sources 必须是非执行代码数据。",
                        selected,
                        resolved,
                    )
                resolved_sources.append(resolved)
        rationale = value.get("rationale")
        if case_model == "external" and not case_sources:
            _contract_error(findings, "test-system-external-case-missing", "external case_model 必须声明 case_sources。", selected, mechanism_id)
        if case_model in {"none", "inline"} and case_sources:
            _contract_error(findings, "test-system-case-source-unexpected", "none/inline case_model 不应声明 case_sources。", selected, mechanism_id)
        if case_model == "inline" and (not isinstance(rationale, str) or not rationale.strip()):
            _contract_error(findings, "test-system-inline-rationale", "inline case_model 必须说明为何不适合数据化。", selected, mechanism_id)
        mechanisms.append(
            {
                "id": mechanism_id,
                "rule_owner": owner_path or owner,
                "case_model": case_model,
                "case_sources": resolved_sources,
                "rationale": rationale if isinstance(rationale, str) else None,
            }
        )

    runners = []  # type: List[Dict[str, Any]]
    runner_ids = set()  # type: Set[str]
    file_owners = defaultdict(list)  # type: Dict[str, List[str]]
    shared_boundaries = defaultdict(list)  # type: Dict[Tuple[str, str], List[str]]
    for index, value in enumerate(runners_value):
        label = "runners[{}]".format(index)
        if not isinstance(value, dict):
            _contract_error(findings, "test-system-runner-shape", "{} 必须是对象。".format(label), selected)
            continue
        _validate_keys(
            value,
            RUNNER_KEYS,
            {"id", "boundary", "mode", "command", "files", "covers"},
            label,
            selected,
            findings,
        )
        runner_id = value.get("id")
        boundary = value.get("boundary")
        mode = value.get("mode")
        command = value.get("command")
        files = value.get("files")
        covers = value.get("covers")
        if not isinstance(runner_id, str) or not ID_RE.match(runner_id):
            _contract_error(findings, "test-system-runner-id", "{} 的 id 格式无效。".format(label), selected, repr(runner_id))
            continue
        if runner_id in runner_ids:
            _contract_error(findings, "test-system-runner-duplicate", "测试 runner id 重复。", selected, runner_id)
            continue
        runner_ids.add(runner_id)
        if not isinstance(boundary, str) or not ID_RE.match(boundary):
            _contract_error(findings, "test-system-runner-boundary", "{} 的 boundary 必须是稳定标识。".format(label), selected, repr(boundary))
        if mode not in RUNNER_MODES:
            _contract_error(findings, "test-system-runner-mode", "{} 的 mode 无效。".format(label), selected, repr(mode))
        if not isinstance(command, str) or not command.strip():
            _contract_error(findings, "test-system-runner-command", "{} 必须声明非空 command。".format(label), selected)
        if not _is_string_list(files, allow_empty=False):
            _contract_error(findings, "test-system-runner-files", "{} 的 files 必须是非空字符串数组。".format(label), selected)
            files = []
        if not _is_string_list(covers, allow_empty=False):
            _contract_error(findings, "test-system-runner-covers", "{} 的 covers 必须是非空字符串数组。".format(label), selected)
            covers = []

        resolved_files = []  # type: List[str]
        for file_value in files:
            resolved = _resolve_declared_file(
                repository_root,
                file_value,
                findings,
                selected,
                "test-system-runner-file-missing",
                "runner files",
            )
            if resolved:
                resolved_files.append(resolved)
                file_owners[resolved].append(runner_id)
        for mechanism_id in covers:
            if mechanism_id not in mechanism_ids:
                _contract_error(findings, "test-system-runner-unknown-mechanism", "runner 引用了未知测试机制。", selected, "{} -> {}".format(runner_id, mechanism_id))
            if mode == "shared" and isinstance(boundary, str):
                shared_boundaries[(mechanism_id, boundary)].append(runner_id)

        if mode == "standalone":
            for field in ("owner", "reason", "exit_condition"):
                field_value = value.get(field)
                if not isinstance(field_value, str) or not field_value.strip():
                    _contract_error(findings, "test-system-standalone-governance", "standalone runner 必须声明 owner、reason 和 exit_condition。", selected, "{} missing={}".format(runner_id, field))

        runners.append(
            {
                "id": runner_id,
                "boundary": boundary,
                "mode": mode,
                "command": command,
                "files": resolved_files,
                "covers": list(covers),
                "owner": value.get("owner"),
                "reason": value.get("reason"),
                "exit_condition": value.get("exit_condition"),
            }
        )

    exclusions = []  # type: List[Dict[str, Any]]
    for index, value in enumerate(exclusions_value):
        label = "exclusions[{}]".format(index)
        if not isinstance(value, dict):
            _contract_error(findings, "test-system-exclusion-shape", "{} 必须是对象。".format(label), selected)
            continue
        _validate_keys(
            value,
            EXCLUSION_KEYS,
            {"file", "reason"},
            label,
            selected,
            findings,
        )
        file_value = value.get("file")
        reason = value.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            _contract_error(findings, "test-system-exclusion-reason", "{} 必须说明排除原因。".format(label), selected)
        if not isinstance(file_value, str) or not file_value.strip():
            _contract_error(findings, "test-system-exclusion-file", "{} 必须声明文件路径。".format(label), selected)
            continue
        resolved = _resolve_declared_file(
            repository_root,
            file_value,
            findings,
            selected,
            "test-system-exclusion-file-missing",
            "exclusion file",
        )
        if resolved:
            file_owners[resolved].append("exclusion:{}".format(index))
            exclusions.append(
                {
                    "file": resolved,
                    "reason": reason,
                    "owner": value.get("owner"),
                    "review_when": value.get("review_when"),
                }
            )

    inventory_set = set(inventory_files)
    assigned_set = set(file_owners)
    unregistered = sorted(inventory_set - assigned_set)
    outside_inventory = sorted(assigned_set - inventory_set)
    duplicate_assignments = {
        path: owners for path, owners in sorted(file_owners.items()) if len(owners) != 1
    }
    duplicate_boundaries = {
        "{}@{}".format(mechanism, boundary): sorted(set(ids))
        for (mechanism, boundary), ids in sorted(shared_boundaries.items())
        if len(set(ids)) > 1
    }
    if unregistered:
        _contract_error(findings, "test-system-unregistered-file", "测试体系合同存在未登记文件。", selected, json.dumps(unregistered[:40], ensure_ascii=False))
    if outside_inventory:
        _contract_error(findings, "test-system-file-outside-inventory", "runner/exclusion 文件未被 inventory_patterns 覆盖。", selected, json.dumps(outside_inventory[:40], ensure_ascii=False))
    if duplicate_assignments:
        _contract_error(findings, "test-system-file-multiple-owners", "同一测试文件被多个 runner/exclusion 登记。", selected, json.dumps(duplicate_assignments, ensure_ascii=False))
    if duplicate_boundaries:
        _contract_error(findings, "test-system-duplicate-shared-boundary", "同一机制和执行边界存在多个共享 runner；应收敛或改为有治理信息的 standalone。", selected, json.dumps(duplicate_boundaries, ensure_ascii=False))

    covered = {item for runner in runners for item in runner["covers"]}
    uncovered_mechanisms = sorted(mechanism_ids - covered)
    if uncovered_mechanisms:
        _contract_error(findings, "test-system-mechanism-uncovered", "测试机制没有 runner 覆盖。", selected, json.dumps(uncovered_mechanisms, ensure_ascii=False))

    error_count = sum(1 for item in findings if item.get("severity") == "error") - errors_before
    status = "fail" if error_count else "pass"
    checks = [
        {
            "id": "contract-valid",
            "status": "fail" if error_count else "pass",
            "evidence": {"path": str(selected), "schema_version": raw.get("schema_version")},
        },
        {
            "id": "inventory-covered",
            "status": "fail" if unregistered or outside_inventory or duplicate_assignments else "pass",
            "evidence": {
                "matched": len(inventory_files),
                "unregistered": unregistered,
                "outside_inventory": outside_inventory,
                "multiple_owners": duplicate_assignments,
            },
        },
        {
            "id": "rule-owners-resolved",
            "status": "fail" if any(not item.get("rule_owner") for item in mechanisms) else "pass",
            "evidence": {"mechanisms": len(mechanisms)},
        },
        {
            "id": "runner-boundaries",
            "status": "fail" if duplicate_boundaries else "pass",
            "evidence": {
                "runners": len(runners),
                "duplicate_shared_boundaries": duplicate_boundaries,
            },
        },
    ]
    return {
        "status": status,
        "contract": {
            "status": "valid" if not error_count else "invalid",
            "path": str(selected),
            "discovery": discovery,
            "schema_version": raw.get("schema_version"),
        },
        "inventory": {
            "basis": "git-worktree" if git_files is not None else "filesystem",
            "tracked_matched_count": sum(
                1 for path in inventory_files if path in tracked
            ),
            "untracked_matched_count": sum(
                1 for path in inventory_files if path in untracked
            ),
            "patterns": list(patterns),
            "matched_count": len(inventory_files),
            "matched_files": inventory_files,
        },
        "mechanisms": mechanisms,
        "runners": runners,
        "exclusions": exclusions,
        "unregistered_files": unregistered,
        "checks": checks,
        "limitations": [
            "只校验源仓声明、执行边界和文件引用，不推断测试业务语义。",
            "不执行目标代码、不联网、不读取 Git 历史。",
        ],
    }
