#!/usr/bin/env python3
"""
article-workflow 端到端校验工具
严格验证每个阶段的 handoff.yaml 和 outputs 是否存在
失败时必须返回非零退出码
"""

import os
import sys
import yaml
from pathlib import Path

# 期望的步骤顺序（定义了所有可能的步骤）
EXPECTED_STEPS = [
    "00_init",
    "01_research",
    "02_rag",
    "03_titles",
    "04_select_title",
    "05_draft",
    "06_polish",
    "07_humanize",
    "08_prompts",
    "09_images",
    "10_upload_images",
    "11_wx_html",
    "12_draftbox",
]

# 有 handoff 输出的步骤（初始化步骤除外）
HANDOFF_STEPS = [s for s in EXPECTED_STEPS if s != "00_init"]


def validate_yaml_schema(handoff, step_id):
    """验证 handoff.yaml 的 schema 是否正确"""
    issues = []

    # 检查必需字段
    required_fields = ['step_id', 'inputs', 'outputs', 'summary']
    for field in required_fields:
        if field not in handoff:
            issues.append(f"❌ 缺少必需字段: {field}")

    # 检查 step_id 类型
    if 'step_id' in handoff:
        if not isinstance(handoff['step_id'], str):
            issues.append(f"❌ step_id 必须是字符串类型")

    # 检查 inputs 类型
    if 'inputs' in handoff:
        if not isinstance(handoff['inputs'], list):
            issues.append(f"❌ inputs 必须是列表类型")

    # 检查 outputs 类型
    if 'outputs' in handoff:
        if not isinstance(handoff['outputs'], list):
            issues.append(f"❌ outputs 必须是列表类型")

    # 检查 summary 类型
    if 'summary' in handoff:
        if not isinstance(handoff['summary'], str):
            issues.append(f"❌ summary 必须是字符串类型")

    return issues


def check_output_file(run_dir, output_path, step_id) -> list:
    """校验输出文件，递归处理目录"""
    issues = []

    if output_path.startswith('wechat'):
        output_file = Path(run_dir) / output_path
    else:
        # 相对于平台目录的路径
        platform_dir = Path(run_dir) / 'wechat'
        output_file = platform_dir / output_path

    if not output_file.exists():
        issues.append(f"❌ {step_id}: 输出不存在: {output_path}")
        return issues

    # 新增：如果是目录，递归检查内容
    if output_file.is_dir():
        files_in_dir = list(output_file.glob('*'))
        if not files_in_dir:
            issues.append(f"⚠️  {step_id}: 目录为空: {output_path}")
        for child_file in files_in_dir:
            if not child_file.exists():
                issues.append(f"❌ {step_id}: 目录内文件缺失: {output_path}/{child_file.name}")

    return issues


def check_handoff(run_dir, platform="wechat"):
    """检查指定平台的 handoff 文件完整性"""
    platform_dir = Path(run_dir) / platform
    issues = []
    step_ids = []

    for step_id in HANDOFF_STEPS:
        step_num = step_id.split("_")[0][:2]
        handoff_file = platform_dir / f"{step_num}_handoff.yaml"

        # 检查 handoff.yaml 是否存在
        if not handoff_file.exists():
            issues.append(f"❌ {step_id}: handoff.yaml 不存在")
            continue

        # 检查 step_id 唯一性
        if step_id in step_ids:
            issues.append(f"⚠️  {step_id}: step_id 重复（可能被覆盖）")
        step_ids.append(step_id)

        # 读取并验证 handoff.yaml 内容
        try:
            with open(handoff_file, 'r', encoding='utf-8') as f:
                handoff = yaml.safe_load(f)

            # Schema 校验
            schema_issues = validate_yaml_schema(handoff, step_id)
            if schema_issues:
                issues.extend([f"  {step_id}: {issue}" for issue in schema_issues])

            # 验证 step_id 与文件名是否匹配
            if 'step_id' in handoff and handoff['step_id'] != step_id:
                issues.append(f"⚠️  {step_id}: step_id 字段值 '{handoff['step_id']}' 与文件名不匹配")

            # 检查 outputs 中的文件是否存在
            if 'outputs' in handoff:
                for output_path in handoff['outputs']:
                    # output_errors = check_output_file(run_dir, output_path, step_id)
                    # issues.extend(output_errors)
                    # 如果是目录，列出目录内文件检查
                    if output_path.endswith('/'):
                        # 目录路径
                        dir_path = Path(run_dir) / output_path.rstrip('/')
                        if dir_path.exists() and dir_path.is_dir():
                            files_in_dir = list(dir_path.glob('*'))
                            if not files_in_dir:
                                issues.append(f"⚠️  {step_id}: 目录为空: {output_path}")
                        else:
                            issues.append(f"❌ {step_id}: 目录不存在: {output_path}")
                    else:
                        # 普通文件
                        file_path = Path(run_dir) / output_path
                        if not file_path.exists():
                            issues.append(f"❌ {step_id}: 输出文件不存在: {output_path}")

        except yaml.YAMLError as e:
            issues.append(f"❌ {step_id}: YAML 解析失败: {e}")
        except Exception as e:
            issues.append(f"❌ {step_id}: 读取失败: {e}")

    return issues, step_ids


