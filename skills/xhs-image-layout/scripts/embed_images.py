#!/usr/bin/env python3
"""
图片布局打印机 - Base64 嵌入版本生成器
将图片转为 base64 嵌入 HTML，解决 CORS 问题
"""

import base64
import sys
from pathlib import Path


def image_to_base64(img_path: Path) -> str:
    """将图片转为 base64"""
    with open(img_path, 'rb') as f:
        data = f.read()
    
    ext = img_path.suffix.lower()
    mime_map = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }
    mime = mime_map.get(ext, 'image/jpeg')
    
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def embed_images_to_html(html_path: Path, output_path: Path = None):
    """将 HTML 中的图片路径替换为 base64"""
    
    if output_path is None:
        output_path = html_path.parent / f"{html_path.stem}_embedded.html"
    
    # 读取 HTML
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # 查找所有图片引用
    import re
    img_pattern = r'src="([^"]+\.(?:jpg|jpeg|png|gif|webp))"'
    matches = re.findall(img_pattern, html_content, re.IGNORECASE)
    
    print(f"找到 {len(matches)} 个图片引用")
    
    # 转换每张图片
    base_folder = html_path.parent
    for img_rel_path in set(matches):  # 去重
        img_path = base_folder / img_rel_path
        
        if img_path.exists():
            try:
                base64_data = image_to_base64(img_path)
                html_content = html_content.replace(img_rel_path, base64_data)
                size_kb = len(base64_data) // 1024
                print(f"✅ {img_rel_path} ({size_kb}KB)")
            except Exception as e:
                print(f"❌ 转换失败 {img_rel_path}: {e}")
        else:
            print(f"⚠️ 图片不存在: {img_path}")
    
    # 保存
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\n🎉 嵌入版本已保存: {output_path}")
    print(f"💡 可直接双击打开，无需服务器")
    
    return output_path


def main():
    if len(sys.argv) < 2:
        print("用法: python embed_images.py <html文件>")
        print("示例: python embed_images.py ./collage.html")
        sys.exit(1)
    
    html_path = Path(sys.argv[1])
    
    if not html_path.exists():
        print(f"❌ HTML 文件不存在: {html_path}")
        sys.exit(1)
    
    embed_images_to_html(html_path)


if __name__ == '__main__':
    main()
