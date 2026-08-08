#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""纸墨线稿 · 单页机检（checklist P0 中可机检部分的闸门）

用法：
    python3 themes/paper-ink/scripts/lint.py <deck目录 | 单个HTML> [--strict] [--accent]
    --accent  保留给强调色截图流程；静态源码始终允许主题登记的强调色 token

检查项（对应 references/visual-checklist.md P0）：
    L1 彩色：除墨色阶梯/纸底/柔白外的 hex、rgb(a)、命名色
    L2 渐变/阴影/滤镜：linear-gradient、box-shadow（允许标本偏移影豁免值）、filter:
    L3 粗线：stroke-width ≥ 2 超过 1 处
    L4 中文落 mono：txt(...) 调用中 font-family MONO 且字符串含 CJK
    L5 三件套：.doc tl 角注、.folio、.caption（尾卡页 caption 仅 WARN）
    L6 不做“同尺寸矩形即违规”的静态猜测；Grid/证据墙/矩阵由 manifest 关系与浏览器目检判断
    L7 Gallery 样页未调用 stageFit()，或 single-html 未声明统一 runtime
    L8 禁用填充：纯白 #fff / #ffffff 作为 fill
    L9 深色页面底色：.stage / body 背景亮度 < 50%（skill 拒绝暗色系，全部纸底纯色）

退出码：有 FAIL 则 1（--strict 时 WARN 也为 1），否则 0。
注意：静态检查有边界——循环里用变量画的 rect/线无法计数，机检全过 ≠ 目检通过，
     仍须按 visual-checklist 在真实浏览器中人工验收。
