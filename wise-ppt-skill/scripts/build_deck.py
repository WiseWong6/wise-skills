#!/usr/bin/env python3
"""Build the current Wise PPT deck HTML from the runtime shell and slide fragments."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = SKILL_ROOT / "runtime" / "app-template.html"
BUILD_FILE = "deck-build.json"
DEFAULTS = {
    "stylesheet_href": "assets/shared.css",
    "runtime_script_src": "assets/deck-runtime.js",
}
ALLOWED_BUILD_KEYS = {"deck_title", *DEFAULTS}
SLIDES_START = "<!-- WISE_PPT_SLIDES_START -->"
SLIDES_END = "<!-- WISE_PPT_SLIDES_END -->"
PLACEHOLDERS = {
    "{{LANG}}",
    "{{DECK_TITLE}}",
    "{{PAGE_TITLE}}",
    "{{STYLESHEET_HREF}}",
    "{{RUNTIME_SCRIPT_SRC}}",
    "{{SLIDES}}",
}


class BuildError(RuntimeError):
    pass


def load_object(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BuildError(f"无法读取 JSON：{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BuildError(f"JSON 顶层必须是对象：{path}")
    return value


def resolve_local_file(deck: Path, reference: str, label: str, *, within_deck: bool = False) -> Path:
    candidate = Path(reference)
    if candidate.is_absolute() or "://" in reference:
        raise BuildError(f"{label} 必须是本地相对路径：{reference}")
    target = (deck / candidate).resolve()
    if within_deck:
        try:
            target.relative_to(deck)
        except ValueError as exc:
            raise BuildError(f"{label} 必须位于 deck 目录内：{target}") from exc
    if not target.is_file():
        raise BuildError(f"{label} 不存在：{target}")
    return target


def replace_once(source: str, token: str, value: str) -> str:
    count = source.count(token)
    if count != 1:
        raise BuildError(f"runtime 模板中的 {token} 应出现一次，实际 {count} 次")
    return source.replace(token, value, 1)


def extract_slides(source: str, path: Path) -> str:
    if source.count(SLIDES_START) != 1 or source.count(SLIDES_END) != 1:
        raise BuildError(f"{path} 必须各包含一个页面区开始/结束标记")
    start = source.index(SLIDES_START) + len(SLIDES_START)
    end = source.index(SLIDES_END, start)
    slides = source[start:end].replace("{{SLIDES}}", "").strip()
    lowered = slides.casefold()
    forbidden = ("<!doctype", "<html", "<head", "<body", 'id="board"', 'id="track"', "<iframe")
    found = [token for token in forbidden if token in lowered]
    if found:
        raise BuildError(f"页面区只能包含 section.slide fragments，不得包含 {found}")
    if not re.search(r'<section\s+class="[^"]*\bslide\b', slides):
        raise BuildError("页面区中没有 section.slide")
    return slides


def render(deck: Path) -> tuple[Path, str]:
    build_path = deck / BUILD_FILE
    render_path = deck / "render-plan.json"
    build = dict(DEFAULTS)
    if build_path.is_file():
        declared = load_object(build_path)
        unknown = sorted(set(declared) - ALLOWED_BUILD_KEYS)
        if unknown:
            raise BuildError(f"{build_path} 包含未声明字段：{unknown}")
        build.update(declared)
    render_plan = load_object(render_path)
    output_file = render_plan.get("output_file")
    if output_file != "index.html":
        raise BuildError("Render Plan 的 output_file 必须是 index.html")
    content_ref = render_plan.get("content_file")
    if not isinstance(content_ref, str) or not content_ref:
        raise BuildError("Render Plan 缺少 content_file")
    content = load_object(resolve_local_file(deck, content_ref, "content_file", within_deck=True))
    brief = content.get("brief")
    if not isinstance(brief, dict):
        raise BuildError("Content Contract 缺少 brief")
    title = brief.get("title")
    language = brief.get("language")
    if not isinstance(title, str) or not title.strip():
        raise BuildError("brief.title 必须是非空字符串")
    if not isinstance(language, str) or not language.strip():
        raise BuildError("brief.language 必须是非空字符串")

    stylesheet_href = str(build["stylesheet_href"])
    runtime_script_src = str(build["runtime_script_src"])
    resolve_local_file(deck, stylesheet_href, "stylesheet_href")
    resolve_local_file(deck, runtime_script_src, "runtime_script_src")
    output_path = deck / "index.html"
    slides = extract_slides(output_path.read_text(encoding="utf-8"), output_path)

    deck_title = build.get("deck_title", title)
    if not isinstance(deck_title, str) or not deck_title.strip():
        raise BuildError("deck_title 必须是非空字符串")
    source = TEMPLATE.read_text(encoding="utf-8")
    values = {
        "{{LANG}}": html.escape(language.strip(), quote=True),
        "{{DECK_TITLE}}": html.escape(deck_title.strip(), quote=True),
        "{{PAGE_TITLE}}": html.escape(title.strip()),
        "{{STYLESHEET_HREF}}": html.escape(stylesheet_href, quote=True),
        "{{RUNTIME_SCRIPT_SRC}}": html.escape(runtime_script_src, quote=True),
        "{{SLIDES}}": slides,
    }
    if set(values) != PLACEHOLDERS:
        raise BuildError("构建器占位符定义与 runtime 模板不一致")
    for token, value in values.items():
        source = replace_once(source, token, value)
    unresolved = sorted(set(re.findall(r"{{[A-Z_]+}}", source)))
    if unresolved:
        raise BuildError(f"输出仍有未替换占位符：{unresolved}")
    notice = "<!-- Generated shell: edit slides only between WISE_PPT_SLIDES markers, then run scripts/build_deck.py. -->\n"
    output = source.replace("<!doctype html>\n", f"<!doctype html>\n{notice}", 1)
    return output_path, output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", type=Path, help="包含 content/render/index 与可选 deck-build 的 deck 目录")
    parser.add_argument("--check", action="store_true", help="只检查 index.html 是否与权威源一致")
    args = parser.parse_args()
    deck = args.deck.expanduser().resolve()
    try:
        output_path, output = render(deck)
        if args.check:
            actual = output_path.read_text(encoding="utf-8") if output_path.is_file() else ""
            if actual != output:
                raise BuildError(f"生成产物已漂移：{output_path}；请重新运行 build_deck.py")
            print(f"PASS build-check output={output_path}")
            return 0
        output_path.write_text(output, encoding="utf-8")
        print(f"PASS build output={output_path}")
        return 0
    except (BuildError, OSError, UnicodeDecodeError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
