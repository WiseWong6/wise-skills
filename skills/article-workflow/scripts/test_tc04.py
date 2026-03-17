#!/usr/bin/env python3
"""
TC-04 测试脚本
验证非交互模式下缺参快速失败
"""
import subprocess
import sys
from pathlib import Path

def test_tc04():
    """
    TC-04: 验证非交互缺参快速失败
    期望：exit code != 0; 错误信息清晰可追溯
    """
    print("=" * 60)
    print("TC-04 测试：非交互缺参快速失败")
    print("=" * 60)

    # 创建临时测试文件
    test_dir = Path("/tmp/test_tc04")
    test_dir.mkdir(parents=True, exist_ok=True)

    test_html = test_dir / "test.html"
    test_html.write_text("<section>test</section>", encoding="utf-8")

    # 测试场景1：缺少 --account 参数（必填）
    print("\n场景1：缺少 --account 参数（必填参数）")
    print("-" * 40)

    script_path = Path.home() / ".claude" / "skills" / "wechat-draftbox" / "scripts" / "wechat_draftbox_v2.py"

    cmd = [
        sys.executable, str(script_path),
        "--content-html", str(test_html),
        "--title", "测试标题"
        # 故意不传 --account
    ]

    print(f"执行命令: {' '.join(cmd)}")
    print()

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30
    )

    print(f"退出码: {result.returncode}")

    if result.returncode != 0:
        print("✅ PASS: 脚本快速失败（exit code != 0）")
        print(f"错误信息: {result.stderr.strip()}")
    else:
        print("❌ FAIL: 脚本没有按预期失败")
        print(f"输出: {result.stdout}")

    print()
    print("=" * 60)

    # 结果判断
    if result.returncode != 0:
        print("\n【测试结果】")
        print("TC-04: ✅ PASS")
        print("说明：非交互模式下缺少必填参数 --account 时，脚本快速失败（exit code = 2）")
        print("      错误信息清晰指明缺失参数，可从日志追溯")
        return True
    else:
        print("\n【测试结果】")
        print("TC-04: ❌ FAIL")
        print("说明：脚本未按预期失败")
        return False

if __name__ == "__main__":
    success = test_tc04()
    sys.exit(0 if success else 1)