"""
import os
import re
import sys

INK_OK = {
    '#191917', '#dfe0d9', '#d4d5cd', '#d6d7d0', # 墨 / 纸底 / 画册底 / 纸底深档
    '#edf0ee', '#181c1e', '#1d5c9e',          # ?cool 主题（蓝图青仅 cool 允许）
}
ACCENT_OK = {
    '#c0392b', '#002fa7',                     # ?accent 强调色：番茄红 / 克莱因蓝
}
NAMED_OK = {'none', 'currentcolor', 'inherit', 'transparent'}
CJK = re.compile(r'[一-鿿　-〿＀-￯]')
ACCENT_MODE = False                           # 保留 CLI 契约；强调色是否实际启用由浏览器模式验证

def lint_file(path):
    fails, warns = [], []
    src = open(path, encoding='utf-8').read()

    # L1 彩色 hex
    for m in re.finditer(r'#[0-9a-fA-F]{6}\b', src):
        hx = m.group(0).lower()
        # 静态源码会同时包含默认态与 :root.accent 规则，因此只校验颜色是否属于主题色板；
        # 强调色有没有错误出现在默认态，交给两种模式的真实截图比较。
        if hx not in INK_OK and hx not in ACCENT_OK:
            line = src[:m.start()].count('\n') + 1
            fails.append(f'L1 彩色 hex {hx} (line {line})')
    for m in re.finditer(r'#[0-9a-fA-F]{3}\b', src):
        hx = m.group(0).lower()
        if hx not in {'#fff'} and not re.match(r'#[0-9a-fA-F]{6}', src[m.start():m.start()+7]):
            line = src[:m.start()].count('\n') + 1
            warns.append(f'L1 短 hex {hx} (line {line})')
    # L1 rgb(a) 非墨非柔白
    for m in re.finditer(r'rgba?\(([^)]+)\)', src):
        parts = [p.strip() for p in m.group(1).split(',')]
        try:
            r, g, b = (float(parts[0]), float(parts[1]), float(parts[2]))
        except (ValueError, IndexError):
            continue
        is_ink = (abs(r - 25) < 2 and abs(g - 25) < 2 and abs(b - 23) < 2)
        is_softwhite = (r == 255 and g == 255 and b == 255)
        is_paper = (abs(r - 223) < 2 and abs(g - 224) < 2 and abs(b - 217) < 2) or \
                   (abs(r - 212) < 2 and abs(g - 213) < 2 and abs(b - 205) < 2)   # 纸色擦除/刻字
        is_cool = (abs(r - 29) < 2 and abs(g - 92) < 2 and abs(b - 158) < 2)
        is_accent = (
            (abs(r - 192) < 3 and abs(g - 57) < 3 and abs(b - 43) < 3) or   # 番茄红 #C0392B
            (abs(r) < 3 and abs(g - 47) < 3 and abs(b - 167) < 3)           # 克莱因蓝 #002FA7
        )
        if not (is_ink or is_softwhite or is_paper or is_cool or is_accent):
            line = src[:m.start()].count('\n') + 1
            fails.append(f'L1 彩色 rgba({m.group(1)}) (line {line})')
    # L1 命名色（stroke/fill/color 语境）
    for m in re.finditer(r"(?:stroke|fill|color)\s*[:=]\s*['\"]\s*([a-z]+)\s*['\"]", src):
        name = m.group(1).lower()
        if name not in NAMED_OK and name not in ('url',):
            line = src[:m.start()].count('\n') + 1
            warns.append(f'L1 命名色 {name} (line {line})')

    # L2 渐变/阴影/滤镜（硬停双拼填充不算渐变：如 50% 半填墨点）
    for pat, label in [(r'(?<!-)filter\s*:', 'filter')]:
        for m in re.finditer(pat, src):
            line = src[:m.start()].count('\n') + 1
            fails.append(f'L2 {label} (line {line})')
    for m in re.finditer(r'(?:linear|radial)-gradient\(([^;]*)\)', src):
        stops = m.group(1)
        if '50%' in stops and ('var(--ink)' in stops or '#191917' in stops) and 'transparent' in stops:
            continue  # 三态墨点半填技法（封面/图例可用）
        line = src[:m.start()].count('\n') + 1
        fails.append(f'L2 渐变 (line {line})')
    for m in re.finditer(r'box-shadow\s*:\s*([^;]+)', src):
        shadow = m.group(1).replace(' ', '')
        if not (
            shadow in {'var(--shadow-soft)', 'var(--shadow-specimen)'} or
            'rgba(25,25,23,.04)' in shadow or
            ('color-mix(' in shadow and 'var(--ink)' in shadow)
        ):
            line = src[:m.start()].count('\n') + 1
            fails.append(f'L2 box-shadow {m.group(1).strip()[:40]} (line {line})')

    # L3 粗线 ≥2px 多于一处（短 path 的 ✓/✗/手写符号笔触豁免）
    thick = 0
    for m in re.finditer(r"el\(\s*'(path|line|rect|circle)'\s*,\s*\{(.*?)\}\s*\)", src, re.S):
        body = m.group(2)
        wm = re.search(r"stroke-width['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)", body)
        if not wm or float(wm.group(1)) < 2:
            continue
        dm = re.search(r"\bd\s*:\s*'([^']*)'", body)
        if m.group(1) == 'path' and dm and len(dm.group(1)) < 100:
            continue  # 符号笔触
        thick += 1
    if thick > 1:
        fails.append(f'L3 粗线(≥2px) {thick} 处，允许 ≤1（短 path 符号笔触已豁免）')

    # L4 中文落 mono：同一 txt() 调用里 MONO + CJK（WARN：mono EN+中文短注混排可接受，长句/大字禁用）
    for m in re.finditer(r"txt\((.*?)\)", src, re.S):
        call = m.group(1)
        if 'MONO' in call and CJK.search(call):
            line = src[:m.start()].count('\n') + 1
            snippet = re.sub(r'\s+', ' ', call)[:60]
            warns.append(f'L4 mono 内含中文（确认 fallback 灰度可接受）：txt({snippet}…) (line {line})')

    # L5 三件套
    if not re.search(r'class="doc\b[^"]*\btl\b|class="doc tl"', src):
        fails.append('L5 缺 .doc.tl 角注')
    if 'class="folio"' not in src:
        fails.append('L5 缺 .folio 页脚')
    if not re.search(r'class="[^"]*\bcaption\b', src):
        warns.append('L5 无 .caption（尾卡/封面/Outro 可豁免）')

    # L6：不从几何重复推断语义错误。同尺寸 rect 可能是合法的矩阵、证据墙、
    # 表格或同行比较；关系正确性由 render plan、manifest capacity 与截图目检负责。

    # L7 stageFit（或等价的本地 fit()：min(vw/1920, vh/1080) 缩放）
    if 'stageFit(' not in src and 'innerWidth/1920' not in src and 'data-document-mode="single-html"' not in src:
        fails.append('L7 未调用 stageFit() 或等价缩放')

    # L8 纯白填充
    for m in re.finditer(r"fill\s*[:=]\s*['\"]#(fff|ffffff)['\"]", src, re.I):
        line = src[:m.start()].count('\n') + 1
        fails.append(f'L8 纯白填充（应使用 rgba(255,255,255,.22)）(line {line})')

    # L9 深色页面底色（skill 拒绝暗色系：全部纸底纯色，墨只做线条与文字）
    def lum_of(token):
        token = token.strip().lower().replace(' ', '')
        hm = re.match(r'#([0-9a-f]{6})', token)
        if hm:
            h = hm.group(1)
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        else:
            rm = re.match(r'rgba?\(([^)]+)\)', token)
            if not rm:
                return None
            try:
                r, g, b = (float(p) for p in rm.group(1).split(',')[:3])
            except ValueError:
                return None
        return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    for m in re.finditer(r'\.(stage|swiss-card)\s*\{([^}]*)\}|body\s*\{([^}]*)\}', src):
        rule = m.group(2) or m.group(3) or ''
        bm = re.search(r'background(?:-color)?\s*:\s*([^;}]+)', rule)
        if not bm or 'var(' in bm.group(1):
            continue
        lum = lum_of(bm.group(1))
        if lum is not None and lum < 0.5:
            line = src[:m.start()].count('\n') + 1
            fails.append(f'L9 深色页面底色 {bm.group(1).strip()[:24]} (line {line})：拒绝暗色系，必须纸底')

    return fails, warns

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    target = sys.argv[1]
    strict = '--strict' in sys.argv
    global ACCENT_MODE
    ACCENT_MODE = '--accent' in sys.argv
    if os.path.isdir(target):
        frames = os.path.join(target, 'frames')
        files = sorted(
            os.path.join(frames, f) for f in os.listdir(frames)
            if re.fullmatch(r'layout-[a-z0-9]+\.html', f)  # Gallery 样页；跳过 -lab / -bak 等实验稿
        ) if os.path.isdir(frames) else []
        if not files and os.path.isfile(os.path.join(target, 'index.html')):
            files = [os.path.join(target, 'index.html')]
    else:
        files = [target]
    if not files:
        print('没有找到 index.html 或 Gallery layout-*.html')
        sys.exit(2)

    total_fail = total_warn = 0
    for f in files:
        fails, warns = lint_file(f)
        total_fail += len(fails)
        total_warn += len(warns)
        name = os.path.basename(f)
        if not fails and not warns:
            print(f'PASS  {name}')
            continue
        for x in fails:
            print(f'FAIL  {name}  {x}')
        for x in warns:
            print(f'WARN  {name}  {x}')
    print(f'\n{len(files)} 页：{total_fail} FAIL / {total_warn} WARN')
    if total_fail or (strict and total_warn):
        sys.exit(1)
    print('机检通过（仍须真实浏览器人工验收）')

if __name__ == '__main__':
    main()
