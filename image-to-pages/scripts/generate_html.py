#!/usr/bin/env python3
"""
图片布局打印机 - HTML 生成器（图片以 base64 嵌入）
将图片拼接成 3:4 白色容器，生成可直接双击打开的独立 HTML
"""

import base64
import re
import struct
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple, Union


MIME_MAP = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
}

SUPPORTED_EXTS = set(MIME_MAP.keys())

# 3:4 比例的容差（±8%）
TARGET_RATIO = 4 / 3  # 高/宽
RATIO_TOLERANCE = 0.08

# macOS 常见 Chromium 内核浏览器路径（按优先级排序）
CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Arc.app/Contents/MacOS/Arc",
]


def natural_sort_key(path: Path) -> list:
    """自然排序键：把数字作为数值比较，避免 1,10,2 的问题"""
    return [int(s) if s.isdigit() else s.lower()
            for s in re.split(r'(\d+)', path.name)]


def get_image_size(img_path: Path) -> Tuple[Optional[int], Optional[int]]:
    """纯Python读取图片宽高，不依赖PIL"""
    try:
        with open(img_path, 'rb') as f:
            header = f.read(32)

        # PNG
        if header[:8] == b'\x89PNG\r\n\x1a\n':
            w, h = struct.unpack('>II', header[16:24])
            return w, h

        # GIF（GIF87a / GIF89a）：宽高为紧跟头部的小端 uint16
        if header[:6] in (b'GIF87a', b'GIF89a'):
            w, h = struct.unpack('<HH', header[6:10])
            return w, h

        # WebP（RIFF....WEBP），三种子格式尺寸位置不同
        if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
            fmt = header[12:16]
            if fmt == b'VP8 ':  # 有损：14-bit 宽/高，小端，位于帧头
                w = struct.unpack('<H', header[26:28])[0] & 0x3fff
                h = struct.unpack('<H', header[28:30])[0] & 0x3fff
                return w, h
            if fmt == b'VP8L':  # 无损：宽/高各 14-bit，紧凑打包
                b1, b2, b3, b4 = header[21], header[22], header[23], header[24]
                w = ((b2 & 0x3f) << 8 | b1) + 1
                h = ((b4 & 0x0f) << 10 | b3 << 2 | (b2 & 0xc0) >> 6) + 1
                return w, h
            if fmt == b'VP8X':  # 扩展：宽/高各 24-bit 减一，小端
                w = (header[24] | header[25] << 8 | header[26] << 16) + 1
                h = (header[27] | header[28] << 8 | header[29] << 16) + 1
                return w, h

        # JPEG
        if header[:2] == b'\xff\xd8':
            with open(img_path, 'rb') as f:
                f.read(2)
                while True:
                    byte = f.read(1)
                    while byte == b'\xff':
                        byte = f.read(1)
                    if not byte:
                        break
                    # SOF0 (baseline) or SOF2 (progressive)
                    if byte in (b'\xc0', b'\xc2'):
                        f.read(3)  # length + precision
                        h, w = struct.unpack('>HH', f.read(4))
                        return w, h
                    elif byte == b'\xd9':  # EOI
                        break
                    elif byte in (b'\xd0', b'\xd1', b'\xd2', b'\xd3',
                                  b'\xd4', b'\xd5', b'\xd6', b'\xd7',
                                  b'\x01', b'\x00'):
                        continue
                    else:
                        length_bytes = f.read(2)
                        if len(length_bytes) < 2:
                            break
                        length = struct.unpack('>H', length_bytes)[0]
                        if length >= 2:
                            f.read(length - 2)
    except Exception:
        pass
    return None, None


def get_images_from_folder(folder_path: Union[str, Path]) -> List[Path]:
    """从文件夹获取所有图片，按自然排序"""
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"文件夹不存在: {folder}")

    images = [f for f in folder.iterdir()
              if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS]

    return sorted(images, key=natural_sort_key)


