#!/usr/bin/env python3
"""工作流步骤输出验证器

用于验证每个步骤的输出是否符合预期，确保工作流可以继续执行。
"""

from pathlib import Path


class StepValidationError(Exception):
    """步骤验证失败异常"""
    pass


def validate_step_outputs(step_id: str, run_dir: str, expected_outputs: list[str]) -> None:
    """验证步骤输出文件是否存在且非空

    Args:
        step_id: 步骤ID（用于错误信息）
        run_dir: 运行目录根路径
        expected_outputs: 期望的输出文件列表（相对于 run_dir 的路径）

    Raises:
        StepValidationError: 当任何输出文件不存在或为空时
    """
    run_path = Path(run_dir)
    for rel_path in expected_outputs:
        full_path = run_path / rel_path
        if not full_path.exists():
            raise StepValidationError(f"步骤 {step_id} 失败：文件不存在 {rel_path}")
        if full_path.is_file() and full_path.stat().st_size == 0:
            raise StepValidationError(f"步骤 {step_id} 失败：文件为空 {rel_path}")
    print(f"✓ 步骤 {step_id} 验证通过")


def validate_handoff(handoff_path: str) -> dict:
    """验证 handoff.yaml 文件并返回其内容

    Args:
        handoff_path: handoff.yaml 文件路径

    Returns:
        handoff.yaml 的解析内容

    Raises:
        StepValidationError: 当文件不存在、格式错误或缺少必要字段时
    """
    path = Path(handoff_path)
    if not path.exists():
        raise StepValidationError(f"handoff.yaml 不存在: {handoff_path}")

    try:
        import yaml
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except Exception as e:
        raise StepValidationError(f"handoff.yaml 解析失败: {e}")

    # 验证必要字段
    required_fields = ['step_id', 'inputs', 'outputs', 'summary']
    for field in required_fields:
        if field not in data:
            raise StepValidationError(f"handoff.yaml 缺少必要字段: {field}")

    return data


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("用法: python step_validator.py <step_id> <run_dir> <expected_output1> [expected_output2 ...]")
        sys.exit(1)

    step_id = sys.argv[1]
    run_dir = sys.argv[2]
    expected_outputs = sys.argv[3:]

    try:
        validate_step_outputs(step_id, run_dir, expected_outputs)
        sys.exit(0)
    except StepValidationError as e:
        print(f"验证失败: {e}", file=sys.stderr)
        sys.exit(1)
