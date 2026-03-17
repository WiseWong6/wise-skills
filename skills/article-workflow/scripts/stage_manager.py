#!/usr/bin/env python3
"""
Article Workflow 阶段管理器
强制状态追踪 + 阻断检查点
"""

import os
import sys
import yaml
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, Literal


@dataclass
class StageGate:
    """阶段检查点定义"""
    stage_id: str
    required_files: List[str]
    required_markers: List[str]  # frontmatter 中必须存在的标记
    auto_actions: List[str]  # 自动执行的操作
    block_message: str  # 阻断时显示的消息


# 定义所有强制检查点
STAGE_GATES = {
    "07_select_title": StageGate(
        stage_id="07_select_title",
        required_files=["04_标题方案.md"],
        required_markers=["selected_title"],
        auto_actions=["rename_project_dir"],
        block_message="""
⚠️ 阶段7未完成：标题确认后必须执行以下操作：
1. 重命名项目目录（自动）
2. 更新 frontmatter 中的 topic 字段

正在自动执行..."""
    ),
    "12_prompts": StageGate(
        stage_id="12_prompts", 
        required_files=["07_图片提示词.md"],
        required_markers=["image_prompter", "style_selected", "copy_spec_confirmed"],
        auto_actions=[],
        block_message="""
⚠️ 阶段12违规：图片提示词必须通过 /image-prompter 技能生成

当前状态：检测到 07_图片提示词.md 缺少 image-prompter 阶段标记

正确流程：
1. 调用 /image-prompter 技能
2. 完成5阶段流程（需求澄清→配图规划→风格选择→文案定稿→提示词封装）
3. 阶段标记自动写入后，方可进入阶段13

请执行：claude /image-prompter --input 06_终稿.md"""
    ),
    "13_images": StageGate(
        stage_id="13_images",
        required_files=["08_图片/"],
        required_markers=["images_generated"],
        auto_actions=[],
        block_message="""
⚠️ 阶段13依赖检查失败：阶段12未完成

请先完成阶段12（image-prompter），然后再生成图片。"""
    )
}


class StageManager:
    """阶段管理器"""
    
    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.frontmatter_file = self._find_frontmatter_file()
        self.frontmatter = self._load_frontmatter()
    
    def _find_frontmatter_file(self) -> Optional[Path]:
        """查找包含 frontmatter 的主文件"""
        # Obsidian 模式：查找 📋 开头的 .md 文件
        for f in self.project_dir.glob("📋 *.md"):
            return f
        # 查找任何包含 project_id 的 .md 文件
        for f in self.project_dir.glob("*.md"):
            content = f.read_text()
            if "project_id:" in content:
                return f
        return None
    
    def _load_frontmatter(self) -> dict:
        """加载 frontmatter"""
        if not self.frontmatter_file:
            return {}
        content = self.frontmatter_file.read_text()
        if content.startswith("---"):
            _, fm, _ = content.split("---", 2)
            return yaml.safe_load(fm) or {}
        return {}
    
    def _save_frontmatter(self):
        """保存 frontmatter"""
        if not self.frontmatter_file:
            return False
        content = self.frontmatter_file.read_text()
        fm_yaml = yaml.dump(self.frontmatter, allow_unicode=True, sort_keys=False)
        if content.startswith("---"):
            _, _, body = content.split("---", 2)
            new_content = f"---\n{fm_yaml}---{body}"
        else:
            new_content = f"---\n{fm_yaml}---\n{content}"
        self.frontmatter_file.write_text(new_content)
        return True
    
    def check_stage_gate(self, stage_id: str) -> tuple[bool, str]:
        """
        检查阶段检查点
        返回: (是否通过, 消息)
        """
        gate = STAGE_GATES.get(stage_id)
        if not gate:
            return True, f"阶段 {stage_id} 无强制检查点"
        
        # 检查 required_markers
        steps = self.frontmatter.get("steps", {})
        stage_info = steps.get(stage_id.replace("0", "").replace("_", ""), {})
        
        for marker in gate.required_markers:
            if marker == "selected_title":
                if not self.frontmatter.get("selected_title"):
                    return False, gate.block_message
            elif marker == "image_prompter":
                # 检查 07_图片提示词.md 是否有 image-prompter 标记
                prompts_file = self.project_dir / "07_图片提示词.md"
                if not prompts_file.exists():
                    return False, gate.block_message
                content = prompts_file.read_text()
                if "image_prompter:" not in content:
                    return False, gate.block_message
        
        return True, f"阶段 {stage_id} 检查通过"
    
    def mark_stage_complete(self, stage_id: str, **markers):
        """标记阶段完成，写入标记"""
        if "steps" not in self.frontmatter:
            self.frontmatter["steps"] = {}
        
        # 转换 stage_id 格式
        key = stage_id.replace("0", "").replace("_", "")
        if key not in self.frontmatter["steps"]:
            self.frontmatter["steps"][key] = {}
        
        self.frontmatter["steps"][key]["status"] = "done"
        for k, v in markers.items():
            self.frontmatter["steps"][key][k] = v
        
        self._save_frontmatter()
        return True
    
    def auto_rename_project(self, new_title: str) -> str:
        """
        自动重命名项目目录
        返回新路径
        """
        # 生成新目录名
        date_str = self.project_dir.name[:10]  # 保留日期部分
        # 简化标题为 slug
        import re
        slug = re.sub(r'[^\u4e00-\u9fff\w]+', '-', new_title).strip('-')[:40]
        new_dir_name = f"{date_str}-{slug}"
        
        new_path = self.project_dir.parent / new_dir_name
        
        # 执行重命名
        self.project_dir.rename(new_path)
        
        # 更新 frontmatter
        self.frontmatter["topic"] = new_title
        self.mark_stage_complete("07_select_title", rename_completed=True)
        
        return str(new_path)


def main():
    """CLI 入口"""
    import argparse
    parser = argparse.ArgumentParser(description="Article Workflow Stage Manager")
    parser.add_argument("--project-dir", required=True, help="项目目录路径")
    parser.add_argument("--check", required=True, help="检查的阶段ID")
    parser.add_argument("--mark-complete", help="标记阶段完成")
    parser.add_argument("--rename", help="重命名为新标题")
    
    args = parser.parse_args()
    
    manager = StageManager(args.project_dir)
    
    if args.rename:
        new_path = manager.auto_rename_project(args.rename)
        print(f"✅ 项目已重命名为: {new_path}")
        return
    
    if args.check:
        passed, message = manager.check_stage_gate(args.check)
        print(message)
        sys.exit(0 if passed else 1)
    
    if args.mark_complete:
        manager.mark_stage_complete(args.mark_complete)
        print(f"✅ 阶段 {args.mark_complete} 已标记为完成")


if __name__ == "__main__":
    main()
