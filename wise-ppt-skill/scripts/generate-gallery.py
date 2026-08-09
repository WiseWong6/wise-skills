#!/usr/bin/env python3
"""从公共 Gallery manifest 确定性刷新 paper-ink 画册目录与样张声明。"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "capabilities/layouts/gallery-manifest.json"
PUBLIC_GALLERY_ROOT = ROOT / "gallery/paper-ink"
GEO_JSON_PATH = ROOT / "capabilities/vendors/geo/guangdong-geo.json"
GEO_SCRIPT_PATH = ROOT / "capabilities/vendors/geo/guangdong-geo.js"
ARRAY_PATTERN = re.compile(
    r"var LAYOUTS = /\*__LAYOUTS__\*/.*?; /\*__LAYOUTS_END__\*/", re.S
)
PAGE_ATTRS = (
    "data-page-id",
    "data-page-role",
    "data-theme",
    "data-layout",
    "data-layout-source",
    "data-density",
    "data-reuse-mode",
)
BLOCK_ATTRS = (
    "data-block-id",
    "data-provider",
    "data-renderer-kind",
    "data-component-source",
    "data-component",
    "data-component-id",
    "data-content-ref",
)


def _gallery_path(relative: str | Path) -> Path:
    """Resolve a v2 Gallery path without a legacy-theme fallback."""

    logical = Path(relative)
    try:
        logical.relative_to(Path("gallery/paper-ink"))
    except ValueError as exc:
        raise SystemExit(f"Gallery v2 路径必须位于 gallery/paper-ink：{logical}") from exc
    return ROOT / logical


def load_recipes() -> list[dict[str, Any]]:
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"无法读取 Gallery manifest：{exc}") from exc
    recipes = data.get("recipes") if isinstance(data, dict) else None
    if (
        not isinstance(data, dict)
        or data.get("contract_version") != 2
        or not isinstance(recipes, list)
    ):
        raise SystemExit("gallery-manifest.json 必须是 v2 且包含 recipes 数组")
    if data.get("recipe_count") != len(recipes):
        raise SystemExit("recipe_count 与 recipes 实际数量不一致")
    ids = [item.get("recipe_id") for item in recipes]
    codes = [item.get("display_code") for item in recipes]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise SystemExit("recipe_id 缺失或重复")
    if any(not item for item in codes) or len(codes) != len(set(codes)):
        raise SystemExit("display_code 缺失或重复")
    return recipes


def gallery_rows(recipes: list[dict[str, Any]], corpus: str) -> list[dict[str, str]]:
    rows = []
    for recipe in recipes:
        example = recipe.get("examples", {}).get(corpus)
        if not example:
            raise SystemExit(f"{recipe.get('recipe_id')} 缺少 {corpus} example")
        rows.append(
            {
                "id": recipe["recipe_id"],
                "fam": recipe["family"],
                "code": recipe["display_code"],
                "name": recipe["name"],
                "file": Path(example).name,
                "use": recipe["description"],
            }
        )
    return rows


def with_attrs(tag: str, attrs: Mapping[str, str], known: tuple[str, ...]) -> str:
    for name in known:
        tag = re.sub(rf"\s+{re.escape(name)}=(?:\"[^\"]*\"|'[^']*')", "", tag)
    suffix = "".join(
        f' {name}="{html.escape(value, quote=True)}"' for name, value in attrs.items()
    )
    return tag[:-1] + suffix + ">"


def with_gallery_shell(source: str, href: str) -> str:
    pattern = re.compile(
        r'(<link\b[^>]*\brel=["\']stylesheet["\'][^>]*\bhref=)["\'][^"\']*shell\.css["\']',
        re.IGNORECASE,
    )
    updated, count = pattern.subn(rf'\1"{href}"', source, count=1)
    if count != 1:
        raise SystemExit("Gallery 页面必须且只能声明一个 shell.css")
    return updated


def primary_renderer(recipe: Mapping[str, Any]) -> Mapping[str, str]:
    slots = recipe.get("slots") if isinstance(recipe.get("slots"), list) else []
    primary_slots = [
        slot
        for slot in slots
        if isinstance(slot, Mapping) and slot.get("visual_role") == "primary"
    ]
    if len(primary_slots) != 1:
        raise SystemExit(f"{recipe.get('recipe_id')} 必须且只能有一个 primary slot")
    renderer = primary_slots[0].get("default_renderer")
    if not isinstance(renderer, Mapping):
        raise SystemExit(f"{recipe.get('recipe_id')} primary slot 缺少 default_renderer")
    required = ("renderer_kind", "component_source", "component_id")
    if any(not renderer.get(key) for key in required):
        raise SystemExit(f"{recipe.get('recipe_id')} default_renderer 不完整")
    return {key: str(renderer[key]) for key in required}


def sync_frame(source: str, recipe: Mapping[str, Any], corpus: str) -> str:
    html_match = re.search(r"<html\b[^>]*>", source)
    if not html_match:
        raise SystemExit(f"样张没有 <html>：{recipe['recipe_id']} ({corpus})")
    page_tag = with_attrs(
        html_match.group(0),
        {
            "data-page-id": f"gallery-{corpus}-{recipe['display_code'].lower()}",
            "data-page-role": (recipe.get("roles") or ["explain"])[0],
            "data-theme": "paper-ink",
            "data-layout": recipe["recipe_id"],
            "data-layout-source": "gallery",
        },
        PAGE_ATTRS,
    )
    source = source[: html_match.start()] + page_tag + source[html_match.end() :]

    stage_match = re.search(
        r"<(?:div|main)\b[^>]*\bclass=(?:\"[^\"]*\bstage\b[^\"]*\"|'[^']*\bstage\b[^']*')[^>]*>",
        source,
    )
    if not stage_match:
        raise SystemExit(f"样张没有 .stage：{recipe['recipe_id']} ({corpus})")
    renderer = primary_renderer(recipe)
    block_tag = with_attrs(
        stage_match.group(0),
        {
            "data-block-id": "gallery-primary",
            "data-renderer-kind": renderer["renderer_kind"],
            "data-component-source": renderer["component_source"],
            "data-component-id": renderer["component_id"],
            "data-content-ref": f"example.{recipe['display_code'].lower()}",
        },
        BLOCK_ATTRS,
    )
    return source[: stage_match.start()] + block_tag + source[stage_match.end() :]


def planned_outputs(recipes: list[dict[str, Any]]) -> dict[Path, str]:
    outputs: dict[Path, str] = {}
    try:
        geo = json.loads(GEO_JSON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"无法读取本地广东地图数据：{exc}") from exc
    outputs[GEO_SCRIPT_PATH] = (
        "window.WISE_GUANGDONG_GEO = "
        + json.dumps(geo, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )
    for corpus in ("general", "ai"):
        index_path = _gallery_path(f"gallery/paper-ink/{corpus}/index.html")
        if not index_path.is_file():
            raise SystemExit(f"画册目录不存在：gallery/paper-ink/{corpus}/index.html")
        current = index_path.read_text(encoding="utf-8")
        rows = json.dumps(gallery_rows(recipes, corpus), ensure_ascii=False, indent=2)
        replacement = f"var LAYOUTS = /*__LAYOUTS__*/{rows}; /*__LAYOUTS_END__*/"
        if not ARRAY_PATTERN.search(current):
            raise SystemExit(f"画册缺少生成标记：{index_path}")
        index_source = ARRAY_PATTERN.sub(lambda _: replacement, current, count=1)
        outputs[index_path] = with_gallery_shell(index_source, "../../shell.css")

        for recipe in recipes:
            relative = recipe["examples"][corpus]
            frame_path = _gallery_path(relative)
            if not frame_path.is_file():
                raise SystemExit(f"样张不存在：{relative}")
            source = frame_path.read_text(encoding="utf-8")
            frame_source = sync_frame(source, recipe, corpus)
            outputs[frame_path] = with_gallery_shell(frame_source, "../../../shell.css")
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只检查生成结果是否最新")
    args = parser.parse_args()

    outputs = planned_outputs(load_recipes())
    stale = [
        path
        for path, expected in outputs.items()
        if not path.is_file() or path.read_text(encoding="utf-8") != expected
    ]
    if args.check:
        if stale:
            for path in stale:
                print(f"STALE {path.relative_to(ROOT)}", file=sys.stderr)
            return 1
        print(f"OK gallery：2 indexes + {len(outputs) - 3} frames + 1 local geo asset")
        return 0

    for path in stale:
        path.write_text(outputs[path], encoding="utf-8")
        print(f"UPDATED {path.relative_to(ROOT)}")
    print(f"OK gallery：2 indexes + {len(outputs) - 3} frames + 1 local geo asset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
