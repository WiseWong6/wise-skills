#!/Users/wisewong/.openclaw/workspace/.venvs/image-gen/bin/python3
import argparse
import base64
import copy
import json
import os
import sys
import ssl
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import yaml
from pathlib import Path
from dotenv import load_dotenv

from openai import OpenAI, OpenAIError

# Load environment variables from .env file
load_dotenv()

# 使用certifi的SSL证书
try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = None

# Pillow 用于生成占位符图片
try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False


def extract_prompts_from_markdown(markdown_file: str) -> tuple[str, list[str]]:
    """从markdown文件中提取图片提示词

    支持格式：

    格式1（标准格式 - 推荐）：
    ## 【封面图｜标题：xxx】
    **核心内容**：一句话描述
    **绘画提示词**：
    极简手绘笔记风格，16:9横版...

    **负面约束**：无复杂背景
    **参数**：比例 16:9，分辨率 2560x1440

    格式2（image-prompter 旧输出 - 代码块格式）：
    ## 图1：封面（21:9 超宽横版）
    ```
    极简手绘笔记风格，21:9超宽横版...
    ```

    格式3（兼容旧格式）：
    ### 封面图（16:9横版）
    **提示词**：
    Create a clean 16:9 horizontal infographic...

    Returns:
        tuple: (cover_prompt, poster_prompts_list)
            - cover_prompt: 封面图提示词（如果存在）
            - poster_prompts: 正文图提示词列表
    """
    cover_prompt = ""
    poster_prompts = []

    try:
        with open(markdown_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 按 ## 标题块分割（兼容所有格式）
        blocks = content.split('##')
        for block in blocks:
            block = block.strip()
            if not block:
                continue

            # 格式3: 新简洁格式（代码块包裹）
            # 检测：标题行包含 "封面" 或 "图N"，内容在代码块中
            if '```' in block:
                # 提取代码块内容
                code_start = block.find('```')
                code_end = block.find('```', code_start + 3)
                if code_end == -1:
                    code_end = len(block)

                # 获取代码块内容（跳过第一行的 ```）
                code_content = block[code_start + 3:code_end].strip()
                # 移除可能的语言标记（如 ```text）
                if '\n' in code_content:
                    first_line = code_content.split('\n')[0].strip()
                    if first_line and not first_line.startswith('极简') and not first_line.startswith('Create'):
                        code_content = '\n'.join(code_content.split('\n')[1:]).strip()

                if code_content:
                    # 判断是封面还是正文图
                    # 封面标记：标题包含 "封面"
                    is_cover = '封面' in block.split('\n')[0]
                    if is_cover:
                        cover_prompt = code_content
                    else:
                        poster_prompts.append(code_content)
                continue

            # 格式2: **绘画提示词**（image-prompter 旧格式）
            if '**绘画提示词**：' in block or '**绘画提示词**:' in block:
                start = block.find('**绘画提示词**：')
                if start == -1:
                    start = block.find('**绘画提示词**:')
                if start != -1:
                    start += len('**绘画提示词**：')

                    # 找到下一个标记或块结束
                    end_markers = ['负面约束：', '参数：', '##', '---']
                    end = len(block)
                    for marker in end_markers:
                        pos = block.find(marker, start)
                        if pos != -1 and pos < end:
                            end = pos

                    prompt = block[start:end].strip()
                    if prompt:
                        # 判断是封面图还是正文图
                        # 封面图标记：
                        # - 旧格式：标题包含 "封面" (如 "【第1张｜封面图：xxx")
                        # - 更旧格式：包含 "额外生成" 或 "【封面图"
                        first_line = block.split('\n')[0]
                        is_cover = ('封面' in first_line) or ('额外生成' in block) or ('【封面图' in block)
                        if is_cover:
                            cover_prompt = prompt
                        else:
                            poster_prompts.append(prompt)
                continue

            # 格式1: **提示词**（旧格式兼容）
            if '**提示词**：' in block or '**提示词**:' in block:
                start = block.find('**提示词**：')
                if start == -1:
                    start = block.find('**提示词**:')
                if start != -1:
                    start += len('**提示词**：')

                    end_markers = ['##', '---', '**视觉元素**', '**概念**']
                    end = len(block)
                    for marker in end_markers:
                        pos = block.find(marker, start)
                        if pos != -1 and pos < end:
                            end = pos

                    prompt = block[start:end].strip()
                    if prompt:
                        poster_prompts.append(prompt)

    except Exception as e:
        print(f"解析markdown文件失败: {e}")

    return cover_prompt, poster_prompts


def refactored_prompts_for_image_generation(prompts: list[str]) -> list[str]:
    """重构提示词：将具体场景描述放在前面，风格描述放在后面

    原因：image-prompter 输出的格式是"风格前缀 + 场景描述"，但模型会优先响应开头的风格描述，
    导致生成的图片风格一致而内容差异不明显。

    策略：将提示词重构为"场景描述 + 风格后缀"，让模型优先满足内容要求。
    """
    refactored = []
    for prompt in prompts:
        # 检测是否有风格前缀（通常以 "xxx style," 开头）
        parts = prompt.split('\n\n', 1)
        if len(parts) == 2 and 'style,' in parts[0]:
            # 交换顺序：场景在前，风格在后
            scene, style = parts
            refactored.append(f"{scene}\n\n{style}")
        else:
            refactored.append(prompt)
    return refactored


def load_image_plan_from_markdown(markdown_file: str) -> list[dict]:
    """从 Markdown frontmatter 读取 image_plan 元数据。

    兼容两种写法：
    1. 顶层 image_plan
    2. image_prompter.image_plan
    """
    try:
        content = Path(markdown_file).read_text(encoding="utf-8")
    except Exception as e:
        print(f"读取 image_plan 失败: {e}")
        return []

    if not content.startswith("---"):
        return []

    parts = content.split("---", 2)
    if len(parts) < 3:
        return []

    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
    except Exception as e:
        print(f"解析 image_plan frontmatter 失败: {e}")
        return []

    image_plan = frontmatter.get("image_plan")
    if not image_plan:
        image_plan = (frontmatter.get("image_prompter") or {}).get("image_plan")

    if not isinstance(image_plan, list):
        return []

    normalized = []
    for idx, item in enumerate(image_plan, 1):
        if not isinstance(item, dict):
            continue
        normalized.append({
            "index": idx,
            "role": item.get("role") or ("cover" if idx == 1 else "poster"),
            "title": item.get("title") or item.get("alt") or item.get("label") or f"配图 {idx}",
            "insert_after": item.get("insert_after"),
            "insert_after_heading": item.get("insert_after_heading"),
        })
    return normalized


def find_insert_line_after_heading(lines: list[str], heading_text: str) -> int | None:
    """找到指定标题后的插入行。"""
    heading_text = (heading_text or "").strip().lstrip("#").strip()
    if not heading_text:
        return None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        current_heading = stripped.lstrip("#").strip()
        if current_heading == heading_text:
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            return j
    return None


def find_insert_line_after_text(lines: list[str], needle: str) -> int | None:
    """找到包含指定文本的行后插入。"""
    needle = (needle or "").strip()
    if not needle:
        return None

    for i, line in enumerate(lines):
        if needle in line:
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            return j
    return None


def build_image_slots(img_files: list[Path], image_plan: list[dict]) -> list[dict]:
    """将生成后的图片文件与 image_plan 绑定。"""
    cover_file = next((f for f in img_files if f.name.startswith("cover_")), None)
    poster_files = [f for f in img_files if f.name.startswith("poster_")]

    slots = []
    poster_idx = 0

    if image_plan:
        for idx, plan in enumerate(image_plan, 1):
            role = plan.get("role", "poster")
            if role == "cover" and cover_file:
                file_path = cover_file
            elif poster_idx < len(poster_files):
                file_path = poster_files[poster_idx]
                poster_idx += 1
            elif role == "cover" and cover_file:
                file_path = cover_file
            else:
                continue

            slots.append({
                "file": file_path,
                "label": plan.get("title") or ("封面" if role == "cover" else f"配图 {idx}"),
                "role": role,
                "insert_after": plan.get("insert_after"),
                "insert_after_heading": plan.get("insert_after_heading"),
            })

    # 兜底：把未消耗的图片按旧策略补上
    used_names = {slot["file"].name for slot in slots}
    remaining = [f for f in img_files if f.name not in used_names]
    for extra_idx, file_path in enumerate(remaining, 1):
        role = "cover" if file_path.name.startswith("cover_") else "poster"
        slots.append({
            "file": file_path,
            "label": "封面" if role == "cover" else f"配图补位 {extra_idx}",
            "role": role,
            "insert_after": None,
            "insert_after_heading": None,
        })

    return slots


FALLBACK_MODEL = "doubao-seedream-4-0-250828"

# 统一的宽高比配置（SSOT - Single Source of Truth）
# 火山引擎 Seedream 4.5 官方推荐尺寸
ASPECT_CONFIGS = {
    '21:9': {'width': 3024, 'height': 1296, 'size_str': '3024x1296', 'pixels': 3919104},
    '16:9': {'width': 2560, 'height': 1440, 'size_str': '2560x1440', 'pixels': 3686400},
    '4:3': {'width': 2304, 'height': 1728, 'size_str': '2304x1728', 'pixels': 3981312},
    '3:4': {'width': 1728, 'height': 2304, 'size_str': '1728x2304', 'pixels': 3981312},
    '1:1': {'width': 2048, 'height': 2048, 'size_str': '2048x2048', 'pixels': 4194304},
}

# 固定平台比例规则（优先级最高）
PLATFORM_FIXED_RATIOS = {
    'wechat': {
        'cover': '21:9',    # 公众号封面：超宽横版
        'poster': '16:9',   # 公众号正文：标准宽屏
    },
    'xiaohongshu': {
        'cover': '3:4',     # 小红书封面：竖版
        'poster': '3:4',    # 小红书正文：竖版
    },
}

# 兼容性别名（向后兼容）
ASPECT_RATIO_TO_SIZE = {ratio: config['size_str'] for ratio, config in ASPECT_CONFIGS.items()}

# Standard output filenames
COVER_FILENAME = "cover_{ratio}.jpg"
POSTER_FILENAME = "poster_{index:02d}_{ratio}.jpg"


def detect_platform_from_path(output_path: str = None, out_dir: str = None, prompts_file: str = None) -> str | None:
    """从输出路径检测目标平台

    Args:
        output_path: 单个输出文件路径
        out_dir: 输出目录路径
        prompts_file: 提示词文件路径
    """
    # 检查多个可能的路径
    paths_to_check = [output_path, out_dir, prompts_file]
    for path in paths_to_check:
        if not path:
            continue
        path_lower = path.lower()
        if 'wechat' in path_lower or '公众号' in path_lower:
            return 'wechat'
        elif 'xiaohongshu' in path_lower or '小红书' in path_lower:
            return 'xiaohongshu'
    return None


def get_ratio_for_image(platform: str | None, index: int, custom_ratio: str | None = None) -> str:
    """获取单张图片的比例

    优先级：
    1. 用户手动指定的 --aspect-ratio（最高）
    2. 固定平台比例规则（本次修改重点）
    3. 默认 1:1（兜底）

    Args:
        platform: 平台类型（'wechat' | 'xiaohongshu' | None）
        index: 图片序号（0-based，0=封面）
        custom_ratio: 用户手动指定的比例

    Returns:
        比例字符串（如 '16:9'）
    """
    if custom_ratio:
        return custom_ratio

    if platform and platform in PLATFORM_FIXED_RATIOS:
        ratios = PLATFORM_FIXED_RATIOS[platform]
        return ratios['cover'] if index == 0 else ratios['poster']

    return '1:1'  # 默认兜底


def get_default_ratios_for_platform(platform: str) -> tuple:
    """根据平台获取默认的封面图和正文图比例

    Returns:
        tuple: (cover_ratio, poster_ratio)
    """
    return PLATFORM_FIXED_RATIOS.get(platform, {
        'cover': '21:9',
        'poster': '16:9'
    })


def try_generate_single(client: OpenAI, args: argparse.Namespace, api_key: str, image_index: int = 0) -> dict:
    """生成单张图片"""
    models = [args.model]
    if args.model != FALLBACK_MODEL:
        models.append(FALLBACK_MODEL)

    for model in models:
        args.model = model
        # 先试 SDK
        try:
            print(f"\n[图片 {image_index + 1}] [SDK] 使用模型: {model}, size={args.size}")
            resp = client.images.generate(
                model=model,
                prompt=args.prompt,
                size=args.size,
                response_format=args.response_format,
                extra_body={
                    "watermark": args.watermark == "true",
                },
            )
            if args.response_format == "url":
                return {"data": [{"url": resp.data[0].url}]}
            else:
                return {"data": [{"b64_json": resp.data[0].b64_json}]}
        except OpenAIError as e:
            print(f"✗ 图片 {image_index + 1} SDK 失败，尝试原生 HTTP: {e}")

        # SDK 失败，降级到原生 HTTP
        try:
            print(f"[图片 {image_index + 1}] [HTTP] 使用模型: {model}")
            return http_generate(args, api_key)
        except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
            print(f"✗ 图片 {image_index + 1} HTTP 失败: {e}")

    raise RuntimeError(f"图片 {image_index + 1}: 所有模型和调用方式均失败")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate images via Ark (OpenAI-compatible) or Gemini 3 Pro Image."
    )
    parser.add_argument(
        "--provider",
        choices=["ark", "gemini"],
        default="ark",
        help="Image provider to use (default: ark)"
    )
    parser.add_argument("--prompts-file", help="Path to prompts file (markdown)")
    parser.add_argument("--prompt", help="Image prompt text (direct or from file)")
    parser.add_argument(
        "--input-image", "-i",
        action="append",
        dest="input_images",
        metavar="IMAGE",
        help="Input image path(s) for editing/composition (Gemini only, up to 14 images)"
    )
    parser.add_argument(
        "--resolution", "-r",
        choices=["1K", "2K", "4K"],
        default=None,
        help="Output resolution for Gemini (default: auto-detect from input or 1K)"
    )
    parser.add_argument(
        "--model",
        default="doubao-seedream-5-0-260128",
        help="Model ID to use",
    )
    parser.add_argument("--size", default="2K", help="Image size, e.g. 2K")
    parser.add_argument(
        "--cover-ratio",
        choices=["21:9", "16:9", "4:3", "1:1"],
        default="21:9",
        help="[Deprecated] 公众号封面比例（默认自动使用 21:9）",
    )
    parser.add_argument(
        "--poster-ratio",
        choices=["16:9", "4:3", "3:4", "1:1"],
        default="16:9",
        help="[Deprecated] 公众号正文比例（默认自动使用 16:9）",
    )
    parser.add_argument(
        "--response-format",
        choices=["url", "b64_json"],
        default="b64_json",
        help="Response format (default: b64_json for direct download)",
    )
    parser.add_argument(
        "--watermark",
        choices=["true", "false"],
        default="false",
        help="Whether to add watermark",
    )
    parser.add_argument(
        "--out-dir",
        help="Output directory for generated images",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=4,
        help="Number of poster images to generate",
    )
    parser.add_argument(
        "--base-url",
        default="https://ark.cn-beijing.volces.com/api/v3",
        help="Ark API base URL",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key override (defaults to ARK_API_KEY env var)",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Non-interactive mode (no input prompts)",
    )
    # Backward compatibility
    parser.add_argument(
        "--aspect-ratio",
        choices=["1:1", "16:9", "9:16", "4:3", "3:4", "21:9"],
        help="手动指定比例（覆盖自动检测）。可选：1:1, 16:9, 9:16, 4:3, 3:4, 21:9",
    )
    parser.add_argument(
        "--output",
        help="Optional output path to save image (URL download or base64 decode) - deprecated",
    )
    parser.add_argument(
        "--num-images",
        type=int,
        default=1,
        help="Number of images to generate (deprecated, use --count)",
    )
    parser.add_argument(
        "--handoff-out",
        help="Path to write handoff.yaml",
    )
    parser.add_argument(
        "--insert-into",
        help="Path to markdown file to insert generated images (auto-detects positions)",
    )
    return parser.parse_args()


