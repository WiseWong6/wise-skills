#!/usr/bin/env python3
"""Deterministically query public layout recipes and optional Atlas components."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


class CatalogError(RuntimeError):
    """Raised when a public capability catalog cannot be loaded."""


def _append_filter(parser: argparse.ArgumentParser, flag: str, help_text: str) -> None:
    parser.add_argument(flag, action="append", default=[], help=help_text)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CatalogError(f"缺少文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise CatalogError(
            f"JSON 无法解析：{path}:{exc.lineno}:{exc.colno} {exc.msg}"
        ) from exc


def _resolve_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    configured = os.environ.get("WISE_PPT_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        if isinstance(item, str):
            output.append(item)
        elif isinstance(item, Mapping):
            identifier = item.get("id") or item.get("name") or item.get("value")
            if identifier:
                output.append(str(identifier))
    return output


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _load_registry(root: Path) -> tuple[dict[str, Any], Path]:
    path = root / "capabilities" / "registry.json"
    document = _load_json(path)
    if not isinstance(document, dict) or document.get("contract_version") != 2:
        raise CatalogError(f"公共能力注册表 contract_version 必须为 2：{path}")
    for key in ("renderer_kinds", "component_sources", "capabilities"):
        if not isinstance(document.get(key), list):
            raise CatalogError(f"公共能力注册表缺少 {key}[]：{path}")
    return document, path


def _registered_values(registry: Mapping[str, Any], key: str, field: str) -> set[str]:
    return {
        str(item[field])
        for item in registry.get(key, [])
        if isinstance(item, Mapping) and item.get(field)
    }


def _validate_axis_filters(
    registry: Mapping[str, Any],
    renderer_kinds: Sequence[str],
    component_sources: Sequence[str],
) -> None:
    known_renderers = _registered_values(registry, "renderer_kinds", "renderer_kind")
    known_sources = _registered_values(registry, "component_sources", "component_source")
    unknown_renderers = sorted(set(renderer_kinds) - known_renderers)
    unknown_sources = sorted(set(component_sources) - known_sources)
    if unknown_renderers:
        raise CatalogError(f"未知 renderer_kind：{unknown_renderers}")
    if unknown_sources:
        raise CatalogError(f"未知 component_source：{unknown_sources}")


def _layout_manifest_path(root: Path, registry: Mapping[str, Any]) -> Path:
    entry = next(
        (
            item
            for item in registry.get("capabilities", [])
            if isinstance(item, Mapping) and item.get("capability_id") == "layout-gallery"
        ),
        None,
    )
    if not entry or not entry.get("manifest"):
        raise CatalogError("公共能力注册表缺少 layout-gallery manifest")
    return (root / str(entry["manifest"])).resolve()


def _load_layout_records(
    root: Path, registry: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], Path]:
    path = _layout_manifest_path(root, registry)
    document = _load_json(path)
    recipes = document.get("recipes") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("contract_version") != 2
        or not isinstance(recipes, list)
    ):
        raise CatalogError(f"Gallery manifest 必须是 v2 且包含 recipes[]：{path}")
    if document.get("recipe_count") != len(recipes):
        raise CatalogError(f"recipe_count 与 recipes 实际数量不一致：{path}")
    records = [dict(item) for item in recipes if isinstance(item, Mapping)]
    if len(records) != len(recipes):
        raise CatalogError(f"recipes[] 只能包含对象：{path}")
    identifiers = [item.get("recipe_id") for item in records]
    if any(not item for item in identifiers) or len(identifiers) != len(set(identifiers)):
        raise CatalogError(f"recipe_id 缺失或重复：{path}")
    return records, path


def _slug(value: Any) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return normalized or "component"


def _find_atlas_catalog() -> Path:
    candidates: list[Path] = []
    configured = os.environ.get("PPT_COMPONENT_ATLAS_CATALOG")
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend(
        [
            Path.home()
            / ".codex"
            / "skills"
            / "ppt-component-atlas"
            / "public"
            / "catalog-data.js",
            Path.home()
            / ".agents"
            / "skills"
            / "ppt-component-atlas"
            / "public"
            / "catalog-data.js",
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise CatalogError(
        "缺少 PPT Component Atlas catalog；请安装该能力或设置 "
        "PPT_COMPONENT_ATLAS_CATALOG"
    )


def _parse_atlas_document(path: Path) -> list[Mapping[str, Any]]:
    if path.suffix.casefold() != ".js":
        document = _load_json(path)
        entries = document.get("components") if isinstance(document, dict) else None
    else:
        source = path.read_text(encoding="utf-8")
        marker = "window.SWISS_CATALOG_DATA"
        marker_index = source.find(marker)
        object_index = source.find("{", marker_index)
        if marker_index < 0 or object_index < 0:
            raise CatalogError(f"Atlas catalog 缺少 {marker} JSON 对象：{path}")
        try:
            document, _ = json.JSONDecoder().raw_decode(source[object_index:])
        except json.JSONDecodeError as exc:
            raise CatalogError(f"Atlas catalog 无法解析：{path}: {exc}") from exc
        entries = document.get("entries") if isinstance(document, dict) else None
    if not isinstance(entries, list):
        raise CatalogError(f"Atlas catalog 缺少组件数组：{path}")
    return [item for item in entries if isinstance(item, Mapping)]


def _normalize_atlas_component(raw: Mapping[str, Any]) -> dict[str, Any]:
    number = raw.get("num")
    canonical_name = raw.get("name") or raw.get("component_id") or raw.get("id")
    component_id = raw.get("component_id") or raw.get("id")
    if not component_id:
        number_part = f"{int(number):03d}." if isinstance(number, int) else ""
        component_id = f"atlas.{number_part}{_slug(canonical_name)}"
        if raw.get("variant"):
            component_id += f".{_slug(raw['variant'])}"
    label = raw.get("label") or raw.get("display_name") or canonical_name or component_id
    aliases = _unique(
        str(item)
        for item in (
            canonical_name,
            label,
            raw.get("variant"),
            str(number) if number is not None else None,
            *_strings(raw.get("aliases")),
        )
        if item
    )
    return {
        "component_id": str(component_id),
        "name": str(label),
        "canonical_name": str(canonical_name or component_id),
        "variant": raw.get("variant"),
        "group": raw.get("group"),
        "group_label": raw.get("groupLabel") or raw.get("group_label"),
        "description": raw.get("description", ""),
        "tasks": _strings(raw.get("tasks") or raw.get("task")),
        "roles": _strings(raw.get("roles")),
        "relations": _strings(raw.get("relations") or raw.get("relation_shapes")),
        "primitives": _strings(raw.get("primitives") or raw.get("core_primitives")),
        "renderer_kinds": _strings(raw.get("renderer_kinds"))
        or ["native-html", "svg"],
        "component_sources": ["ppt-component-atlas"],
        "aliases": aliases,
        "selection_notes": raw.get("selection_notes") or raw.get("description") or "",
        "requires": _strings(raw.get("requires")),
    }


def _load_component_records() -> tuple[list[dict[str, Any]], Path]:
    path = _find_atlas_catalog()
    records = [_normalize_atlas_component(item) for item in _parse_atlas_document(path)]
    unique: dict[str, dict[str, Any]] = {}
    for record in records:
        unique.setdefault(record["component_id"], record)
    return list(unique.values()), path


def _record_values(record: Mapping[str, Any], field: str, kind: str) -> set[str]:
    if kind == "layouts":
        if field == "primitives":
            structure = record.get("structure_contract")
            core = structure.get("core_primitives", []) if isinstance(structure, Mapping) else []
            values = [*_strings(record.get("primitives")), *_strings(core)]
        elif field in {"renderer_kinds", "component_sources"}:
            slot_key = (
                "allowed_renderer_kinds"
                if field == "renderer_kinds"
                else "allowed_component_sources"
            )
            values = [
                value
                for slot in record.get("slots", [])
                if isinstance(slot, Mapping)
                for value in _strings(slot.get(slot_key))
            ]
        else:
            values = _strings(record.get(field))
    else:
        values = _strings(record.get(field))
    return {value.casefold() for value in values}


def _evaluate(
    record: Mapping[str, Any],
    *,
    kind: str,
    roles: Sequence[str],
    relations: Sequence[str],
    primitives: Sequence[str],
    renderer_kinds: Sequence[str],
    component_sources: Sequence[str],
    tasks: Sequence[str],
    name: str | None,
) -> tuple[bool, list[str]]:
    requested = {
        "roles": roles,
        "relations": relations,
        "primitives": primitives,
        "renderer_kinds": renderer_kinds,
        "component_sources": component_sources,
        "tasks": tasks,
    }
    reasons: list[str] = []
    for field, values in requested.items():
        available = _record_values(record, field, kind)
        missing = [value for value in values if value.casefold() not in available]
        if missing:
            reasons.append(f"{field} 缺少 {missing}")

    query = (name or "").casefold().strip()
    identifier = record.get("recipe_id") or record.get("component_id")
    haystack = " ".join(
        str(item)
        for item in (
            identifier,
            record.get("name"),
            record.get("canonical_name"),
            record.get("display_code"),
            record.get("description"),
            *(record.get("aliases") or []),
        )
        if item
    ).casefold()
    if query and query not in haystack:
        reasons.append(f"name 未包含 {name!r}")
    return not reasons, reasons


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="catalog.py",
        description="只按公共能力元数据过滤候选，不替内容规划做主观选择。",
    )
    parser.add_argument("kind", choices=("layouts", "components"), help="查询布局或 Atlas 组件")
    parser.add_argument("--root", help="wise-ppt-skill 根目录")
    _append_filter(parser, "--role", "按 role 精确过滤；可重复")
    _append_filter(parser, "--relation", "按 relation 精确过滤；可重复")
    _append_filter(parser, "--primitive", "按 primitive 精确过滤；可重复")
    _append_filter(parser, "--renderer-kind", "按 renderer_kind 精确过滤；可重复")
    _append_filter(parser, "--component-source", "按 component_source 精确过滤；可重复")
    _append_filter(parser, "--task", "按组件任务标签精确过滤；可重复")
    parser.add_argument("--name", help="按稳定 ID、名称、展示码、别名或描述做包含过滤")
    parser.add_argument("--compact", action="store_true", help="输出单行 JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = _resolve_root(args.root)
    try:
        registry, _ = _load_registry(root)
        _validate_axis_filters(registry, args.renderer_kind, args.component_source)
        if args.kind == "layouts":
            records, source_path = _load_layout_records(root, registry)
        elif args.component_source and "ppt-component-atlas" not in args.component_source:
            records, source_path = [], root / "capabilities" / "registry.json"
        else:
            records, source_path = _load_component_records()
    except CatalogError as exc:
        print(f"ERROR config.catalog: {exc}", file=sys.stderr)
        return 2

    evaluations: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    id_key = "recipe_id" if args.kind == "layouts" else "component_id"
    for record in records:
        fit, reasons = _evaluate(
            record,
            kind=args.kind,
            roles=args.role,
            relations=args.relation,
            primitives=args.primitive,
            renderer_kinds=args.renderer_kind,
            component_sources=args.component_source,
            tasks=args.task,
            name=args.name,
        )
        evaluations.append(
            {
                id_key: record[id_key],
                "result": "fit" if fit else "reject",
                "reasons": reasons or ["匹配全部查询条件"],
            }
        )
        if fit:
            matches.append(record)

    matches.sort(key=lambda item: str(item[id_key]))
    evaluations.sort(key=lambda item: str(item[id_key]))
    payload = {
        "kind": args.kind,
        "source": str(source_path),
        "filters": {
            "roles": args.role,
            "relations": args.relation,
            "primitives": args.primitive,
            "renderer_kinds": args.renderer_kind,
            "component_sources": args.component_source,
            "tasks": args.task,
            "name": args.name,
        },
        "evaluated_count": len(records),
        "count": len(matches),
        "items": matches,
        "candidate_evaluations": evaluations,
        "semantic_decision": "not-performed",
    }
    indent = None if args.compact else 2
    print(json.dumps(payload, ensure_ascii=False, indent=indent, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
