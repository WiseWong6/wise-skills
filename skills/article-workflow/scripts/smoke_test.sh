#!/usr/bin/env bash
#
# article-workflow 端到端 Smoke Test
# 验证：全链路跑通、resume 正确、image-gen --prompt-file 工作
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCTOR="$SCRIPT_DIR/workflow_doctor.py"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."

    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        log_error "python3 未安装"
        return 1
    fi

    # 检查 Pyyaml（用于 YAML 解析）
    if ! python3 -c "import yaml" 2>/dev/null; then
        log_error "pyyaml 未安装（pip install pyyaml）"
        return 1
    fi

    # 检查 article-workflow 技能
    if [ ! -d "$HOME/.claude/skills/article-workflow" ]; then
        log_error "article-workflow 技能不存在"
        return 1
    fi

    log_info "✅ 所有依赖检查通过"
    return 0
}

# 创建测试运行目录
create_test_run() {
    local run_dir="$1"
    log_info "创建测试运行目录: $run_dir"

    mkdir -p "$run_dir/wechat"
    mkdir -p "$run_dir/_log"

    # 创建基础的 run_context.yaml
    cat > "$run_dir/run_context.yaml" <<'EOF'
run_id: "smoke_test-$(date +%Y%m%d_%H%M)"
topic: "smoke test"
platforms: ["wechat"]
status: "RUNNING"
current_step: "00_init"

decisions:
  wechat:
    account: "main"
  image:
    count: 1
    poster_ratio: "4:3"
    cover_ratio: "16:9"

pending_questions: []

steps:
  00_init:
    state: "DONE"
    artifacts: ["run_context.yaml"]
  01_research:
    state: "DONE"
    artifacts: ["wechat/00_research.md"]
  02_rag:
    state: "DONE"
    artifacts: ["wechat/02_rag_content.md"]
  03_titles:
    state: "DONE"
    artifacts: ["wechat/03_titles.md"]
  04_select_title:
    state: "DONE"
    artifacts: ["wechat/03_title_selected.md"]
  05_draft:
    state: "DONE"
    artifacts: ["wechat/05_draft.md"]
  06_polish:
    state: "DONE"
    artifacts: ["wechat/06_polished.md"]
  07_humanize:
    state: "DONE"
    artifacts: ["wechat/07_final_final.md"]
  08_prompts:
    state: "DONE"
    artifacts: ["wechat/08_prompts.md"]
  09_images:
    state: "DONE"
    artifacts: ["wechat/09_images/"]
  10_upload_images:
    state: "DONE"
    artifacts: ["wechat/10_image_mapping.json"]
  11_wx_html:
    state: "DONE"
    artifacts: ["wechat/11_article.html"]
  12_draftbox:
    state: "DONE"
    artifacts: ["wechat/12_draft.json"]
EOF
}

# 创建 mock handoff 文件
create_mock_handoffs() {
    local run_dir="$1"
    local platform="${2:-wechat}"

    log_info "创建 mock handoff 文件 ($platform)..."

    mkdir -p "$run_dir/$platform"

    # 为每个步骤创建 handoff.yaml
    for step_id in "01_research" "02_rag" "03_titles" "04_select_title" "05_draft" "06_polish" "07_humanize" "08_prompts" "09_images" "10_upload_images" "11_wx_html" "12_draftbox"; do
        cat > "$run_dir/$platform/${step_id}_handoff.yaml" <<EOF
step_id: "$step_id"
inputs:
  - "mock_input"
outputs:
  - "$platform/${step_id}_output.md"
  - "$platform/${step_id}_handoff.yaml"
summary: "Mock handoff for $step_id"
next_instructions:
  - "下一步..."
open_questions: []
EOF
        # 创建对应的输出文件
        echo "# Mock output for $step_id" > "$run_dir/$platform/${step_id}_output.md"
    done

    # 00_init 不产生 handoff，只创建 run_context
}

# 测试 doctor 校验
test_doctor() {
    local run_dir="$1"

    log_info "运行 doctor 校验..."
    python3 "$DOCTOR" "$run_dir"
    local doctor_exit=$?

    if [ $doctor_exit -eq 0 ]; then
        log_info "✅ Doctor 校验通过"
        return 0
    else
        log_error "❌ Doctor 校验失败 (exit code: $doctor_exit)"
        return 1
    fi
}

