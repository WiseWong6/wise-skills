#!/bin/bash
# 纸墨线稿 · 逐页截图复核脚本
# 用法：
#   ./shot-screenshot.sh <deck目录> [输出目录] [URL参数] [模式]
# 示例：
#   ./shot-screenshot.sh /path/to/deck                    # 截 frames/shot-*.html 到 /tmp/paper-ink-shots
#   ./shot-screenshot.sh /path/to/deck /tmp/out "?ppt"    # 带 ?ppt 参数截（验证页脚显示）
#   ./shot-screenshot.sh /path/to/deck "" "" thumb        # 生成画板缩略图 frames/thumb-NN.png（640×360）
#
# thumb 模式说明：
#   - 输出目录强制为 <deck>/frames/，文件名前缀 thumb-（供 app-template 的画板 <img> 使用）
#   - 只截 shot-*.html（不截 layout-*，缩略图只针对真实 deck 页）
#   - 尺寸 640×360（16:9），足够画板清晰显示，体积约为 1920 全尺寸的 1/9
#   - 幂等：重复执行只覆盖同名文件，可安全用于「改了某页后整体重跑」
set -u
DECK="${1:?用法: shot-screenshot.sh <deck目录> [输出目录] [URL参数] [模式]}"
OUT="${2:-/tmp/paper-ink-shots}"
QUERY="${3:-}"
MODE="${4:-}"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
[ -x "$CHROME" ] || CHROME="$(command -v chrome || command -v chromium || true)"
[ -n "$CHROME" ] || { echo "找不到 Chrome"; exit 1; }

# thumb 模式：覆盖默认参数
if [ "$MODE" = "thumb" ]; then
  OUT="$DECK/frames"
  QUERY=""
  WIN="640,360"
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

for f in "${FILES[@]}"; do
  [ -e "$f" ] || continue
  name="$(basename "$f" .html)"
  # thumb 模式：shot-01 → thumb-01；普通模式：保留原名
  if [ "$MODE" = "thumb" ]; then
    out_name="thumb-${name#shot-}"
  else
    out_name="$name"
  fi
  "$CHROME" --headless --disable-gpu --hide-scrollbars \
    --screenshot="$OUT/$out_name.png" --window-size="$WIN" \
    --virtual-time-budget=4000 "file://$f$QUERY" >/dev/null 2>&1
  # 串行间隔：连续启动多个 headless Chrome 会触发 allocator 冲突，
  # 导致后续截图截到渲染未完成的深色帧（thumb 模式 640×360 尤其严重）
  sleep 1
  echo "ok $OUT/$out_name.png"
done
