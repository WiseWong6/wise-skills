#!/usr/bin/env python3
"""
Swiss Editorial HTML Converter
将 Markdown 转换为 600x800px 杂志风信息卡片
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional
import markdown
from markdown.extensions import codehilite, fenced_code


# ============ 配色方案 ============
SCHEME_COVER = {
    'bg': '#f2efe9',
    'text': '#1a1a1a',
    'accent': '#d95e00',
}

SCHEME_BODY = {
    'bg': '#ffffff',
    'text': '#1a1a1a',
    'accent': '#d95e00',
}


# ============ CSS 样式 ============
def create_card(content: str, card_type: str = 'body') -> str:
    """创建单张卡片"""
    scheme_class = 'swiss-card--cover' if card_type == 'cover' else 'swiss-card--body'

    card_css = """<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;700&family=Noto+Sans+SC:wght@300;400;700&display=swap');

* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

.swiss-card {{
    width: 600px;
    height: 800px;
    border-radius: 0 !important;
    overflow: hidden;
    position: relative;
    font-family: 'Noto Sans SC', 'Noto Serif SC', -apple-system, sans-serif;
    background: {bg};
    color: {text};
}}

.swiss-card--cover {{
    background: {cover_bg};
}}

.swiss-card--body {{
    background: {body_bg};
}}

/* 标题层级 */
.swiss-card h1 {{
    font-family: 'Noto Serif SC', serif;
    font-size: 48px;
    font-weight: 700;
    line-height: 1.2;
    letter-spacing: -0.02em;
    margin-bottom: 24px;
}}

.swiss-card h2 {{
    font-family: 'Noto Serif SC', serif;
    font-size: 32px;
    font-weight: 700;
    line-height: 1.3;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 3px solid {accent};
}}

.swiss-card h3 {{
    font-size: 22px;
    font-weight: 700;
    line-height: 1.4;
    margin-bottom: 16px;
    color: {accent};
}}

/* 正文段落 */
.swiss-card p {{
    font-size: 16px;
    font-weight: 300;
    line-height: 2.0;
    margin-bottom: 20px;
    text-align: justify;
}}

/* 加粗 */
.swiss-card strong {{
    font-weight: 700;
    color: {accent};
}}

/* 强调/斜体 */
.swiss-card em {{
    font-style: italic;
    color: {accent};
    font-weight: 400;
}}

/* 引用块 */
.swiss-card blockquote {{
    margin: 24px 0;
    padding: 20px 24px;
    border-left: 4px solid {accent};
    background: rgba(217, 94, 0, 0.05);
    font-style: italic;
    font-size: 15px;
    line-height: 1.8;
}}

.swiss-card blockquote p {{
    margin-bottom: 0;
    text-align: left;
}}

/* 代码块 */
.swiss-card pre {{
    background: #1a1a1a;
    color: #f2efe9;
    padding: 20px;
    margin: 20px 0;
    font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
    font-size: 13px;
    line-height: 1.6;
    overflow-x: auto;
    white-space: pre-wrap;
    border-radius: 0 !important;
}}

.swiss-card code {{
    font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
    font-size: 0.9em;
    background: rgba(26, 26, 26, 0.08);
    padding: 2px 6px;
    border-radius: 0 !important;
}}

.swiss-card pre code {{
    background: none;
    padding: 0;
}}

/* 行内代码 */
.swiss-card p code {{
    background: rgba(217, 94, 0, 0.1);
    color: {accent};
    padding: 2px 8px;
    font-size: 14px;
}}

/* 链接 */
.swiss-card a {{
    color: {accent};
    text-decoration: none;
    border-bottom: 1px solid {accent};
    transition: opacity 0.2s;
}}

.swiss-card a:hover {{
    opacity: 0.7;
}}

/* 列表 */
.swiss-card ul, .swiss-card ol {{
    margin: 20px 0;
    padding-left: 28px;
}}

.swiss-card li {{
    font-size: 16px;
    font-weight: 300;
    line-height: 2.0;
    margin-bottom: 8px;
}}

.swiss-card ul li::marker {{
    color: {accent};
}}

/* 分割线 */
.swiss-card hr {{
    border: none;
    height: 2px;
    background: {accent};
    margin: 32px 0;
    width: 60px;
    margin-left: 0;
}}

/* 图片 */
.swiss-card img {{
    max-width: 100%;
    height: auto;
    display: block;
    margin: 20px auto;
}}

/* 表格 */
.swiss-card table {{
    width: 100%;
    border-collapse: collapse;
    margin: 24px 0;
    font-size: 14px;
}}

.swiss-card th, .swiss-card td {{
    padding: 12px 16px;
    text-align: left;
    border-bottom: 1px solid rgba(26, 26, 26, 0.1);
}}

.swiss-card th {{
    font-weight: 700;
    color: {accent};
    background: rgba(217, 94, 0, 0.05);
}}

/* 封面特殊样式 */
.swiss-card--cover .cover-title {{
    font-family: 'Noto Serif SC', serif;
    font-size: 56px;
    font-weight: 700;
    line-height: 1.1;
    margin-bottom: 32px;
}}

.swiss-card--cover .cover-meta {{
    font-size: 14px;
    font-weight: 300;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: {accent};
    margin-top: auto;
}}

/* 卡片内容区域 */
.swiss-card__content {{
    padding: 40px;
    height: 100%;
    display: flex;
    flex-direction: column;
}}

