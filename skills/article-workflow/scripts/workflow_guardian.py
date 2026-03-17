#!/usr/bin/env python3
"""
Workflow Guardian - 工作流守卫者
执行前强制检查，阻断违规操作
"""

import os
import sys
import yaml
from pathlib import Path
from typing import List, Tuple


class WorkflowGuardian:
    """工作流守卫者"""
    
    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def check_stage_07_rename(self) -> bool:
        """检查阶段7：目录是否已重命名"""
        # 检查目录名格式
        dir_name = self.project_dir.name
        
        # 如果目录名包含 __，说明还是临时格式，需要重命名
        if "__" in dir_name:
            # 检查 frontmatter 中是否有 rename_completed 标记
            frontmatter = self._load_frontmatter()
            steps = frontmatter.get("steps", {})
            
            if not steps.get("selected_title", {}).get("rename_completed"):
                self.errors.append(f"""
❌ 阶段7检查失败：目录未重命名

当前目录: {dir_name}
检测到格式仍为临时格式（包含 __），但 frontmatter 中缺少 rename_completed 标记。

正确操作：
1. 确认用户已选择标题
2. 运行：python stage_manager.py --project-dir {self.project_dir} --rename "选中的标题"

或手动重命名目录并更新 frontmatter。
""")
                return False
        
        return True
    
    def check_stage_12_prompts(self) -> bool:
        """检查阶段12：image-prompter 是否规范执行"""
        prompts_file = self.project_dir / "07_图片提示词.md"
        
        if not prompts_file.exists():
            self.errors.append("""
❌ 阶段12检查失败：07_图片提示词.md 不存在

必须先调用 /image-prompter 技能生成提示词文件。
""")
            return False
        
        content = prompts_file.read_text()
        
        # 检查是否有 image_prompter frontmatter
        if "image_prompter:" not in content:
            self.errors.append(f"""
❌ 阶段12检查失败：图片提示词文件未通过 image-prompter 技能生成

检测到 07_图片提示词.md 缺少 image_prompter 标记。
可能原因：
- 文件是手动创建的
- AI 直接生成了文件，未调用技能

正确操作：
1. 删除当前 07_图片提示词.md
2. 调用：claude /image-prompter --input 06_终稿.md
3. 完成5阶段流程后，再执行阶段13
""")
            return False
        
        # 解析 frontmatter 检查各阶段状态
        try:
            _, fm_content, _ = content.split("---", 2)
            fm = yaml.safe_load(fm_content) or {}
        except:
            self.warnings.append("⚠️ 无法解析 07_图片提示词.md 的 frontmatter")
            return True  # 保守通过，但警告
        
        ip_info = fm.get("image_prompter", {})
        stages = ip_info.get("stages", {})
        
        # 检查各阶段
        required_stages = [
            ("brief", "需求澄清"),
            ("plan", "配图规划"),
            ("style", "风格选择"),
            ("layout", "布局选择"),
            ("copy", "文案定稿"),
            ("prompts", "提示词封装"),
        ]
        
        incomplete = []
        for stage_id, stage_name in required_stages:
            stage_info = stages.get(stage_id, {})
            if stage_info.get("status") != "done":
                incomplete.append(stage_name)
        
        if incomplete:
            self.errors.append(f"""
❌ 阶段12检查失败：image-prompter 6阶段未完成

未完成阶段: {', '.join(incomplete)}

请完成所有阶段后再进入阶段13。
""")
            return False
        
        # 检查风格选择
        if not ip_info.get("style_selected"):
            self.errors.append("""
❌ 阶段12检查失败：未选择图片风格

必须在阶段2.5选择风格，并记录在 frontmatter 中。
""")
            return False

        # 检查布局选择
        if not ip_info.get("layout_selected"):
            self.errors.append("""
❌ 阶段12检查失败：未选择图片布局

必须在阶段2.6选择布局，并记录在 frontmatter 中。
""")
            return False

        return True
    
    def check_stage_13_prerequisites(self) -> bool:
        """检查阶段13前置条件"""
        # 阶段13依赖阶段12
        return self.check_stage_12_prompts()
    
    def _load_frontmatter(self) -> dict:
        """加载 frontmatter"""
        # 查找主文件
        main_file = None
        for f in self.project_dir.glob("📋 *.md"):
            main_file = f
            break
        
        if not main_file:
            for f in self.project_dir.glob("*.md"):
                if "project_id:" in f.read_text():
                    main_file = f
                    break
        
        if not main_file:
            return {}
        
        content = main_file.read_text()
        if content.startswith("---"):
            _, fm, _ = content.split("---", 2)
            return yaml.safe_load(fm) or {}
        return {}
    
    def run_all_checks(self) -> Tuple[bool, List[str], List[str]]:
        """运行所有检查"""
        self.check_stage_07_rename()
        self.check_stage_12_prompts()
        
        passed = len(self.errors) == 0
        return passed, self.errors, self.warnings
    
    def print_report(self):
        """打印检查报告"""
        passed, errors, warnings = self.run_all_checks()
        
        print("╔══════════════════════════════════════════════════════════════════╗")
        print("║           🔍 Workflow Guardian 检查报告                          ║")
        print("╠══════════════════════════════════════════════════════════════════╣")
        print(f"║  项目目录: {str(self.project_dir):<48} ║")
        print("╠══════════════════════════════════════════════════════════════════╣")
        
        if passed and not warnings:
            print("║  ✅ 所有检查通过                                                ║")
        elif passed:
            print("║  ⚠️ 检查通过，但有警告                                          ║")
        else:
            print("║  ❌ 检查失败，请修复以下问题                                    ║")
        
        print("╚══════════════════════════════════════════════════════════════════╝")
        print()
        
        if errors:
            print("❌ 错误（必须修复）：")
            for i, error in enumerate(errors, 1):
                print(f"\n【错误 {i}】{error}")
        
        if warnings:
            print("\n⚠️ 警告（建议修复）：")
            for warning in warnings:
                print(f"  - {warning}")
        
        return passed


def main():
    """CLI 入口"""
    import argparse
    parser = argparse.ArgumentParser(description="Workflow Guardian")
    parser.add_argument("--project-dir", required=True, help="项目目录")
    parser.add_argument("--before-stage", help="在执行某阶段前检查")
    parser.add_argument("--strict", action="store_true", help="严格模式（有警告也失败）")
    
    args = parser.parse_args()
    
    guardian = WorkflowGuardian(args.project_dir)
    
    if args.before_stage:
        # 执行特定阶段前的检查
        if args.before_stage == "13":
            passed = guardian.check_stage_12_prompts()
        elif args.before_stage == "08":
            passed = guardian.check_stage_07_rename()
        else:
            passed = True
        
        if not passed:
            print("\n".join(guardian.errors))
            sys.exit(1)
        sys.exit(0)
    
    # 运行全部检查
    passed = guardian.print_report()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
