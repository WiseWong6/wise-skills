#!/usr/bin/env python3
"""
微信订阅号草稿箱管理工具 - 非交互版本
支持创建草稿、更新草稿、自动上传图片等功能
"""
import argparse
import json
import mimetypes
import os
import re
import ssl
import sys
import uuid
from pathlib import Path
from typing import Dict, Tuple, List, Optional, Union
from urllib import parse, request
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# 创建禁用SSL验证的context（仅用于开发环境）
SSL_CONTEXT = ssl._create_unverified_context()

TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
ADD_MATERIAL_URL = "https://api.weixin.qq.com/cgi-bin/material/add_material"
UPLOADIMG_URL = "https://api.weixin.qq.com/cgi-bin/media/uploadimg"
DRAFT_URL = "https://api.weixin.qq.com/cgi-bin/draft/add"
DRAFT_UPDATE_URL = "https://api.weixin.qq.com/cgi-bin/draft/update"


def get_account_config(account: str) -> tuple[str, str]:
    """获取指定账号的appid和secret
    account: main（歪斯Wise）/ sub（人类）
    """
    if not account:
        raise RuntimeError("--account 参数必填（main/sub）")

    suffix_map = {"main": "MAIN", "sub": "SUB"}
    env_suffix = suffix_map.get(account.lower())

    if not env_suffix:
        raise RuntimeError(f"无效的账号: {account}。必须是 'main' 或 'sub'")

    # 优先尝试有后缀的变量
    appid = os.environ.get(f"WECHAT_APPID_{env_suffix}")
    secret = os.environ.get(f"WECHAT_APPSECRET_{env_suffix}")

    # 回退到无后缀变量（兼容性）
    if not appid:
        appid = os.environ.get("WECHAT_APPID")
    if not secret:
        secret = os.environ.get("WECHAT_APPSECRET")

    if not appid or not secret:
        missing = []
        if not appid:
            missing.append(f"WECHAT_APPID_{env_suffix}")
        if not secret:
            missing.append(f"WECHAT_APPSECRET_{env_suffix}")
        raise RuntimeError(f"缺少公众号环境变量: {', '.join(missing)}")

    account_name = {"main": "歪斯Wise", "sub": "人类"}.get(account.lower(), account)
    print(f"使用公众号: {account_name} ({appid})")
    return appid, secret


def check_wechat_error(payload: Dict) -> None:
    if payload.get("errcode"):
        raise RuntimeError(f"微信接口错误: {payload}")


def get_json(url: str, timeout: int = 15) -> Dict:
    with request.urlopen(url, timeout=timeout, context=SSL_CONTEXT) as resp:
        return json.load(resp)


def post_json(url: str, payload: Dict, timeout: int = 30) -> Dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    req.add_header("Content-Length", str(len(body)))
    with request.urlopen(req, timeout=timeout, context=SSL_CONTEXT) as resp:
        return json.load(resp)


def build_multipart(field_name: str, filename: str, content_type: str, data: bytes) -> Tuple[bytes, str]:
    boundary = f"----CodexBoundary{uuid.uuid4().hex}"
    parts = [
        f"--{boundary}\r\n".encode("utf-8"),
        (
            f"Content-Disposition: form-data; name=\"{field_name}\"; "
            f"filename=\"{filename}\"\r\n"
        ).encode("utf-8"),
        f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
        data,
        f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ]
    return b"".join(parts), boundary


def post_multipart(url: str, body: bytes, boundary: str, timeout: int = 30) -> Dict:
    req = request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Content-Length", str(len(body)))
    with request.urlopen(req, timeout=timeout, context=SSL_CONTEXT) as resp:
        return json.load(resp)


def get_access_token(appid: str, secret: str) -> str:
    params = {"grant_type": "client_credential", "appid": appid, "secret": secret}
    payload = get_json(f"{TOKEN_URL}?{parse.urlencode(params)}")
    check_wechat_error(payload)
    token = payload.get("access_token")
    if not token:
        raise RuntimeError(f"无法获取 access_token: {payload}")
    return token


