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
            header = f.read(24)

        # PNG
        if header[:8] == b'\x89PNG\r\n\x1a\n':
            w, h = struct.unpack('>II', header[16:24])
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


def generate_html(image_paths: List[Path], output_path: Path, title: str = "图片展示", mode: str = "auto"):
    """生成图片以 base64 嵌入的独立 HTML 文件

    mode:
        auto - 任意比例图片，每容器最多放2张（各占50%高度），自动拼成3:4容器
        full - 每张图本身是3:4比例，每张图独占一个完整容器，直接拼接展示
    """

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

    if mode == "full":
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
            aspect-ratio: 3 / 4;
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
            }}

            @page {{
                size: 150mm 200mm;
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
  auto (默认) - 任意比例图片，每容器最多2张，自动拼成3:4
  full        - 图片本身已是3:4比例，每张独占一个完整容器

示例:
  python generate_html.py ./my_images
  python generate_html.py ./my_images output --mode full
        '''
    )
    parser.add_argument('folder', help='图片文件夹路径')
    parser.add_argument('output', nargs='?', help='输出文件名（默认与文件夹同名）')
    parser.add_argument('--mode', choices=['auto', 'full'], default='auto',
                        help='布局模式: auto=自动拼成3:4容器, full=每张图独占完整容器')
    parser.add_argument('--no-pdf', action='store_true', default=False,
                        help='跳过 PDF 生成，仅输出 HTML')

    args = parser.parse_args()

    input_folder = Path(args.folder)
    output_name = args.output or f"{input_folder.name}_layout"
    mode = args.mode

    try:
        images = get_images_from_folder(input_folder)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)

    if not images:
        print(f"❌ 文件夹中没有图片: {input_folder}")
        sys.exit(1)

    # 收集元数据并建议模式
    image_meta = []
    for img in images:
        w, h = get_image_size(img)
        ratio = h / w if w and h else None
        image_meta.append({'path': img, 'width': w, 'height': h, 'ratio': ratio, 'is_34': ratio and abs(ratio - TARGET_RATIO) / TARGET_RATIO <= RATIO_TOLERANCE})

    suggested = detect_suggested_mode(image_meta)

    if mode == 'auto' and suggested == 'full':
        print(f"📊 检测到 {sum(1 for m in image_meta if m.get('is_34'))}/{len(images)} 张图片接近3:4比例")
        print(f"💡 建议使用 --mode full 获得更好效果（已自动应用）")
        mode = 'full'

    mode_label = "3:4容器拼接" if mode == "auto" else "完整图片排列"
    print(f"📁 找到 {len(images)} 张图片，模式: {mode_label}，正在嵌入...")

    output_html = input_folder / f"{output_name}.html"
    generate_html(images, output_html, title=output_name, mode=mode)

    # --- PDF 生成 ---
    if not args.no_pdf:
        chrome = find_chrome()
        if chrome:
            output_pdf = input_folder / f"{output_name}.pdf"
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
