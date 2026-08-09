#!/usr/bin/env python3
"""从 paper-ink layout manifest 确定性刷新两套画册目录与样张声明。"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "themes/paper-ink/layout-manifest.json"
GALLERIES = {
    "general": ROOT / "themes/paper-ink/gallery/general/index.html",
    "ai": ROOT / "themes/paper-ink/gallery/ai/index.html",
}
ARRAY_PATTERN = re.compile(
    r"var LAYOUTS = /\*__LAYOUTS__\*/.*?; /\*__LAYOUTS_END__\*/", re.S
)
PAGE_ATTRS = (
    "data-page-id",
    "data-page-role",
    "data-theme",
    "data-layout",
    "data-density",
    "data-reuse-mode",
)
BLOCK_ATTRS = (
    "data-block-id",
    "data-provider",
    "data-component",
    "data-content-ref",
)


def load_layouts() -> list[dict]:
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"无法读取 layout manifest：{exc}") from exc
    layouts = data.get("layouts")
    if not isinstance(layouts, list):
        raise SystemExit("layout-manifest.json 缺少 layouts 数组")
    if data.get("layout_count") != len(layouts):
        raise SystemExit("layout_count 与 layouts 实际数量不一致")
    ids = [item.get("layout_id") for item in layouts]
    codes = [item.get("display_code") for item in layouts]
    if len(ids) != len(set(ids)) or len(codes) != len(set(codes)):
        raise SystemExit("layout_id 或 display_code 重复")
    return layouts


def gallery_rows(layouts: list[dict], corpus: str) -> list[dict]:
    rows = []
    for layout in layouts:
        example = layout.get("examples", {}).get(corpus)
        if not example:
            raise SystemExit(f"{layout.get('layout_id')} 缺少 {corpus} example")
        rows.append(
            {
                "id": layout["layout_id"],
                "fam": layout["family"],
                "code": layout["display_code"],
                "name": layout["name"],
                "file": Path(example).name,
                # 画册栏面向浏览者，只展示自然语言用途；roles / relations /
                # capacity / selection_notes 留在 manifest，供 AI 确定性筛选。
                "use": layout["description"],
            }
        )
    return rows


def with_attrs(tag: str, attrs: dict[str, str], known: tuple[str, ...]) -> str:
    for name in known:
        tag = re.sub(rf"\s+{re.escape(name)}=(?:\"[^\"]*\"|'[^']*')", "", tag)
    suffix = "".join(
        f' {name}="{html.escape(value, quote=True)}"' for name, value in attrs.items()
    )
    return tag[:-1] + suffix + ">"


def primary_provider(layout: dict) -> str:
    renderers = layout.get("renderers") or []
    for provider in renderers:
        if provider != "typography":
            return provider
    return renderers[0] if renderers else "native-html"


def sync_frame(source: str, layout: dict, corpus: str) -> str:
    html_match = re.search(r"<html\b[^>]*>", source)
    if not html_match:
        raise SystemExit(f"样张没有 <html>：{layout['layout_id']} ({corpus})")
    densities = layout.get("densities") or ["balanced"]
    density = "balanced" if "balanced" in densities else densities[0]
    page_tag = with_attrs(
        html_match.group(0),
        {
            "data-page-id": f"gallery-{corpus}-{layout['display_code'].lower()}",
            "data-page-role": (layout.get("roles") or ["explain"])[0],
            "data-theme": "paper-ink",
            "data-layout": layout["layout_id"],
            "data-density": density,
            "data-reuse-mode": "copy",
        },
        PAGE_ATTRS,
    )
    source = source[: html_match.start()] + page_tag + source[html_match.end() :]

    stage_match = re.search(r"<(?:div|main)\b[^>]*\bclass=(?:\"[^\"]*\bstage\b[^\"]*\"|'[^']*\bstage\b[^']*')[^>]*>", source)
    if not stage_match:
        raise SystemExit(f"样张没有 .stage：{layout['layout_id']} ({corpus})")
    block_tag = with_attrs(
        stage_match.group(0),
        {
            "data-block-id": "gallery-primary",
            "data-provider": primary_provider(layout),
            "data-component": "layout-specimen",
            "data-content-ref": f"example.{layout['display_code'].lower()}",
        },
        BLOCK_ATTRS,
    )
    return source[: stage_match.start()] + block_tag + source[stage_match.end() :]


def planned_outputs(layouts: list[dict]) -> dict[Path, str]:
    outputs: dict[Path, str] = {}
    for corpus, index_path in GALLERIES.items():
        current = index_path.read_text(encoding="utf-8")
        rows = json.dumps(gallery_rows(layouts, corpus), ensure_ascii=False, indent=2)
        replacement = f"var LAYOUTS = /*__LAYOUTS__*/{rows}; /*__LAYOUTS_END__*/"
        if not ARRAY_PATTERN.search(current):
            raise SystemExit(f"画册缺少生成标记：{index_path}")
        outputs[index_path] = ARRAY_PATTERN.sub(lambda _: replacement, current, count=1)

        for layout in layouts:
            relative = layout["examples"][corpus]
            frame_path = ROOT / relative
            if not frame_path.is_file():
                raise SystemExit(f"样张不存在：{relative}")
            source = frame_path.read_text(encoding="utf-8")
            outputs[frame_path] = sync_frame(source, layout, corpus)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只检查生成结果是否最新")
    args = parser.parse_args()

    outputs = planned_outputs(load_layouts())
    stale = [path for path, expected in outputs.items() if path.read_text(encoding="utf-8") != expected]
    if args.check:
        if stale:
            for path in stale:
                print(f"STALE {path.relative_to(ROOT)}", file=sys.stderr)
            return 1
        print(f"OK gallery：2 indexes + {len(outputs) - 2} frames")
        return 0

    for path in stale:
        path.write_text(outputs[path], encoding="utf-8")
        print(f"UPDATED {path.relative_to(ROOT)}")
    print(f"OK gallery：2 indexes + {len(outputs) - 2} frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
