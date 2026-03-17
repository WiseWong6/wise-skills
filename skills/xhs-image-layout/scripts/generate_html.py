#!/usr/bin/env python3
"""
图片布局打印机 - HTML 生成器
将图片拼接成 3:4 白色容器的 HTML 页面
"""

import os
import sys
import base64
from pathlib import Path
from typing import List, Union


def get_images_from_folder(folder_path: Union[str, Path]) -> List[Path]:
    """从文件夹获取所有图片"""
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"文件夹不存在: {folder}")
    
    extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    images = [f for f in folder.iterdir() 
              if f.is_file() and f.suffix.lower() in extensions]
    
    return sorted(images)


def generate_html(image_paths: List[Path], output_path: Path, title: str = "图片展示"):
    """生成 HTML 文件"""
    
    # 计算容器数量
    num_pages = (len(image_paths) + 1) // 2
    
    # 生成页面
    pages_html = []
    for page_idx in range(num_pages):
        img_idx = page_idx * 2
        img1 = image_paths[img_idx]
        
        # 第一张图
        img1_path = f"{img1.parent.name}/{img1.name}"
        
        # 第二张图（如果存在）
        if img_idx + 1 < len(image_paths):
            img2 = image_paths[img_idx + 1]
            img2_path = f"{img2.parent.name}/{img2.name}"
            page_html = f'''        <!-- 容器 {page_idx + 1} -->
        <div class="page" id="page-{page_idx + 1}">
            <img src="{img1_path}" alt="图片 {img_idx:02d}">
            <img src="{img2_path}" alt="图片 {img_idx + 1:02d}">
        </div>'''
        else:
            # 单张图
            page_html = f'''        <!-- 容器 {page_idx + 1} (单张) -->
        <div class="page" id="page-{page_idx + 1}">
            <img src="{img1_path}" alt="图片 {img_idx:02d}">
        </div>'''
        
        pages_html.append(page_html)
    
    # HTML 模板
    html_template = f'''<!DOCTYPE html>
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

        .page img:first-child {{
            border-bottom: none;
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
            }}

            @page {{
                size: auto;
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
        // 图片加载失败处理
        document.querySelectorAll('img').forEach(img => {{
            img.onerror = function() {{
                this.style.backgroundColor = '#f0f0f0';
                this.style.display = 'flex';
                this.style.alignItems = 'center';
                this.style.justifyContent = 'center';
                this.alt = '图片加载失败';
                console.error('图片加载失败:', this.src);
            }};
        }});

        // 下载所有容器
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

                    // 使用 html2canvas 截图
                    const canvas = await html2canvas(page, {{
                        scale: 2,
                        useCORS: true,
                        allowTaint: true,
                        backgroundColor: '#ffffff',
                        logging: false
                    }});

                    // 下载
                    const link = document.createElement('a');
                    link.download = fileName;
                    link.href = canvas.toDataURL('image/png');
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);

                    // 更新进度
                    const progress = ((i + 1) / total) * 100;
                    progressFill.style.width = `${{progress}}%`;

                    // 延迟避免浏览器阻止
                    await new Promise(resolve => setTimeout(resolve, 500));
                }}

                progressText.textContent = '下载完成!请检查下载文件夹';
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
    
    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_template)
    
    print(f"✅ HTML 已生成: {output_path}")
    print(f"   共 {len(image_paths)} 张图片 -> {num_pages} 个容器")


def create_cors_server(output_dir: Path):
    """创建 CORS 服务器启动脚本"""
    server_script = '''#!/usr/bin/env python3
"""启动支持 CORS 的本地服务器"""
import http.server
import socketserver
import os

PORT = 8080

class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

os.chdir(os.path.dirname(os.path.abspath(__file__)))

with socketserver.TCPServer(("", PORT), CORSRequestHandler) as httpd:
    print(f"✅ CORS 服务器已启动: http://localhost:{PORT}")
    httpd.serve_forever()
'''
    
    server_path = output_dir / 'start_cors_server.py'
    with open(server_path, 'w') as f:
        f.write(server_script)
    
    # 添加执行权限
    os.chmod(server_path, 0o755)
    print(f"✅ 服务器脚本: {server_path}")


def main():
    if len(sys.argv) < 2:
        print("用法: python generate_html.py <图片文件夹> [输出文件名]")
        print("示例: python generate_html.py ./my_images collage")
        sys.exit(1)
    
    # 输入文件夹
    input_folder = Path(sys.argv[1])
    
    # 输出文件名
    if len(sys.argv) >= 3:
        output_name = sys.argv[2]
    else:
        output_name = input_folder.name
    
    # 获取图片
    try:
        images = get_images_from_folder(input_folder)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    if not images:
        print(f"❌ 文件夹中没有图片: {input_folder}")
        sys.exit(1)
    
    print(f"📁 找到 {len(images)} 张图片")
    
    # 生成 HTML
    output_html = input_folder.parent / f"{output_name}.html"
    generate_html(images, output_html, title=output_name)
    
    # 创建服务器脚本
    create_cors_server(input_folder.parent)
    
    print(f"\n🚀 启动服务器:")
    print(f"   cd {input_folder.parent} && python3 start_cors_server.py")
    print(f"\n📱 访问地址: http://localhost:8080/{output_name}.html")


if __name__ == '__main__':
    main()
