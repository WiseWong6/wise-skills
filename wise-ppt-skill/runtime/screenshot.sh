#!/bin/bash
# wise-ppt · 逐页截图复核脚本
# 用法：
#   ./screenshot.sh <deck目录> [输出目录] [URL参数] [模式]
# 示例：
#   ./screenshot.sh /path/to/deck                    # 截 frames/shot-*.html 到临时复核目录
#   ./screenshot.sh /path/to/deck /tmp/out "?ppt"    # 带 ?ppt 参数截（验证页脚显示）
#   ./screenshot.sh /path/to/deck "" "" thumb        # 生成画板缩略图 frames/thumb-NN.png（640×360）
#   ./screenshot.sh /path/to/deck "" "" audit        # 输出 #body 相对可用区的 dx/dy，centered 超差即失败
#
# thumb 模式说明：
#   - 输出目录强制为 <deck>/frames/，文件名前缀 thumb-（供 app-template 的画板 <img> 使用）
#   - 只截 shot-*.html（不截 layout-*，缩略图只针对真实 deck 页）
#   - 尺寸 640×360（16:9），足够画板清晰显示，体积约为 1920 全尺寸的 1/9
#   - 幂等：重复执行只覆盖同名文件，可安全用于「改了某页后整体重跑」
set -euo pipefail
DECK="${1:?用法: screenshot.sh <deck目录> [输出目录] [URL参数] [模式]}"
[ -d "$DECK/frames" ] || { echo "错误：不存在 frames 目录：$DECK/frames" >&2; exit 1; }
DECK="$(cd "$DECK" && pwd)"
OUT="${2:-/tmp/wise-ppt-shots}"
QUERY="${3:-}"
MODE="${4:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VERIFY_QR="$SCRIPT_DIR/../scripts/verify_qr.py"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
[ -x "$CHROME" ] || CHROME="$(command -v google-chrome || command -v chrome || command -v chromium || true)"
[ -n "$CHROME" ] || { echo "找不到 Chrome"; exit 1; }
PROFILE="$(mktemp -d /tmp/wise-ppt-chrome.XXXXXX)"
ACTIVE_PID=""
WISE_PPT_WAIT_STEPS="${WISE_PPT_WAIT_STEPS:-300}"
case "$WISE_PPT_WAIT_STEPS" in
  ''|*[!0-9]*) echo "WISE_PPT_WAIT_STEPS 必须是正整数" >&2; exit 1 ;;
esac
[ "$WISE_PPT_WAIT_STEPS" -gt 0 ] || { echo "WISE_PPT_WAIT_STEPS 必须大于 0" >&2; exit 1; }

stop_chrome() {
  local pid="${1:-}"
  [ -n "$pid" ] || return 0
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    for _ in {1..20}; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.05
    done
    kill -KILL "$pid" 2>/dev/null || true
  fi
  wait "$pid" 2>/dev/null || true
  ACTIVE_PID=""
}

wait_for_dom() {
  local path="$1"
  local pid="$2"
  local step
  for ((step = 0; step < WISE_PPT_WAIT_STEPS; step++)); do
    if [ -s "$path" ] \
      && grep -q 'data-render-ready="true"' "$path" \
      && grep -q '</html>' "$path"; then
      return 0
    fi
    kill -0 "$pid" 2>/dev/null || return 1
    sleep 0.1
  done
  return 1
}

png_complete() {
  local path="$1"
  [ -s "$path" ] || return 1
  [ "$(tail -c 12 "$path" | od -An -tx1 | tr -d ' \n')" = "0000000049454e44ae426082" ]
}

wait_for_png() {
  local path="$1"
  local pid="$2"
  local step
  for ((step = 0; step < WISE_PPT_WAIT_STEPS; step++)); do
    png_complete "$path" && return 0
    kill -0 "$pid" 2>/dev/null || return 1
    sleep 0.1
  done
  return 1
}

cleanup() {
  stop_chrome "$ACTIVE_PID"
  rm -rf "$PROFILE"
}
trap cleanup EXIT

# thumb 模式：覆盖默认参数
if [ "$MODE" = "thumb" ]; then
  OUT="$DECK/frames"
  QUERY=""
  WIN="640,360"
elif [ "$MODE" = "audit" ]; then
  QUERY="?audit"
  WIN="1920,1080"
else
  WIN="1920,1080"
fi

mkdir -p "$OUT"
# thumb 模式只截 shot-*；普通模式保留原行为（shot-* + layout-*）
if [ "$MODE" = "thumb" ]; then
  FILES=( "$DECK"/frames/shot-*.html )
else
  FILES=( "$DECK"/frames/shot-*.html "$DECK"/frames/layout-*.html )
fi