def download_url(url: str, output_path: str) -> None:
    # 创建SSL上下文，跳过证书验证（在受信任的环境中使用）
    import ssl
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    with urllib.request.urlopen(url, context=ssl_context) as response:
        content = response.read()
    with open(output_path, "wb") as handle:
        handle.write(content)


def write_b64(data: str, output_path: str) -> None:
    with open(output_path, "wb") as handle:
        handle.write(base64.b64decode(data))


def confirm_aspect_ratio(aspect_ratio: str) -> bool:
    # 自动化模式下跳过确认
    print(f"\n即将生成图片，比例设置为: {aspect_ratio}")
    return True


def validate_outputs(output_dir: str, expected_count: int) -> None:
    """验证输出文件数量是否正确"""
    if not output_dir:
        return
    actual = len(list(Path(output_dir).glob("*.jpg")))
    if actual != expected_count:
        raise RuntimeError(
            f"输出验证失败：期望 {expected_count} 张图片，实际 {actual} 张"
        )


def http_generate(args: argparse.Namespace, api_key: str) -> dict:
    url = f"{args.base_url}/images/generations"
    payload = {
        "model": args.model,
        "prompt": args.prompt,
        "response_format": args.response_format,
        "size": args.size,
        "watermark": args.watermark == "true",
    }
    body = json.dumps(payload).encode()

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(req, context=SSL_CONTEXT) as resp:
        return json.load(resp)


