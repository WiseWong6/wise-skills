#!/bin/bash
# wise-ppt · 整 deck 导出 16:9 PDF
# 流程：frames 逐页 PNG（调 screenshot.sh）→ 临时 print HTML（@page 20in×11.25in）
#       → Chrome headless --print-to-pdf → 有 gs 则 ebook 档二次压缩
# 用法：
#   ./export-pdf.sh <deck目录> [输出PDF路径] [--keep-png]
# 示例：
#   ./export-pdf.sh /path/to/deck                       # 输出 /path/to/deck/<deck名>.pdf
#   ./export-pdf.sh /path/to/deck /tmp/deck.pdf --keep-png
set -euo pipefail
DECK="${1:?用法: export-pdf.sh <deck目录> [输出PDF路径] [--keep-png]}"
DECK="$(cd "$DECK" && pwd)"
NAME="$(basename "$DECK")"
OUT="${2:-$DECK/$NAME.pdf}"
KEEP_PNG=0
[ "${3:-}" = "--keep-png" ] && KEEP_PNG=1

SKILL_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PNG_DIR="$(mktemp -d /tmp/wise-ppt-pdf.XXXXXX)"
cleanup() {
  if [ "$KEEP_PNG" -eq 0 ] && [ -d "$PNG_DIR" ]; then rm -rf "$PNG_DIR"; fi
}
trap cleanup EXIT

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
[ -x "$CHROME" ] || CHROME="$(command -v chrome || command -v chromium || command -v chromium-browser || true)"
[ -x "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" ] && [ -z "$CHROME" ] && CHROME="/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
[ -n "$CHROME" ] || { echo "找不到 Chrome/Edge，请在浏览器打开 index.html 后打印为 PDF"; exit 1; }

# 1. 逐页 PNG
"$SKILL_ROOT/runtime/screenshot.sh" "$DECK" "$PNG_DIR" >/dev/null || { echo "截图失败"; exit 1; }
COUNT=$(ls "$PNG_DIR"/shot-*.png 2>/dev/null | wc -l | tr -d ' ')
[ "$COUNT" -gt 0 ] || { echo "没有截到任何页面"; exit 1; }
echo "已截 $COUNT 页 → $PNG_DIR"

# 2. 临时 print HTML（每页一张图，16:9 横版，颜色准确）
PRINT_HTML="$PNG_DIR/print.html"
{
  echo '<!DOCTYPE html><html><head><meta charset="UTF-8"><style>'
  echo '@page { size: 20in 11.25in; margin: 0; }'
  echo '* { print-color-adjust: exact; -webkit-print-color-adjust: exact; }'
  echo 'html, body { margin: 0; padding: 0; }'
  echo '.pg { width: 20in; height: 11.25in; break-after: page; page-break-after: always; overflow: hidden; }'
  echo '.pg:last-child { break-after: auto; page-break-after: auto; }'
  echo '.pg img { width: 100%; height: 100%; object-fit: contain; display: block; }'
  echo '</style></head><body>'
  for p in "$PNG_DIR"/shot-*.png; do
    echo "<div class=\"pg\"><img src=\"file://$p\"></div>"
  done
  echo '</body></html>'
} > "$PRINT_HTML"

# 3. Chrome headless 打印
"$CHROME" --headless --disable-gpu --allow-file-access-from-files --no-pdf-header-footer \
  --virtual-time-budget=8000 --print-to-pdf="$OUT" "file://$PRINT_HTML" >/dev/null 2>&1 || {
    echo "PDF 打印进程失败" >&2; exit 1;
  }
[ -s "$OUT" ] || { echo "PDF 生成失败"; exit 1; }
echo "ok $OUT ($(du -h "$OUT" | cut -f1))"

# 4. Ghostscript 二次压缩（可选，ebook 150dpi）
if command -v gs >/dev/null 2>&1; then
  TMP_PDF="$OUT.tmp.pdf"
  gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/ebook -dNOPAUSE -dQUIET -dBATCH \
    -sOutputFile="$TMP_PDF" "$OUT" && mv "$TMP_PDF" "$OUT"
  echo "gs 压缩后：$(du -h "$OUT" | cut -f1)"
fi

# 5. 复核与清理
[ "$(head -c 5 "$OUT")" = "%PDF-" ] || { echo "PDF 文件头无效：$OUT" >&2; exit 1; }
if command -v pdfinfo >/dev/null 2>&1; then
  PDF_PAGES="$(pdfinfo "$OUT" | awk '/^Pages:/ {print $2}')"
  [ "$PDF_PAGES" = "$COUNT" ] || {
    echo "PDF 页数 $PDF_PAGES，与截图页数 $COUNT 不一致：$OUT" >&2
    exit 1
  }
fi
if [ "$KEEP_PNG" -eq 1 ]; then
  echo "PNG 保留在 $PNG_DIR"
fi
exit 0
