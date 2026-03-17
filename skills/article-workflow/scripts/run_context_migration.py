#!/usr/bin/env python3
"""
run_context.yaml 迁移工具
处理 v1 → v2 的自动迁移
"""

from typing import Dict, Any


def migrate_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    v1 格式 → v2 格式迁移

    变更说明：
    - v2 删除了 current_step 的强制同步（现在是派生值，仅用于显示）
    - v2 使用 workflow.yaml 作为 SSOT（run_context.yaml 仅存储运行时状态）
    - 所有步骤状态存储在 steps 字典中（已存在，无需迁移）

    向后兼容性：
    - v2 格式完全兼容 v1 的 run_context.yaml
    - 现有运行实例可正常恢复
    """
    migrated = False

    # 1. 检查并添加 workflow 字段
    if "workflow" not in data:
        data["workflow"] = {
            "name": "article-creator",
            "version": "3.3.0",
            "created_at": "2026-01-18"
        }
        migrated = True

    # 2. 确保 steps 字段存在并补齐缺失步骤
    required_steps = {
        "00_init": {"state": "PENDING", "artifacts": []},
        "01_research": {"state": "PENDING", "artifacts": []},
        "02_rag": {"state": "PENDING", "artifacts": []},
        "03_titles": {"state": "PENDING", "artifacts": []},
        "04_select_title": {"state": "PENDING", "artifacts": []},
        "05_draft": {"state": "PENDING", "artifacts": []},
        "06_polish": {"state": "PENDING", "artifacts": []},
        "07_humanize": {"state": "PENDING", "artifacts": []},
        "08_prompts": {"state": "PENDING", "artifacts": []},
        "09_images": {"state": "PENDING", "artifacts": []},
        "10_upload_images": {"state": "PENDING", "artifacts": []},
        "11_wx_html": {"state": "PENDING", "artifacts": []},
        "12_draftbox": {"state": "PENDING", "artifacts": []}
    }

    if "steps" not in data:
        data["steps"] = required_steps
        migrated = True
    else:
        for step_id, default_state in required_steps.items():
            if step_id not in data["steps"]:
                data["steps"][step_id] = default_state
                migrated = True

    # 3. 确保 steps_index 存在且完整
    expected_index = [
        "00_init", "01_research", "02_rag", "03_titles",
        "04_select_title", "05_draft", "06_polish",
        "07_humanize", "08_prompts", "09_images",
        "10_upload_images", "11_wx_html", "12_draftbox"
    ]
    if data.get("steps_index") != expected_index:
        data["steps_index"] = expected_index
        migrated = True

    # 4. 确保 decisions 字段完整
    if "decisions" not in data:
        data["decisions"] = {}

    if "llm" not in data["decisions"]:
        data["decisions"]["llm"] = {"provider": "claude-code"}
        migrated = True

    if "wechat" not in data["decisions"]:
        data["decisions"]["wechat"] = {
            "account": None,
            "title": None
        }
        migrated = True

    # 新增：确保 rewrite 决策点存在
    if "rewrite" not in data["decisions"]:
        data["decisions"]["rewrite"] = {
            "style": None,      # 旧版默认使用 style1
            "confirmed": False  # 首次运行需要确认
        }
        migrated = True

    if "image" not in data["decisions"]:
        data["decisions"]["image"] = {
            "confirmed": False,
            "count": None,
            "orientation": "landscape",
            "poster_ratio_landscape": "16:9",
            "poster_ratio_portrait": "3:4",
            "cover_ratio": "16:9",
            "model": "doubao-seedream-4-5-251128",
            "resolution": "2k"
        }
        migrated = True

    # 5. 确保 pending_questions 字段存在
    if "pending_questions" not in data:
        data["pending_questions"] = []
        migrated = True

    # 6. current_step 保留（用于显示，但不影响调度逻辑）
    # v2 不再强制同步 current_step，但保留字段以兼容 --status 命令

    return migrated


def get_version(data: Dict[str, Any]) -> str:
    """获取 run_context.yaml 版本"""
    workflow = data.get("workflow", {})
    return workflow.get("version", "1.0.0")