def generate_placeholder(output_path: str, image_index: int, ratio: str) -> str:
    """生成占位符图片（白底+边框+文字）"""
    if not PILLOW_AVAILABLE:
        # Pillow 不可用，降级为文本占位符
        text_path = output_path.replace('.jpg', '.txt')
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(f"# 配图 {image_index}\n\n图片生成失败，使用占位符替换\n\n比例: {ratio}")
        return text_path

    # 使用统一配置（SSOT）
    config = ASPECT_CONFIGS.get(ratio, {'width': 1024, 'height': 1024})
    width, height = config['width'], config['height']
    print(f"[占位符] 比例 {ratio} → 尺寸 {width}x{height}")

    # 创建白色背景
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)

    # 绘制边框
    border_width = 10
    draw.rectangle(
        [(border_width, border_width), (width - border_width, height - border_width)],
        outline='gray', width=border_width
    )

    # 绘制文字
    text = f"[配图 {image_index}]\n\n图片生成失败\n\n使用占位符替换"
    try:
        # 尝试加载系统字体
        font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 40)
    except Exception:
        # 降级为默认字体
        font = ImageFont.load_default()

    # 计算文字位置（居中）
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    x = (width - text_width) // 2
    y = (height - text_height) // 2

    draw.text((x, y), text, fill='gray', font=font)

    # 保存
    (Path(output_path)).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, 'JPEG', quality=80)
    return output_path