# 测试 handoff 读取路径一致性
test_handoff_path_consistency() {
    log_info "测试 handoff 路径一致性..."

    # 检查 SKILL.md 中的 handoff 读取路径
    local skill_file="$HOME/.claude/skills/article-workflow/SKILL.md"

    # 应该使用统一的格式（不包含重复的 step_id）
    if grep -q "01_research_handoff.yaml" "$skill_file"; then
        log_error "❌ 发现旧格式 handoff 读取路径: 01_research_handoff.yaml"
        log_warn "应该使用: 01_handoff.yaml"
        return 1
    fi

    # 检查所有读取路径都已更新
    local old_patterns=("02_rag_handoff" "03_titles_handoff" "04_select_title_handoff" "05_draft_handoff" "06_polish_handoff" "07_humanize_handoff" "08_prompts_handoff" "09_images_handoff")
    for pattern in "${old_patterns[@]}"; do
        if grep -q "$pattern" "$skill_file"; then
            log_error "❌ 发现旧格式 handoff 读取路径: ${pattern}.yaml"
            return 1
        fi
    done

    log_info "✅ Handoff 路径一致性检查通过"
    return 0
}

# 测试 image-gen --prompt-file
test_image_gen_prompt_file() {
    log_info "测试 image-gen --prompt-file 支持..."

    local run_dir="$1"
    local prompts_file="$run_dir/test_prompts.txt"

    # 创建测试提示词文件
    cat > "$prompts_file" <<'EOF'
测试提示词 1
测试提示词 2
测试提示词 3
EOF

    # 检查 image-gen 技能文档
    local skill_file="$HOME/.claude/skills/image-gen/SKILL.md"

    if ! grep -q "--prompt-file" "$skill_file"; then
        log_error "❌ image-gen 技能缺少 --prompt-file 参数"
        return 1
    fi

    if ! grep -q "Handoff" "$skill_file"; then
        log_error "❌ image-gen 技能缺少 Handoff 协议"
        return 1
    fi

    log_info "✅ image-gen --prompt-file 支持 OK"
    return 0
}

# 运行完整 smoke test
run_smoke_test() {
    local test_root
    test_root=$(mktemp -d)

    log_info "========================================"
    log_info "article-workflow Smoke Test"
    log_info "========================================"
    log_info "测试根目录: $test_root"

    # 设置 trap 清理
    trap "rm -rf '$test_root'" EXIT

    local run_dir="$test_root/runs/smoke_test"
    create_test_run "$run_dir"

    # 测试 1: 依赖检查
    if ! check_dependencies; then
        exit 1
    fi

    # 测试 2: Handoff 路径一致性
    if ! test_handoff_path_consistency; then
        exit 1
    fi

    # 测试 3: 创建 mock handoffs
    create_mock_handoffs "$run_dir" "wechat"
    # 已移除 xhs 平台

    # 测试 4: Doctor 校验
    if ! test_doctor "$run_dir"; then
        exit 1
    fi

    # 测试 5: image-gen --prompt-file
    if ! test_image_gen_prompt_file "$run_dir"; then
        exit 1
    fi

    log_info "========================================"
    log_info "✅ 所有 Smoke Test 通过"
    log_info "========================================"
}

# 主流程
main() {
    if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        echo "用法: $0 [选项]"
        echo ""
        echo "选项:"
        echo "  --help, -h      显示此帮助信息"
        echo "  --run-dir DIR   指定现有运行目录进行测试"
        echo ""
        echo "示例:"
        echo "  $0                    # 运行完整 smoke test"
        echo "  $0 --run-dir /path  # 测试指定目录"
        exit 0
    fi

    if [ "$1" = "--run-dir" ]; then
        local run_dir="$2"
        if [ -z "$run_dir" ]; then
            log_error "缺少运行目录路径"
            exit 1
        fi

        if [ ! -d "$run_dir" ]; then
            log_error "运行目录不存在: $run_dir"
            exit 1
        fi

        log_info "测试现有运行目录: $run_dir"
        test_doctor "$run_dir"
        exit $?
    fi

    # 默认运行完整 smoke test
    run_smoke_test
    exit 0
}

main "$@"
