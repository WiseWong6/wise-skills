#!/bin/bash
# 安装命令别名脚本
# 用途：简化 orchestrator.py 的调用方式

# Skill 根目录（自动检测）
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ORCHESTRATOR="$SCRIPT_DIR/scripts/orchestrator.py"

# 检查 orchestrator 是否存在
if [ ! -f "$ORCHESTRATOR" ]; then
    echo "错误：找不到 orchestrator.py"
    echo "预期路径: $ORCHESTRATOR"
    exit 1
fi

# 设置别名
alias iac-run="python3 $ORCHESTRATOR"
alias iac-status="python3 $ORCHESTRATOR --resume --status"
alias iac-plan="python3 $ORCHESTRATOR --resume --plan"

echo "================================================"
echo "命令别名已安装"
echo "================================================"
echo ""
echo "可用命令："
echo "  iac-run     - 运行 orchestrator（新建或继续）"
echo "  iac-status  - 查看当前状态（同 --resume --status）"
echo "  iac-plan    - 查看执行计划（同 --resume --plan）"
echo ""
echo "使用示例："
echo "  iac-run --topic \"测试话题\""
echo "  iac-status"
echo "  iac-plan"
echo ""
echo "注意：别名在当前 shell 会话有效。"
echo "如需永久生效，请将以下内容添加到 ~/.bashrc 或 ~/.zshrc："
echo ""
echo "  # Insurance Article Creator aliases"
echo '  export SCRIPT_DIR="$HOME/.claude/skills/insurance-article-creator"'
echo '  alias iac-run="python3 $SCRIPT_DIR/scripts/orchestrator.py"'
echo '  alias iac-status="python3 $SCRIPT_DIR/scripts/orchestrator.py --resume --status"'
echo '  alias iac-plan="python3 $SCRIPT_DIR/scripts/orchestrator.py --resume --plan"'
echo ""
echo "然后运行: source ~/.bashrc (或 ~/.zshrc)"