def generate_and_save_image(args: argparse.Namespace, api_key: str, image_index: int, output_dir: str | None, prompt: str | None = None, filename: str | None = None, aspect_ratio: str | None = None) -> tuple[int, bool, str | None, str]:
    """
    生成单张图片并保存

    返回: (image_index, success, path_or_error, type)

    type:
        - 'real': 真实生成的图片
        - 'placeholder': 占位符图片
        - 'error': 完全失败
    """
    try:
        # 创建 args 副本以避免并发竞态条件
        local_args = copy.copy(args)
        # 如果提供了提示词，使用它
        if prompt:
            local_args.prompt = prompt
        # 如果提供了比例，将其转换为 size 参数
        if aspect_ratio:
            size = ASPECT_RATIO_TO_SIZE.get(aspect_ratio, args.size)
            local_args.size = size
            print(f"[图片 {image_index + 1}] 比例 {aspect_ratio} → size={size}")

        client = OpenAI(base_url=local_args.base_url, api_key=api_key)
        result = try_generate_single(client, local_args, api_key, image_index)

        data = result["data"][0]
        # 确定输出文件名
        if filename:
            output_filename = filename
        else:
            ext = Path(args.output).suffix if args.output else ".jpg"
            output_filename = f"image_{image_index + 1:02d}{ext}"

        if args.response_format == "url":
            url = data["url"]
            if output_dir:
                output_path = Path(output_dir) / output_filename
                download_url(url, str(output_path))
            else:
                print(f"图片 {image_index + 1} URL: {url}")
                return image_index, True, url, 'real'
        else:
            b64_data = data["b64_json"]
            if output_dir:
                output_path = Path(output_dir) / output_filename
                write_b64(b64_data, str(output_path))
            else:
                print(f"图片 {image_index + 1} Base64: {b64_data[:50]}...")
                return image_index, True, b64_data[:50], 'real'

        # 验证文件是否真实存在
        if output_dir:
            output_path = Path(output_dir) / output_filename
            if not output_path.exists():
                raise FileNotFoundError(f"文件未创建: {output_path}")

            if output_path.stat().st_size == 0:
                raise ValueError(f"文件为空: {output_path}")

        return image_index, True, str(output_path), 'real'

    except Exception as e:
        print(f"图片 {image_index + 1} 生成失败: {e}")

        # 生成占位符
        if output_dir:
            try:
                if filename:
                    output_filename = filename
                else:
                    output_filename = f"image_{image_index + 1:02d}.jpg"
                output_path = Path(output_dir) / output_filename
                # 使用当前比例（可能是传入的 aspect_ratio 或 args.aspect_ratio）
                current_ratio = aspect_ratio if aspect_ratio else args.aspect_ratio
                generate_placeholder(str(output_path), image_index + 1, current_ratio)
                return image_index, True, str(output_path), 'placeholder'
            except Exception as fallback_error:
                print(f"图片 {image_index + 1} 占位符生成也失败: {fallback_error}")
                return image_index, False, str(e), 'error'
        else:
            return image_index, False, str(e), 'error'