def check_run_context(run_dir):
    """检查 run_context.yaml 状态"""
    context_file = Path(run_dir) / "run_context.yaml"
    issues = []

    if not context_file.exists():
        return ["❌ run_context.yaml 不存在"], {}

    try:
        with open(context_file, 'r', encoding='utf-8') as f:
            context = yaml.safe_load(f)

        # 检查步骤状态
        steps_in_context = {}
        if 'steps' in context:
            for step_id in EXPECTED_STEPS:
                if step_id not in context['steps']:
                    issues.append(f"⚠️  {step_id}: 未在 run_context.yaml 中定义")
                else:
                    step_data = context['steps'][step_id]
                    state = step_data.get('state', 'UNKNOWN')
                    steps_in_context[step_id] = state

                    if (state == 'FAILED'):
                        issues.append(f"❌ {step_id}: 状态为 FAILED")

        return issues, steps_in_context

    except yaml.YAMLError as e:
        return [f"❌ run_context.yaml YAML 解析失败: {e}"], {}
    except Exception as e:
        return [f"❌ run_context.yaml 读取失败: {e}"], {}


def check_consistency(run_dir, context_steps, wechat_step_ids, xhs_step_ids):
    """检查 run_context 状态与 handoff 是否一致"""
    issues = []

    # 检查 wechat 平台一致性
    for step_id in wechat_step_id:
        if step_id in context_steps:
            context_state = context_steps[step_id]
            # 如果 handoff 存在，状态应该是 DONE
            issues.append(f"✓ {step_id}: run_context 状态={context_state}, handoff 存在")
        else:
            # handoff 存在但 run_context 中没有定义
            issues.append(f"⚠️  {step_id}: handoff 存在但 run_context 中未定义")

    # 检查 step_id 顺序是否正确
    all_step_ids = wechat_step_ids
    if xhs_step_ids:
        all_step_ids = sorted(set(wechat_step_ids) | set(xhs_step_ids))

    for i, step_id in enumerate(all_step_ids):
        expected_index = EXPECTED_STEPS.index(step_id) if step_id in EXPECTED_STEPS else -1
        if expected_index >= 0 and expected_index != i + 1:  # +1 因为跳过 00_init
            issues.append(f"⚠️  {step_id}: 顺序可能不正确（期望位置 {expected_index + 1}，实际位置 {i + 1}）")

    return issues


def main():
    if len(sys.argv) < 2:
        print("用法: python workflow_doctor.py <run_dir>")
        sys.exit(1)

    run_dir = sys.argv[1]
    run_path = Path(run_dir)

    if not run_path.exists():
        print(f"❌ 运行目录不存在: {run_dir}")
        sys.exit(1)

    print(f"\n🔍 检查 article-workflow: {run_dir}\n")

    # 检查 run_context.yaml
    print("【检查 run_context.yaml】")
    context_issues, context_steps = check_run_context(run_dir)
    for issue in context_issues:
        print(issue)
    if not context_issues:
        print("✅ run_context.yaml 正常")
    else:
        print(f"⚠️  发现 {len(context_issues)} 个问题")

    # 检查 wechat 平台
    print("\n【检查 wechat handoffs】")
    wechat_issues, wechat_step_ids = check_handoff(run_dir, "wechat")
    for issue in wechat_issues:
        print(issue)
    if not wechat_issues:
        print("✅ wechat 平台正常")
    else:
        print(f"⚠️  发现 {len(wechat_issues)} 个问题")

    # 已移除 xhs 平台检查

    # 检查一致性
    if wechat_step_ids:
        print("\n【检查一致性】")
        consistency_issues = check_consistency(run_dir, context_steps, wechat_step_ids, [])
        for issue in consistency_issues:
            print(issue)
        if not consistency_issues:
            print("✅ run_context 与 handoff 状态一致")
        else:
            print(f"⚠️  发现 {len(consistency_issues)} 个一致性问题")

    # 总结
    total_issues = len(context_issues) + len(wechat_issues)
    if consistency_issues:
        total_issues += len(consistency_issues)

    print("\n" + "=" * 50)
    if total_issues == 0:
        print("✨ 所有检查通过!")
        print("=" * 50)
        sys.exit(0)
    else:
        print(f"❌ 发现 {total_issues} 个问题")
        print("=" * 50)
        sys.exit(1)


if __name__ == "__main__":
    main()
