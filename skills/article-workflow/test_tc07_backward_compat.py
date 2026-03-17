#!/usr/bin/env python3
"""
测试旧版 run_context.yaml 的向后兼容性
验收标准：任何旧 run_context 都能被安全读取，不会崩
"""

import tempfile
import yaml
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from orchestrator import migrate_run_context


def test_minimal_old_context():
    """测试最小旧版结构"""
    print("=" * 70)
    print("测试1：最小旧版结构（只有基本字段）")
    print("=" * 70)

    old_data = {
        "run_id": "20260113__test__abc123",
        "topic": "测试话题",
        "platforms": ["wechat"],
        "status": "RUNNING",
        "current_step": "00_init",
        "decisions": {},
        "pending_questions": []
    }

    migrated = migrate_run_context(old_data)

    # 验证新增字段
    assert "workflow" in old_data, "缺失 workflow 字段"
    assert old_data["workflow"]["name"] == "insurance-article-creator"
    assert "steps" in old_data, "缺失 steps 字段"
    assert "steps_index" in old_data, "缺失 steps_index 字段"
    assert "decisions" in old_data, "缺失 decisions 字段"
    assert "image" in old_data["decisions"], "缺失 decisions.image"
    assert "wechat" in old_data["decisions"], "缺失 decisions.wechat"
    assert old_data["decisions"]["image"]["confirmed"] == False
    assert old_data["decisions"]["wechat"]["confirmed"] == False

    print("PASS: 最小旧版结构成功迁移")
    return True


def test_partial_missing_fields():
    """测试部分字段缺失"""
    print("\n" + "=" * 70)
    print("测试2：部分字段缺失（有 steps，缺 workflow）")
    print("=" * 70)

    old_data = {
        "run_id": "20260113__test__def456",
        "topic": "测试话题",
        "platforms": ["wechat"],
        "status": "RUNNING",
        "current_step": "01_research",
        "decisions": {
            "image": {
                "orientation": "landscape",
                "count": 4
                # 缺 confirmed
            },
            "wechat": {
                "account": "main"
                # 缺 confirmed
            }
        },
        "pending_questions": [],
        "steps": {  # 有 steps
            "00_init": {"state": "DONE", "artifacts": []},
        }
        # 缺 steps_index, workflow
    }

    migrated = migrate_run_context(old_data)

    # 验证新增字段，保留原有字段
    assert "workflow" in old_data
    assert "steps_index" in old_data
    assert old_data["decisions"]["image"]["orientation"] == "landscape", "原有值应保留"
    assert old_data["decisions"]["image"]["confirmed"] == False, "新增 confirmed"
    assert old_data["decisions"]["wechat"]["account"] == "main", "原有值应保留"

    print("PASS: 部分字段缺失成功迁移，原有值保留")
    return True


def test_new_context_no_change():
    """测试新版结构不应触发迁移"""
    print("\n" + "=" * 70)
    print("测试3：新版结构（不应修改）")
    print("=" * 70)

    new_data = {
        "run_id": "20260113__test__ghi789",
        "topic": "测试话题",
        "platforms": ["wechat"],
        "workflow": {
            "name": "insurance-article-creator",
            "version": "1.0.0"
        },
        "steps": {
            "00_init": {"state": "DONE", "artifacts": []}
        },
        "steps_index": ["00_init", "01_research"],
        "status": "RUNNING",
        "current_step": "00_init",
        "decisions": {
            "image": {"confirmed": False},
            "wechat": {"confirmed": False}
        },
        "pending_questions": []
    }

    original_workflow = new_data["workflow"]
    original_steps = new_data["steps"]
    original_decisions = new_data["decisions"]

    migrated = migrate_run_context(new_data)

    # 不应触发迁移
    assert not migrated, "新版结构不应触发迁移"
    assert new_data["workflow"] is original_workflow, "workflow 对象不应被替换"
    assert new_data["steps"] is original_steps, "steps 对象不应被替换"
    assert new_data["decisions"] is original_decisions, "decisions 对象不应被替换"

    print("PASS: 新版结构保持不变")
    return True


def test_with_yaml_file():
    """测试实际 YAML 文件读写"""
    print("\n" + "=" * 70)
    print("测试4：实际 YAML 文件读写（模拟 cmd_status 用例）")
    print("=" * 70)

    old_yaml_content = """
run_id: "20260113__test__jkl012"
topic: "测试话题"
platforms: ["wechat"]
status: "RUNNING"
current_step: "00_init"
decisions: {}
pending_questions: []
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(old_yaml_content)
        temp_path = Path(f.name)

    try:
        # 读取并迁移
        with open(temp_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        migrate_run_context(data)

        # 写回
        with open(temp_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

        # 重新读取验证
        with open(temp_path, 'r', encoding='utf-8') as f:
            migrated_data = yaml.safe_load(f)

        assert "workflow" in migrated_data
        assert "steps" in migrated_data
        assert "steps_index" in migrated_data
        assert migrated_data["decisions"]["image"]["confirmed"] == False
        assert migrated_data["decisions"]["wechat"]["confirmed"] == False

        print("PASS: YAML 文件读写正常")
        return True

    finally:
        temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    print("\n向后兼容性测试\n")

    all_passed = True

    all_passed = all_passed and test_minimal_old_context()
    all_passed = all_passed and test_partial_missing_fields()
    all_passed = all_passed and test_new_context_no_change()
    all_passed = all_passed and test_with_yaml_file()

    print("\n" + "=" * 70)
    if all_passed:
        print("所有测试通过")
        exit(0)
    else:
        print("部分测试失败")
        exit(1)