def main() -> int:
    args = parse_args()

    # 根据 provider 调用不同的生成逻辑
    if args.provider == "gemini":
        if not args.prompt:
            print("Error: --prompt is required for Gemini provider", file=sys.stderr)
            return 1
        return generate_with_gemini(args)

    # Ark provider (default)
    api_key = args.api_key or os.environ.get("ARK_API_KEY")
    if not api_key:
        print("Missing ARK_API_KEY env var or --api-key", file=sys.stderr)
        return 1

    # 检测平台并设置默认比例
    platform = detect_platform_from_path(args.output or "", args.out_dir or "", args.prompts_file or "")
    if platform:
        defaults = get_default_ratios_for_platform(platform)
        args.cover_ratio = defaults['cover']
        args.poster_ratio = defaults['poster']
        print(f"检测到 {platform} 平台，自动设置比例为: 封面 {args.cover_ratio}, 正文 {args.poster_ratio}")

    # 参数兼容：当提供了 --count 参数时，优先使用它
    # 检查是否通过命令行显式传递了 --count（不等于默认值）
    # 如果解析了提示词文件，num_images 会在后面重新计算
    # 这里只在未解析提示词文件时使用 count 或 num_images
    pass  # 这个逻辑在提示词解析后处理

    # Confirm aspect ratio before generating
    if not confirm_aspect_ratio(args.aspect_ratio):
        print("已取消图片生成")
        return 0

    # 如果提供了prompts-file，解析markdown文件
    cover_prompt = ""
    poster_prompts = []
    image_plan = []
    if args.prompts_file:
        image_plan = load_image_plan_from_markdown(args.prompts_file)
        if image_plan:
            print(f"从 {args.prompts_file} 读取到 {len(image_plan)} 个 image_plan 图位")
        cover_prompt, poster_prompts = extract_prompts_from_markdown(args.prompts_file)
        if cover_prompt:
            print(f"从 {args.prompts_file} 解析出封面图提示词")
        if poster_prompts:
            print(f"从 {args.prompts_file} 解析出 {len(poster_prompts)} 个正文图提示词")
            # 重构提示词：场景优先于风格
            poster_prompts = refactored_prompts_for_image_generation(poster_prompts)
            print(f"正文图提示词已重构：场景描述优先于风格描述")
        if not cover_prompt and not poster_prompts:
            print(f"警告：无法从 {args.prompts_file} 解析出提示词，使用默认行为")

    # 单张图片生成（向后兼容）
    # 只有在没有提示词文件且 num_images == 1 时才使用单图路径
    # 有提示词文件时总是走多图路径（便于统一处理封面+正文）
    has_prompts_file = bool(args.prompts_file)
    if not has_prompts_file and args.num_images == 1:
        try:
            client = OpenAI(base_url=args.base_url, api_key=api_key)
            images_response = try_generate_single(client, args, api_key, 0)

            data = images_response["data"][0]
            if args.response_format == "url":
                url = data["url"]
                print(url)
                if args.output:
                    download_url(url, args.output)
            else:
                b64_data = data["b64_json"]
                if args.output:
                    write_b64(b64_data, args.output)
                else:
                    print(b64_data)
        except Exception as e:
            print(f"图片生成失败: {e}")

        # 单图不返回状态码，继续执行后续逻辑（如果有）
        return 0
    else:
        # 多张图片并行生成
        # 计算总图片数：封面图 + 正文图
        num_cover = 1 if cover_prompt else 0
        num_posters = len(poster_prompts) if poster_prompts else args.num_images
        total_images = num_cover + num_posters

        print(f"\n开始并行生成图片：封面 {num_cover} 张 + 正文 {num_posters} 张 = {total_images} 张")

        # 创建输出目录
        output_dir = None
        # 优先使用 --out-dir，其次检查 --output
        if args.out_dir:
            output_dir = Path(args.out_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        elif args.output:
            output_path = Path(args.output)
            if output_path.suffix:  # 是文件路径
                output_dir = output_path.parent
            else:  # 是目录路径
                output_dir = output_path
            output_dir.mkdir(parents=True, exist_ok=True)

        # 动态确定线程数
        max_workers = min(total_images, 5)  # 最多5个并发
        print(f"使用 {max_workers} 个线程并行生成")

        # 使用线程池并行生成
        successful = []
        placeholders = []
        failed = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            futures = []
            task_index = 0

            # 封面图任务（如果存在）
            if cover_prompt:
                cover_filename = f"cover_{args.cover_ratio.replace(':', 'x')}.jpg"
                future = executor.submit(
                    generate_and_save_image,
                    args, api_key, task_index,
                    str(output_dir) if output_dir else None,
                    cover_prompt,
                    cover_filename,
                    args.cover_ratio
                )
                futures.append(future)
                task_index += 1

            # 正文图任务
            for i, prompt in enumerate(poster_prompts if poster_prompts else []):
                poster_filename = f"poster_{i + 1:02d}_{args.poster_ratio.replace(':', 'x')}.jpg"
                future = executor.submit(
                    generate_and_save_image,
                    args, api_key, task_index,
                    str(output_dir) if output_dir else None,
                    prompt,
                    poster_filename,
                    args.poster_ratio
                )
                futures.append(future)
                task_index += 1

            # 收集结果
            for future in as_completed(futures):
                image_index, success, result, img_type = future.result()
                if success:
                    if img_type == 'real':
                        successful.append((image_index, result))
                        print(f"✓ 图片生成成功: {result}")
                    elif img_type == 'placeholder':
                        placeholders.append((image_index, result))
                        print(f"⚠️  图片失败，使用占位符: {result}")
                else:
                    failed.append((image_index, result))
                    print(f"✗ 图片完全失败: {result}")

        print(f"\n生成完成: 真实 {len(successful)} 张, 占位符 {len(placeholders)} 张, 失败 {len(failed)} 张")

        # 生成 handoff.yaml（如果指定了输出目录）
        if args.handoff_out and output_dir:
            try:
                import yaml

                handoff = {
                    "step_id": "09_images",
                    "inputs": ["wechat/08_prompts_handoff.yaml"],
                    "outputs": ["wechat/09_images/", "wechat/09_handoff.yaml"],
                    "summary": f"生成文章配图：真实 {len(successful)} 张, 占位符 {len(placeholders)} 张",
                    "status": "partial_success" if placeholders else ("success" if successful else "failed"),
                    "image_stats": {
                        "real": len(successful),
                        "placeholder": len(placeholders),
                        "failed": len(failed),
                    },
                    "failed_files": [path for idx, path in failed],
                    "placeholder_files": [path for idx, path in placeholders],
                    "next_instructions": [
                        "下一步：md-to-wxhtml 转换为 HTML",
                    ] + ([f"注意：{len(placeholders)} 张图片使用占位符"] if placeholders else []),
                    "open_questions": []
                }

                handoff_path = Path(output_dir) / "../09_handoff.yaml"
                with open(handoff_path, 'w', encoding='utf-8') as f:
                    yaml.dump(handoff, f, allow_unicode=True, default_flow_style=False)
                print(f"✓ handoff.yaml 已生成: {handoff_path}")
            except Exception as e:
                print(f"⚠️  handoff.yaml 生成失败: {e}")

        # 验证输出文件数量
        try:
            validate_outputs(str(output_dir), total_images)
            print(f"✓ 输出验证通过：{total_images} 张图片")
        except RuntimeError as e:
            print(f"✗ {e}")
            return 1

        # 返回状态码（有完全失败时返回非零）
        if len(failed) > 0:
            return 1

        # 插入图片到 Markdown 文件
        if args.insert_into and successful:
            insert_images_to_markdown(args.insert_into, output_dir, len(successful), image_plan=image_plan)

        return 0


def insert_images_to_markdown(markdown_path: str, images_dir: str, image_count: int, image_plan: list[dict] | None = None) -> bool:
    """将生成的图片插入到 Markdown 文件。

    优先级：
    1. image_plan 图位元数据（insert_after / insert_after_heading）
    2. 旧的顺序插图策略（H1 后 + 各章节后）
    """
    md_path = Path(markdown_path)
    if not md_path.exists():
        print(f"❌  Markdown 文件不存在: {md_path}", file=sys.stderr)
        return False

    content = md_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    try:
        img_dir = Path(images_dir).relative_to(md_path.parent)
    except ValueError:
        # 图片目录不在 markdown 父目录下，使用目录名
        img_dir = Path(Path(images_dir).name)

    img_files = sorted(Path(images_dir).glob("*.jpg"))

    if not img_files:
        print(f"⚠️  未找到图片文件在: {images_dir}")
        return False

    slots = build_image_slots(img_files, image_plan or [])
    section_headings = [i for i, line in enumerate(lines) if line.startswith("## ")]
    section_cursor = 0
    insert_positions = []

    for slot in slots[:image_count]:
        pos = None
        if slot.get("insert_after_heading"):
            pos = find_insert_line_after_heading(lines, slot["insert_after_heading"])
        if pos is None and slot.get("insert_after"):
            pos = find_insert_line_after_text(lines, slot["insert_after"])

        if pos is None:
            if slot.get("role") == "cover":
                # 封面图片插入到一级标题后
                for i, line in enumerate(lines):
                    if line.startswith("# "):
                        pos = i + 1
                        while pos < len(lines) and not lines[pos].strip():
                            pos += 1
                        break
            else:
                if section_cursor < len(section_headings):
                    heading_line = section_headings[section_cursor]
                    section_title = lines[heading_line].replace("## ", "").strip()
                    slot["label"] = slot.get("label") or section_title
                    pos = heading_line + 1
                    while pos < len(lines) and not lines[pos].strip():
                        pos += 1
                    section_cursor += 1

        if pos is None:
            pos = len(lines)

        rel_path = img_dir / slot["file"].name
        img_ref = f"\n![{slot.get('label') or '配图'}]({rel_path})\n"
        # 检查是否已存在该图片引用（使用 markdown 图片语法检查）
        img_markdown = f"]({rel_path})"
        if img_markdown in content:
            print(f"  ℹ️  图片已存在，跳过: {rel_path}")
            continue
        insert_positions.append((pos, img_ref))

    insert_positions.sort(key=lambda x: x[0], reverse=True)
    for pos, img_ref in insert_positions:
        lines.insert(pos, img_ref)

    try:
        md_path.write_text("\n".join(lines), encoding="utf-8")
        mode = "image_plan" if image_plan else "fallback"
        print(f"✓ 已插入 {len(insert_positions)} 张图片到 {md_path.name}（模式: {mode}）")
        return True
    except IOError as e:
        print(f"❌  写入 Markdown 文件失败: {e}", file=sys.stderr)
        return False



def generate_with_gemini(args: argparse.Namespace) -> int:
    """使用 Gemini 3 Pro Image 生成图片"""
    # 获取 API key
    api_key = (
        os.environ.get("NANO_BANANA_PRO_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
    )
    if not api_key:
        print("Error: No Gemini API key provided.", file=sys.stderr)
        print("Please set NANO_BANANA_PRO_API_KEY or GEMINI_API_KEY env var", file=sys.stderr)
        return 1

    try:
        from google import genai
        from google.genai import types
        from PIL import Image as PILImage
    except ImportError:
        print("Error: google-genai or pillow not installed.", file=sys.stderr)
        print("Run: pip install google-genai pillow", file=sys.stderr)
        return 1

    # 初始化客户端
    client = genai.Client(api_key=api_key)

    # 设置输出路径
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path("output.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 加载输入图片（编辑/合成模式）
    input_images = []
    max_input_dim = 0
    if args.input_images:
        if len(args.input_images) > 14:
            print(f"Error: Too many input images ({len(args.input_images)}). Maximum is 14.", file=sys.stderr)
            return 1

        for img_path in args.input_images:
            try:
                with PILImage.open(img_path) as img:
                    copied = img.copy()
                    width, height = copied.size
                input_images.append(copied)
                print(f"Loaded input image: {img_path}")
                max_input_dim = max(max_input_dim, width, height)
            except Exception as e:
                print(f"Error loading input image '{img_path}': {e}", file=sys.stderr)
                return 1

    # 确定分辨率
    resolution = args.resolution
    if resolution is None:
        if input_images and max_input_dim > 0:
            if max_input_dim >= 3000:
                resolution = "4K"
            elif max_input_dim >= 1500:
                resolution = "2K"
            else:
                resolution = "1K"
            print(f"Auto-detected resolution: {resolution} (from max input dimension {max_input_dim})")
        else:
            resolution = "1K"

    # 构建内容
    if input_images:
        contents = [*input_images, args.prompt]
        img_count = len(input_images)
        print(f"Processing {img_count} image{'s' if img_count > 1 else ''} with resolution {resolution}...")
    else:
        contents = args.prompt
        print(f"Generating image with resolution {resolution}...")

    try:
        # 构建图片配置
        image_cfg_kwargs = {"image_size": resolution}
        if args.aspect_ratio:
            image_cfg_kwargs["aspect_ratio"] = args.aspect_ratio

        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                image_config=types.ImageConfig(**image_cfg_kwargs)
            )
        )

        # 处理响应
        image_saved = False
        for part in response.parts:
            if part.text is not None:
                print(f"Model response: {part.text}")
            elif part.inline_data is not None:
                from io import BytesIO

                image_data = part.inline_data.data
                if isinstance(image_data, str):
                    image_data = base64.b64decode(image_data)

                image = PILImage.open(BytesIO(image_data))

                # 确保 RGB 模式
                if image.mode == 'RGBA':
                    rgb_image = PILImage.new('RGB', image.size, (255, 255, 255))
                    rgb_image.paste(image, mask=image.split()[3])
                    rgb_image.save(str(output_path), 'PNG')
                elif image.mode == 'RGB':
                    image.save(str(output_path), 'PNG')
                else:
                    image.convert('RGB').save(str(output_path), 'PNG')
                image_saved = True

        if image_saved:
            full_path = output_path.resolve()
            print(f"\nImage saved: {full_path}")
            print(f"MEDIA:{full_path}")
            return 0
        else:
            print("Error: No image was generated in the response.", file=sys.stderr)
            return 1

    except Exception as e:
        print(f"Error generating image: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
