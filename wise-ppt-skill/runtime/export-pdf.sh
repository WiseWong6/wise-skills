#!/bin/bash
# wise-ppt · 无截图 PDF 导出：新 deck 直接打印；旧 frames deck 使用 /tmp 临时加载壳。
set -euo pipefail
DECK="${1:?用法: export-pdf.sh <deck目录> [输出PDF路径]}"
DECK="$(cd "$DECK" && pwd)"
NAME="$(basename "$DECK")"
OUT="${2:-$DECK/$NAME.pdf}"
TMP_ROOT="$(mktemp -d /tmp/wise-ppt-pdf.XXXXXX)"
mkdir -p "$TMP_ROOT/ready-profile" "$TMP_ROOT/print-profile" "$(dirname "$OUT")"
CHROME_PID=""
stop_chrome() {
  [ -n "$CHROME_PID" ] || return 0
  if kill -0 "$CHROME_PID" 2>/dev/null; then
    kill "$CHROME_PID" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "$CHROME_PID" 2>/dev/null || break
      sleep 0.1
    done
    kill -9 "$CHROME_PID" 2>/dev/null || true
  fi
  wait "$CHROME_PID" 2>/dev/null || true
  CHROME_PID=""
}
cleanup(){ stop_chrome; rm -rf "$TMP_ROOT"; }
trap cleanup EXIT INT TERM

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
[ -x "$CHROME" ] || CHROME="$(command -v google-chrome || command -v chrome || command -v chromium || command -v chromium-browser || true)"
if [ ! -x "$CHROME" ] && [ -x "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" ]; then CHROME="/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"; fi
[ -x "$CHROME" ] || { echo "找不到 Chrome/Edge" >&2; exit 1; }

MODE="legacy"
if [ -f "$DECK/render-plan.json" ]; then
  MODE="$(python3 - "$DECK/render-plan.json" <<'PY'
import json, sys
doc=json.load(open(sys.argv[1],encoding='utf-8'))
print('single-html' if doc.get('document_mode')=='single-html' else 'legacy')
PY
)"
fi

if [ "$MODE" = "single-html" ]; then
  HTML="$DECK/index.html"
  [ -f "$HTML" ] || { echo "缺少 single-html 输出：$HTML" >&2; exit 1; }
  COUNT="$(python3 - "$HTML" <<'PY'
from html.parser import HTMLParser
import sys
class P(HTMLParser):
    def __init__(self): super().__init__(); self.count=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='section' and 'slide' in a.get('class','').split() and a.get('data-page-id'): self.count+=1
p=P(); p.feed(open(sys.argv[1],encoding='utf-8').read()); print(p.count)
PY
)"
  [ "$COUNT" -gt 0 ] || { echo "index.html 中没有 slide" >&2; exit 1; }
  URL="$(python3 - "$HTML" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve().as_uri()+'?print=1')
PY
)"
else
  shopt -s nullglob
  FRAMES=("$DECK"/frames/shot-*.html)
  [ "${#FRAMES[@]}" -gt 0 ] || { echo "旧 deck 缺少 frames/shot-*.html" >&2; exit 1; }
  COUNT="${#FRAMES[@]}"
  PRINT_HTML="$TMP_ROOT/legacy-print.html"
  {
    printf '%s\n' '<!doctype html><html data-deck-ready="false"><head><meta charset="UTF-8"><style>@page{size:20in 11.25in;margin:0}*{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}html,body{margin:0}.page{width:1920px;height:1080px;break-after:page;overflow:hidden}.page:last-child{break-after:auto}.page iframe{display:block;width:1920px;height:1080px;border:0}</style></head><body>'
    for frame in "${FRAMES[@]}"; do
      URI="$(python3 - "$frame" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve().as_uri())
PY
)"
      printf '<div class="page"><iframe src="%s"></iframe></div>\n' "$URI"
    done
    printf '%s\n' '<script>(function(){var nodes=[].slice.call(document.querySelectorAll("iframe"));function ready(){var ok=nodes.every(function(f){try{return f.contentDocument&&f.contentDocument.documentElement.dataset.renderReady==="true"}catch(e){return false}});if(ok)document.documentElement.dataset.deckReady="true";else setTimeout(ready,50)}ready()})();</script></body></html>'
  } > "$PRINT_HTML"
  URL="$(python3 - "$PRINT_HTML" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve().as_uri())
PY
)"
fi

DOM="$TMP_ROOT/ready.html"
COMMON=(--headless --disable-gpu --allow-file-access-from-files --disable-background-networking --disable-component-update --disable-default-apps --disable-sync --no-first-run --no-default-browser-check --metrics-recording-only)
"$CHROME" "${COMMON[@]}" --user-data-dir="$TMP_ROOT/ready-profile" --virtual-time-budget=12000 --dump-dom "$URL" >"$DOM" 2>"$TMP_ROOT/load.log" &
CHROME_PID=$!
for _ in $(seq 1 240); do
  if rg -q 'data-deck-ready="true"|data-deck-error=' "$DOM" 2>/dev/null; then break; fi
  kill -0 "$CHROME_PID" 2>/dev/null || break
  sleep 0.1
done
stop_chrome
rg -q 'data-deck-ready="true"' "$DOM" || { echo "deck 未在时限内完成渲染" >&2; tail -20 "$TMP_ROOT/load.log" >&2; exit 1; }
"$CHROME" "${COMMON[@]}" --user-data-dir="$TMP_ROOT/print-profile" --no-pdf-header-footer --virtual-time-budget=12000 --print-to-pdf="$OUT" "$URL" >"$TMP_ROOT/print.log" 2>&1 &
CHROME_PID=$!
for _ in $(seq 1 300); do
  if [ -s "$OUT" ] && [ "$(head -c 5 "$OUT" 2>/dev/null || true)" = "%PDF-" ]; then break; fi
  kill -0 "$CHROME_PID" 2>/dev/null || break
  sleep 0.1
done
stop_chrome
[ -s "$OUT" ] || { echo "PDF 生成失败：$OUT" >&2; exit 1; }
[ "$(head -c 5 "$OUT")" = "%PDF-" ] || { echo "PDF 文件头无效：$OUT" >&2; exit 1; }
if command -v pdfinfo >/dev/null 2>&1; then
  PDF_PAGES="$(pdfinfo "$OUT" | awk '/^Pages:/ {print $2}')"
  [ "$PDF_PAGES" = "$COUNT" ] || { echo "PDF 页数 $PDF_PAGES，与 slide 数 $COUNT 不一致" >&2; exit 1; }
fi
echo "PASS pdf mode=$MODE pages=$COUNT output=$OUT"
