"""Explainable structural-quality matrix for one Skill lifecycle graph."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set

from .model import add_finding


STANDARD_TOP_LEVEL_DIRS = {"references", "scripts", "assets"}
KNOWN_TOP_LEVEL_ROLES = {
    "agents": "agent-adapter",
    "references": "on-demand-documentation",
    "scripts": "runtime-or-validation-code",
    "assets": "runtime-resource",
    "bin": "runtime-entry",
    "runtime": "runtime-core",
    "catalog": "runtime-data",
    "capabilities": "runtime-capability",
    "themes": "runtime-theme",
    "examples": "user-showcase",
    "docs": "human-documentation",
    "tests": "development-test",
    "test": "development-test",
    ".github": "repository-automation",
    "archive": "archive-only",
    "archives": "archive-only",
    "badcase": "archive-only",
    "badcases": "archive-only",
    "legacy": "archive-only",
}
LEGAL_PREFIXES = ("license", "copying", "notice", "attribution", "third_party")


def _root_file_role(name: str) -> Optional[str]:
    lower = name.lower()
    if name == "SKILL.md":
        return "skill-contract"
    if lower.startswith("readme") or lower in {"changelog.md", "installation_guide.md"}:
        return "user-documentation"
    if lower.startswith(LEGAL_PREFIXES):
        return "legal-envelope"
    if lower in {"package.json", "pyproject.toml", "requirements.txt"}:
        return "runtime-manifest"
    if "manifest" in lower:
        return "integrity-or-provenance"
    return None


def _reference_cycles(graph: Mapping[str, Sequence[str]]) -> List[List[str]]:
    cycles = []  # type: List[List[str]]
    state = {}  # type: Dict[str, int]
    stack = []  # type: List[str]

    def visit(node: str) -> None:
        state[node] = 1
        stack.append(node)
        for target in graph.get(node, []):
            if state.get(target, 0) == 0:
                visit(target)
            elif state.get(target) == 1 and target in stack:
                start = stack.index(target)
                cycle = stack[start:] + [target]
                if cycle not in cycles:
                    cycles.append(cycle)
        stack.pop()
        state[node] = 2

    for node in sorted(set(graph) | {item for values in graph.values() for item in values}):
        if state.get(node, 0) == 0:
            visit(node)
    return cycles


def inspect_structure(
    records: Sequence[Mapping[str, Any]],
    texts: Mapping[str, str],
    reference_graph: Mapping[str, Sequence[str]],
    lifecycle: Mapping[str, Any],
    schema_profile: str,
    surface: str,
    findings: List[Dict[str, Any]],
    test_system: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Return evidence checks rather than an opaque structural score."""

    top_level = defaultdict(lambda: {"bytes": 0, "files": 0})  # type: Dict[str, Dict[str, int]]
    for record in records:
        path = str(record["file"])
        top = path.split("/", 1)[0]
        top_level[top]["bytes"] += int(record["bytes"])
        top_level[top]["files"] += 1

    roles = []  # type: List[Dict[str, Any]]
    unclassified = []  # type: List[str]
    for name, metrics in sorted(top_level.items()):
        is_directory = any(str(record["file"]).startswith(name + "/") for record in records)
        role = KNOWN_TOP_LEVEL_ROLES.get(name) if is_directory else _root_file_role(name)
        if role is None:
            role = "unclassified"
            unclassified.append(name)
        roles.append(
            {
                "name": name,
                "kind": "directory" if is_directory else "file",
                "role": role,
                "files": metrics["files"],
                "bytes": metrics["bytes"],
            }
        )

    if unclassified:
        add_finding(
            findings,
            "warning",
            "structure-top-level-unclassified",
            "以下顶层项无法从当前 Skill 合同解释职责：{}。".format("、".join(unclassified)),
            evidence=json.dumps(unclassified, ensure_ascii=False),
            surface=surface,
            kind="candidate",
            confidence="medium",
        )

    redskill_deviations = []  # type: List[str]
    if schema_profile == "redskill":
        for item in roles:
            if item["kind"] != "directory":
                continue
            if item["name"] not in STANDARD_TOP_LEVEL_DIRS:
                redskill_deviations.append(str(item["name"]))
        if redskill_deviations:
            add_finding(
                findings,
                "warning",
                "redskill-top-level-structure-policy",
                "RedSkill 推荐五件套把自定义顶层目录归入 assets；该项是结构政策，不是通用审核硬门槛。",
                evidence="、".join(redskill_deviations),
                surface="release",
                kind="policy",
                confidence="high",
            )

    cycles = _reference_cycles(reference_graph)
    if cycles:
        add_finding(
            findings,
            "warning",
            "reference-graph-cycle",
            "按需引用图存在循环；不会造成软链级阻断，但会增加 Agent 查找和规则主人歧义。",
            evidence=json.dumps(cycles[:8], ensure_ascii=False),
            surface="context",
            kind="candidate",
            confidence="high",
        )

    adapter_bytes = sum(
        int(record["bytes"])
        for record in records
        if str(record["file"]).startswith("agents/")
    )
    adapter_lines = sum(
        len(text.splitlines()) for path, text in texts.items() if path.startswith("agents/")
    )
    adapter_heavy = adapter_bytes > 8 * 1024 or adapter_lines > 80
    if adapter_heavy:
        add_finding(
            findings,
            "warning",
            "agent-adapter-heavy",
            "Agent metadata/适配器偏重，需确认没有复制业务合同。",
            evidence="bytes={} lines={}".format(adapter_bytes, adapter_lines),
            surface="metadata",
            kind="candidate",
            confidence="medium",
        )

    codes = {str(item.get("code")) for item in findings}
    topology_cycle = any(
        str(entry.get("status")) == "cycle"
        for entry in lifecycle.get("agent_entries", [])
        if isinstance(entry, dict)
    )
    duplicate_owner = "duplicate-paragraph" in codes
    legacy_signal = "legacy-signal" in codes
    cross_agent = "agent-entry-cross-agent-upstream" in codes
    authority_explicit = lifecycle.get("authority", {}).get("status") == "explicit"
    test_system = test_system or {"status": "not-applicable"}
    test_system_status = str(test_system.get("status", "not-applicable"))
    test_system_check_status = (
        "fail"
        if test_system_status == "fail"
        else "review"
        if test_system_status == "review"
        else "pass"
        if test_system_status == "pass"
        else "not-applicable"
    )

    checks = [
        {
            "id": "single-owner",
            "status": "review" if duplicate_owner or legacy_signal else "pass",
            "evidence": {
                "duplicate_rule": duplicate_owner,
                "active_legacy_signal": legacy_signal,
            },
            "rule": "一个规则、资源和版本坐标只保留一个主人。",
        },
        {
            "id": "lifecycle-dag",
            "status": "fail" if topology_cycle else "review" if cycles else "pass",
            "evidence": {"symlink_cycle": topology_cycle, "reference_cycles": cycles[:8]},
            "rule": "安装传播拓扑必须无环；文档引用环需人工收敛。",
        },
        {
            "id": "thin-agent-adapters",
            "status": "review" if adapter_heavy or cross_agent else "pass",
            "evidence": {
                "adapter_bytes": adapter_bytes,
                "adapter_lines": adapter_lines,
                "cross_agent_upstream": cross_agent,
            },
            "rule": "Agent 层只做薄适配，不承载共享业务合同或借道其他 Agent 安装目录。",
        },
        {
            "id": "surface-separation",
            "status": "pass" if authority_explicit or surface == "source" else "review",
            "evidence": {
                "surface": surface,
                "explicit_authority": authority_explicit,
            },
            "rule": "开发、发行、安装和运行证据分别记录，不按目录名推断权威。",
        },
        {
            "id": "top-level-explainable",
            "status": "review" if unclassified else "pass",
            "evidence": {"unclassified": unclassified},
            "rule": "每个顶层目录都能解释其唯一职责。",
        },
        {
            "id": "platform-structure-policy",
            "status": "review" if redskill_deviations else "pass",
            "evidence": {
                "schema_profile": schema_profile,
                "redskill_deviations": redskill_deviations,
            },
            "rule": "平台推荐结构与通用正确性分开报告，不把过审与结构优秀混为一谈。",
        },
        {
            "id": "test-systemization",
            "status": test_system_check_status,
            "evidence": {
                "test_system_status": test_system_status,
                "contract_status": test_system.get("contract", {}).get("status"),
                "candidate_count": test_system.get("inventory", {}).get(
                    "candidate_count",
                    test_system.get("inventory", {}).get("matched_count", 0),
                ),
                "unregistered_files": test_system.get("unregistered_files", []),
            },
            "rule": "测试语义归目标源仓合同所有；审计器只校验规则主人、执行边界和文件覆盖。",
        },
    ]

    return {
        "score": None,
        "top_level_roles": roles,
        "checks": checks,
        "reference_cycles": cycles,
        "policy": "不输出含糊总分；每项只给规则、状态和可复核证据。",
    }