def upload_permanent_image(access_token: str, image_path: Path) -> str:
    """上传图片为永久素材（newspic类型使用）"""
    mime = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"
    body, boundary = build_multipart("media", image_path.name, mime, image_path.read_bytes())
    params = {"access_token": access_token, "type": "image"}
    payload = post_multipart(f"{ADD_MATERIAL_URL}?{parse.urlencode(params)}", body, boundary)
    check_wechat_error(payload)
    media_id = payload.get("media_id")
    if not media_id:
        raise RuntimeError(f"上传图片失败: {payload}")
    return media_id


def upload_permanent_thumb(access_token: str, image_path: Path) -> str:
    """上传封面为永久素材（news类型使用）"""
    mime = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"
    body, boundary = build_multipart("media", image_path.name, mime, image_path.read_bytes())
    params = {"access_token": access_token, "type": "thumb"}
    payload = post_multipart(f"{ADD_MATERIAL_URL}?{parse.urlencode(params)}", body, boundary)
    check_wechat_error(payload)
    media_id = payload.get("media_id")
    if not media_id:
        raise RuntimeError(f"上传封面失败: {payload}")
    return media_id


def upload_content_image(access_token: str, image_path: Path) -> str:
    """上传正文中图片，返回临时URL"""
    mime = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"
    body, boundary = build_multipart("media", image_path.name, mime, image_path.read_bytes())
    params = {"access_token": access_token}
    payload = post_multipart(f"{UPLOADIMG_URL}?{parse.urlencode(params)}", body, boundary)
    check_wechat_error(payload)
    url = payload.get("url")
    if not url:
        raise RuntimeError(f"上传图文图片失败: {payload}")
    return url


def replace_local_images(access_token: str, content_html: str, html_dir: Path) -> Tuple[str, Dict[str, str]]:
    """替换正文中的本地图片为微信URL"""
    img_pattern = re.compile(r'<img[^>]+src=([\'"])([^\'"]+)\1[^>]*>', re.IGNORECASE)
    cache: Dict[str, str] = {}

    def replace(match: re.Match) -> str:
        src = match.group(2)
        # 检查是否已经是微信 CDN URL（避免重复上传）
        if src.startswith(("http://", "https://", "data:")) or src.startswith("mmbiz"):
            return match.group(0)

        local_path = Path(src)
        if not local_path.is_absolute():
            local_path = (html_dir / local_path).resolve()

        if not local_path.exists():
            raise RuntimeError(f"找不到图片文件: {local_path}")

        key = str(local_path)
        if key not in cache:
            print(f"  上传图片: {local_path.name}")
            cache[key] = upload_content_image(access_token, local_path)

        return match.group(0).replace(src, cache[key])

    updated = img_pattern.sub(replace, content_html)
    return updated, cache


def convert_markdown_to_html(markdown_path: Path) -> str:
    """将Markdown转换为HTML"""
    try:
        import markdown
    except ImportError:
        raise RuntimeError("需要安装 markdown 库: pip install markdown")

    md_text = markdown_path.read_text(encoding="utf-8")
    html = markdown.markdown(
        md_text,
        extensions=[
            'markdown.extensions.extra',
            'markdown.extensions.codehilite',
            'markdown.extensions.tables',
            'markdown.extensions.toc'
        ]
    )
    return html


def create_draft(access_token: str, article: Dict) -> Dict:
    payload = post_json(f"{DRAFT_URL}?{parse.urlencode({'access_token': access_token})}", {"articles": [article]})
    check_wechat_error(payload)
    return payload


def update_draft(access_token: str, media_id: str, index: int, article: Dict) -> Dict:
    """更新草稿"""
    payload = {
        "media_id": media_id,
        "index": index,
        "articles": article
    }
    result = post_json(f"{DRAFT_UPDATE_URL}?{parse.urlencode({'access_token': access_token})}", payload)
    check_wechat_error(result)
    return result


