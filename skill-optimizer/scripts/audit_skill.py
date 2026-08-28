#!/usr/bin/env python3
"""Backward-compatible CLI and Python import entry for Skill auditing."""

from __future__ import annotations

from typing import Any

from skill_audit import core as _core


MAX_TEXT_BYTES = _core.MAX_TEXT_BYTES
audit_skill = _core.audit_skill
estimate_tokens = _core.estimate_tokens
format_text = _core.format_text
main = _core.main
parse_args = _core.parse_args


def __getattr__(name: str) -> Any:
    """Keep historical public imports working while implementation lives in core."""

    return getattr(_core, name)


if __name__ == "__main__":
    raise SystemExit(main())
