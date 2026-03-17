#!/usr/bin/env python3
"""
微信订阅号图片上传工具
上传图片到微信 CDN，获取可用于正文的 URL

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
from typing import Dict, List, Tuple, Optional, Any
from urllib import parse, request

# 中继配置
RELAY_CONFIG_PATH = Path.home() / ".claude" / "skills" / "wechat-relay" / "config.yaml"

# 创建禁用SSL验证的context（仅用于开发环境）
SSL_CONTEXT = ssl._create_unverified_context()

TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
UPLOADIMG_URL = "https://api.weixin.qq.com/cgi-bin/media/uploadimg"


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
    # 从远程 .bashrc 提取 WECHAT 相关变量（绕过非交互模式 return 问题）
    extract_wechat_vars = "eval $(grep -E '^export WECHAT_' ~/.bashrc 2>/dev/null || true); "
    cmd = f"{extract_wechat_vars}cd {work_dir} && {env_prefix}python3 {script_name} {' '.join(remote_args)} --output {remote_output}"
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

    account_name = {"main": "歪斯Wise", "sub": "人类是我的副业"}.get(account.lower(), account)
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


def get_access_access_token(appid: str, secret: str) -> str:
    params = {"grant_type": "client_credential", "appid": appid, "secret": secret}
    payload = get_json(f"{TOKEN_URL}?{parse.urlencode(params)}")
    check_wechat_error(payload)
    token = payload.get("access_token")
    if not token:
        raise RuntimeError(f"无法获取 access_token: {payload}")
    return token


def upload_content_image(access_token: str, image_path: Path) -> str:
    """上传图片，返回微信 CDN URL"""
    mime = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"
    body, boundary = build_multipart("media", image_path.name, mime, image_path.read_bytes())
    params = {"access_token": access_token}
    payload = post_multipart(f"{UPLOADIMG_URL}?{parse.urlencode(params)}", body, boundary)
    check_wechat_error(payload)
    url = payload.get("url")
    if not url:
        raise RuntimeError(f"上传图文图片失败: {payload}")
    return url


def main() -> int:
    parser = argparse.ArgumentParser(
        description="微信订阅号图片上传工具 - 上传图片获取微信 CDN URL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 1. 批量上传图片目录中的所有图片
  python3 wechat_uploadimg.py \\
    --account main \\
    --images-dir /path/to/images/ \\
    --output image_mapping.json

  # 2. 单独上传封面图片
  python3 wechat_uploadimg.py \\
    --account main \\
    --cover-image /path/to/cover.jpg \\
    --output cover_url.json

  # 3. 通过 SSH 中继上传（解决 IP 白名单问题）
  python3 wechat_uploadimg.py \\
    --account main \\
    --images-dir /path/to/images/ \\
    --output image_mapping.json \\
    --relay

SSH 中继配置 (~/.claude/skills/wechat-relay/config.yaml):
  relay:
    enabled: true
    host: "115.191.35.152"
    user: "root"
    key_path: "/path/to/key.pem"
    work_dir: "/tmp/wechat_relay"

环境变量:
  WECHAT_APPID_MAIN / WECHAT_APPSECRET_MAIN    # 主公众号（歪斯Wise）
  WECHAT_APPID_SUB / WECHAT_APPSECRET_SUB      # 副业公众号（人类是我的副业）
        """
    )

    # 账号（必填）
    parser.add_argument("--account", choices=["main", "sub"], required=True,
                        help="公众号账号：main=歪斯Wise, sub=人类")

    # 图片源模式
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--images-dir", help="图片目录路径（批量上传所有图片）")
    group.add_argument("--cover-image", help="封面图片路径（单独上传）")

    # 输出
    parser.add_argument("--output", required=True, help="输出文件路径（JSON格式）")

    # SSH 中继选项
    parser.add_argument("--relay", action="store_true", default=None,
                        help="使用 SSH 中继（通过固定 IP 服务器转发请求）")
    parser.add_argument("--no-relay", dest="relay", action="store_false",
                        help="禁用 SSH 中继")
    parser.add_argument("--verbose", action="store_true", help="显示详细日志")

    args = parser.parse_args()

    try:
        # 检查是否启用中继
        use_relay = is_relay_enabled(args.relay)

        if use_relay:
            if args.verbose:
                print("[中继模式] 通过 SSH 中继执行")

            # 收集需要上传的文件
            upload_files = []
            if args.cover_image:
                upload_files.append(args.cover_image)
            elif args.images_dir:
                images_path = Path(args.images_dir)
                image_patterns = ["*.jpg", "*.jpeg", "*.png", "*.gif", "*.bmp"]
                for pattern in image_patterns:
                    for img_file in images_path.glob(pattern):
                        upload_files.append(str(img_file))

            # 获取当前脚本路径
            script_path = Path(__file__).resolve()

            # 构建参数
            relay_args = ["--account", args.account, "--no-relay"]  # 远程不需要再中继
            if args.images_dir:
                # 中继模式：图片已上传到 work_dir，用 . 作为路径
                relay_args.extend(["--images-dir", "."])
            if args.cover_image:
                relay_args.extend(["--cover-image", args.cover_image])
            relay_args.extend(["--output", "output.json"])

            # 执行中继
            returncode, output = execute_via_relay(
                script_path=str(script_path),
                args=relay_args,
                upload_files=upload_files,
                output_file=args.output,
                verbose=args.verbose
            )

            # 保存结果
            if returncode == 0 and output:
                try:
                    result = json.loads(output)
                    Path(args.output).write_text(
                        json.dumps(result, ensure_ascii=False, indent=2),
                        encoding="utf-8"
                    )
                    print(f"\n结果已保存到: {args.output}")
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                except json.JSONDecodeError:
                    print(output)

            return returncode

        # ========== 本地执行模式 ==========
        # 获取账号配置
        appid, secret = get_account_config(args.account)
        access_token = get_access_access_token(appid, secret)

        result = {}

        if args.cover_image:
            # 单独上传封面
            cover_path = Path(args.cover_image)
            if not cover_path.exists():
                raise RuntimeError(f"封面文件不存在: {cover_path}")

            print(f"正在上传封面: {cover_path.name}")
            url = upload_content_image(access_token, cover_path)
            result["cover_url"] = url
            result["cover_filename"] = cover_path.name

        elif args.images_dir:
            # 批量上传图片目录
            images_dir = Path(args.images_dir)
            if not images_dir.exists() or not images_dir.is_dir():
                raise RuntimeError(f"图片目录不存在: {images_dir}")

            # 支持的图片格式
            image_patterns = ["*.jpg", "*.jpeg", "*.png", "*.gif", "*.bmp"]
            image_files = []

            for pattern in image_patterns:
                image_files.extend(images_dir.glob(pattern))

            if not image_files:
                print(f"警告: 目录中没有找到图片文件")
                result["cover_urls"] = {}
                result["poster_urls"] = {}
            else:
                print(f"找到 {len(image_files)} 张图片")

                # 分类图片：封面和正文
                cover_urls = {}
                poster_urls = {}

                for img_path in sorted(image_files):
                    filename = img_path.name.lower()

                    # 判断是封面还是正文图片
                    if filename.startswith("cover"):
                        print(f"  上传封面: {img_path.name}")
                        url = upload_content_image(access_token, img_path)
                        cover_urls[img_path.name] = url
                    else:
                        print(f"  上传正文图片: {img_path.name}")
                        url = upload_content_image(access_token, img_path)
                        poster_urls[img_path.name] = url

                result["cover_urls"] = cover_urls
                result["poster_urls"] = poster_urls
                result["total"] = len(image_files)

                # 生成扁平化映射（用于 md-to-wxhtml）
                flat_mapping = {}
                flat_mapping.update(cover_urls)
                flat_mapping.update(poster_urls)
                result["image_mapping_flat"] = flat_mapping

        # 输出结果
        output_path = Path(args.output)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n结果已保存到: {args.output}")

        # 打印摘要
        print(json.dumps(result, ensure_ascii=False, indent=2))

        return 0

    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