def parse_crop_coord(crop_str: Optional[str]) -> Optional[Dict[str, str]]:
    """解析裁剪坐标字符串: X1_Y1_X2_Y2"""
    if not crop_str:
        return None
    parts = crop_str.split("_")
    if len(parts) != 4:
        raise ValueError(f"裁剪坐标格式错误，应为 X1_Y1_X2_Y2: {crop_str}")
    return {
        "x1": parts[0],
        "y1": parts[1],
        "x2": parts[2],
        "y2": parts[3]
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="微信订阅号草稿箱管理工具 - 非交互版本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 1. 从Markdown创建草稿（自动转换并上传图片）
  python wechat_draftbox_v2.py \
    --account main \
    --title "文章标题" \
    --markdown article.md \
    --cover-image cover.png \
    --out draft_result.json

  # 2. 从HTML创建草稿（自动上传正文图片）
  python wechat_draftbox_v2.py \
    --account sub \
    --title "文章标题" \
    --content-html article.html \
    --cover-image cover.png \
    --out draft_result.json

  # 3. 更新已存在的草稿
  python wechat_draftbox_v2.py \
    --account main \
    --media-id MEDIA_ID \
    --title "更新后的标题" \
    --markdown article.md \
    --out draft_result.json

环境变量:
  WECHAT_APPID_MAIN / WECHAT_APPSECRET_MAIN    # 主公众号（歪斯Wise）
  WECHAT_APPID_SUB / WECHAT_APPSECRET_SUB      # 副业公众号（人类）
        """
    )

    # 操作模式
    parser.add_argument("--media-id", help="草稿ID（用于更新现有草稿）")

    # 内容源（互斥）
    content_group = parser.add_mutually_exclusive_group(required=True)
    content_group.add_argument("--content-html", help="HTML 文件路径")
    content_group.add_argument("--markdown", help="Markdown 文件路径（自动转换为HTML）")

    # 基本参数
    parser.add_argument("--title", required=True, help="文章标题")
    parser.add_argument("--author", help="作者（默认：公众号名称）")
    parser.add_argument("--digest", default="", help="摘要（news类型有效）")
    parser.add_argument("--content-source-url", default="", help="原文链接（news类型有效）")

    # 评论设置
    parser.add_argument("--need-open-comment", dest="need_open_comment", action="store_true", help="开启评论")
    parser.add_argument("--no-open-comment", dest="need_open_comment", action="store_false", help="关闭评论")
    parser.set_defaults(need_open_comment=True)
    parser.add_argument("--only-fans-can-comment", action="store_true", help="仅粉丝可评论（需开启评论）")

    # 文章类型
    parser.add_argument("--article-type", default="news", choices=["news", "newspic"],
                        help="文章类型：news=图文消息（默认）, newspic=图片消息")

    # 账号（必填）
    parser.add_argument("--account", choices=["main", "sub"], required=True,
                        help="公众号账号：main=歪斯Wise, sub=人类")

    # news 类型参数
    parser.add_argument("--cover-image", help="封面图片路径（news类型，用于生成永久素材）")
    parser.add_argument("--thumb-media-id", help="已有封面永久素材 media_id（news类型）")
    parser.add_argument("--pic-crop-235-1", help="封面裁剪为2.35:1的坐标 X1_Y1_X2_Y2（news类型）")
    parser.add_argument("--pic-crop-1-1", help="封面裁剪为1:1的坐标 X1_Y1_X2_Y2（news类型）")

    # newspic 类型参数
    parser.add_argument("--images", nargs="+", help="图片文件路径列表（newspic类型，最多20张）")
    parser.add_argument("--image-media-ids", nargs="+", help="已有图片永久素材 media_id 列表（newspic类型）")

    # 图片处理
    parser.add_argument("--no-upload-images", dest="upload_images", action="store_false",
                        help="不上传正文中的本地图片（默认自动上传）")
    parser.set_defaults(upload_images=True)

    # 输出
    parser.add_argument("--out", help="输出结果 JSON 文件")
    parser.add_argument("--verbose", action="store_true", help="显示详细日志")

    args = parser.parse_args()

    try:
        # 获取账号配置
        appid, secret = get_account_config(args.account)
        access_token = get_access_token(appid, secret)

        # 处理内容源
        if args.markdown:
            if args.verbose:
                print(f"正在转换 Markdown: {args.markdown}")
            content_html = convert_markdown_to_html(Path(args.markdown))
            html_dir = Path(args.markdown).parent
        else:
            content_path = Path(args.content_html)
            if not content_path.exists():
                raise RuntimeError(f"HTML 文件不存在: {content_path}")
            content_html = content_path.read_text(encoding="utf-8")
            html_dir = content_path.parent

        # 自动上传正文图片
        content_image_urls: Dict[str, str] = {}
        if args.upload_images and args.article_type == "news":
            if args.verbose:
                print("正在扫描并上传正文图片...")
            content_html, content_image_urls = replace_local_images(access_token, content_html, html_dir)
            if content_image_urls and args.verbose:
                print(f"  已上传 {len(content_image_urls)} 张图片")

        # 设置默认作者
        if not args.author:
            args.author = "歪斯Wise" if args.account == "main" else "人类"

        # 构建文章对象
        article = {
            "article_type": args.article_type,
            "title": args.title,
            "author": args.author,
            "need_open_comment": 1 if args.need_open_comment else 0,
            "only_fans_can_comment": 1 if args.only_fans_can_comment else 0,
        }

        if args.article_type == "news":
            # 图文消息类型
            article["content"] = content_html
            article["digest"] = args.digest
            article["content_source_url"] = args.content_source_url

            # 处理封面
            thumb_media_id = args.thumb_media_id
            if not thumb_media_id and not args.cover_image:
                # 更新模式：不强制要求封面（使用现有草稿的封面）
                thumb_media_id = None
            elif not thumb_media_id and args.cover_image:
                # 创建模式：上传新封面
                cover_path = Path(args.cover_image)
                if not cover_path.exists():
                    raise RuntimeError(f"封面文件不存在: {cover_path}")
                if args.verbose:
                    print(f"正在上传封面: {cover_path.name}")
                thumb_media_id = upload_permanent_thumb(access_token, cover_path)

            if thumb_media_id:
                article["thumb_media_id"] = thumb_media_id

            # 封面裁剪参数
            crop_235_1 = parse_crop_coord(args.pic_crop_235_1)
            crop_1_1 = parse_crop_coord(args.pic_crop_1_1)
            if crop_235_1:
                article["pic_crop_235_1"] = crop_235_1
            if crop_1_1:
                article["pic_crop_1_1"] = crop_1_1

        elif args.article_type == "newspic":
            # 图片消息类型
            article["content"] = content_html

            # 处理图片列表
            image_media_ids = args.image_media_ids or []

            if args.images:
                if len(args.images) > 20:
                    raise RuntimeError("newspic类型最多支持20张图片")
                for img_path in args.images:
                    path = Path(img_path)
                    if not path.exists():
                        raise RuntimeError(f"图片文件不存在: {path}")
                    if args.verbose:
                        print(f"正在上传图片: {path.name}")
                    media_id = upload_permanent_image(access_token, path)
                    image_media_ids.append(media_id)

            if len(image_media_ids) == 0:
                raise RuntimeError("newspic类型需要 --images 或 --image-media-ids")

            article["image_info"] = {
                "image_list": [{"image_media_id": mid} for mid in image_media_ids]
            }

            # newspic类型不支持digest和content_source_url
            if args.digest or args.content_source_url:
                print("注意：newspic类型不支持 digest 和 content_source_url 参数")

        # 执行操作
        if args.media_id:
            # 更新草稿
            if args.verbose:
                print(f"正在更新草稿: {args.media_id}")
            result = update_draft(access_token, args.media_id, 0, article)
            action = "updated"
        else:
            # 创建草稿
            if args.verbose:
                print("正在创建草稿...")
            result = create_draft(access_token, article)
            action = "created"

        # 构建输出
        output = {
            "action": action,
            "article_type": args.article_type,
            "draft_media_id": result.get("media_id"),
            "result": result,
        }

        if args.article_type == "news":
            output["thumb_media_id"] = article.get("thumb_media_id")
        if args.article_type == "newspic":
            output["image_media_ids"] = [item["image_media_id"] for item in article["image_info"]["image_list"]]

        if content_image_urls:
            output["content_image_urls"] = content_image_urls

        # 打印结果
        print(json.dumps(output, ensure_ascii=False, indent=2))

        # 保存到文件
        if args.out:
            Path(args.out).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
            if args.verbose:
                print(f"结果已保存到: {args.out}")

        return 0

    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
