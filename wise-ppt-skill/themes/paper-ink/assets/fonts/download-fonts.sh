#!/bin/bash
# 纸墨线稿 PPT · 字体检测与下载脚本
# ============================================================
# 作用：wise-ppt-skill skill 依赖 5 个本地开源字体（共约 79MB），字体文件
#       不进 git（体积过大）。本脚本检测缺失字体并从官方源下载，保证
#       任何人拿到 skill（clone / 解压 / 拷贝）后第一次用都能自动就绪。
#
# 用法：
#   bash download-fonts.sh            # 检测 + 下载缺失字体
#   bash download-fonts.sh --force    # 强制重新下载全部字体（校验/修复用）
#
# 字体来源（均为开源、可商用）：
#   - 思源宋体 CN Medium   adobe-fonts/source-han-serif   (SIL OFL 1.1)
#   - 思源黑体 CN Light    adobe-fonts/source-han-sans    (SIL OFL 1.1)
#   - 思源黑体 CN Regular  adobe-fonts/source-han-sans    (SIL OFL 1.1)
#   - Courier Prime        google/fonts                    (SIL OFL 1.1)
#   - 霞鹜文楷 Regular     lxgw/LxgwWenKai                 (SIL OFL 1.1)
#
# 说明：思源官方仓库提供的是 CN 命名（SubsetOTF/CN/），与字形一致；
#       本 skill 统一采用官方 CN 命名（shared.css 的 @font-face 同步引用）。
# ============================================================
set -u

# 脚本所在目录即字体落地目录（无论从哪里调用）
FONT_DIR="$(cd "$(dirname "$0")" && pwd)"
FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

# 字体清单：本地文件名 | 官方下载 URL
FONTS=(
  "SourceHanSerifCN-Medium.otf|https://raw.githubusercontent.com/adobe-fonts/source-han-serif/release/SubsetOTF/CN/SourceHanSerifCN-Medium.otf"
  "SourceHanSansCN-Light.otf|https://raw.githubusercontent.com/adobe-fonts/source-han-sans/release/SubsetOTF/CN/SourceHanSansCN-Light.otf"
  "SourceHanSansCN-Regular.otf|https://raw.githubusercontent.com/adobe-fonts/source-han-sans/release/SubsetOTF/CN/SourceHanSansCN-Regular.otf"
  "CourierPrime-Regular.ttf|https://raw.githubusercontent.com/google/fonts/main/ofl/courierprime/CourierPrime-Regular.ttf"
  "LXGWWenKai-Regular.ttf|https://raw.githubusercontent.com/lxgw/LxgwWenKai/main/fonts/TTF/LXGWWenKai-Regular.ttf"
)

# 选一个可用的下载工具
if command -v curl >/dev/null 2>&1; then
  FETCH="curl -fL --progress-bar -o"
elif command -v wget >/dev/null 2>&1; then
  FETCH="wget -q --show-progress -O"
else
  echo "✗ 需要 curl 或 wget，两者都未找到。请安装其一后重试。" >&2
  exit 1
fi

echo "字体目录: $FONT_DIR"
echo ""

missing=0
downloaded=0
failed=0

for entry in "${FONTS[@]}"; do
  name="${entry%%|*}"
  url="${entry##*|}"
  target="$FONT_DIR/$name"

  # 检测：文件存在且非空则跳过（除非 --force）
  if [ -s "$target" ] && [ "$FORCE" -eq 0 ]; then
    echo "✓ 已存在  $name"
    continue
  fi

  missing=$((missing + 1))
  echo "↓ 下载中  $name"
  # 下载到临时文件，成功后才替换，避免半截文件
  tmp="$target.part"
  if $FETCH "$tmp" "$url" && [ -s "$tmp" ]; then
    mv "$tmp" "$target"
    echo "✓ 完成    $name"
    downloaded=$((downloaded + 1))
  else
    rm -f "$tmp"
    echo "✗ 失败    $name  ←  $url" >&2
    failed=$((failed + 1))
  fi
done

echo ""
echo "结果：$downloaded 个下载成功，$failed 个失败，$((5 - missing)) 个已存在。"

if [ "$failed" -gt 0 ]; then
  echo ""
  echo "⚠ 有字体下载失败，可能原因：网络问题 / 上游仓库路径变动。"
  echo "  请检查上方失败行的 URL，或稍后重试：bash download-fonts.sh"
  exit 1
fi

# 全部就绪提示
if [ "$missing" -eq 0 ] && [ "$FORCE" -eq 0 ]; then
  echo "全部字体就绪，无需下载。"
else
  echo "全部字体就绪。"
fi
