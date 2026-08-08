#!/usr/bin/env python3
"""Validate wise-ppt content, planning, rendering and catalog artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _ppt_contracts import VALIDATORS, resolve_root, run_validation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validate.py",
        description="用 Core schema 与 Theme manifest 校验 wise-ppt 产物。",
    )
    parser.add_argument("command", choices=tuple(VALIDATORS), help="校验阶段")
    parser.add_argument("target", help="JSON 文件、deck 目录、主题目录或主题 ID")
    parser.add_argument(
        "--root",
        help="wise-ppt-skill 根目录；默认取脚本上一级，测试/集成可覆盖",
    )
    parser.add_argument("--quiet", action="store_true", help="通过时只返回退出码")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = resolve_root(args.root)
    target = Path(args.target).expanduser()
    if not target.is_absolute() and args.command != "gallery":
        target = (Path.cwd() / target).resolve()
    elif not target.is_absolute() and target.exists():
        target = (Path.cwd() / target).resolve()

    result = run_validation(args.command, target, root)
    for issue in result.issues:
        print(issue.format())
    if result.ok:
        if not args.quiet:
            print(f"PASS {args.command}: {target}")
        return 0
    print(f"FAIL {args.command}: {len(result.errors)} error(s)", file=sys.stderr)
    return 2 if result.has_config_error else 1


if __name__ == "__main__":
    raise SystemExit(main())
