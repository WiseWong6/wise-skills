#!/usr/bin/env python3
"""
content-research-workflow 测试脚本

验证技能配置和 MCP 工具可用性。
"""

import json
import subprocess
import sys
from pathlib import Path


def print_section(title: str) -> None:
    """打印章节标题"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def check_skill_config() -> dict:
    """检查技能配置"""
    print_section("检查技能配置")

    skill_dir = Path(__file__).parent.parent
    skill_md = skill_dir / "SKILL.md"

    results = {
        "skill_dir_exists": skill_dir.exists(),
        "skill_md_exists": skill_md.exists(),
        "scripts_dir_exists": (skill_dir / "scripts").exists(),
    }

    print(f"✅ 技能目录: {skill_dir}")
    print(f"✅ SKILL.md: {results['skill_md_exists']}")
    print(f"✅ scripts 目录: {results['scripts_dir_exists']}")

    if results["skill_md_exists"]:
        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read()
            print(f"✅ SKILL.md 版本: {extract_version(content)}")
            print(f"✅ SKILL.md 大小: {len(content)} 字节")

    return results


def extract_version(content: str) -> str:
    """提取版本号"""
    for line in content.split('\n'):
        if line.startswith("version:"):
            return line.split(":")[1].strip().replace('"', '')
    return "未知"


def check_mcp_servers() -> dict:
    """检查 MCP 服务器可用性"""
    print_section("检查 MCP 服务器")

    results = {}

    try:
        output = subprocess.check_output(
            ["claude", "mcp", "list"],
            stderr=subprocess.DEVNULL,
            text=True
        )

        # 解析输出
        servers = []
        for line in output.split('\n'):
            if '✓' in line or '✗' in line:
                servers.append(line)

        for server in servers:
            name = server.split(':')[0].strip()
            status = '✅' if '✓' in server else '❌'
            print(f"{status} {name}")

        results["servers"] = servers

    except Exception as e:
        print(f"❌ MCP 列表命令失败: {e}")
        results["error"] = str(e)

    return results


def test_cli_scripts() -> dict:
    """测试 CLI 脚本"""
    print_section("测试 CLI 脚本")

    script_dir = Path(__file__).parent
    results = {}

    scripts = [
        "trend_analysis.py",
        "gap_analysis.py",
        "research_search.py",
        "brief_generator.py"
    ]

    for script in scripts:
        script_path = script_dir / script
        if script_path.exists():
            print(f"✅ {script}")
            results[script] = "exists"
        else:
            print(f"❌ {script} - 不存在")
            results[script] = "missing"

    return results


def test_brief_generator() -> dict:
    """测试 Brief 生成器"""
    print_section("测试 Brief 生成器")

    script_dir = Path(__file__).parent
    brief_gen = script_dir / "brief_generator.py"

    results = {}

    if not brief_gen.exists():
        print("❌ brief_generator.py 不存在")
        return {"error": "script_not_found"}

    # 测试生成模板
    print("📝 生成 Brief 模板...")

    try:
        output = subprocess.check_output(
            [sys.executable, str(str(brief_gen)), "--topic", "测试主题"],
            stderr=subprocess.PIPE,
            text=True
        )

        output_file = Path("content_brief.md")
        if output_file.exists():
            print(f"✅ Brief 文件已生成: {output_file}")
            print(f"✅ 文件大小: {len(output_file.read_bytes())} 字节")

            results["output_file"] = str(output_file)
            results["output_size"] = len(output_file.read_bytes())
        else:
            print("❌ Brief 文件未生成")
            results["error"] = "file_not_created"

    except Exception as e:
        print(f"❌ Brief 生成失败: {e}")
        results["error"] = str(e)

    return results


def show_usage_examples() -> None:
    """显示使用示例"""
    print_section("使用示例")

    print("""
CLI 调用：
  # 趋势分析
  python3 scripts/trend_analysis.py --domain AI --time-range month

  # 缺口分析
  python3 scripts/gap_analysis.py --competitors 公众号A 公众号B --platform 公众号

  # 研究搜索
  python3 scripts/research_search.py --query "AI Agent 最佳实践"

  # Brief 生成
  python3 scripts/brief_generator.py --topic "AI Agent 最佳实践"

  # 管道输入
  echo "AI Agent 最佳实践" | python3 scripts/brief_generator.py --stdin

Claude Code 调用：
  在对话中直接说：
  - "分析 AI 领域在 2026 年 1 月的趋势"
  - "研究 Claude 3.5 Sonnet 的编程能力"
  - "为 'AI Agent 最佳实践' 生成内容 Brief"

  AI 将自动调用 MCP 工具（Firecrawl、Context7）执行真实搜索。
""")


def main():
    """主函数"""
    print("🧪 content-research-workflow 技能测试")
    print(f"时间戳: {subprocess.check_output(['date'], text=True).strip()}")

    all_results = {}

    # 检查技能配置
    all_results["skill_config"] = check_skill_config()

    # 检查 MCP 服务器
    all_results["mcp_servers"] = check_mcp_servers()

    # 测试 CLI 脚本
    all_results["cli_scripts"] = test_cli_scripts()

    # 测试 Brief 生成器
    all_results["brief_generator"] = test_brief_generator()

    # 显示使用示例
    show_usage_examples()

    # 保存结果
    print_section("测试结果")

    with open("test_results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print("✅ 测试结果已保存到: test_results.json")

    # 清理生成的测试文件
    brief_file = Path("content_brief.md")
    if brief_file.exists():
        # 不删除，让用户可以查看结果
        print(f"💡 测试 Brief 文件: {brief_file.absolute()}")

    print("\n✅ 测试完成")


if __name__ == "__main__":
    main()
