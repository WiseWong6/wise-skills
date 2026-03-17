#!/usr/bin/env python3
"""Convert constrained Markdown to WeChat-editor-stable HTML."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RAW_BLOCK_START = "<!--RAW-->"
RAW_BLOCK_END = "<!--/RAW-->"

LIST_ITEM_RE = re.compile(r"^(?:\s*)([-*+]|\d+[.)])\s+(.+)$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")
HR_RE = re.compile(r"^(\*\s*){3,}$|^(-\s*){3,}$|^(_\s*){3,}$")
RAW_INLINE_RE = re.compile(r"\{\{\{(.*?)\}\}\}")
SECTION_RE = re.compile(r"^(\d{2})(?:\s*)(.+)$")
# 中文章节标题正则：匹配 "第一部分：xxx" 或 "第1部分：xxx" 格式
CHINESE_SECTION_RE = re.compile(r"^第([一二三四五六七八九十\d]+)部分[：:]\s*(.+)$")

# Markdown 表格正则
TABLE_ROW_RE = re.compile(r"^\|(.+)\|$")
TABLE_DIVIDER_RE = re.compile(r"^\|[-:\s|]+\|$")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

BODY_SERIF = "'PingFangSC-Light','PingFangSC',-apple-system,BlinkMacSystemFont,sans-serif"
UI_SANS = "'PingFangSC',-apple-system,BlinkMacSystemFont,sans-serif"

# 账号类型配置
ACCOUNT_CONFIG = {
    "wise": {
        "top_text": "⭐️ 关注星标，收看AI实战",
        "bottom_text": "⭐️ 关注星标，收看AI实战",
    },
    "human": {
        "top_text": "⭐️ 关注星标，收看AI、商业新知",
        "bottom_text": "⭐️ 关注星标，收看AI、商业新知",
    },
}

TEXT_COLOR = "rgba(0,0,0,0.9)"
ACCENT = "#0052FF"
ACCENT_LIGHT = "#E6F0FF"
BORDER_LIGHT = "#E8E8E8"
BLOCKQUOTE_BG = "#F8FAFC"
BLOCKQUOTE_BORDER = "#E6EDF7"

@dataclass
class RenderConfig:
    list_style: str
    divider_policy: str
    image_container: str
    toc_mode: str
    code_wrap: str
    highlight_direction: str
    account_type: str  # "wise" or "human"
    content_mode: str = "default"


def load_template(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def strip_frontmatter(md_text: str) -> str:
    """Remove YAML frontmatter (content between --- markers at the start)."""
    lines = md_text.splitlines()
    if lines and lines[0].strip() == "---":
        # Find the closing ---
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1:])
        # No closing --- found, return as is
        return md_text
    return md_text


def chinese_to_arabic(chinese_num: str) -> str:
    """Convert Chinese number to Arabic number string with zero padding.
    一 -> 01, 二 -> 02, ..., 十 -> 10
    """
    mapping = {
        "一": "01", "二": "02", "三": "03", "四": "04", "五": "05",
        "六": "06", "七": "07", "八": "08", "九": "09", "十": "10"
    }
    if chinese_num in mapping:
        return mapping[chinese_num]
    # 如果是数字字符串，补零
    if chinese_num.isdigit():
        return chinese_num.zfill(2)
    return "00"


def clean_metadata(md_text: str) -> str:
    """Drop tail metadata blocks from article workflows."""
    lines = md_text.splitlines()
    metadata_markers = [
        "**参考资料**",
        "**创作时间**",
        "## 金句来源说明",
        "<!-- 本润色由",
    ]
    cutoff = len(lines)
    for i, line in enumerate(lines):
        if any(marker in line.strip() for marker in metadata_markers):
            cutoff = i
            break
    while cutoff > 0 and lines[cutoff - 1].strip() == "":
        cutoff -= 1
    return "\n".join(lines[:cutoff])


def escape_text(text: str) -> str:
    return html.escape(text, quote=False)


def find_cdn_url(url: str, image_mapping: dict[str, Any]) -> str:
    """Resolve a local path or filename to mapped CDN URL when available."""
    if not image_mapping:
        return url
    if url in image_mapping and isinstance(image_mapping[url], str):
        return image_mapping[url]

    url_filename = Path(url).name
    flat = image_mapping.get("image_mapping_flat")
    if isinstance(flat, dict) and url_filename in flat:
        return flat[url_filename]

    for key in ["cover_urls", "poster_urls"]:
        node = image_mapping.get(key)
        if isinstance(node, dict) and url_filename in node:
            return node[url_filename]

    for k, v in image_mapping.items():
        if isinstance(v, str) and v.startswith("http") and (k == url_filename or url.endswith(k)):
            return v
    return url


def normalize_code_text(text: str, mode: str) -> str:
    if mode != "smart-url":
        return text

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if "http://" not in normalized and "https://" not in normalized:
        return normalized

    label_patterns = [
        "下载地址",
        "文档地址",
        "体验链接",
        "GLM图片生成接口文档",
        "即梦图片生成接口文档",
    ]
    label_union = "|".join(re.escape(label) for label in label_patterns)

    # URL immediately followed by another URL or Chinese label text.
    normalized = re.sub(r"(https?://\S+?)(?=https?://)", r"\1\n", normalized)
    normalized = re.sub(r"(https?://[^\s]+?)(?=[\u4e00-\u9fa5])", r"\1\n", normalized)

    # If URL is glued to previous text, split to next line.
    normalized = re.sub(r"(?<![\s\n])(https?://)", r"\n\1", normalized)

    # Frequent merged label+URL patterns.
    normalized = re.sub(rf"({label_union})\s*[：:]?\s*(https?://\S+)", r"\1\n\2", normalized)
    normalized = re.sub(rf"(https?://\S+?)({label_union})", r"\1\n\2", normalized)
    normalized = re.sub(rf"(https?://\S+)\s+({label_union})", r"\1\n\2", normalized)

    # Trim right whitespace before newline and collapse excessive blank lines.
    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized


def render_inline_link(text: str, url: str, gradient_dir: str) -> str:
    direction = "90deg" if gradient_dir == "ltr" else "180deg"
    return (
        f'<a href="{html.escape(url, quote=True)}" '
        f'style="color:{ACCENT};text-decoration:none;font-weight:600;word-break:break-word;'
        f'border-bottom:3px solid rgba(0,82,255,0.42);background:linear-gradient({direction},rgba(0,82,255,0.08) 0%,rgba(0,82,255,0.03) 100%);padding:0 1px;border-radius:0;">'
        f"{text}</a>"
    )


def format_inline(text: str, gradient_dir: str) -> str:
    parts: list[str] = []
    last = 0
    for match in RAW_INLINE_RE.finditer(text):
        parts.append(_format_inline_fragment(text[last : match.start()], gradient_dir))
        parts.append(match.group(1))
        last = match.end()
    parts.append(_format_inline_fragment(text[last:], gradient_dir))
    return "".join(parts)


def _format_inline_fragment(text: str, gradient_dir: str) -> str:
    escaped = escape_text(text)

    def replace_link(m: re.Match[str]) -> str:
        return render_inline_link(m.group(1), m.group(2), gradient_dir)

    escaped = MD_LINK_RE.sub(replace_link, escaped)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)

    # 4.html 风格加粗：渐变背景
    strong_style = 'font-weight:700;color:#1a1a1a;padding:0 3px;border-radius:2px;background:linear-gradient(90deg,rgba(0,82,255,0.12) 0%,rgba(0,82,255,0.04) 100%);'
    strong_tpl = rf'<span textstyle="" style="{strong_style}"><strong>\1</strong></span>'
    em_tpl = strong_tpl

    escaped = re.sub(r"\*\*([^*]+)\*\*", strong_tpl, escaped)
    escaped = re.sub(r"__([^_]+)__", strong_tpl, escaped)
    escaped = re.sub(r"\*([^*\n]+)\*", em_tpl, escaped)
    escaped = re.sub(r"_([^_\n]+)_", em_tpl, escaped)

    # 高亮保持简单样式
    escaped = re.sub(
        r"==([^=]+)==",
        f'<span textstyle="" style="color:{ACCENT};"><strong>\\1</strong></span>',
        escaped,
    )
    return escaped


def render_top_banner(account_type: str) -> str:
    """渲染顶部关注引导文案"""
    config = ACCOUNT_CONFIG.get(account_type, ACCOUNT_CONFIG["wise"])
    text = config["top_text"]
    return (
        f'<p style="font-size:17px;font-weight:300;color:{TEXT_COLOR};margin-bottom:24px;line-height:2.0;text-align:center;font-family:{BODY_SERIF};">'
        f'<span textstyle="" style="color:{ACCENT};"><strong>{text}</strong></span>'
        f'</p>'
    )


def render_bottom_banner(account_type: str) -> str:
    """渲染底部关注引导文案（含分割线）"""
    config = ACCOUNT_CONFIG.get(account_type, ACCOUNT_CONFIG["wise"])
    text = config["bottom_text"]
    return (
        f'<section style="margin-top:40px;">'
        f'<hr style="border-style:solid;border-width:1px 0 0;border-color:rgba(0,0,0,0.1);'
        f'transform:scale(1,0.5);-webkit-transform:scale(1,0.5);margin:0 0 24px 0;"/>'
        f'<p style="margin:0;text-align:center;font-size:17px;font-weight:300;color:{TEXT_COLOR};font-family:{BODY_SERIF};">'
        f'<span textstyle="" style="color:{ACCENT};"><strong>{text}</strong></span></p>'
        f'</section>'
    )


def render_paragraph(lines: list[str], gradient_dir: str, layout_id: int = 0) -> str:
    text = "\n".join(lines).replace("\r", "")
    text = re.sub(r"  \n", "<br/>", text)
    text = text.replace("\n", " ").strip()
    if not text:
        return ""
    return (
        f'<section data-layout-id="{layout_id}" style="font-size:17px;font-weight:300;color:{TEXT_COLOR};margin-bottom:24px;line-height:2.0;font-family:{BODY_SERIF};">'
        f"{format_inline(text, gradient_dir)}</section>"
    )


def render_section_header(number: str, title: str, config) -> str:
    """4.html 风格章节标题：左侧大号数字 + 右侧标题 + 分割线"""
    title_html = format_inline(title.strip(), config.highlight_direction)
    return f'''<section class="section-header" style="margin: 12px auto 28px;">
  <div class="section-top">
    <div class="section-num-cell">
      <span class="section-num-wrap">{number}</span>
    </div>
    <div class="section-main-cell">
      <div class="section-title-group">
        <h2 class="section-title">{title_html}</h2>
        <div class="section-line">
          <span class="section-accent"></span>
        </div>
      </div>
    </div>
  </div>
</section>'''


def render_heading(level: int, text: str, gradient_dir: str) -> str:
    text_html = format_inline(text.strip(), gradient_dir)
    if level <= 3:
        return (
            f'<h3 style="color:#1a1a1a;font-size:22px;margin:28px 0 20px;padding-bottom:10px;border-bottom:1px solid {BORDER_LIGHT};line-height:1.4;font-family:{BODY_SERIF};font-weight:700;">'
            f"{text_html}</h3>"
        )
    return (
        f'<h4 style="color:#1a1a1a;font-size:18px;margin:26px 0 16px;padding-left:10px;border-left:3px solid {ACCENT};line-height:1.5;font-family:{BODY_SERIF};font-weight:700;">'
        f"{text_html}</h4>"
    )


def render_blockquote(lines: list[str], gradient_dir: str) -> str:
    body = render_paragraph(lines, gradient_dir)
    if not body:
        return ""
    return (
        f'<blockquote style="margin:32px 0;padding:20px 24px;background:{BLOCKQUOTE_BG};border:1px solid {BLOCKQUOTE_BORDER};'
        f'border-left:3px solid {ACCENT};border-radius:0 12px 12px 0;position:relative;color:#1f2937;font-family:{BODY_SERIF};">'
        f"{body}</blockquote>"
    )


def render_list(list_lines: list[str], config: RenderConfig) -> str:
    if config.list_style == "code":
        # 处理 inline 格式后再渲染成代码块风格（跳过转义，保留 HTML 标签）
        formatted_lines = []
        for line in list_lines:
            match = LIST_ITEM_RE.match(line)
            if match:
                content = format_inline(match.group(2).strip(), config.highlight_direction)
                formatted_lines.append(f"- {content}")
            else:
                formatted_lines.append(line)
        return render_code_block(formatted_lines, "markdown", config.code_wrap, skip_escape=True)

    items = []
    for line in list_lines:
        match = LIST_ITEM_RE.match(line)
        if not match:
            continue
        content = format_inline(match.group(2).strip(), config.highlight_direction)
        items.append(f'<li style="margin:6px 0;"><span style="font-size:17px;font-weight:300;color:{TEXT_COLOR};font-family:{BODY_SERIF};line-height:2.0;">{content}</span></li>')
    if not items:
        return ""
    return f'<ul style="margin:0 0 24px;padding-left:20px;">{"".join(items)}</ul>'


def render_table(rows: list[str], gradient_dir: str) -> str:
    """Convert Markdown table rows to HTML table."""
    if len(rows) < 2:
        return ""

    html_rows = []
    for i, row in enumerate(rows):
        # 跳过分隔行（如 |---|---|）
        if TABLE_DIVIDER_RE.match(row):
            continue

        cells = [c.strip() for c in row.strip("|").split("|")]
        cell_tag = "th" if i == 0 else "td"
        cell_style = f"padding:12px 16px;border:1px solid {BORDER_LIGHT};text-align:left;font-family:{BODY_SERIF};"
        if i == 0:
            cell_style += f"background:#f8fafc;font-weight:700;"

        cells_html = "".join(
            f"<{cell_tag} style=\"{cell_style}\">{format_inline(c, gradient_dir)}</{cell_tag}>"
            for c in cells
        )
        html_rows.append(f"<tr>{cells_html}</tr>")

    if not html_rows:
        return ""

    return (
        f'<table style="width:100%;border-collapse:collapse;margin:24px 8px;font-size:15px;border:1px solid {BORDER_LIGHT};">'
        f'{"".join(html_rows)}'
        '</table>'
    )


def render_code_block(code_lines: list[str], lang: str, code_wrap_mode: str, skip_escape: bool = False) -> str:
    code = "\n".join(code_lines)
    code = normalize_code_text(code, code_wrap_mode)
    escaped = code if skip_escape else escape_text(code)
    lang = escape_text(lang or "text")
    return (
        '<section class="code-snippet__fix" '
        'style="margin:24px 0 32px;background:#1a1a2e;border-radius:12px;overflow:hidden;display:block;">'
        '<p class="code-header" style="margin:0;overflow:hidden;padding:12px 16px;background:#2b2b43;border-bottom:1px solid rgba(255,255,255,0.16);">'
        '<span class="code-dots" style="float:left;font-size:0;line-height:1;">'
        '<span class="code-dot" style="display:inline-block;font-size:14px;line-height:1;margin-right:6px;vertical-align:middle;color:#ff5f56;">●</span>'
        '<span class="code-dot" style="display:inline-block;font-size:14px;line-height:1;margin-right:6px;vertical-align:middle;color:#ffbd2e;">●</span>'
        '<span class="code-dot" style="display:inline-block;font-size:14px;line-height:1;vertical-align:middle;color:#27c93f;">●</span>'
        '</span>'
        f'<span class="code-lang" style="float:right;font-size:12px;color:#a9afc5;line-height:1.2;font-family:{UI_SANS};">{lang.lower()}</span>'
        '</p>'
        f'<pre data-lang="{lang}" style="margin:0;padding:14px 16px;font-family:Consolas,Monaco,monospace;font-size:14px;line-height:1.7;color:#e4e4e7;background:#1a1a2e;border-radius:0 0 10px 10px;display:block;white-space:pre-wrap;word-break:break-all;text-indent:0;"><code><span class="code-snippet_outer">{escaped}</span></code></pre>'
        '</section>'
    )


def render_image(line: str, image_template: str, image_mapping: dict[str, Any], image_container_mode: str) -> str | None:
    match = IMAGE_RE.match(line.strip())
    if not match:
        return None

    alt = html.escape(match.group(1), quote=True)
    url = match.group(2).strip()
    url = find_cdn_url(url, image_mapping)

    if url.startswith("<") and url.endswith(">"):
        url = url[1:-1]
    url = html.escape(url.split()[0], quote=True)

    if image_container_mode == "original":
        return image_template.replace("{{src}}", url).replace("{{alt}}", alt)

    if image_container_mode == "image-only":
        return f'<img src="{url}" alt="{alt}" style="width:100%;max-width:100%;height:auto;display:block;margin:0 auto;"/>'

    # full: container + image full width (default)
    return (
        '<section style="display:block;width:100%;margin:12px 0;line-height:0;text-align:center;">'
        f'<img src="{url}" alt="{alt}" style="width:100%;max-width:100%;height:auto;display:block;margin:0 auto;border-radius:0;"/>'
        '</section>'
    )


def render_divider(divider_policy: str, divider_html: str) -> str:
    if divider_policy == "remove":
        return ""
    if divider_policy == "line":
        return '<p style="margin:30px 0;border-top:1px solid rgba(0,0,0,0.12);height:0;line-height:0;font-size:0;text-indent:0;"> </p>'
    if divider_policy == "wechat-hr":
        return '<hr style="border-style:solid;border-width:1px 0 0;border-color:rgba(0,0,0,0.1);transform:scale(1,0.5);-webkit-transform:scale(1,0.5);"/>'
    return divider_html


def render_toc_text(sections: list[dict[str, str]]) -> str:
    lines = []
    for s in sections:
        lines.append(f"{s['num']} · {s['title']}")
    items = "<br/>".join(lines)
    return (
        f'<section class="toc" style="margin:40px 0 44px;padding:24px 0;border-bottom:1px solid {BORDER_LIGHT};">'
        f'<p style="margin:0 8px 12px;font-size:11px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:#999;font-family:{UI_SANS};">CONTENTS</p>'
        f'<p style="margin:0 8px;font-size:13px;line-height:1.8;color:#555;font-family:{BODY_SERIF};">{items}</p>'
        '</section>'
    )


def chunk_sections(sections: list[dict[str, str]], size: int) -> list[list[dict[str, str]]]:
    return [sections[i : i + size] for i in range(0, len(sections), size)]


def render_toc_fixed5_single(sections: list[dict[str, str]]) -> str:
    rows: list[str] = []
    row_chunks = chunk_sections(sections, 5)
    for row_items in row_chunks:
        cols = max(len(row_items), 1)
        width = "20" if cols >= 5 else f"{(100 / cols):.3f}"
        cells: list[str] = []
        for item in row_items:
            cells.append(
                f'<section style="float:left;vertical-align:top;width:{width}%;padding:0 6px;box-sizing:border-box;font-size:16px;line-height:1.4;">'
                f'<p style="margin:0 0 8px;border-top:2px solid {BORDER_LIGHT};height:0;line-height:0;font-size:0;"></p>'
                f'<p style="margin:0 0 6px;font-size:30px;line-height:1;font-weight:900;color:{BORDER_LIGHT};font-family:{UI_SANS};">{item["num"]}</p>'
                f'<p style="margin:0 0 2px;font-size:13px;line-height:1.25;font-weight:700;color:#1a1a1a;font-family:{UI_SANS};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{item["label"]}</p>'
                f'<p style="margin:0;font-size:11px;line-height:1.35;color:#999;font-family:{BODY_SERIF};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{item["title"]}</p>'
                '</section>'
            )
        rows.append(
            '<section style="display:block;overflow:hidden;">'
            + "".join(cells)
            +
            '</section>'
        )

    return (
        f'<section class="toc" style="margin:40px 0 44px;padding:24px 0;">'
        f'<p style="margin:0 0 18px;font-size:11px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:#999;font-family:{UI_SANS};">Contents</p>'
        '<section style="display:block;">'
        + "".join(rows)
        + '</section>'
        f'<p style="margin:22px 6px 0 6px;border-top:1px solid {BORDER_LIGHT};height:0;line-height:0;font-size:0;"> </p>'
        '</section>'
    )


def render_toc_fixed5_scroll(sections: list[dict[str, str]]) -> str:
    cards = []
    for item in sections:
        cards.append(
            '<section style="display:inline-block;vertical-align:top;width:188px;padding:0 6px;box-sizing:border-box;font-size:16px;line-height:1.4;">'
            f'<p style="margin:0 0 8px;border-top:2px solid {BORDER_LIGHT};height:0;line-height:0;font-size:0;"></p>'
            f'<p style="margin:0 0 6px;font-size:30px;line-height:1;font-weight:900;color:{BORDER_LIGHT};font-family:{UI_SANS};">{item["num"]}</p>'
            f'<p style="margin:0 0 2px;font-size:13px;line-height:1.25;font-weight:700;color:#1a1a1a;font-family:{UI_SANS};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{item["label"]}</p>'
            f'<p style="margin:0;font-size:11px;line-height:1.35;color:#999;font-family:{BODY_SERIF};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{item["title"]}</p>'
            '</section>'
        )

    return (
        f'<section class="toc" style="margin:40px 0 44px;padding:24px 0;">'
        f'<p style="margin:0 0 18px;font-size:11px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:#999;font-family:{UI_SANS};">Contents</p>'
        '<section style="display:block;overflow-x:auto;white-space:nowrap;-webkit-overflow-scrolling:touch;">'
        + "".join(cards)
        + '</section>'
        f'<p style="margin:22px 6px 0 6px;border-top:1px solid {BORDER_LIGHT};height:0;line-height:0;font-size:0;"> </p>'
        '</section>'
    )


def build_toc(sections: list[dict[str, str]], toc_mode: str) -> str:
    if not sections or toc_mode == "none":
        return ""
    if toc_mode == "text":
        return render_toc_text(sections)
    if toc_mode == "fixed5-single":
        return render_toc_fixed5_single(sections)
    # fixed5-scroll default
    if len(sections) <= 5:
        return render_toc_fixed5_single(sections)
    return render_toc_fixed5_scroll(sections)


def inject_toc(blocks: list[str], toc_html: str) -> list[str]:
    if not toc_html:
        return blocks
    # Insert after first paragraph-like intro block when possible.
    for i, block in enumerate(blocks):
        if block.startswith("<p"):
            return blocks[: i + 1] + [toc_html] + blocks[i + 1 :]
    return [toc_html] + blocks


def convert_markdown(
    md_text: str,
    config: RenderConfig,
    divider_html: str,
    image_template: str,
    image_mapping: dict[str, Any] | None = None,
) -> str:
    lines = md_text.splitlines()
    output: list[str] = []
    sections: list[dict[str, str]] = []
    layout_id = 0

    in_code = False
    code_lang = ""
    code_lines: list[str] = []

    in_table = False
    table_lines: list[str] = []

    raw_mode = False
    para_lines: list[str] = []
    list_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal para_lines, layout_id
        if para_lines:
            rendered = render_paragraph(para_lines, config.highlight_direction, layout_id)
            if rendered:
                output.append(rendered)
                layout_id += 1
            para_lines = []

    def flush_list() -> None:
        nonlocal list_lines
        if list_lines:
            rendered = render_list(list_lines, config)
            if rendered:
                output.append(rendered)
            list_lines = []

    def flush_code() -> None:
        nonlocal code_lines, code_lang
        if code_lines or code_lang:
            output.append(render_code_block(code_lines, code_lang, config.code_wrap))
            code_lines = []
            code_lang = ""

    def flush_table() -> None:
        nonlocal table_lines, in_table
        if table_lines:
            rendered = render_table(table_lines, config.highlight_direction)
            if rendered:
                output.append(rendered)
            table_lines = []
            in_table = False

    image_mapping = image_mapping or {}

    for line in lines:
        stripped = line.strip()

        if raw_mode:
            if stripped == RAW_BLOCK_END:
                raw_mode = False
                continue
            output.append(line.rstrip("\n"))
            continue

        if stripped == RAW_BLOCK_START:
            flush_paragraph()
            flush_list()
            raw_mode = True
            continue

        if in_code:
            if stripped.startswith("```"):
                in_code = False
                flush_code()
            else:
                code_lines.append(line.rstrip("\n"))
            continue

        if stripped.startswith("```"):
            flush_paragraph()
            flush_list()
            in_code = True
            code_lang = stripped[3:].strip()
            code_lines = []
            continue

        if stripped == "":
            flush_paragraph()
            flush_list()
            # 表格结束于空行
            if in_table:
                flush_table()
            continue

        # 检测表格行（以 | 开头和结尾）
        if TABLE_ROW_RE.match(stripped):
            flush_paragraph()
            flush_list()
            in_table = True
            table_lines.append(stripped)
            continue

        # 如果在表格中但当前行不是表格行，结束表格
        if in_table:
            flush_table()

        if HR_RE.match(stripped):
            flush_paragraph()
            flush_list()
            divider = render_divider(config.divider_policy, divider_html)
            if divider:
                output.append(divider)
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            flush_list()
            quote_text = stripped[1:].strip()
            rendered = render_blockquote([quote_text], config.highlight_direction)
            if rendered:
                output.append(rendered)
            continue

        if stripped.startswith("<"):
            flush_paragraph()
            flush_list()
            output.append(line.rstrip("\n"))
            continue

        heading_match = HEADING_RE.match(line)
        if heading_match:
            flush_paragraph()
            flush_list()
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()

            # 跳过 h1 标题（微信有独立的标题字段）
            if level == 1:
                continue

            # 检查中文章节标题格式："第X部分：标题"
            chinese_match = CHINESE_SECTION_RE.match(title)
            if chinese_match and level == 2:
                section_number = chinese_to_arabic(chinese_match.group(1))
                section_title = chinese_match.group(2).strip()
                # 简洁章节标题不需要标签映射
                sections.append({
                    "num": section_number,
                    "label": f"Section {section_number}",
                    "title": section_title,
                    "id": f"section-{section_number}",
                })
                output.append(render_section_header(section_number, section_title, config))
                continue

            # 检查数字章节标题格式："01 标题"
            section_match = SECTION_RE.match(title)
            if section_match and level == 2:
                section_number = section_match.group(1)
                section_title = section_match.group(2).strip()
                # 简洁章节标题不需要标签映射
                sections.append({
                    "num": section_number,
                    "label": f"Section {section_number}",
                    "title": section_title,
                    "id": f"section-{section_number}",
                })
                output.append(render_section_header(section_number, section_title, config))
            else:
                output.append(render_heading(level, title, config.highlight_direction))
            continue

        image_html = render_image(line, image_template, image_mapping, config.image_container)
        if image_html:
            flush_paragraph()
            flush_list()
            output.append(image_html)
            continue

        if LIST_ITEM_RE.match(line):
            flush_paragraph()
            list_lines.append(line.strip())
            continue

        if list_lines:
            flush_list()
        para_lines.append(line)

    flush_paragraph()
    flush_list()
    if in_code:
        flush_code()
    if in_table:
        flush_table()

    toc_html = build_toc(sections, config.toc_mode)
    output = inject_toc(output, toc_html)

    # 添加顶部和底部文案
    top_banner = render_top_banner(config.account_type)
    bottom_banner = render_bottom_banner(config.account_type)

    result = top_banner + "\n" + "\n".join(output).strip() + "\n" + bottom_banner + "\n"
    return result


def insert_images_auto(html_content: str, image_mapping: dict[str, Any]) -> str:
    """Auto insert mapped images after section headings (workflow helper)."""
    if not image_mapping:
        return html_content

    url_lookup: dict[str, str] = {}
    for key in ["poster_urls", "cover_urls"]:
        node = image_mapping.get(key)
        if isinstance(node, dict):
            url_lookup.update(node)

    flat = image_mapping.get("image_mapping_flat")
    if isinstance(flat, dict):
        url_lookup.update(flat)

    if not url_lookup:
        for k, v in image_mapping.items():
            if isinstance(v, str) and v.startswith("http"):
                url_lookup[k] = v

    if not url_lookup:
        return html_content

    section_images = [
        ("02 AI，如何破解这个困局？", "poster_01"),
        ("03 技术，已经准备好了", "poster_02"),
        ("04 AI不是医生的敌人，而是超级助理", "poster_03"),
    ]

    img_template = (
        '<section style="display:block;width:100%;margin:12px 0;line-height:0;text-align:center;">'
        '<img src="{}" alt="文章配图" style="width:100%;max-width:100%;display:block;margin:0 auto;"/>'
        '</section>'
    )

    output_lines = []
    lines = html_content.split("\n")

    for line in lines:
        output_lines.append(line)
        for section_title, image_keyword in section_images:
            patterns = [
                f">{section_title}</section>",
                f">{section_title}</h2>",
                f">{section_title}</h3>",
                f">{section_title}</h4>",
            ]
            if any(pattern in line for pattern in patterns):
                image_url = next((u for fn, u in url_lookup.items() if image_keyword in fn), None)
                if image_url:
                    output_lines.append(img_template.format(image_url))
                break

    return "\n".join(output_lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert Markdown to WeChat-editor-stable HTML.")
    parser.add_argument("input", help="Path to the Markdown file")
    parser.add_argument("-o", "--output", help="Output HTML file (defaults to stdout)")

    parser.add_argument("--target", choices=["wechat"], default="wechat", help="Render target (default: wechat)")
    parser.add_argument(
        "--content-mode",
        choices=["default", "article"],
        default="default",
        help="Preset bundle for content rendering. article = wechat article friendly defaults",
    )
    parser.add_argument("--list-style", choices=["code", "html"], default="code", help="Render lists as code blocks or HTML lists")
    parser.add_argument(
        "--toc-mode",
        choices=["fixed5-single", "fixed5-scroll", "text", "none"],
        default="none",
        help="TOC strategy: fixed 5 columns, scroll mode, text mode, or none",
    )
    parser.add_argument(
        "--divider-policy",
        choices=["remove", "line", "decorative", "wechat-hr"],
        default="wechat-hr",
        help="How to render Markdown horizontal rules",
    )
    parser.add_argument(
        "--image-container",
        choices=["full", "image-only", "original"],
        default="full",
        help="Image wrapper strategy (full = container+image 100%%)",
    )
    parser.add_argument(
        "--code-wrap",
        choices=["none", "smart-url"],
        default="smart-url",
        help="Code text normalization mode",
    )
    parser.add_argument(
        "--highlight-direction",
        choices=["ltr", "ttb"],
        default="ltr",
        help="Gradient direction: left-to-right or top-to-bottom",
    )
    parser.add_argument(
        "--account-type",
        choices=["wise", "human"],
        default="wise",
        help="Account type for top/bottom banner text: wise or human",
    )
    parser.add_argument(
        "--divider-template",
        default=str(Path(__file__).resolve().parent.parent / "assets" / "divider.html"),
        help="Path to divider HTML template (used when --divider-policy=decorative)",
    )
    parser.add_argument(
        "--image-template",
        default=str(Path(__file__).resolve().parent.parent / "assets" / "image_template.html"),
        help="Path to image HTML template (used when --image-container=original)",
    )
    parser.add_argument("--image-mapping", help="Path to JSON file mapping local paths to CDN URLs")
    parser.add_argument(
        "--auto-insert-images",
        action="store_true",
        help="Automatically insert images after specific section headings using --image-mapping",
    )
    parser.add_argument(
        "--page-shell",
        choices=["none", "preview"],
        default="preview",
        help="Page shell: preview with toolbar, or none for pure content",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.content_mode == "article":
        if args.list_style == "code":
            args.list_style = "html"
        if args.toc_mode == "none":
            args.toc_mode = "none"
        if args.divider_policy == "wechat-hr":
            args.divider_policy = "wechat-hr"
        if args.image_container == "full":
            args.image_container = "full"
        if args.page_shell == "preview":
            args.page_shell = "none"

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    divider_html = load_template(Path(args.divider_template))
    image_template = load_template(Path(args.image_template))

    image_mapping: dict[str, Any] = {}
    if args.image_mapping:
        mapping_path = Path(args.image_mapping)
        if mapping_path.exists():
            image_mapping = json.loads(mapping_path.read_text(encoding="utf-8"))

    config = RenderConfig(
        list_style=args.list_style,
        divider_policy=args.divider_policy,
        image_container=args.image_container,
        toc_mode=args.toc_mode,
        code_wrap=args.code_wrap,
        highlight_direction=args.highlight_direction,
        account_type=args.account_type,
        content_mode=args.content_mode,
    )

    md_text = input_path.read_text(encoding="utf-8")
    md_text = strip_frontmatter(md_text)
    md_text = clean_metadata(md_text)
    html_text = convert_markdown(md_text, config, divider_html, image_template, image_mapping)

    if args.auto_insert_images and image_mapping:
        html_text = insert_images_auto(html_text, image_mapping)

    # Wrap with page shell if requested
    if args.page_shell == "preview":
        shell_path = Path(__file__).resolve().parent.parent / "assets" / "preview_shell.html"
        if shell_path.exists():
            shell_html = shell_path.read_text(encoding="utf-8")
            html_text = shell_html.replace("{{CONTENT}}", html_text)

    if args.output:
        Path(args.output).write_text(html_text, encoding="utf-8")
    else:
        sys.stdout.write(html_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
