"""Platform-specific frontmatter policy without conflating audit intensity."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from .model import add_finding


SCHEMA_PROFILE_CHOICES = ("auto", "codex", "redskill")
CODEX_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REDSKILL_NAME_RE = re.compile(r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def effective_schema_profile(requested: str) -> str:
    if requested not in SCHEMA_PROFILE_CHOICES:
        raise ValueError(
            "schema profile 必须是 {} 之一：{}".format(
                "、".join(SCHEMA_PROFILE_CHOICES), requested
            )
        )
    return "codex" if requested == "auto" else requested


def validate_frontmatter_schema(
    values: Dict[str, str],
    directory_name: str,
    requested_profile: str,
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Validate one parsed frontmatter mapping against an explicit platform policy."""

    profile = effective_schema_profile(requested_profile)
    name = values.get("name", "").strip()
    version = values.get("version", "").strip()
    keys = sorted(values)

    if profile == "codex":
        allowed = {"name", "description"}
        if name and not CODEX_NAME_RE.fullmatch(name):
            add_finding(
                findings,
                "error",
                "skill-name-invalid",
                "Codex Skill 名称必须使用小写字母、数字和单连字符。",
                "SKILL.md",
                surface="metadata",
                kind="policy",
                confidence="high",
            )
        if name and directory_name != name:
            add_finding(
                findings,
                "error",
                "skill-name-directory-mismatch",
                "frontmatter 名称 {} 与目录名 {} 不一致。".format(name, directory_name),
                "SKILL.md",
                surface="metadata",
                kind="policy",
                confidence="high",
            )
    else:
        allowed = {"name", "description", "version", "metadata"}
        if name and (len(name) > 64 or not REDSKILL_NAME_RE.fullmatch(name)):
            add_finding(
                findings,
                "warning",
                "redskill-name-policy",
                "RedSkill 结构规范建议 name 仅使用 ASCII 字母、数字和单连字符，且不超过 64 字符。",
                "SKILL.md",
                surface="release",
                kind="policy",
                confidence="high",
            )
        if name and directory_name != name:
            add_finding(
                findings,
                "warning",
                "redskill-name-directory-policy",
                "目录名与 frontmatter name 不一致；这不是通用阻断，但会增加平台标识解释成本。",
                "SKILL.md",
                surface="release",
                kind="policy",
                confidence="medium",
            )
        if not version:
            add_finding(
                findings,
                "warning",
                "redskill-version-policy",
                "RedSkill 文档结构规范建议在 frontmatter 顶层声明 version；过审实证表明它不是审核硬门槛。",
                "SKILL.md",
                surface="release",
                kind="policy",
                confidence="high",
            )
        elif not SEMVER_RE.fullmatch(version):
            add_finding(
                findings,
                "warning",
                "redskill-version-format-policy",
                "RedSkill version 应使用 x.y.z 三段数字；线上版本仍由平台独立管理。",
                "SKILL.md",
                surface="release",
                kind="policy",
                confidence="high",
            )

    unexpected = sorted(set(keys) - allowed)
    if unexpected:
        add_finding(
            findings,
            "warning",
            "frontmatter-extra-keys",
            "frontmatter 含有当前 {} profile 未声明的字段：{}".format(
                profile, "、".join(unexpected)
            ),
            "SKILL.md",
            surface="metadata",
            kind="policy",
            confidence="high",
        )

    return {
        "requested": requested_profile,
        "effective": profile,
        "source": (
            "Codex 当前兼容合同"
            if profile == "codex"
            else "2026-08-28 RedSkill 文档结构规范；结构政策与平台审核硬门槛分开"
        ),
        "required_fields": ["name", "description"],
        "policy_fields": ["version"] if profile == "redskill" else [],
        "optional_fields": ["metadata"] if profile == "redskill" else [],
        "name": name or None,
        "version": version or None,
        "directory": Path(directory_name).name,
    }