def image_to_base64(img_path: Path) -> str:
    """将图片转为 base64 data URI"""
    with open(img_path, 'rb') as f:
        data = f.read()

    mime = MIME_MAP.get(img_path.suffix.lower(), 'image/jpeg')
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def generate_html(image_paths: List[Path], output_path: Path, title: str = "图片展示",
                  mode: str = "auto", orientation_key: str = "portrait_34"):
    """生成图片以 base64 嵌入的独立 HTML 文件

    mode:
        auto - 任意比例图片，每容器最多放2张（各占50%高度），自动拼成3:4容器
        full - 每张图本身是3:4比例，每张图独占一个完整容器，直接拼接展示
    orientation_key: ORIENTATION_PRESETS 的 key，决定页面方向（横/竖）与比例。
        横版时每张图独占一个横版页面（一页一张）。
    """
    page_size, aspect_ratio, _orient_label = ORIENTATION_PRESETS[orientation_key]
    is_landscape = orientation_key.startswith('landscape')
    # page_size 形如 "267mm 150mm"（宽 高）；取高度分量用于打印时固定页高，
    # 避免用 aspect-ratio 反推高度时因 mm 取整产生亚像素溢出（每页拖出空白尾页）
    page_h = page_size.split()[1]

    # 收集图片元数据
    image_meta = []
    for img in image_paths:
        w, h = get_image_size(img)
        ratio = h / w if w and h else None
        image_meta.append({
            'path': img,
            'width': w,
            'height': h,
            'ratio': ratio,
            'is_34': ratio and abs(ratio - TARGET_RATIO) / TARGET_RATIO <= RATIO_TOLERANCE,
        })

    if is_landscape:
        # 横版：每张图独占一个横版页面，object-fit: contain 不裁切
        num_pages = len(image_paths)
        pages_html = []
        for page_idx, meta in enumerate(image_meta):
            b64 = image_to_base64(meta['path'])
            size_kb = len(b64) // 1024
            ratio_str = f"{meta['ratio']:.3f}" if meta['ratio'] else "未知"
            print(f"  ✅ {meta['path'].name} ({size_kb}KB) 比例={ratio_str}")
            page_html = f'''        <div class="page landscape" id="page-{page_idx + 1}">
            <img src="{b64}" alt="图片 {page_idx + 1:02d}">
        </div>'''
            pages_html.append(page_html)
    elif mode == "full":
        num_pages = len(image_paths)
        pages_html = []
        for page_idx, meta in enumerate(image_meta):
            img = meta['path']
            b64 = image_to_base64(img)
            size_kb = len(b64) // 1024

            ratio_str = f"{meta['ratio']:.3f}" if meta['ratio'] else "未知"
            fit_mode = "contain" if meta.get('is_34') else "cover"
            fit_note = "✓" if meta.get('is_34') else "⚠ cover裁剪"

            print(f"  ✅ {img.name} ({size_kb}KB) 比例={ratio_str} {fit_note}")

            page_html = f'''        <div class="page full" id="page-{page_idx + 1}">
            <img src="{b64}" alt="图片 {page_idx + 1:02d}" style="object-fit: {fit_mode};">
        </div>'''
            pages_html.append(page_html)
    else:
        # 模式1（默认）：每容器最多放2张，每张50%高度
        num_pages = (len(image_paths) + 1) // 2
        pages_html = []
        for page_idx in range(num_pages):
            img_idx = page_idx * 2
            meta1 = image_meta[img_idx]
            img1 = meta1['path']
            b64_1 = image_to_base64(img1)
            size_kb = len(b64_1) // 1024

            ratio_str = f"{meta1['ratio']:.3f}" if meta1['ratio'] else "未知"
            print(f"  ✅ {img1.name} ({size_kb}KB) 比例={ratio_str}")

            if img_idx + 1 < len(image_paths):
                meta2 = image_meta[img_idx + 1]
                img2 = meta2['path']
                b64_2 = image_to_base64(img2)
                size_kb = len(b64_2) // 1024

                ratio_str = f"{meta2['ratio']:.3f}" if meta2['ratio'] else "未知"
                print(f"  ✅ {img2.name} ({size_kb}KB) 比例={ratio_str}")

                page_html = f'''        <div class="page" id="page-{page_idx + 1}">
            <img src="{b64_1}" alt="图片 {img_idx + 1:02d}">
            <img src="{b64_2}" alt="图片 {img_idx + 2:02d}">
        </div>'''
            else:
                # 单张时占满整个容器
                page_html = f'''        <div class="page" id="page-{page_idx + 1}">
            <img src="{b64_1}" alt="图片 {img_idx + 1:02d}" style="height: 100%;">
        </div>'''

            pages_html.append(page_html)

    html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }}

        .container {{
            max-width: 600px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}

        .page {{
            background: white;
            aspect-ratio: {aspect_ratio};
            display: flex;
            flex-direction: column;
            overflow: hidden;
            page-break-after: always;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
            position: relative;
        }}

        .page img {{
            width: 100%;
            height: 50%;
            object-fit: contain;
            display: block;
            margin: 0;
            padding: 0;
        }}

        .page.full img {{
            height: 100%;
        }}

        .page.landscape img {{
            width: 100%;
            height: 100%;
            object-fit: contain;
            display: block;
        }}

        @media print {{
            body {{
                background: white;
                padding: 0;
            }}

            .container {{
                max-width: none;
                gap: 0;
            }}

            .page {{
                box-shadow: none;
                page-break-after: always;
                border-radius: 0;
                aspect-ratio: auto;
                width: 100%;
                height: calc({page_h} - 1px);
                overflow: hidden;
            }}

            .page:last-child {{
                page-break-after: avoid;
            }}

            @page {{
                size: {page_size};
                margin: 0;
            }}
        }}

        .btn-group {{
            position: fixed;
            top: 20px;
            right: 20px;
            display: flex;
            gap: 10px;
            z-index: 1000;
        }}

        .btn {{
            background: #007AFF;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 500;
            box-shadow: 0 4px 12px rgba(0, 122, 255, 0.3);
            transition: all 0.3s ease;
        }}

        .btn:hover {{
            background: #0051D5;
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(0, 122, 255, 0.4);
        }}

        .btn:disabled {{
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }}

        .btn.download {{
            background: #34C759;
        }}

        .btn.download:hover {{
            background: #28a745;
        }}

        .progress-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 2000;
        }}

        .progress-box {{
            background: white;
            padding: 30px 40px;
            border-radius: 12px;
            text-align: center;
        }}

        .progress-text {{
            font-size: 18px;
            margin-bottom: 15px;
        }}

        .progress-bar {{
            width: 300px;
            height: 8px;
            background: #e0e0e0;
            border-radius: 4px;
            overflow: hidden;
        }}

        .progress-fill {{
            height: 100%;
            background: #34C759;
            width: 0%;
            transition: width 0.3s ease;
        }}

        @media print {{
            .btn-group, .progress-overlay {{
                display: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="btn-group">
        <button class="btn" onclick="window.print()">打印 / 导出PDF</button>
        <button class="btn download" id="downloadAllBtn" onclick="downloadAllPages()">下载所有容器</button>
    </div>

    <div class="progress-overlay" id="progressOverlay">
        <div class="progress-box">
            <div class="progress-text" id="progressText">准备下载...</div>
            <div class="progress-bar">
                <div class="progress-fill" id="progressFill"></div>
            </div>
        </div>
    </div>

    <div class="container">
{chr(10).join(pages_html)}
    </div>

    <script>
        document.querySelectorAll('img').forEach(img => {{
            img.onerror = function() {{
                this.style.backgroundColor = '#f0f0f0';
                this.alt = '图片加载失败';
            }};
        }});

        async function downloadAllPages() {{
            const pages = document.querySelectorAll('.page');
            const total = pages.length;
            const downloadBtn = document.getElementById('downloadAllBtn');
            const progressOverlay = document.getElementById('progressOverlay');
            const progressText = document.getElementById('progressText');
            const progressFill = document.getElementById('progressFill');

            downloadBtn.disabled = true;
            progressOverlay.style.display = 'flex';

            try {{
                for (let i = 0; i < pages.length; i++) {{
                    const page = pages[i];
                    const fileName = `page_${{String(i + 1).padStart(2, '0')}}.png`;

                    progressText.textContent = `正在生成: ${{i + 1}}/${{total}} - ${{fileName}}`;

                    const canvas = await html2canvas(page, {{
                        scale: 2,
                        useCORS: true,
                        allowTaint: true,
                        backgroundColor: '#ffffff',
                        logging: false
                    }});

                    const link = document.createElement('a');
                    link.download = fileName;
                    link.href = canvas.toDataURL('image/png');
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);

                    const progress = ((i + 1) / total) * 100;
                    progressFill.style.width = `${{progress}}%`;

                    await new Promise(resolve => setTimeout(resolve, 500));
                }}

                progressText.textContent = '下载完成!';
                setTimeout(() => {{
                    progressOverlay.style.display = 'none';
                    downloadBtn.disabled = false;
                    progressFill.style.width = '0%';
                }}, 2000);

            }} catch (error) {{
                console.error('下载失败:', error);
                alert(`下载失败: ${{error.message}}`);
                progressOverlay.style.display = 'none';
                downloadBtn.disabled = false;
            }}
        }}
    </script>
</body>
</html>'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\n✅ HTML 已生成: {output_path}")
    print(f"   共 {len(image_paths)} 张图片 -> {num_pages} 个容器")
    print(f"💡 可直接双击打开，无需服务器")


def detect_suggested_mode(image_meta: List[dict]) -> str:
    """根据图片比例自动建议模式"""
    ratios = [m['ratio'] for m in image_meta if m['ratio']]
    if not ratios:
        return 'auto'

    # 如果超过70%的图片接近3:4，建议full模式
    near_34_count = sum(1 for r in ratios if abs(r - TARGET_RATIO) / TARGET_RATIO <= RATIO_TOLERANCE)
    if near_34_count / len(ratios) >= 0.7:
        return 'full'
    return 'auto'


# 方向 -> (@page size, .page aspect-ratio, 人类可读比例标签)
ORIENTATION_PRESETS = {
    'portrait_34': ('150mm 200mm', '3 / 4', '3:4 竖版'),
    'landscape_43': ('200mm 150mm', '4 / 3', '4:3 横版'),
    'landscape_169': ('267mm 150mm', '16 / 9', '16:9 横版'),
}


def detect_orientation(image_meta: List[dict]) -> str:
    """根据图片实际宽高决定 PDF 方向与页面比例（主方向统一）。

    横版图（宽>高）占比更大 -> 横版 PDF；否则竖版。
    横版时按横版图 w/h 中位数 snap 到 4:3 或 16:9，竖版固定 3:4。

    Returns: ORIENTATION_PRESETS 的 key
    """
    landscapes = [m for m in image_meta if m['width'] and m['height'] and m['width'] > m['height']]
    portraits = [m for m in image_meta if m['width'] and m['height'] and m['width'] <= m['height']]

    if len(landscapes) > len(portraits) and landscapes:
        ratios = sorted(m['width'] / m['height'] for m in landscapes)
        median = ratios[len(ratios) // 2]
        return 'landscape_169' if median >= 1.5 else 'landscape_43'
    return 'portrait_34'


def find_chrome() -> Optional[str]:
    """查找系统上安装的 Chromium 内核浏览器

    Returns:
        浏览器可执行文件路径，或 None（未找到）
    """
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).is_file():
            return candidate

    import shutil
    for name in ("chromium", "google-chrome", "google-chrome-stable", "chrome"):
        found = shutil.which(name)
        if found:
            return found

    return None


def generate_pdf(
    chrome_path: str,
    html_path: Path,
    pdf_path: Path,
    timeout: int = 120,
) -> Tuple[bool, str]:
    """使用 Chrome headless 将 HTML 转换为 PDF

    Args:
        chrome_path: Chrome 可执行文件路径
        html_path: HTML 文件路径
        pdf_path: 输出 PDF 路径
        timeout: 超时秒数（默认 120s）

    Returns:
        (成功与否, 消息)
    """
    html_uri = html_path.resolve().as_uri()

    cmd = [
        chrome_path,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--disable-extensions",
        "--no-first-run",
        "--no-default-browser-check",
        # 等所有合成阶段绘制完成、给虚拟时钟足够预算，确保大量 base64 图全部 decode 后再打印，
        # 避免海量大图时在解码完成前出图导致零星空白页
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=20000",
        f"--print-to-pdf={pdf_path}",
        html_uri,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            stderr_lines = result.stderr.strip().splitlines()
            real_errors = [
                line for line in stderr_lines
                if "bytes written" not in line
                and "allocator" not in line.lower()
                and "DEPRECATED_ENDPOINT" not in line
            ]
            msg = real_errors[-1] if real_errors else result.stderr.strip()[-200:]
            return False, f"Chrome 退出码 {result.returncode}: {msg}"

        if not pdf_path.exists() or pdf_path.stat().st_size == 0:
            return False, "Chrome 执行成功但 PDF 文件未生成"

        size_mb = pdf_path.stat().st_size / (1024 * 1024)
        return True, f"PDF 已生成: {pdf_path} ({size_mb:.1f}MB)"

    except subprocess.TimeoutExpired:
        return False, f"Chrome 超时（>{timeout}秒），文件可能过大"
    except FileNotFoundError:
        return False, f"Chrome 未找到: {chrome_path}"
    except Exception as e:
        return False, f"PDF 生成失败: {e}"


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='将图片拼接成3:4容器的HTML生成器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
模式说明:
  auto (默认) - 竖版任意比例图片，每容器最多2张，自动拼成3:4
  full        - 竖版3:4比例图片，每张独占一个完整容器
  （横版图片自动走横版布局，每页一张，--mode 不生效）

页面方向（--orientation）:
  auto        按图片主方向自动判定（默认）
  landscape   强制横版 PDF，每页一张
  portrait    强制竖版 PDF

示例:
  python generate_html.py ./my_images
  python generate_html.py ./my_images output --mode full
  python generate_html.py ./landscape_images          # 横版图集，自动横版
  python generate_html.py ./imgs --orientation landscape
  python generate_html.py --files 封面.png 01.png 02.png  # 文件名无序号时按指定顺序
        '''
    )
    parser.add_argument('folder', nargs='?', help='图片文件夹路径（与 --files 二选一）')
    parser.add_argument('output', nargs='?', help='输出文件名（默认与文件夹同名；--files 模式请用 --output）')
    parser.add_argument('--output', dest='output_opt', default=None,
                        help='输出文件名，--files 模式下使用（覆盖位置 output，避免与 --files 的多值参数冲突）')
    parser.add_argument('--files', nargs='+',
                        help='显式图片路径列表，按给定顺序排版（跳过文件名排序）。文件名无序号时由调用方排好顺序后传入')
    parser.add_argument('--mode', choices=['auto', 'full'], default='auto',
                        help='布局模式（仅竖版生效）: auto=自动拼成3:4容器, full=每张图独占完整容器')
    parser.add_argument('--orientation', choices=['auto', 'landscape', 'portrait'], default='auto',
                        help='页面方向: auto=按图片主方向自动判定, landscape=强制横版(每页一张), portrait=强制竖版')
    parser.add_argument('--no-pdf', action='store_true', default=False,
                        help='跳过 PDF 生成，仅输出 HTML')

    args = parser.parse_args()

    # --- 输入解析：--files（显式有序列表）或 folder（文件夹+自然排序）---
    if args.files:
        images = [Path(f) for f in args.files]
        missing = [f for f in images if not f.is_file()]
        if missing:
            print(f"❌ 找不到图片文件: {', '.join(str(m) for m in missing)}")
            sys.exit(1)
        base_dir = images[0].parent
        output_name = args.output_opt or args.output or f"{base_dir.name}_layout"
        print(f"📁 使用显式文件列表：{len(images)} 张图片（按给定顺序，不重排）")
    elif args.folder:
        input_folder = Path(args.folder)
        output_name = args.output_opt or args.output or f"{input_folder.name}_layout"
        try:
            images = get_images_from_folder(input_folder)
        except FileNotFoundError as e:
            print(f"❌ {e}")
            sys.exit(1)
        if not images:
            print(f"❌ 文件夹中没有图片: {input_folder}")
            sys.exit(1)
        base_dir = input_folder
    else:
        parser.error("请提供文件夹路径，或用 --files 指定图片列表")

    # --- 收集元数据 ---
    image_meta = []
    for img in images:
        w, h = get_image_size(img)
        ratio = h / w if w and h else None
        image_meta.append({'path': img, 'width': w, 'height': h, 'ratio': ratio,
                           'is_34': ratio and abs(ratio - TARGET_RATIO) / TARGET_RATIO <= RATIO_TOLERANCE})

    # --- 决定方向与页面比例 ---
    if args.orientation == 'landscape':
        landscapes = [m for m in image_meta if m['width'] and m['height'] and m['width'] > m['height']]
        if landscapes:
            ratios = sorted(m['width'] / m['height'] for m in landscapes)
            median = ratios[len(ratios) // 2]
            orientation_key = 'landscape_169' if median >= 1.5 else 'landscape_43'
        else:
            orientation_key = 'landscape_43'  # 无横版图也强制横版，默认 4:3
    elif args.orientation == 'portrait':
        orientation_key = 'portrait_34'
    else:  # auto
        orientation_key = detect_orientation(image_meta)

    is_landscape = orientation_key.startswith('landscape')

    # 竖版时保留 mode 自动升级；横版时 mode 不生效（横版固定每页一张）
    mode = args.mode
    if not is_landscape:
        suggested = detect_suggested_mode(image_meta)
        if mode == 'auto' and suggested == 'full':
            print(f"📊 检测到 {sum(1 for m in image_meta if m.get('is_34'))}/{len(images)} 张图片接近3:4比例")
            print(f"💡 建议使用 --mode full 获得更好效果（已自动应用）")
            mode = 'full'

    _page_size, _aspect, orient_label = ORIENTATION_PRESETS[orientation_key]
    mode_label = "横版每页一张" if is_landscape else ("3:4容器拼接" if mode == "auto" else "完整图片排列")
    print(f"📐 方向: {orient_label}")
    print(f"📁 共 {len(images)} 张图片，模式: {mode_label}，正在嵌入...")

    output_html = base_dir / f"{output_name}.html"
    generate_html(images, output_html, title=output_name, mode=mode, orientation_key=orientation_key)

    # --- PDF 生成 ---
    if not args.no_pdf:
        chrome = find_chrome()
        if chrome:
            output_pdf = base_dir / f"{output_name}.pdf"
            print(f"\n📄 正在生成 PDF（使用 Chrome headless）...")
            ok, msg = generate_pdf(chrome, output_html, output_pdf)
            if ok:
                print(f"   {msg}")
            else:
                print(f"   ⚠️ {msg}")
                print(f"   💡 HTML 文件仍可手动在浏览器中打开并打印为 PDF")
        else:
            print(f"\n⚠️ 未找到 Chrome/Chromium 浏览器，跳过 PDF 生成")
            print(f"   💡 HTML 文件仍可手动在浏览器中打开并打印为 PDF")
    else:
        print(f"\n⏭️ 已跳过 PDF 生成（--no-pdf）")


if __name__ == '__main__':
    main()
