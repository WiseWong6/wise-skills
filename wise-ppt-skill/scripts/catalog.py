#!/usr/bin/env python3
"""Deterministically filter layout and component catalogs.

The command reports manifest metadata only.  It does not score candidates or
decide which semantic expression a slide should use; that remains a Core
planning responsibility.
"""

from __future__ import annotations

import argparse
import json
import sys

from _ppt_contracts import (
    ContractError,
    filter_catalog,
    load_component_catalog,
    load_layout_catalog,
    public_catalog_record,
    resolve_root,
)


def _append_filter(parser: argparse.ArgumentParser, flag: str, help_text: str) -> None:
    parser.add_argument(flag, action="append", default=[], help=help_text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="catalog.py",
        description="只按 manifest 元数据过滤候选，不替 Core 做语义选择。",
    )
    parser.add_argument("kind", choices=("layouts", "components"), help="查询目录类型")
    parser.add_argument("--root", help="wise-ppt-skill 根目录")
    parser.add_argument("--theme", help="主题 ID；省略时使用 themes/registry.json 的默认主题")
    _append_filter(parser, "--role", "按 role 精确过滤；可重复")
    _append_filter(parser, "--relation", "按 relation 精确过滤；可重复")
    _append_filter(parser, "--density", "按 density 精确过滤；可重复")
    _append_filter(parser, "--provider", "按 provider 精确过滤；可重复")
    _append_filter(parser, "--primitive", "按 layout.core_primitives 精确过滤；可重复")
    _append_filter(parser, "--task", "按组件任务标签精确过滤；可重复")
    parser.add_argument("--name", help="按稳定 ID、名称、展示码、别名或描述做不区分大小写的包含过滤")
    parser.add_argument("--compact", action="store_true", help="输出单行 JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = resolve_root(args.root)
    try:
        if args.kind == "layouts":
            theme, records, _ = load_layout_catalog(root, args.theme)
            source_path = theme.layout_manifest_path
        else:
            theme, records, source_path = load_component_catalog(root, args.theme)
        matches = filter_catalog(
            records,
            roles=args.role,
            relations=args.relation,
            densities=args.density,
            providers=args.provider,
            primitives=args.primitive,
            tasks=args.task,
            name=args.name,
        )
    except ContractError as exc:
        print(f"ERROR config.catalog: {exc}", file=sys.stderr)
        return 2

    payload = {
        "kind": args.kind,
        "theme_id": theme.theme_id,
        "source": str(source_path),
        "filters": {
            "roles": args.role,
            "relations": args.relation,
            "densities": args.density,
            "providers": args.provider,
            "primitives": args.primitive,
            "tasks": args.task,
            "name": args.name,
        },
        "count": len(matches),
        "items": [public_catalog_record(record) for record in matches],
        "semantic_decision": "not-performed",
    }
    indent = None if args.compact else 2
    print(json.dumps(payload, ensure_ascii=False, indent=indent, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
