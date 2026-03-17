"""
Handoff Utils - 步骤交接工具模块

用于生成和写入 handoff.yaml 文件，记录工作流的输入输出。
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml


@dataclass
class HandoffFields:
    """Handoff 字段定义"""
    step_id: str
    inputs: List[str]
    outputs: List[str]
    summary: str
    style: Optional[str] = None
    next_instructions: Optional[List[str]] = None
    open_questions: Optional[List[str]] = None


def generate_handoff(
    step_id: str,
    inputs: List[str],
    outputs: List[str],
    summary: str,
    style: Optional[str] = None,
    next_instructions: Optional[List[str]] = None,
    open_questions: Optional[List[str]] = None,
) -> dict:
    """
    生成 handoff 数据结构

    Args:
        step_id: 步骤标识
        inputs: 输入文件列表
        outputs: 输出文件列表
        summary: 步骤摘要
        style: 写作风格（可选）
        next_instructions: 下一步指令（可选）
        open_questions: 待解决问题（可选）

    Returns:
        handoff 数据字典
    """
    handoff = {
        "step_id": step_id,
        "timestamp": datetime.now().isoformat(),
        "inputs": inputs,
        "outputs": outputs,
        "summary": summary,
    }

    if style:
        handoff["style"] = style

    if next_instructions:
        handoff["next_instructions"] = next_instructions

    if open_questions:
        handoff["open_questions"] = open_questions

    return handoff


def write_handoff_yaml(output_path: str, handoff_data: dict) -> None:
    """
    写入 handoff.yaml 文件

    Args:
        output_path: 输出文件路径
        handoff_data: handoff 数据字典
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(handoff_data, f, allow_unicode=True, default_flow_style=False)
