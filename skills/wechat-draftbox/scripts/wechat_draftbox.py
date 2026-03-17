#!/usr/bin/env python3
"""
微信订阅号草稿箱管理工具
支持创建草稿、更新草稿、自动上传图片等功能

支持 SSH 中继模式：通过固定 IP 服务器转发请求，解决本地 IP 变化导致的白名单问题
"""
import argparse
import json
import mimetypes
import os
import re
import shlex
import ssl
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Tuple, List, Optional, Union, Any
from urllib import parse, request

# 创建禁用SSL验证的context（仅用于开发环境）
SSL_CONTEXT = ssl._create_unverified_context()

TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
ADD_MATERIAL_URL = "https://api.weixin.qq.com/cgi-bin/material/add_material"
UPLOADIMG_URL = "https://api.weixin.qq.com/cgi-bin/media/uploadimg"
DRAFT_URL = "https://api.weixin.qq.com/cgi-bin/draft/add"
DRAFT_UPDATE_URL = "https://api.weixin.qq.com/cgi-bin/draft/update"

# 中继配置
RELAY_CONFIG_PATH = Path.home() / ".claude" / "skills" / "wechat-relay" / "config.yaml"


# ============== SSH 中继功能 ==============

def load_relay_config() -> Dict:
    """加载中继配置"""
    if not RELAY_CONFIG_PATH.exists():
        return {"relay": {"enabled": False}}

    config = {"relay": {"enabled": False}}
    try:
        with open(RELAY_CONFIG_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        if "enabled: true" in content:
            config["relay"]["enabled"] = True

        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("host:"):
                config["relay"]["host"] = line.split(":", 1)[1].strip().strip('"')
            elif line.startswith("user:"):
                config["relay"]["user"] = line.split(":", 1)[1].strip().strip('"')
            elif line.startswith("key_path:"):
                config["relay"]["key_path"] = line.split(":", 1)[1].strip().strip('"')
            elif line.startswith("work_dir:"):
                config["relay"]["work_dir"] = line.split(":", 1)[1].strip().strip('"')
    except Exception:
        pass

    return config


def is_relay_enabled(cli_relay: Optional[bool] = None) -> bool:
    """判断是否启用中继"""
    if cli_relay is not None:
        return cli_relay
    config = load_relay_config()
    return config.get("relay", {}).get("enabled", False)


def get_relay_config() -> Tuple[str, str, str, str]:
    """获取中继配置: (host, user, key_path, work_dir)"""
    config = load_relay_config()
    relay = config.get("relay", {})
    host = relay.get("host", "")
    user = relay.get("user", "root")
    key_path = relay.get("key_path", "")
    work_dir = relay.get("work_dir", "/tmp/wechat_relay")

    if not host or not key_path:
        raise RuntimeError("中继配置不完整，请检查 ~/.claude/skills/wechat-relay/config.yaml")

    return host, user, key_path, work_dir


def ssh_exec(host: str, user: str, key_path: str, cmd: str, verbose: bool = False) -> Tuple[int, str, str]:
    """执行 SSH 命令"""
    ssh_cmd = ["ssh", "-i", key_path, "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10", f"{user}@{host}", cmd]
    if verbose:
        print(f"[SSH] {cmd[:80]}...")
    result = subprocess.run(ssh_cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def scp_upload(host: str, user: str, key_path: str, local: str, remote: str, verbose: bool = False) -> bool:
    """上传文件"""
    cmd = ["scp", "-i", key_path, "-o", "StrictHostKeyChecking=no", local, f"{user}@{host}:{remote}"]
    if verbose:
        print(f"[SCP] {local} -> {remote}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def scp_download(host: str, user: str, key_path: str, remote: str, local: str, verbose: bool = False) -> bool:
    """下载文件"""
    cmd = ["scp", "-i", key_path, "-o", "StrictHostKeyChecking=no", f"{user}@{host}:{remote}", local]
    if verbose:
        print(f"[SCP] {remote} -> {local}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def execute_via_relay(
    script_path: str,
    args: List[str],
    upload_files: List[str],
    output_file: str,
    verbose: bool = False
) -> Tuple[int, str]:
    """通过 SSH 中继执行脚本"""
    host, user, key_path, work_dir = get_relay_config()

    if verbose:
        print(f"[中继] 服务器: {host}")
        print(f"[中继] 工作目录: {work_dir}")

    # 1. 创建远程目录
    ssh_exec(host, user, key_path, f"mkdir -p {work_dir}", verbose)

    # 2. 上传脚本
    script_name = Path(script_path).name
    remote_script = f"{work_dir}/{script_name}"
    if not scp_upload(host, user, key_path, script_path, remote_script, verbose):
        raise RuntimeError("上传脚本失败")

    # 3. 上传文件
    for local_file in upload_files:
        local_path = Path(local_file)
        if not local_path.exists():
            raise RuntimeError(f"文件不存在: {local_file}")
        remote_file = f"{work_dir}/{local_path.name}"
        if not scp_upload(host, user, key_path, str(local_path), remote_file, verbose):
            raise RuntimeError(f"上传文件失败: {local_file}")

    # 4. 构建远程命令（替换路径）
    remote_args = []
    for arg in args:
        if arg.startswith("/") and Path(arg).exists():
            remote_args.append(f"{work_dir}/{Path(arg).name}")
        else:
            remote_args.append(arg)

    # 输出文件使用远程路径
    remote_output = f"{work_dir}/output.json"

    # 构建环境变量导出（传递微信相关环境变量到远程）
    env_exports = []
    for env_key in ["WECHAT_APPID_MAIN", "WECHAT_APPSECRET_MAIN",
                    "WECHAT_APPID_SUB", "WECHAT_APPSECRET_SUB",
                    "WECHAT_APPID", "WECHAT_APPSECRET"]:
        env_val = os.environ.get(env_key)
        if env_val:
            env_exports.append(f"export {env_key}={shlex.quote(env_val)}")

    env_prefix = " && ".join(env_exports) + " && " if env_exports else ""

    # 使用 shlex.quote 对参数进行转义，处理空格和特殊字符
    quoted_args = [shlex.quote(arg) for arg in remote_args]
    # 从远程 .bashrc 提取 WECHAT 相关变量（绕过非交互模式 return 问题）
    # .bashrc 开头的 [ -z "$PS1" ] && return 会跳过环境变量定义
    extract_wechat_vars = "eval $(grep -E '^export WECHAT_' ~/.bashrc 2>/dev/null || true); "
    cmd = f"{extract_wechat_vars}cd {work_dir} && {env_prefix}python3 {script_name} {' '.join(quoted_args)} --out {remote_output}"
    returncode, stdout, stderr = ssh_exec(host, user, key_path, cmd, verbose)

    if verbose and stderr:
        print(f"[SSH] stderr: {stderr}")

    # 5. 下载结果
    local_output = tempfile.mktemp(suffix=".json")
    output_content = stdout
    if scp_download(host, user, key_path, remote_output, local_output, verbose):
        with open(local_output, "r", encoding="utf-8") as f:
            output_content = f.read()
        os.unlink(local_output)

    return returncode, output_content


def get_account_config(account: str) -> tuple[str, str]:
    """获取指定账号的appid和secret
    account: main（歪斯Wise），默认）/ sub（副业）
    """
    suffix_map = {"main": "MAIN", "sub": "SUB"}
    env_suffix = suffix_map.get(account.lower(), "MAIN")

    # 优先尝试有后缀的变量
    appid = os.environ.get(f"WECHAT_APPID_{env_suffix}")
    secret = os.environ.get(f"WECHAT_APPSECRET_{env_suffix}")

    # 回退到无后缀变量（兼容性）
    if not appid:
        appid = os.environ.get("WECHAT_APPID")
    if not secret:
        secret = os.environ.get("WECHAT_APPSECRET")

    # 对于 main 账号，也尝试无后缀变量作为备选
    if account.lower() == "main" and not appid:
        appid = os.environ.get("WECHAT_APPID")
        secret = os.environ.get("WECHAT_APPSECRET")

    if not appid or not secret:
        # 提供更友好的错误信息
        main_appid = os.environ.get("WECHAT_APPID_MAIN")
        main_secret = os.environ.get("WECHAT_APPSECRET_MAIN")
        sub_appid = os.environ.get("WECHAT_APPID_SUB")
        sub_secret = os.environ.get("WECHAT_APPSECRET_SUB")

        missing_vars = []
        if account.lower() == "main":
            if appid is None:
                if main_appid:
                    missing_vars.append("WECHAT_APPID_MAIN")
                else:
                    missing_vars.append("WECHAT_APPID")
            if secret is None:
                if main_secret:
                    missing_vars.append("WECHAT_APPSECRET_MAIN")
                else:
                    missing_vars.append("WECHAT_APPSECRET")
        elif account.lower() == "sub":
            if appid is None:
                if sub_appid:
                    missing_vars.append("WECHAT_APPID_SUB")
                else:
                    missing_vars.append("WECHAT_APPID")
            if secret is None:
                if sub_secret:
                    missing_vars.append("WECHAT_APPSECRET_SUB")
                else:
                    missing_vars.append("WECHAT_APPSECRET")

        raise RuntimeError(f"缺少公众号环境变量: {', '.join(missing_vars)}")

    # 根据实际 appid 判断公众号名称
    account_names = {
        "wx2a1acad6ced44ddc": "人类是我的副业",
        "wx1fb9341ba4c7cc73": "歪斯Wise"
    }
    account_name = account_names.get(appid, account)
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


def get_access_token(appid: str, secret: str) -> str:
    params = {"grant_type": "client_credential", "appid": appid, "secret": secret}
    url = f"{TOKEN_URL}?grant_type=client_credential&appid={appid}&secret={secret}"
    payload = get_json(url)
    check_wechat_error(payload)
    token = payload.get("access_token")
    if not token:
        raise RuntimeError(f"无法获取 access_token: {payload}")
    return token


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


def replace_local_images(access_token: str, content_html: str, content_base_dir: Path, verbose: bool = False) -> Tuple[str, Dict[str, str]]:
    """替换正文中的本地图片为微信URL

    Args:
        access_token: 微信访问令牌
        content_html: HTML内容
        content_base_dir: 内容基准目录，用于解析相对路径
        verbose: 是否显示详细日志
    """
    img_pattern = re.compile(r'<img[^>]+src=([\'"])([^\'"]+)\1[^>]*>', re.IGNORECASE)
    cache: Dict[str, str] = {}

    if verbose:
        print(f"[路径解析] 内容基准目录: {content_base_dir}")

    def replace(match: re.Match) -> str:
        src = match.group(2)
        # 检查是否已经是微信 CDN URL（避免重复上传）
        if src.startswith(("http://", "https://", "data:")) or src.startswith("mmbiz"):
            if verbose:
                print(f"[图片] 跳过远程URL: {src[:50]}...")
            return match.group(0)

        local_path = Path(src)
        if not local_path.is_absolute():
            # 解析相对路径
            resolved_path = (content_base_dir / local_path).resolve()
            if verbose:
                print(f"[路径] 相对路径 {src} → {resolved_path}")
            local_path = resolved_path

        if not local_path.exists():
            # 改进错误消息，显示期望的文件位置
            raise RuntimeError(
                f"找不到图片文件\n"
                f"  原始路径: {src}\n"
                f"  解析路径: {local_path}\n"
                f"  基准目录: {content_base_dir}"
            )

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


def remove_h1_from_html(content_html: str) -> str:
    """移除正文中的第一个 h1 标签

    微信公众号有独立的标题字段，正文中不需要重复显示标题。
    此函数始终执行，无论标题是手动指定还是自动提取。
    """
    # 移除第一个 h1 标签
    content = re.sub(r'<h1[^>]*>.*?</h1>', '', content_html, count=1, flags=re.IGNORECASE | re.DOTALL)
    return content.strip()


def generate_digest(content_html: str, max_length: int = 120) -> str:
    """从 HTML 内容中提取或生成摘要

    策略：
    1. 提取第一个正文段落（<h3> 之后的第一个 <p>）
    2. 跳过引导文案（包含星标或特定关键词）
    3. 如果内容太短，返回空字符串（微信会自动截取）
    """
    from html.parser import HTMLParser

    # 需要跳过的关键词
    SKIP_KEYWORDS = ['关注星标', '⭐️', '收看AI实战', '收看AI、商业新知']

    class TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.text_parts = []
            self.in_p = False
            self.found_first_h3 = False  # 是否找到第一个 h3 标签

        def handle_starttag(self, tag, attrs):
            if tag == 'h3':
                self.found_first_h3 = True
            elif tag == 'p':
                self.in_p = True

        def handle_endtag(self, tag):
            if tag == 'p':
                self.in_p = False

        def handle_data(self, data):
            # 只在找到第一个 h3 之后才提取内容
            if not self.found_first_h3:
                return

            if self.in_p:
                text = data.strip()
                if text and len(text) > 10:  # 忽略太短的段落
                    # 检查是否包含需要跳过的关键词
                    should_skip = any(kw in text for kw in SKIP_KEYWORDS)
                    if not should_skip:
                        self.text_parts.append(text)

    extractor = TextExtractor()
    extractor.feed(content_html)

    if extractor.text_parts:
        # 取第一个有意义的段落
        first_para = extractor.text_parts[0]
        # 清理多余空白
        first_para = re.sub(r'\s+', ' ', first_para)
        # 截取前 max_length 字符
        if len(first_para) > max_length:
            return first_para[:max_length] + '...'
        return first_para

    return ""


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
        description="微信订阅号草稿箱管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 1. 从Markdown创建草稿（自动转换并上传图片）
  python wechat_draftbox.py \\
    --account sub \\
    --title "文章标题" \\
    --markdown article.md \\
    --cover-image cover.png

  # 2. 从HTML创建草稿（自动上传正文图片）
  python wechat_draftbox.py \\
    --account sub \\
    --title "文章标题" \\
    --content-html article.html \\
    --cover-image cover.png

  # 3. 更新已存在的草稿
  python wechat_draftbox.py \\
    --account sub \\
    --media-id MEDIA_ID \\
    --title "更新后的标题" \\
    --markdown article.md

  # 4. 创建图片消息
  python wechat_draftbox.py \\
    --account sub \\
    --article-type newspic \\
    --title "图片消息" \\
    --images img1.jpg img2.jpg img3.jpg

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

    # 多账号支持
    parser.add_argument("--account", choices=["main", "sub"],
                        help="公众号账号：main=歪斯Wise, sub=副业（人类）；不指定时将询问用户选择")

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

    # SSH 中继选项
    parser.add_argument("--relay", action="store_true", default=None,
                        help="使用 SSH 中继（通过固定 IP 服务器转发请求）")
    parser.add_argument("--no-relay", dest="relay", action="store_false",
                        help="禁用 SSH 中继")

    args = parser.parse_args()

    # ============== SSH 中继模式 ==============
    use_relay = is_relay_enabled(args.relay)

    if use_relay:
        if args.verbose:
            print("[中继模式] 通过 SSH 中继执行")

        # 收集需要上传的文件
        upload_files = []
        if args.cover_image:
            upload_files.append(args.cover_image)
        if args.content_html:
            upload_files.append(args.content_html)
        if args.markdown:
            upload_files.append(args.markdown)
        if args.images:
            upload_files.extend(args.images)

        # 获取当前脚本路径
        script_path = Path(__file__).resolve()

        # 构建参数（添加 --no-relay 防止远程再中继）
        relay_args = ["--account", args.account, "--no-relay", "--title", args.title]

        if args.content_html:
            relay_args.extend(["--content-html", args.content_html])
        if args.markdown:
            relay_args.extend(["--markdown", args.markdown])
        if args.media_id:
            relay_args.extend(["--media-id", args.media_id])
        if args.article_type:
            relay_args.extend(["--article-type", args.article_type])
        if args.author:
            relay_args.extend(["--author", args.author])
        if args.digest:
            relay_args.extend(["--digest", args.digest])
        if args.content_source_url:
            relay_args.extend(["--content-source-url", args.content_source_url])
        if args.cover_image:
            relay_args.extend(["--cover-image", args.cover_image])
        if args.thumb_media_id:
            relay_args.extend(["--thumb-media-id", args.thumb_media_id])
        if args.images:
            relay_args.extend(["--images"] + args.images)
        if args.image_media_ids:
            relay_args.extend(["--image-media-ids"] + args.image_media_ids)
        if not args.upload_images:
            relay_args.append("--no-upload-images")
        if args.need_open_comment:
            relay_args.append("--need-open-comment")
        if args.only_fans_can_comment:
            relay_args.append("--only-fans-can-comment")

        # 执行中继
        returncode, output = execute_via_relay(
            script_path=str(script_path),
            args=relay_args,
            upload_files=upload_files,
            output_file=args.out or "output.json",
            verbose=args.verbose
        )

        # 保存结果
        if returncode == 0 and output:
            try:
                result = json.loads(output)
                if args.out:
                    Path(args.out).write_text(
                        json.dumps(result, ensure_ascii=False, indent=2),
                        encoding="utf-8"
                    )
                    if args.verbose:
                        print(f"[中继] 结果已保存到: {args.out}")
                print(output)
            except json.JSONDecodeError:
                print(output)

        return returncode

    # ============== 本地执行模式 ==============

    # 如果未指定账号，询问用户选择
    if not args.account:
        print("\n请选择要同步的公众号：")
        print("  1. 歪斯Wise (main)")
        print("  2. 人类 (sub)")
        choice = input("请输入选项 (1 或 2): ").strip()
        if choice == "1":
            args.account = "main"
        elif choice == "2":
            args.account = "sub"
        else:
            print("无效选择，默认使用 main")
            args.account = "main"

    try:
        # 获取账号配置
        appid, secret = get_account_config(args.account)
        access_token = get_access_token(appid, secret)

        # 处理内容源
        if args.markdown:
            if args.verbose:
                print(f"正在转换 Markdown: {args.markdown}")
            content_html = convert_markdown_to_html(Path(args.markdown))
            content_base_dir = Path(args.markdown).parent
        else:
            content_path = Path(args.content_html)
            if not content_path.exists():
                raise RuntimeError(f"HTML 文件不存在: {content_path}")
            content_html = content_path.read_text(encoding="utf-8")
            content_base_dir = content_path.parent

        # 始终移除正文中的 h1 标签（微信有独立标题字段）
        content_html = remove_h1_from_html(content_html)
        if args.verbose:
            print("[正文] 已移除 h1 标题标签")

        # 自动上传正文图片
        content_image_urls: Dict[str, str] = {}
        if args.upload_images and args.article_type == "news":
            if args.verbose:
                print("正在扫描并上传正文图片...")
            content_html, content_image_urls = replace_local_images(
                access_token, content_html, content_base_dir, args.verbose
            )
            if content_image_urls and args.verbose:
                print(f"  已上传 {len(content_image_urls)} 张图片")

        # 设置默认作者
        if not args.author:
            args.author = "Wise Wong" if args.account == "main" else "吃粿条"

        # 自动生成摘要（如果未提供）
        if args.article_type == "news" and not args.digest:
            args.digest = generate_digest(content_html)
            if args.verbose and args.digest:
                print(f"[摘要] 自动生成: {args.digest[:50]}...")

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

            # newspic测试：移除强制校验
            # newspic测试：移除强制校验

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
