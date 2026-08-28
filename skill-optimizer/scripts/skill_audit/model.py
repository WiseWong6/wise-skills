"""Shared finding/result helpers for Skill audits."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def add_finding(
    findings: List[Dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    file: Optional[str] = None,
    line: Optional[int] = None,
    evidence: Optional[str] = None,
    surface: Optional[str] = None,
    kind: Optional[str] = None,
    confidence: Optional[str] = None,
    **extra: Any,
) -> None:
    """Append one backward-compatible finding with optional evidence metadata."""

    item = {"severity": severity, "code": code, "message": message}  # type: Dict[str, Any]
    optional = {
        "file": file,
        "line": line,
        "evidence": evidence,
        "surface": surface,
        "kind": kind,
        "confidence": confidence,
    }
    item.update({key: value for key, value in optional.items() if value is not None})
    item.update({key: value for key, value in extra.items() if value is not None})
    findings.append(item)


def sort_findings(findings: List[Dict[str, Any]]) -> None:
    findings.sort(
        key=lambda item: (
            SEVERITY_ORDER.get(str(item.get("severity")), 99),
            str(item.get("file", "")),
            int(item.get("line", 0) or 0),
            str(item.get("code", "")),
        )
    )


def count_findings(findings: List[Dict[str, Any]]) -> Dict[str, int]:
    return {
        severity: sum(1 for item in findings if item.get("severity") == severity)
        for severity in ("error", "warning", "info")
    }