/* 封面布局 */
.swiss-card--cover .swiss-card__content {{
    justify-content: center;
    padding: 60px;
}}
</style>""".format(
        bg=SCHEME_BODY['bg'],
        text=SCHEME_BODY['text'],
        accent=SCHEME_BODY['accent'],
        cover_bg=SCHEME_COVER['bg'],
        body_bg=SCHEME_BODY['bg'],
    )

    return f'''{card_css}
<div class="swiss-card {scheme_class}">
    <div class="swiss-card__content">
{content}
    </div>
</div>'''


def parse_cover_and_body(md_content: str) -> tuple:
    """解析封面和正文内容"""
    # 默认：第一张 --- 之前的内容为封面，之后的为正文
    parts = md_content.split('\n---\n', 1)

    if len(parts) == 2:
        cover_md = parts[0].strip()
        body_md = parts[1].strip()
    else:
        # 没有明确分隔，整个作为正文
        cover_md = ''
        body_md = md_content.strip()

    return cover_md, body_md


def md_to_html(md: str) -> str:
    """Markdown 转 HTML（简化版）"""
    # 基础 markdown 转换
    md_parser = markdown.Markdown(
        extensions=[
            'codehilite',
            'fenced_code',
            'tables',
        ]
    )

    # 自定义预处理
    html = md

    # 处理加粗 **text**
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)

    # 处理强调 *text*
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)

    # 处理行内代码 `code`
    html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)

    # 处理标题
    for level in range(6, 0, -1):
        prefix = '#' * level
        html = re.sub(
            rf'^{prefix}\s+(.+)$',
            rf'<h{level}>\1</h{level}>',
            html,
            flags=re.MULTILINE
        )

    # 处理链接
    html = re.sub(
        r'\[([^\]]+)\]\(([^\)]+)\)',
        r'<a href="\2">\1</a>',
        html
    )

    # 处理分割线
    html = re.sub(r'^---+$', '<hr>', html, flags=re.MULTILINE)

    # 处理列表
    html = re.sub(
        r'^\s*[-*]\s+(.+)$',
        r'<li>\1</li>',
        html,
        flags=re.MULTILINE
    )

    # 包裹连续的 <li> 为 <ul>
    html = re.sub(r'(<li>.*?</li>\n?)+', r'<ul>\g<0></ul>', html)

    # 处理数字列表
    html = re.sub(
        r'^\s*(\d+)\.\s+(.+)$',
        r'<li>\2</li>',
        html,
        flags=re.MULTILINE
    )

    # 处理引用块
    html = re.sub(
        r'^>\s*(.+)$',
        r'<blockquote>\1</blockquote>',
        html,
        flags=re.MULTILINE
    )

    # 包裹连续的 blockquote
    html = re.sub(r'(<blockquote>.*?</blockquote>\n?)+', r'<blockquote>\g<0></blockquote>', html)

    # 处理代码块
    html = re.sub(
        r'```(\w*)\n(.*?)```',
        r'<pre><code class="language-\1">\2</code></pre>',
        html,
        flags=re.DOTALL
    )

    # 处理图片
    html = re.sub(
        r'!\[([^\]]*)\]\(([^\)]+)\)',
        r'<img src="\2" alt="\1">',
        html
    )

    # 处理段落
    html = re.sub(r'\n\n+', '\n\n', html)
    paragraphs = []
    for block in html.split('\n\n'):
        block = block.strip()
        if not block:
            continue
        # 跳过已经是块级标签的
        if re.match(r'^(<h[1-6]|<pre|<ul|<ol|<blockquote|<hr|<img|<div)', block):
            paragraphs.append(block)
        else:
            paragraphs.append(f'<p>{block}</p>')

    return '\n\n'.join(paragraphs)


def convert_md_to_swiss_cards(md_content: str, num_cards: int = 1) -> List[str]:
    """将 Markdown 转换为多张卡片"""
    cards = []

    cover_md, body_md = parse_cover_and_body(md_content)

    # 如果有封面，创建封面卡片
    if cover_md:
        cover_html = md_to_html(cover_md)
        # 封面特殊处理：标题不加 p 标签
        cover_html = re.sub(r'<p>(<h1.*?</h1>)</p>', r'\1', cover_html)
        cards.append(create_card(cover_html, 'cover'))

    # 拆分正文为多张卡片（按分割线或固定长度）
    if body_md:
        # 按 --- 分割成多个 section
        sections = body_md.split('\n---\n')

        for i, section in enumerate(sections):
            if not section.strip():
                continue

            section_html = md_to_html(section.strip())

            # 如果只有一张卡，直接返回
            if len(sections) == 1 and not cover_md:
                cards.append(create_card(section_html, 'body'))
            else:
                cards.append(create_card(section_html, 'body'))

    # 如果没有封面也没有正文，创建默认封面
    if not cards:
        cards.append(create_card('<h1>Untitled</h1>', 'cover'))

    return cards


def main():
    parser = argparse.ArgumentParser(description='Swiss Editorial HTML Converter')
    parser.add_argument('input', help='输入 Markdown 文件')
    parser.add_argument('-o', '--output', help='输出 HTML 文件')
    parser.add_argument('-n', '--num-cards', type=int, default=1,
                        help='输出的卡片数量（按 --- 分割）')

    args = parser.parse_args()

    # 读取输入
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误：文件 {args.input} 不存在", file=sys.stderr)
        sys.exit(1)

    md_content = input_path.read_text(encoding='utf-8')

    # 转换
    cards = convert_md_to_swiss_cards(md_content, args.num_cards)

    # 输出
    output_html = '\n\n'.join(cards)

    if args.output:
        Path(args.output).write_text(output_html, encoding='utf-8')
        print(f"已生成: {args.output}")
    else:
        print(output_html)


if __name__ == '__main__':
    main()