count=0
for f in "${FILES[@]}"; do
  [ -e "$f" ] || continue
  count=$((count + 1))
  name="$(basename "$f" .html)"
  # thumb 模式：shot-01 → thumb-01；普通模式：保留原名
  if [ "$MODE" = "thumb" ]; then
    out_name="thumb-${name#shot-}"
  else
    out_name="$name"
  fi
  target="$OUT/$out_name.png"
  url="file://$f$QUERY"
  dom_file="$PROFILE/$out_name.html"
  log_file="$PROFILE/$out_name.log"
  rm -f "$target"
  # DOM readiness and image capture use two short-lived Chrome runs. Combining
  # --dump-dom and --screenshot leaves some Chrome builds alive after writing
  # both files, which leaks processes and locks the temporary profile.
  "$CHROME" --headless --disable-gpu --hide-scrollbars \
    --disable-background-networking --disable-component-update --disable-default-apps \
    --disable-sync --no-first-run --no-default-browser-check --metrics-recording-only \
    --allow-file-access-from-files --user-data-dir="$PROFILE" \
    --dump-dom --window-size="$WIN" \
    --virtual-time-budget=8000 "$url" >"$dom_file" 2>"$log_file" &
  ACTIVE_PID=$!
  if ! wait_for_dom "$dom_file" "$ACTIVE_PID"; then
    stop_chrome "$ACTIVE_PID"
    {
      echo "错误：Chrome 加载失败：$f" >&2
      tail -20 "$log_file" >&2
      exit 1
    }
  fi
  stop_chrome "$ACTIVE_PID"
  if [ "$MODE" = "audit" ]; then
    python3 - "$dom_file" "$f" <<'PY'
import html
import re
import sys

dom_path, page_path = sys.argv[1:]
text = open(dom_path, encoding='utf-8').read()
match = re.search(r'<html\b([^>]*)>', text, re.I | re.S)
if not match:
    raise SystemExit(f"错误：找不到 html 根节点：{page_path}")
attrs = dict((key.lower(), html.unescape(value)) for key, _, value in re.findall(
    r'([\w:-]+)\s*=\s*([\"\'])(.*?)\2', match.group(1), re.S
))
status = attrs.get('data-balance-status', 'missing')
mode = attrs.get('data-balance-mode', 'n/a')
dx = attrs.get('data-balance-dx', 'n/a')
dy = attrs.get('data-balance-dy', 'n/a')
box = attrs.get('data-balance-box', 'n/a')
frame = attrs.get('data-balance-frame', 'n/a')
overflow = attrs.get('data-balance-overflow', 'n/a')
print(f"{status:>20} {page_path} mode={mode} dx={dx} dy={dy} box={box} frame={frame} overflow={overflow}")
if status not in {'pass', 'report'}:
    raise SystemExit(1)
PY
    continue
  fi
  "$CHROME" --headless --disable-gpu --hide-scrollbars \
    --disable-background-networking --disable-component-update --disable-default-apps \
    --disable-sync --no-first-run --no-default-browser-check --metrics-recording-only \
    --allow-file-access-from-files --user-data-dir="$PROFILE" \
    --screenshot="$target" --window-size="$WIN" \
    --run-all-compositor-stages-before-draw --virtual-time-budget=8000 \
    "$url" >/dev/null 2>>"$log_file" &
  ACTIVE_PID=$!
  if ! wait_for_png "$target" "$ACTIVE_PID"; then
    stop_chrome "$ACTIVE_PID"
    {
      echo "错误：Chrome 截图失败：$f" >&2
      tail -20 "$log_file" >&2
      exit 1
    }
  fi
  stop_chrome "$ACTIVE_PID"
  [ -s "$target" ] || { echo "错误：截图为空：$target" >&2; exit 1; }
  python3 - "$target" "$WIN" <<'PY'
import struct
import sys

path, expected = sys.argv[1], sys.argv[2]
expected_size = tuple(map(int, expected.split(',')))
with open(path, 'rb') as fh:
    header = fh.read(24)
if len(header) != 24 or header[:8] != b'\x89PNG\r\n\x1a\n':
    raise SystemExit(f"错误：不是有效 PNG：{path}")
actual_size = struct.unpack('>II', header[16:24])
if actual_size != expected_size:
    raise SystemExit(f"错误：截图尺寸 {actual_size}，预期 {expected_size}：{path}")
PY
  while IFS= read -r payload; do
    [ -n "$payload" ] || continue
    python3 "$VERIFY_QR" -- "$target" "$payload"
  done < <(python3 - "$dom_file" <<'PY'
from html.parser import HTMLParser
import sys

class Payloads(HTMLParser):
    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == 'data-qr-payload' and value:
                print(value)

parser = Payloads()
parser.feed(open(sys.argv[1], encoding='utf-8').read())
PY
)
  echo "ok $target"
done

[ "$count" -gt 0 ] || { echo "错误：没有找到可截图的 HTML 页面：$DECK/frames" >&2; exit 1; }
