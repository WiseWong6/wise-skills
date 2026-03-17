#!/usr/bin/env python3
"""
技能契约调用器
确保子技能按规范执行并留下完成标记
"""

import os
import sys
import yaml
from pathlib import Path
from typing import Optional


class ImagePrompterInvoker:
    """
    image-prompter 技能契约调用器
    强制完成5阶段流程，并留下标记
    """
    
    STAGES = [
        ("brief", "需求澄清", "确认内容/场景/受众/字多字少"),
        ("plan", "配图规划", "确定图片数量和内容拆块"),
        ("style", "风格选择", "从8种风格中选择"),
        ("layout", "布局选择", "从5种布局中选择"),
        ("copy", "文案定稿", "逐字定稿每张图的文案"),
        ("prompts", "提示词封装", "生成可复制的生图提示词"),
    ]
    
    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.output_file = self.project_dir / "07_图片提示词.md"
    
    def generate_stage_template(self) -> str:
        """生成5阶段流程模板"""
        lines = [
            "---",
            "image_prompter:",
            "  version: \"2.0\"",
            "  stages:",
        ]
        
        for stage_id, stage_name, desc in self.STAGES:
            lines.extend([
                f"    {stage_id}:",
                f"      name: \"{stage_name}\"",
                f"      description: \"{desc}\"",
                "      status: \"pending\"",
                "      confirmed_by: \"\"",
                "      timestamp: \"\"",
            ])
        
        lines.extend([
            "  style_selected: \"\"",
            "  layout_selected: \"\"",
            "  image_count: 0",
            "  copy_spec_confirmed: false",
            "---",
            "",
            "# 图片提示词",
            "",
            "> ⚠️ **本文件必须通过 `/image-prompter` 技能生成**",
            "> ",
            "> 禁止直接编辑或手动创建。如需修改，请重新调用技能。",
            "",
            "## 生成进度",
        ])
        
        for i, (stage_id, stage_name, desc) in enumerate(self.STAGES, 1):
            lines.append(f"- [ ] 阶段{i}：{stage_name} - {desc}")
        
        lines.extend([
            "",
            "---",
            "",
            "<!-- 阶段完成后在此填充内容 -->",
            "",
        ])
        
        return "\n".join(lines)
    
    def validate_completion(self) -> tuple[bool, str]:
        """
        验证 image-prompter 5阶段是否全部完成
        返回: (是否完成, 未完成阶段列表)
        """
        if not self.output_file.exists():
            return False, "文件不存在"
        
        content = self.output_file.read_text()
        
        # 检查 frontmatter
        if not content.startswith("---"):
            return False, "缺少 image_prompter frontmatter 标记"
        
        try:
            _, fm_content, _ = content.split("---", 2)
            fm = yaml.safe_load(fm_content) or {}
        except:
            return False, "frontmatter 解析失败"
        
        ip_info = fm.get("image_prompter", {})
        stages = ip_info.get("stages", {})
        
        incomplete = []
        for stage_id, stage_name, _ in self.STAGES:
            stage_info = stages.get(stage_id, {})
            if stage_info.get("status") != "done":
                incomplete.append(stage_name)
        
        if incomplete:
            return False, f"未完成阶段: {', '.join(incomplete)}"
        
        # 检查 style_selected
        if not ip_info.get("style_selected"):
            return False, "未选择风格"

        # 检查 layout_selected
        if not ip_info.get("layout_selected"):
            return False, "未选择布局"

        if not ip_info.get("copy_spec_confirmed"):
            return False, "文案定稿未确认"
        
        return True, "所有阶段已完成"
    
    def mark_stage_done(self, stage_id: str, confirmed_by: str = "user"):
        """标记某个阶段完成"""
        if not self.output_file.exists():
            return False
        
        content = self.output_file.read_text()
        if not content.startswith("---"):
            return False
        
        _, fm_content, body = content.split("---", 2)
        fm = yaml.safe_load(fm_content) or {}
        
        if "image_prompter" not in fm:
            fm["image_prompter"] = {}
        if "stages" not in fm["image_prompter"]:
            fm["image_prompter"]["stages"] = {}
        
        import datetime
        fm["image_prompter"]["stages"][stage_id] = {
            "status": "done",
            "confirmed_by": confirmed_by,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # 重新生成 frontmatter
        new_fm = yaml.dump(fm, allow_unicode=True, sort_keys=False)
        new_content = f"---\n{new_fm}---{body}"
        self.output_file.write_text(new_content)
        
        return True
    
    def print_checklist(self):
        """打印给用户的手动执行清单"""
        print("""
╔══════════════════════════════════════════════════════════════════╗
║  🎨 Image Prompter 执行清单（必须完成6阶段）                      ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  请按顺序完成以下阶段：                                          ║
║                                                                  ║""")
        
        for i, (stage_id, stage_name, desc) in enumerate(self.STAGES, 1):
            print(f"║  阶段{i}：{stage_name:<10} - {desc:<30}  ║")
        
        print("""║                                                                  ║
║  执行方式：                                                      ║
║  1. 调用：claude /image-prompter --input 06_终稿.md              ║
║  2. 按技能指引完成5阶段流程                                      ║
║  3. 完成后运行：python skill_invoker.py --validate               ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
""")


def main():
    """CLI 入口"""
    import argparse
    parser = argparse.ArgumentParser(description="Skill Invoker")
    parser.add_argument("--project-dir", required=True, help="项目目录")
    parser.add_argument("--init", action="store_true", help="初始化模板")
    parser.add_argument("--validate", action="store_true", help="验证完成状态")
    parser.add_argument("--mark-done", help="标记阶段完成（stage_id）")
    parser.add_argument("--checklist", action="store_true", help="打印清单")
    
    args = parser.parse_args()
    
    invoker = ImagePrompterInvoker(args.project_dir)
    
    if args.init:
        template = invoker.generate_stage_template()
        invoker.output_file.write_text(template)
        print(f"✅ 已初始化模板: {invoker.output_file}")
        return
    
    if args.validate:
        is_complete, message = invoker.validate_completion()
        if is_complete:
            print(f"✅ {message}")
            sys.exit(0)
        else:
            print(f"❌ {message}")
            sys.exit(1)
    
    if args.mark_done:
        invoker.mark_stage_done(args.mark_done)
        print(f"✅ 阶段 {args.mark_done} 已标记为完成")
        return
    
    if args.checklist:
        invoker.print_checklist()
        return
    
    parser.print_help()


if __name__ == "__main__":
    main()
