#!/usr/bin/env python3
"""
文章创作工作流 - Orchestrator
核心职责：
1. 管理 run_context.yaml（运行时状态，非 SSOT）
2. 使用 ParallelScheduler 执行 DAG 调度
3. 处理强制确认点
4. 支持 resume 机制
5. 调用下游 skills

SSOT 变更（v4.2.0）：
- 传统模式：run_context.yaml + handoff.yaml
- Obsidian 模式：frontmatter + wikilinks + Bases

"""

import os
import sys
import yaml
import json
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import re

# 导入迁移工具
from run_context_migration import migrate_v1_to_v2

# Obsidian Vault 路径
OBSIDIAN_VAULT = Path("/Users/wisewong/Documents/Obsidian Vault")
OBSIDIAN_PROJECTS_DIR = OBSIDIAN_VAULT / "01_文章项目"
OBSIDIAN_RESEARCH_DIR = OBSIDIAN_VAULT / "00_研究库"
OBSIDIAN_TEMPLATES_DIR = OBSIDIAN_PROJECTS_DIR / ".templates"

# 导入共享的 style_recommender 模块
_shared_dir = Path(__file__).parent.parent.parent / "shared"
sys.path.insert(0, str(_shared_dir))
from style_recommender import (
    normalize_style,
    recommend_style,
    get_style_description,
    list_all_styles,
)

# 导入 article-formatted 的 MarkdownCleaner
_formatted_dir = Path(__file__).parent.parent.parent / "article-formatted" / "references"
sys.path.insert(0, str(_formatted_dir))
from cleaner import MarkdownCleaner


# ==================== Obsidian Frontmatter 工具 ====================

def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """解析 Markdown frontmatter，返回 (metadata, body)"""
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    try:
        metadata = yaml.safe_load(parts[1]) or {}
        body = parts[2].strip()
        return metadata, body
    except yaml.YAMLError:
        return {}, content


def write_frontmatter(metadata: Dict[str, Any], body: str) -> str:
    """将 metadata 和 body 组合成带 frontmatter 的 Markdown"""
    yaml_content = yaml.dump(metadata, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return f"---\n{yaml_content}---\n\n{body}"


def update_frontmatter(file_path: Path, updates: Dict[str, Any]) -> None:
    """更新 Markdown 文件的 frontmatter"""
    content = file_path.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(content)
    metadata.update(updates)
    metadata["updated"] = datetime.now().strftime("%Y-%m-%d")
    file_path.write_text(write_frontmatter(metadata, body), encoding="utf-8")


def read_frontmatter(file_path: Path) -> Dict[str, Any]:
    """读取 Markdown 文件的 frontmatter"""
    content = file_path.read_text(encoding="utf-8")
    metadata, _ = parse_frontmatter(content)
    return metadata


class RunContext:
    """管理 run_context.yaml 或 Obsidian frontmatter 的读写和状态转换"""

    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir)
        self.context_file = self.run_dir / "run_context.yaml"
        self.is_obsidian = not self.context_file.exists()
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        """加载状态（支持传统模式和 Obsidian 模式）"""
        # 传统模式：run_context.yaml
        if self.context_file.exists():
            with open(self.context_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            # 执行迁移检查
            if migrate_run_context(data):
                with open(self.context_file, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
            return data

        # Obsidian 模式：从主 Markdown 文件读取 frontmatter
        md_files = list(self.run_dir.glob("*.md"))
        if not md_files:
            raise FileNotFoundError(f"未找到 run_context.yaml 或 Markdown 文件: {self.run_dir}")

        # 使用第一个 Markdown 文件（通常是主项目文件）
        main_file = md_files[0]
        metadata = read_frontmatter(main_file)

        # 转换为传统格式的数据
        data = {
            "run_id": metadata.get("project_id", self.run_dir.name),
            "topic": metadata.get("topic", ""),
            "platforms": metadata.get("platforms", ["wechat"]),
            "status": metadata.get("status", "draft").upper(),
            "current_step": metadata.get("current_step", ""),
            "steps": self._convert_obsidian_steps(metadata.get("steps", {})),
            "decisions": {
                "wechat": metadata.get("publish", {}).get("wechat", {}),
                "xhs": metadata.get("publish", {}).get("xhs", {}),
            },
            "pending_questions": [],
        }
        return data

    def _convert_obsidian_steps(self, obsidian_steps: Dict) -> Dict[str, Any]:
        """将 Obsidian frontmatter 步骤格式转换为传统格式"""
        steps = {}
        step_mapping = {
            "research": "01_research",
            "outline": "02_outliner",
            "draft": "04_writer",
            "rag_enhance": "05_rag_enhance",
            "titles": "06_titles",
            "polish": "08_polish",
            "final": "09_final",
            "publish": "10_publish",
        }

        for obs_key, step_data in obsidian_steps.items():
            if obs_key in step_mapping:
                step_id = step_mapping[obs_key]
                status_map = {
                    "pending": "PENDING",
                    "draft": "RUNNING",
                    "done": "DONE",
                    "in_progress": "RUNNING",
                    "review": "RUNNING",
                }
                steps[step_id] = {
                    "state": status_map.get(step_data.get("status", "pending"), "PENDING"),
                    "artifacts": [step_data.get("file", "")] if step_data.get("file") else [],
                }
        return steps

    def save(self):
        """保存状态"""
        if self.is_obsidian:
            # Obsidian 模式：更新 Markdown 文件的 frontmatter
            md_files = list(self.run_dir.glob("*.md"))
            if md_files:
                main_file = md_files[0]
                metadata, body = parse_frontmatter(main_file.read_text(encoding="utf-8"))

                # 更新 frontmatter
                metadata["topic"] = self.data.get("topic", metadata.get("topic", ""))
                metadata["status"] = self.data.get("status", "draft").lower()
                metadata["updated"] = datetime.now().strftime("%Y-%m-%d")
                if "current_step" in self.data:
                    metadata["current_step"] = self.data["current_step"]

                main_file.write_text(write_frontmatter(metadata, body), encoding="utf-8")
        else:
            # 传统模式：保存 run_context.yaml
            with open(self.context_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.data, f, allow_unicode=True, default_flow_style=False)

    def get_step_state(self, step_id: str) -> str:
        """获取步骤状态"""
        return self.data["steps"][step_id]["state"]

    def update_step_state(self, step_id: str, state: str, artifacts: Optional[List[str]] = None):
        """更新步骤状态"""
        step = self.data["steps"].setdefault(step_id, {"state": "PENDING", "artifacts": []})
        prev_state = step.get("state")
        step["state"] = state
        if artifacts is not None:
            step["artifacts"] = artifacts

        now = datetime.now().isoformat(timespec="seconds")
        if state == "RUNNING":
            if not step.get("started_at") or prev_state == "FAILED":
                step["started_at"] = now
                step.pop("ended_at", None)
                step.pop("duration_sec", None)
        elif state in ["DONE", "FAILED"]:
            step["ended_at"] = now
            started_at = step.get("started_at")
            if started_at:
                try:
                    start_ts = datetime.fromisoformat(started_at)
                    end_ts = datetime.fromisoformat(now)
                    step["duration_sec"] = int((end_ts - start_ts).total_seconds())
                except ValueError:
                    step["duration_sec"] = None
        # 不再同步 current_step - 并行执行时会有多个 RUNNING 步骤
        self.save()

    def add_pending_question(self, question: Dict[str, Any]):
        """添加待确认问题"""
        self.data["pending_questions"].append(question)
        self.data["status"] = "WAITING_FOR_USER"
        self.save()

    def clear_pending_questions(self):
        """清空待确认问题"""
        self.data["pending_questions"] = []
        self.data["status"] = "RUNNING"
        self.save()

    def update_decision(self, key: str, value: Any):
        """更新决策"""
        keys = key.split('.')
        target = self.data["decisions"]
        for k in keys[:-1]:
            target = target.setdefault(k, {})
        target[keys[-1]] = value
        self.save()

    def get_decision(self, key: str, default: Any = None) -> Any:
        """获取决策值"""
        keys = key.split('.')
        target = self.data["decisions"]
        try:
            for k in keys:
                target = target[k]
            return target
        except (KeyError, TypeError):
            return default

    def get_active_steps(self) -> List[str]:
        """获取当前 RUNNING 状态的步骤"""
        active = []
        for step_id, state in self.data.get("steps", {}).items():
            if state.get("state") == "RUNNING":
                active.append(step_id)
        return active

    def get_completion_percentage(self) -> int:
        """获取完成百分比"""
        steps = self.data.get("steps", {})
        if not steps:
            return 0
        done = sum(1 for s in steps.values() if s.get("state") == "DONE")
        return int(done / len(steps) * 100)


class Orchestrator:
    """工作流编排器"""

    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir)
        self.context = RunContext(run_dir)
        self.is_obsidian = self.context.is_obsidian
        # Obsidian 模式下不使用 _log 目录
        self.log_dir = self.run_dir / "_log" if not self.is_obsidian else None
        if self.log_dir:
            self.log_dir.mkdir(exist_ok=True)

    def _slugify(self, txt: str) -> str:
        s = txt.lower().strip()
        s = re.sub(r"[^0-9a-z\u4e00-\u9fa5]+", "-", s)
        s = re.sub(r"-+", "-", s)
        s = s.strip("-")
        return s[:80] if s else "untitled"

    def _rename_run_dir_with_title(self, title: str):
        """确认标题后重命名项目目录为 日期-标题 格式"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        slug = self._slugify(title)
        new_run_id = f"{date_str}-{slug}"
        parent = self.run_dir.parent
        target = parent / new_run_id

        # 处理目录已存在的情况
        if target.exists():
            i = 1
            while True:
                t = parent / f"{new_run_id}-{i}"
                if not t.exists():
                    target = t
                    break
                i += 1

        # Obsidian 模式：需要更新主 Markdown 文件名
        if self.is_obsidian:
            # 找到当前主 Markdown 文件
            md_files = list(self.run_dir.glob("*.md"))
            if md_files:
                old_main_file = md_files[0]
                # 读取旧文件内容
                content = old_main_file.read_text(encoding="utf-8")
                # 更新 frontmatter 中的标题
                metadata, body = parse_frontmatter(content)
                metadata["topic"] = title
                metadata["project_id"] = target.name
                metadata["updated"] = date_str

                # 重命名目录
                self.run_dir.rename(target)
                self.run_dir = target

                # 删除旧的 emoji 文件（因为目录名变了，需要重新创建）
                # 新文件名（不带 emoji）
                new_main_file = target / f"{title[:30]}.md"
                new_main_file.write_text(write_frontmatter(metadata, body), encoding="utf-8")
                old_main_file.unlink()

                # 更新 context
                self.context.run_dir = target
                self.context.data["run_id"] = target.name
                self.context.data["topic"] = title
            else:
                # 没有 Markdown 文件，直接重命名目录
                self.run_dir.rename(target)
                self.run_dir = target
        else:
            # 传统模式
            self.run_dir.rename(target)
            self.run_dir = target
            self.log_dir = self.run_dir / "_log"
            self.context.run_dir = target
            self.context.context_file = target / "run_context.yaml"
            self.context.data["run_id"] = target.name
            self.context.save()

    def log(self, step_id: str, message: str):
        """写入步骤日志（Obsidian 模式下跳过）"""
        if self.is_obsidian or not self.log_dir:
            return
        log_file = self.log_dir / f"step_{step_id}.log"
        timestamp = datetime.now().isoformat()
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")

    def write_handoff(self, platform: str, step_id: str, inputs: List[str],
                    outputs: List[str], summary: str, next_instructions: List[str],
                    open_questions: List[str] = None) -> str:
        """生成 handoff.yaml 文件"""
        if open_questions is None:
            open_questions = []

        handoff_data = {
            "step_id": step_id,
            "inputs": inputs,
            "outputs": outputs,
            "summary": summary,
            "next_instructions": next_instructions,
            "open_questions": open_questions
        }

        # 提取步骤数字用于 handoff 文件名
        step_num = step_id.split("_")[0][:2]
        handoff_file = self.run_dir / platform / f"{step_num}_handoff.yaml"
        handoff_file.parent.mkdir(parents=True, exist_ok=True)

        with open(handoff_file, 'w', encoding='utf-8') as f:
            yaml.dump(handoff_data, f, allow_unicode=True, default_flow_style=False)

        return str(handoff_file.relative_to(self.run_dir))

    def execute_step(self, step_id: str, func: callable, *args, **kwargs) -> bool:
        """执行单个步骤"""
        try:
            # 标记为 RUNNING
            self.context.update_step_state(step_id, "RUNNING")
            self.log(step_id, "开始执行")

            # 执行步骤
            result = func(*args, **kwargs)

            # 标记为 DONE
            artifacts = result.get('artifacts', []) if isinstance(result, dict) else []
            self.context.update_step_state(step_id, "DONE", artifacts)
            self.log(step_id, f"执行成功，产物: {artifacts}")

            return True

        except Exception as e:
            # 标记为 FAILED
            self.context.update_step_state(step_id, "FAILED")
            self.log(step_id, f"执行失败: {str(e)}")
            print(f"步骤 {step_id} 失败: {str(e)}", file=sys.stderr)
            return False

    def _normalize_wechat_account(self, raw: str) -> Optional[str]:
        value = (raw or "").strip().lower()
        mapping = {
            "main": "main",
            "wise": "main",
            "1": "main",
            "sub": "sub",
            "human": "sub",
            "2": "sub",
        }
        return mapping.get(value)

    def _apply_image_config_answer(self, answer: str) -> bool:
        """解析图片配置回复。"""
        answer = (answer or "").strip()
        if not answer:
            print("请明确提供图片配置，例如：横屏，4张，封面21:9，正文16:9")
            return False

        has_orientation = any(keyword in answer for keyword in ["横屏", "竖屏", "landscape", "portrait"])
        if not has_orientation:
            print("请明确选择横屏或竖屏（如：横屏，4张）")
            return False

        answer_cleaned = (
            answer.replace("16:9", "")
            .replace("16x9", "")
            .replace("3:4", "")
            .replace("3x4", "")
            .replace("21:9", "")
            .replace("21x9", "")
        )
        count_match = re.search(r'(\d+)\s*(?:张|幅|$)', answer_cleaned)
        if not count_match:
            print("请指定张数（如：横屏，4张）")
            return False

        if "横屏" in answer or "landscape" in answer:
            orientation = "landscape"
        else:
            orientation = "portrait"

        count = int(count_match.group(1))
        self.context.update_decision("image.orientation", orientation)
        self.context.update_decision("image.count", count)

        if "封面" in answer or "cover" in answer:
            cover_match = re.search(r'(?:封面|cover)[：:\s]*([\d:x]+)', answer)
            if cover_match:
                self.context.update_decision("image.cover_ratio", cover_match.group(1))
        elif not self.context.get_decision("image.cover_ratio"):
            self.context.update_decision("image.cover_ratio", "21:9" if orientation == "landscape" else "3:4")

        if "正文" in answer or "poster" in answer:
            poster_match = re.search(r'(?:正文|poster)[：:\s]*([\d:x]+)', answer)
            if poster_match:
                self.context.update_decision("image.poster_ratio", poster_match.group(1))
            else:
                self.context.update_decision("image.poster_ratio", self._derive_poster_ratio())
        else:
            self.context.update_decision("image.poster_ratio", self._derive_poster_ratio())

        self.context.update_decision("image.confirmed", True)
        print(f"已确认：{orientation}，{count}张，封面{self.context.get_decision('image.cover_ratio')}，正文{self.context.get_decision('image.poster_ratio')}")
        return True

    def check_preflight_gates(self) -> bool:
        """优先合并 Gate A/B，减少来回确认。"""
        account_missing = not self.context.get_decision("wechat.account")
        image_missing = not self.context.get_decision("image.confirmed", False)

        if account_missing and image_missing:
            question = {
                "id": "preflight_setup",
                "question": (
                    "一次性确认发布前置设置：请选择公众号账号(main/sub，wise=main，human=sub) + 配图配置。\n"
                    "示例：main，横屏，4张，封面21:9，正文16:9"
                ),
                "type": "text",
                "required": True
            }
            self.context.add_pending_question(question)
            print("\nPreflight Gate: 需要一次性确认账号与配图配置")
            return False

        if account_missing:
            return self.check_gate_a()
        if image_missing:
            return self.check_gate_b()
        return True

    def check_gate_a(self) -> bool:
        """检查 Gate A: 公众号账号选择"""
        account = self.context.get_decision("wechat.account")
        if account is None:
            question = {
                "id": "account_selection",
                "question": "请选择公众号账号（main/sub，也支持 wise/human）",
                "type": "choice",
                "options": ["main", "sub"],
                "required": True
            }
            self.context.add_pending_question(question)
            print("\nGate A: 需要选择公众号账号")
            return False
        return True

    def _derive_poster_ratio(self) -> str:
        """根据 orientation 派生 poster_ratio"""
        orientation = self.context.get_decision("image.orientation", "landscape")
        if orientation == "landscape":
            return self.context.get_decision("image.poster_ratio_landscape", "16:9")
        else:
            return self.context.get_decision("image.poster_ratio_portrait", "3:4")

    def check_gate_b(self) -> bool:
        """检查 Gate B: 图片配置确认"""
        # 检查确认状态（confirmed 标志是 SSOT）
        confirmed = self.context.get_decision("image.confirmed", False)
        if not confirmed:
            # 使用当前 orientation/count 作为默认值提示用户
            orientation = self.context.get_decision("image.orientation", "landscape")
            count = self.context.get_decision("image.count", 4)

            orientation_zh = "横屏" if orientation == "landscape" else "竖屏"

            question = {
                "id": "image_config",
                "question": f"请确认配图：当前设置 {orientation_zh}，{count}张\n可直接回车确认，或修改（如：横屏，4张 或 竖屏，5张，封面16:9，正文3:4）",
                "type": "text",
                "required": True
            }
            self.context.add_pending_question(question)
            print(f"\nGate B: 需要确认图片配置（当前：{orientation_zh}，{count}张）")
            return False

        # 已确认，派生 poster_ratio（运行时写入）
        self.context.update_decision("image.poster_ratio", self._derive_poster_ratio())
        return True

    def process_pending_questions(self):
        """处理待确认问题"""
        if not self.context.data["pending_questions"]:
            return

        print("\n" + "=" * 60)
        print("需要您的确认")
        print("=" * 60)

        for question in self.context.data["pending_questions"]:
            print(f"\n? {question['question']}")

            if question["type"] == "choice":
                print("选项:", ", ".join(question["options"]))
                answer = input("请输入您的选择: ").strip()

            elif question["type"] == "integer":
                min_val = question.get("min", 1)
                max_val = question.get("max", 10)
                while True:
                    answer = input(f"请输入数字 ({min_val}-{max_val}): ").strip()
                    if answer.isdigit() and min_val <= int(answer) <= max_val:
                        answer = int(answer)
                        break
                    print("输入无效，请重试")

            elif question["type"] == "confirm":
                answer = input("确认吗? (y/n): ").strip().lower() == 'y'

            else:
                answer = input("请输入: ").strip()

            # 更新决策
            if question["id"] == "preflight_setup":
                account = self._normalize_wechat_account(answer)
                if not account:
                    print("请先明确公众号账号：main/sub（也支持 wise/human）")
                    return False
                self.context.update_decision("wechat.account", account)
                if not self._apply_image_config_answer(answer):
                    return False

            elif question["id"] == "account_selection":
                account = self._normalize_wechat_account(answer)
                if not account:
                    print("请输入有效账号：main/sub（也支持 wise/human）")
                    return False
                self.context.update_decision("wechat.account", account)

            elif question["id"] == "image_config":
                if not self._apply_image_config_answer(answer):
                    return False

            elif question["id"] == "image_count":
                self.context.update_decision("image.count", answer)

        # 清空待确认问题
        self.context.clear_pending_questions()
        print("\n确认完成，继续执行...")

    def run(self, start_from: Optional[str] = None):
        """使用 ParallelScheduler 执行工作流"""
        print(f"\n开始执行工作流: {self.context.data['topic']}")
        print(f"运行目录: {self.run_dir}")

        # 提前检查 Gate A/B，优先合并确认点，避免流程后段卡住
        self.check_preflight_gates()

        # 处理待确认问题（优先级最高）
        if self.context.data["pending_questions"]:
            self.process_pending_questions()
            if self.context.data["status"] == "WAITING_FOR_USER":
                print("\n工作流暂停，等待用户确认")
                return

        # 加载工作流定义
        workflow = self._load_workflow()

        # 创建调度器并执行
        from scheduler import ParallelScheduler
        scheduler = ParallelScheduler(self, workflow, self.context)
        scheduler.run(start_from)

        # 更新最终状态
        if self._all_steps_done(workflow):
            self.context.data["status"] = "DONE"
            self.context.save()
            print("\n工作流全部完成！")

    def _load_workflow(self) -> Dict[str, Any]:
        """加载 workflow.yaml"""
        from scheduler import load_workflow
        return load_workflow()

    def _all_steps_done(self, workflow: Dict[str, Any]) -> bool:
        """检查所有步骤是否完成"""
        return all(
            self.context.get_step_state(config["id"]) == "DONE"
            for config in workflow["steps"].values()
        )

    # ==================== 步骤实现 ====================

    def step_init(self):
        """初始化步骤 - 目录已在 init_run_dir 中创建"""
        print("初始化完成")
        return {"artifacts": ["run_context.yaml"]}

    def step_research(self):
        """内容调研 - 调用 research-workflow 技能（支持双写机制）

        Obsidian 模式下实现双写：
        1. 研究输出到研究库（00_研究库）
        2. 文章项目在 01_文章项目
        3. 文章项目的 00_素材与链接.md 引用研究库
        """
        platform = "wechat"
        step_id = "01_research"

        print("执行内容调研...")
        self.log(step_id, "调用 /research-workflow 技能")

        topic = self.context.data["topic"]

        # Obsidian 模式：实现双写机制
        if self.is_obsidian:
            return self._step_research_obsidian_dual_write(topic)

        # 传统模式：保持原有逻辑
        return self._step_research_traditional(topic)

    def _step_research_obsidian_dual_write(self, topic: str) -> dict:
        """Obsidian 模式下的双写研究逻辑"""
        import sys
        sys.path.insert(0, str(Path.home() / ".claude" / "skills" / "research-workflow" / "scripts"))

        from obsidian_utils import (
            get_research_path,
            get_obsidian_research_ref,
            should_use_obsidian_mode,
            generate_obsidian_frontmatter,
            write_frontmatter as obsidian_write_frontmatter
        )

        step_id = "01_research"

        # 1. 确定研究库路径
        research_path = get_research_path(topic, use_obsidian=True)
        research_dir = Path(research_path)
        research_dir.mkdir(parents=True, exist_ok=True)

        # 2. 调用 research-workflow 技能（Obsidian 模式）
        cmd = [
            "claude", "/research-workflow",
            "--idea", topic,
            "--obsidian",  # 启用 Obsidian 模式
            "--markdown"
        ]

        print(f"  调用 research-workflow (Obsidian 模式)...")
        self.log(step_id, f"调用 /research-workflow --obsidian --idea {topic}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                raise RuntimeError(f"research-workflow 执行失败: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise TimeoutError("research-workflow 执行超时")

        # 3. 验证研究库输出
        research_index = research_dir / "index.md"
        if not research_index.exists():
            # 如果 index.md 不存在，可能是 research-workflow 使用了不同的路径
            # 尝试查找最近创建的研究目录
            vault_research_dir = OBSIDIAN_RESEARCH_DIR
            if vault_research_dir.exists():
                recent_dirs = sorted(
                    vault_research_dir.iterdir(),
                    key=lambda x: x.stat().st_mtime,
                    reverse=True
                )
                for recent_dir in recent_dirs[:3]:
                    if recent_dir.is_dir() and (recent_dir / "index.md").exists():
                        research_dir = recent_dir
                        research_index = recent_dir / "index.md"
                        print(f"  找到研究目录: {research_dir.name}")
                        break

        if not research_index.exists():
            print(f"  ⚠️ 研究库输出未找到，将创建占位引用")

        # 4. 生成 wikilink 引用
        research_ref = get_obsidian_research_ref(topic)

        # 5. 更新文章项目的 00_素材与链接.md
        materials_file = self.run_dir / "00_素材与链接.md"
        if materials_file.exists():
            content = materials_file.read_text(encoding="utf-8")
            # 如果存在占位符，替换为实际引用
            if "{{RESEARCH_LINK}}" in content:
                content = content.replace("{{RESEARCH_LINK}}", f"[[{research_ref}|调研资料]]")
            elif "待添加" in content:
                content = content.replace("待添加", f"[[{research_ref}|调研资料]]")
            else:
                # 在文件开头添加研究引用（如果不存在）
                if research_ref not in content:
                    lines = content.split("\n")
                    # 找到第一个 ## 标题后插入
                    insert_idx = 0
                    for i, line in enumerate(lines):
                        if line.startswith("## "):
                            insert_idx = i + 1
                            break
                    lines.insert(insert_idx, f"\n[[{research_ref}|调研资料]]\n")
                    content = "\n".join(lines)
            materials_file.write_text(content, encoding="utf-8")
            print(f"  已更新素材引用: [[{research_ref}|调研资料]]")

        # 6. 更新主项目文件的 research_ref
        main_files = list(self.run_dir.glob("📋 *.md"))
        if main_files:
            main_file = main_files[0]
            content = main_file.read_text(encoding="utf-8")
            metadata, body = parse_frontmatter(content)
            metadata["research_ref"] = f"[[{research_ref}|调研资料]]"
            if "steps" in metadata and "research" in metadata["steps"]:
                metadata["steps"]["research"]["status"] = "done"
            main_file.write_text(write_frontmatter(metadata, body), encoding="utf-8")

        # 7. 更新研究库的 article_refs（反向链接）
        if research_index.exists():
            content = research_index.read_text(encoding="utf-8")
            metadata, body = parse_frontmatter(content)
            project_ref = f"01_文章项目/{self.run_dir.name}"
            article_refs = metadata.get("article_refs", [])
            if project_ref not in article_refs:
                article_refs.append(project_ref)
                metadata["article_refs"] = article_refs
                research_index.write_text(obsidian_write_frontmatter(metadata, body), encoding="utf-8")
                print(f"  已添加反向链接到研究库")

        print(f"✅ 双写完成:")
        print(f"   研究库: {research_dir}")
        print(f"   文章项目: {self.run_dir}")

        return {
            "artifacts": [
                f"00_研究库/{research_dir.name}/index.md",
                "00_素材与链接.md"
            ],
            "research_path": str(research_dir),
            "research_ref": research_ref
        }

    def _step_research_traditional(self, topic: str) -> dict:
        """传统模式下的研究逻辑"""
        platform = "wechat"
        step_id = "01_research"

        # 调用 research-workflow 技能
        cmd = ["claude", "/research-workflow", "--idea", topic, "--output-dir", str(self.run_dir)]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                raise RuntimeError(f"research-workflow 执行失败: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise TimeoutError("research-workflow 执行超时")

        # 验证输出文件
        research_file = self.run_dir / platform / "00_research.md"
        if not research_file.exists():
            raise FileNotFoundError(f"research-workflow 未生成输出文件: {research_file}")

        # 生成 handoff.yaml
        handoff_path = self.write_handoff(
            platform=platform,
            step_id=step_id,
            inputs=[],
            outputs=[
                f"{platform}/00_research.md",
                f"{platform}/00_handoff.yaml"
            ],
            summary=f"针对话题「{topic}」进行内容调研",
            next_instructions=[
                "下一步：调用 /article-create-rag 生成草稿",
                f"输入：{platform}/00_research.md"
            ]
        )

        print(f"已生成: {research_file.name}")
        print(f"已生成: {handoff_path}")
        return {"artifacts": [f"{platform}/00_research.md", handoff_path]}

    def step_review(self):
        """调研评审 - 调用 research-review 技能"""
        platform = "wechat"
        step_id = "01b_review"

        print("执行调研评审...")
        self.log(step_id, "调用 /research-review 技能")

        # 检查前置文件
        research_file = self.run_dir / platform / "00_research.md"
        if not research_file.exists():
            raise FileNotFoundError(f"前置文件不存在: {research_file}")

        # 检查 review 脚本是否存在
        review_script = Path.home() / ".claude" / "skills" / "research-review" / "scripts" / "research_review.py"
        if not review_script.exists():
            raise FileNotFoundError(
                f"质检脚本不存在: {review_script}\n"
                f"请确保 research-review 技能已正确安装。"
            )

        # 调用 research-review 脚本
        cmd = ["python3", str(review_script), str(research_file)]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        # 检查结果
        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "未知错误"
            self.log(step_id, f"评审失败: {error_msg}")
            raise RuntimeError(f"调研报告质量检查未通过\n{error_msg}")

        # 输出评审结果
        if result.stdout:
            print(result.stdout)

        # 生成 handoff.yaml
        handoff_path = self.write_handoff(
            platform=platform,
            step_id=step_id,
            inputs=[f"{platform}/00_research.md"],
            outputs=[f"{platform}/00_research.md (updated)"],
            summary="调研评审完成",
            next_instructions=[
                "下一步：调用 /article-create-rag 生成草稿",
                f"输入：{platform}/00_research.md"
            ]
        )

        print(f"已生成: {handoff_path}")
        return {"artifacts": [f"{platform}/00_research.md", handoff_path]}

    def step_rag(self):
        """RAG 生成草稿 - 调用 article-create-rag 技能"""
        platform = "wechat"
        step_id = "02_rag"

        print("基于调研资料调用 RAG 生成草稿...")
        self.log(step_id, "调用 /article-create-rag 技能")

        topic = self.context.data["topic"]

        # 检查前置文件
        research_file = self.run_dir / platform / "00_research.md"
        if not research_file.exists():
            raise FileNotFoundError(f"前置文件不存在: {research_file}")

        # 调用 article-create-rag 技能
        cmd = ["claude", "/article-create-rag", "--input", str(research_file), "--output-dir", str(self.run_dir / platform)]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                raise RuntimeError(f"article-create-rag 执行失败: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise TimeoutError("article-create-rag 执行超时")

        # 验证输出文件
        rag_file = self.run_dir / platform / "02_rag_content.md"
        if not rag_file.exists():
            raise FileNotFoundError(f"article-create-rag 未生成输出文件: {rag_file}")

        # 生成 handoff.yaml
        handoff_path = self.write_handoff(
            platform=platform,
            step_id=step_id,
            inputs=[f"{platform}/00_research.md"],
            outputs=[
                f"{platform}/02_rag_content.md",
                f"{platform}/02_handoff.yaml"
            ],
            summary=f"基于调研资料（{topic}）通过 RAG 生成草稿内容",
            next_instructions=[
                "并行任务：/title-gen 可基于 00_research 或 02_rag_content_no_title 生成标题方案",
                f"输入：{platform}/02_rag_content.md"
            ]
        )

        print(f"已生成: {rag_file.name}")
        print(f"已生成: {handoff_path}")
        return {"artifacts": [f"{platform}/02_rag_content.md", handoff_path]}

    def step_outliner(self):
        """生成 2-3 个差异化提纲方案 - 调用 article-outliner 技能"""
        platform = "wechat"
        step_id = "02_outliner"

        print("生成提纲方案...")
        self.log(step_id, "调用 /article-outliner 技能")

        # 检查调研文件
        research_file = self.run_dir / platform / "00_research.md"
        if not research_file.exists():
            raise FileNotFoundError(f"前置文件不存在: {research_file}")

        # 调用 article-outliner 技能
        cmd = [
            "claude", "/article-outliner",
            "--file", str(research_file),
            "--count", "3",
            "--write",  # 触发并行写作
            "--output-dir", str(self.run_dir / platform)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                raise RuntimeError(f"article-outliner 执行失败: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise TimeoutError("article-outliner 执行超时")

        # 验证输出目录
        outlines_dir = self.run_dir / platform / "02_outlines"
        if not outlines_dir.exists():
            raise FileNotFoundError(f"article-outliner 未生成输出目录: {outlines_dir}")

        # 生成 handoff.yaml
        handoff_path = self.write_handoff(
            platform=platform,
            step_id=step_id,
            inputs=[f"{platform}/00_research.md"],
            outputs=[
                f"{platform}/02_outlines/outline-a.md",
                f"{platform}/02_outlines/outline-b.md",
                f"{platform}/02_outlines/outline-c.md",
                f"{platform}/03_drafts/draft-a.md",  # 并行写作生成的初稿
                f"{platform}/03_drafts/draft-b.md",
                f"{platform}/03_drafts/draft-c.md",
                f"{platform}/02_handoff.yaml"
            ],
            summary=f"基于调研内容生成 3 个差异化提纲方案和对应的初稿",
            next_instructions=[
                "下一步：用户从 3 篇初稿中选择一篇",
                f"输入：{platform}/03_drafts/"
            ]
        )

        print(f"已生成: {outlines_dir.name}/")
        print(f"已生成: {handoff_path}")
        return {"artifacts": [f"{platform}/02_outlines/", f"{platform}/03_drafts/", handoff_path]}

    def step_writer_parallel(self):
        """并行写作 - 由 article-outliner --write 自动触发"""
        # 此步骤实际上由 step_outliner 中的 --write 参数自动完成
        # 这里只更新状态，实际文件已由 article-outliner 生成
        platform = "wechat"
        step_id = "03_writer_parallel"

        print("并行写作已完成（由 article-outliner 触发）...")
        self.log(step_id, "并行写作由 article-outliner --write 自动触发")

        drafts_dir = self.run_dir / platform / "03_drafts"
        if not drafts_dir.exists():
            raise FileNotFoundError(f"初稿目录不存在: {drafts_dir}")

        # 生成 handoff.yaml
        handoff_path = self.write_handoff(
            platform=platform,
            step_id=step_id,
            inputs=[f"{platform}/02_outlines/"],
            outputs=[
                f"{platform}/03_drafts/draft-a.md",
                f"{platform}/03_drafts/draft-b.md",
                f"{platform}/03_drafts/draft-c.md",
                f"{platform}/03_handoff.yaml"
            ],
            summary="并行生成 3 篇初稿",
            next_instructions=[
                "下一步：用户选择初稿"
            ]
        )

        print(f"已生成: {handoff_path}")
        return {"artifacts": [f"{platform}/03_drafts/", handoff_path]}

    def step_select_draft(self):
        """用户交互选择初稿"""
        platform = "wechat"
        step_id = "04_select_draft"

        print("选择初稿...")
        self.log(step_id, "用户选择初稿")

        drafts_dir = self.run_dir / platform / "03_drafts"
        draft_files = sorted(drafts_dir.glob("draft-*.md"))

        if not draft_files:
            raise FileNotFoundError(f"初稿文件不存在: {drafts_dir}/*")

        # 展示初稿摘要
        print("\n=== 初稿方案 ===")
        for i, draft_file in enumerate(draft_files, 1):
            outline_id = draft_file.stem.split('-')[-1].upper()
            content = draft_file.read_text(encoding='utf-8')
            # 提取前几行作为摘要
            lines = content.splitlines()[:5]
            preview = '\n'.join(lines)
            print(f"\n【初稿 {i}】({outline_id}) {draft_file.name}")
            print(f"  {preview[:100]}...")

        # 用户选择（必须显式选择，禁止默认）
        while True:
            choice = input(f"\n请选择初稿 [1-{len(draft_files)}]：").strip()
            try:
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(draft_files):
                    break
            except ValueError:
                pass
            print("请输入明确的初稿编号，不能默认跳过。")

        selected_draft = draft_files[choice_idx]
        selected_content = selected_draft.read_text(encoding='utf-8')

        # 保存选中的初稿
        output_file = self.run_dir / platform / "04_draft_selected.md"
        output_file.write_text(selected_content, encoding='utf-8')

        # 生成 handoff.yaml
        handoff_path = self.write_handoff(
            platform=platform,
            step_id=step_id,
            inputs=[f"{platform}/03_drafts/"],
            outputs=[
                f"{platform}/04_draft_selected.md",
                f"{platform}/04_handoff.yaml"
            ],
            summary=f"用户选择了 {selected_draft.name}",
            next_instructions=[
                "下一步：article-create-rag 对选中的初稿进行 RAG 增强"
            ]
        )

        print(f"\n已选择: {selected_draft.name}")
        print(f"已保存: {output_file.name}")
        print(f"已生成: {handoff_path}")
        return {"artifacts": [f"{platform}/04_draft_selected.md", handoff_path]}

    def step_rag_enhance(self):
        """RAG 增强选中的初稿 - 调用 article-create-rag --enhance 技能"""
        platform = "wechat"
        step_id = "05_rag_enhance"

        print("RAG 增强初稿...")
        self.log(step_id, "调用 /article-create-rag --enhance 技能")

        # 检查初稿文件
        draft_file = self.run_dir / platform / "04_draft_selected.md"
        if not draft_file.exists():
            raise FileNotFoundError(f"前置文件不存在: {draft_file}")

        # 调用 article-create-rag 技能（增强模式）
        cmd = [
            "claude", "/article-create-rag",
            "--draft", str(draft_file),
            "--enhance",
            "--output-path", "05_enhanced.md",
            "--run-dir", str(self.run_dir)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                raise RuntimeError(f"article-create-rag 执行失败: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise TimeoutError("article-create-rag 执行超时")

        # 验证输出文件
        enhanced_file = self.run_dir / platform / "05_enhanced.md"
        if not enhanced_file.exists():
            raise FileNotFoundError(f"article-create-rag 未生成输出文件: {enhanced_file}")

        # 生成 handoff.yaml
        handoff_path = self.write_handoff(
            platform=platform,
            step_id=step_id,
            inputs=[f"{platform}/04_draft_selected.md"],
            outputs=[
                f"{platform}/05_enhanced.md",
                f"{platform}/05_retrieval_snippets.md",
                f"{platform}/05_handoff.yaml"
            ],
            summary=f"使用本地文章库对初稿进行 RAG 增强和润色",
            next_instructions=[
                "下一步：title-gen 生成标题方案",
                "只能引用 snippets 中的内容，不得杜撰来源"
            ]
        )

        print(f"已生成: {enhanced_file.name}")
        print(f"已生成: {handoff_path}")
        return {"artifacts": [f"{platform}/05_enhanced.md", f"{platform}/05_retrieval_snippets.md", handoff_path]}

    def step_titles(self):
        """生成多组标题方案 - 调用 title-gen 技能"""
        platform = "wechat"
        step_id = "06_titles"

        print("生成多组标题方案...")
        self.log(step_id, "调用 /title-gen 技能")

        # 使用 RAG 增强后的文章
        enhanced_file = self.run_dir / platform / "05_enhanced.md"
        research_file = self.run_dir / platform / "00_research.md"
        input_file = None
        input_label = None
        summary_source = "调研内容"
        artifacts = []

        if enhanced_file.exists():
            enhanced_content = enhanced_file.read_text(encoding="utf-8")

            # 提取不含标题的正文（简单实现：跳过第一行标题）
            lines = enhanced_content.splitlines()
            content_no_title = []
            skip_first_title = True
            for line in lines:
                if skip_first_title and line.startswith("#"):
                    skip_first_title = False
                    continue
                content_no_title.append(line)

            no_title_file = self.run_dir / platform / "05_enhanced_no_title.md"
            no_title_file.write_text("\n".join(content_no_title), encoding="utf-8")
            input_file = no_title_file
            input_label = f"{platform}/05_enhanced_no_title.md"
            summary_source = "RAG 增强后的正文"
            artifacts.append(str(no_title_file.relative_to(self.run_dir)))
        elif research_file.exists():
            input_file = research_file
            input_label = f"{platform}/00_research.md"
        else:
            input_label = f"topic:{self.context.data['topic']}"
            summary_source = "话题"

        # 调用 title-gen 技能
        if input_file is None:
            cmd = ["claude", "/title-gen", "--input", self.context.data["topic"], "--output-dir", str(self.run_dir / platform)]
        else:
            cmd = ["claude", "/title-gen", "--input", str(input_file), "--output-dir", str(self.run_dir / platform)]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                raise RuntimeError(f"title-gen 执行失败: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise TimeoutError("title-gen 执行超时")

        # 验证输出文件
        titles_file = self.run_dir / platform / "06_titles.md"
        if not titles_file.exists():
            raise FileNotFoundError(f"title-gen 未生成输出文件: {titles_file}")

        # 生成 handoff.yaml
        handoff_path = self.write_handoff(
            platform=platform,
            step_id=step_id,
            inputs=[input_label],
            outputs=[
                f"{platform}/06_titles.md",
                f"{platform}/06_handoff.yaml"
            ],
            summary=f"基于{summary_source}生成多组标题方案",
            next_instructions=[
                "下一步：用户从多组标题中选择一个",
                f"输入：{platform}/06_titles.md"
            ]
        )

        print(f"已生成: {titles_file.name}")
        print(f"已生成: {handoff_path}")
        artifacts.extend([f"{platform}/06_titles.md", handoff_path])
        return {"artifacts": artifacts}

    def step_select_title(self):
        """用户交互选择标题"""
        platform = "wechat"
        step_id = "07_select_title"

        print("请选择标题...")
        self.log(step_id, "等待用户选择标题")

        # 检查前置文件
        titles_file = self.run_dir / platform / "06_titles.md"
        if not titles_file.exists():
            raise FileNotFoundError(f"前置文件不存在: {titles_file}")

        # 读取标题方案
        titles_content = titles_file.read_text(encoding="utf-8")

        # 显示标题选项
        print("\n" + "=" * 60)
        print("请选择文章标题")
        print("=" * 60)
        print(titles_content)
        print("=" * 60)

        # 用户输入（必须显式选择，禁止默认第一个）
        while True:
            selected_title = input("\n请输入你明确选择的标题编号或完整标题文本：").strip()
            if selected_title:
                break
            print("标题选择不能留空，必须明确选择。")

        # 保存用户选择的标题
        selected_file = self.run_dir / platform / "07_title_selected.md"
        selected_file.write_text(selected_title, encoding="utf-8")

        # 更新决策
        self.context.update_decision("wechat.title", selected_title)

        self._rename_run_dir_with_title(selected_title)

        # 生成 handoff.yaml
        handoff_path = self.write_handoff(
            platform=platform,
            step_id=step_id,
            inputs=[f"{platform}/06_titles.md"],
            outputs=[f"{platform}/07_title_selected.md"],
            summary=f"用户选择标题: {selected_title}",
            next_instructions=[
                "下一步：应用标题到 RAG 增强后的文章",
                f"输入：{platform}/05_enhanced.md + {platform}/07_title_selected.md"
            ]
        )

        print(f"已选择标题: {selected_title}")
        print(f"已生成: {handoff_path}")
        return {"artifacts": [f"{platform}/07_title_selected.md", handoff_path]}

    def step_apply_title(self):
        """应用标题到文章"""
        platform = "wechat"
        step_id = "08_apply_title"

        print("应用标题到文章...")
        self.log(step_id, "应用标题到文章")

        # 读取 RAG 增强后的文章
        enhanced_file = self.run_dir / platform / "05_enhanced.md"
        if not enhanced_file.exists():
            raise FileNotFoundError(f"前置文件不存在: {enhanced_file}")

        # 读取用户选择的标题
        title_file = self.run_dir / platform / "07_title_selected.md"
        if not title_file.exists():
            raise FileNotFoundError(f"前置文件不存在: {title_file}")

        title = title_file.read_text(encoding="utf-8").strip()
        content = enhanced_file.read_text(encoding="utf-8")

        # 替换文章标题（第一行 # 开头的标题）
        lines = content.splitlines()
        if lines and lines[0].startswith("#"):
            lines[0] = f"# {title}"
        else:
            lines.insert(0, f"# {title}")

        # 保存带标题的文章
        output_file = self.run_dir / platform / "08_with_title.md"
        output_file.write_text("\n".join(lines), encoding="utf-8")

        # 生成 handoff.yaml
        handoff_path = self.write_handoff(
            platform=platform,
            step_id=step_id,
            inputs=[
                f"{platform}/05_enhanced.md",
                f"{platform}/07_title_selected.md"
            ],
            outputs=[
                f"{platform}/08_with_title.md",
                f"{platform}/08_handoff.yaml"
            ],
            summary=f"将用户选择的标题应用到文章上",
            next_instructions=[
                "下一步：article-rewrite 专业重写（HKR + 四步爆款法 + 反AI写作）"
            ]
        )

        print(f"已生成: {output_file.name}")
        print(f"已生成: {handoff_path}")
        return {"artifacts": [f"{platform}/08_with_title.md", handoff_path]}

    def step_rewrite(self):
        """文章专业重写 - 调用 article-rewrite 技能（含智能风格推荐）"""
        platform = "wechat"
        step_id = "09_rewrite"

        print("专业重写文章（HKR + 反AI写作）...")
        self.log(step_id, "调用 /article-rewrite 技能")

        # 检查前置文件
        content_file = self.run_dir / platform / "08_with_title.md"
        if not content_file.exists():
            raise FileNotFoundError(f"前置文件不存在: {content_file}")

        # Gate C: 风格选择（智能推荐）
        content = content_file.read_text(encoding="utf-8")

        # 智能推荐风格
        recommended, reason = recommend_style(content)
        print(f"\n🎯 推荐风格: {get_style_description(recommended)}")
        print(f"   理由: {reason}\n")

        # 检查已保存的风格选择
        saved_style = self.context.data.get("decisions", {}).get("rewrite", {}).get("style")

        if saved_style:
            # 使用已保存的风格
            style = normalize_style(saved_style)
            print(f"使用已保存风格: {get_style_description(style)}")
        else:
            # 显示所有可选风格
            print("所有可用风格:")
            for s in list_all_styles():
                print(f"  - {get_style_description(s)}")

            # 交互式确认
            user_choice = input(f"\n使用推荐风格 [{recommended}]？(直接回车确认，或输入其他风格): ").strip()
            style = normalize_style(user_choice) if user_choice else recommended

            # 保存选择
            self.context.update_decision("rewrite.style", style)
            self.context.save()

            print(f"已选择风格: {get_style_description(style)}\n")

        # 调用 article-rewrite 技能
        cmd = [
            "claude", "/article-rewrite",
            "--input", str(content_file),
            "--style", style,
            "--run-dir", str(self.run_dir)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                raise RuntimeError(f"article-rewrite 执行失败: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise TimeoutError("article-rewrite 执行超时")

        # 验证输出文件
        rewritten_file = self.run_dir / platform / "09_rewritten.md"
        if not rewritten_file.exists():
            raise FileNotFoundError(f"article-rewrite 未生成输出文件: {rewritten_file}")

        # 生成 handoff.yaml
        handoff_path = self.write_handoff(
            platform=platform,
            step_id=step_id,
            inputs=[f"{platform}/08_with_title.md"],
            outputs=[
                f"{platform}/09_rewritten.md",
                f"{platform}/09_handoff.yaml"
            ],
            summary=f"使用 HKR + 反AI写作进行专业重写（风格：{get_style_description(style)}）",
            next_instructions=[
                "下一步：article-plug-classicLines 知识库润色"
            ]
        )

        print(f"已生成: {rewritten_file.name}")
        print(f"已生成: {handoff_path}")
        return {"artifacts": [f"{platform}/09_rewritten.md", handoff_path]}

    def step_draft(self):
        """文章创作 - 根据 llm.provider 选择执行方式"""
        platform = "wechat"
        step_id = "05_draft"

        print("生成文章初稿...")
        self.log(step_id, "调用 /article-rewrite 技能")

        topic = self.context.data["topic"]

        # 检查前置文件
        content_file = self.run_dir / platform / "02_rag_content_no_title.md"
        title_file = self.run_dir / platform / "03_title_selected.md"

        if not content_file.exists():
            raise FileNotFoundError(f"前置文件不存在: {content_file}")
        if not title_file.exists():
            raise FileNotFoundError(f"前置文件不存在: {title_file}")

        # 读取标题
        title = title_file.read_text(encoding="utf-8").strip()

        # 读取 LLM provider 配置
        llm_provider = self.context.get_decision("llm.provider", "claude-code")

        if llm_provider == "claude-code":
            # 路径 A：直接使用 Claude Code 模型
            self.log(step_id, f"使用 Claude Code 模型生成内容")
            cmd = [
                "claude", "/article-rewrite",
                "--topic", topic,
                "--title", title,
                "--input", str(content_file),
                "--output-dir", str(self.run_dir / platform),
                "--use-claude-code"
            ]
        else:
            # 路径 B：调用 rewrite_article.py 脚本
            self.log(step_id, f"使用第三方 LLM 提供商: {llm_provider}")
            script_path = Path.home() / ".claude" / "skills" / "article-rewrite" / "scripts" / "rewrite_article.py"
            cmd = [
                sys.executable, str(script_path),
                "--provider", llm_provider,
                "--topic", topic,
                "--title", title,
                "--input", str(content_file),
                "--run-dir", str(self.run_dir / platform),
                "--platforms", platform
            ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                raise RuntimeError(f"article-rewrite 执行失败: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise TimeoutError("article-rewrite 执行超时")

        # 验证输出文件
        draft_file = self.run_dir / platform / "05_draft.md"
        if not draft_file.exists():
            raise FileNotFoundError(f"article-rewrite 未生成输出文件: {draft_file}")

        # 生成 handoff.yaml
        handoff_path = self.write_handoff(
            platform=platform,
            step_id=step_id,
            inputs=[f"{platform}/02_rag_content_no_title.md", f"{platform}/03_title_selected.md"],
            outputs=[
                f"{platform}/05_draft.md",
                f"{platform}/05_handoff.yaml"
            ],
            summary=f"基于 RAG 内容和用户选择的标题（{title}）生成文章初稿（提供商: {llm_provider}）",
            next_instructions=[
                "下一步：调用 /article-plug-classicLines 进行润色",
                f"输入：{platform}/05_draft.md"
            ]
        )

        print(f"已生成: {draft_file.name}")
        print(f"已生成: {handoff_path}")
        return {"artifacts": [f"{platform}/05_draft.md", handoff_path]}

    def step_fact_check(self):
        """文章事实核查 - 调用 research-review 技能的 --article 模式"""
        platform = "wechat"
        step_id = "09b_fact_check"

        print("执行文章事实核查...")
        self.log(step_id, "调用 research-review --article 模式")

        # 检查前置文件
        rewritten_file = self.run_dir / platform / "09_rewritten.md"
        if not rewritten_file.exists():
            raise FileNotFoundError(f"前置文件不存在: {rewritten_file}")

        # 检查 review 脚本是否存在
        review_script = Path.home() / ".claude" / "skills" / "research-review" / "scripts" / "research_review.py"
        if not review_script.exists():
            raise FileNotFoundError(
                f"核查脚本不存在: {review_script}\n"
                f"请确保 research-review 技能已正确安装。"
            )

        # 调用 research-review --article
        # 注意：脚本内部有 input() 调用，在非交互式环境会 EOFError 并自动继续
        cmd = ["python3", str(review_script), str(rewritten_file), "--article"]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            raise TimeoutError("research-review 执行超时")

        # 检查执行结果
        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "未知错误"
            self.log(step_id, f"事实核查失败: {error_msg}")
            print(f"⚠️ 事实核查未通过: {error_msg}")

            # 让用户选择是否继续
            print("\n事实核查失败，是否继续后续流程？")
            user_choice = input("继续？(y/n): ").strip().lower()
            if user_choice not in ('y', 'yes', '是'):
                raise RuntimeError("用户选择终止流程")
            print("继续后续流程...")
        else:
            if result.stdout:
                print(result.stdout)

        # 验证生成的核查报告
        fact_check_report = rewritten_file.with_suffix('.fact_check.md')

        # 生成 handoff.yaml
        handoff_path = self.write_handoff(
            platform=platform,
            step_id=step_id,
            inputs=[f"{platform}/09_rewritten.md"],
            outputs=[f"{platform}/09_rewritten.fact_check.md"] if fact_check_report.exists() else [],
            summary="文章事实核查完成" if fact_check_report.exists() else "文章事实核查完成（未生成报告）",
            next_instructions=[
                "下一步：调用 article-plug-classicLines 进行知识库润色",
                f"输入：{platform}/09_rewritten.md"
            ]
        )

        print(f"已生成: {handoff_path}")

        artifacts = [f"{platform}/09_rewritten.md", handoff_path]
        if fact_check_report.exists():
            artifacts.append(f"{platform}/09_rewritten.fact_check.md")

        return {"artifacts": artifacts}

    def step_polish(self):
        """知识库润色 - 调用 article-plug-classicLines 的 polisher.py 脚本"""
        platform = "wechat"
        step_id = "10_polish"

        print("知识库润色（调用 article-plug-classicLines/polisher.py）...")
        self.log(step_id, "调用 article-plug-classicLines/polisher.py")

        # 检查前置文件
        rewritten_file = self.run_dir / platform / "09_rewritten.md"
        if not rewritten_file.exists():
            raise FileNotFoundError(f"前置文件不存在: {rewritten_file}")

        # 输出文件
        polished_file = self.run_dir / platform / "10_polished.md"
        snippets_file = self.run_dir / platform / "10_retrieval_snippets.md"

        # polisher.py 脚本路径
        polisher_script = Path.home() / ".claude" / "skills" / "article-plug-classicLines" / "polisher.py"
        if not polisher_script.exists():
            raise FileNotFoundError(
                f"polisher.py 脚本不存在: {polisher_script}\n"
                f"请确保 article-plug-classicLines 技能已正确安装。"
            )

        # 调用 polisher.py
        cmd = [
            "python3", str(polisher_script),
            str(rewritten_file),
            "-o", str(polished_file),
            "-n", "2"
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                raise RuntimeError(f"polisher.py 执行失败: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise TimeoutError("polisher.py 执行超时")

        # 验证输出文件
        if not polished_file.exists():
            raise FileNotFoundError(f"polisher.py 未生成输出文件: {polished_file}")

        # 检查 snippets 文件（polisher.py 可能生成）
        if not snippets_file.exists():
            # polisher.py 可能在同目录生成 03_retrieval_snippets.md，需要移动
            source_snippets = rewritten_file.parent / "03_retrieval_snippets.md"
            if source_snippets.exists():
                import shutil
                shutil.move(str(source_snippets), str(snippets_file))
            else:
                # 创建空的 snippets 文件
                snippets_file.write_text("# 检索证据\n\n*未检索到匹配内容*\n", encoding="utf-8")

        # 读取上一步的重写风格
        rewrite_style_id = self.context.data.get("decisions", {}).get("rewrite", {}).get("style")
        if not rewrite_style_id:
            rewrite_style_id = "unknown"
            rewrite_style_desc = "未指定"
        else:
            rewrite_style_desc = get_style_description(rewrite_style_id)

        # 生成 handoff.yaml
        handoff_data = {
            "step_id": step_id,
            "inputs": [f"{platform}/09_rewritten.md"],
            "outputs": [
                f"{platform}/10_polished.md",
                f"{platform}/10_retrieval_snippets.md",
                f"{platform}/10_handoff.yaml"
            ],
            "summary": f"基于知识库（金句库）润色文章（上一步重写风格：{rewrite_style_desc}）",
            "next_instructions": [
                "下一步：调用 /article-formatted 进行去机械化",
                "只能引用 snippets 中的内容，不得杜撰来源",
                "保持文章事实点和结构不变"
            ],
            "open_questions": [],
            "rewrite_style": {
                "id": rewrite_style_id,
                "description": rewrite_style_desc
            }
        }

        # 提取步骤数字用于 handoff 文件名
        step_num = step_id.split("_")[0][:2]
        handoff_file = self.run_dir / platform / f"{step_num}_handoff.yaml"
        handoff_file.parent.mkdir(parents=True, exist_ok=True)

        with open(handoff_file, 'w', encoding='utf-8') as f:
            yaml.dump(handoff_data, f, allow_unicode=True, default_flow_style=False)

        handoff_path = str(handoff_file.relative_to(self.run_dir))

        print(f"已生成: {polished_file.name}")
        print(f"已生成: {snippets_file.name}")
        print(f"已生成: {handoff_path}")

        return {
            "artifacts": [
                f"{platform}/10_polished.md",
                f"{platform}/10_retrieval_snippets.md",
                handoff_path
            ]
        }

    def step_humanize(self):
        """文本去机械化 - 使用 MarkdownCleaner 执行格式清洗"""
        platform = "wechat"
        step_id = "11_humanize"

        print("去机械化处理...")
        self.log(step_id, "使用 MarkdownCleaner 进行格式清洗")

        # 检查前置文件
        polished_file = self.run_dir / platform / "10_polished.md"
        if not polished_file.exists():
            raise FileNotFoundError(f"前置文件不存在: {polished_file}")

        # 读取 polished 内容
        polished_content = polished_file.read_text(encoding="utf-8")

        # 使用 MarkdownCleaner 执行完整格式清洗
        cleaner = MarkdownCleaner(polished_content)
        final_content = cleaner.clean()

        # 额外的去机械化词汇替换（在清洗后执行）
        final_content = final_content.replace("切记", "记住").replace("务必", "建议").replace(
            "千万", "最好"
        ).replace("绝对", "确实").replace("# 调研资料包", "# 调研资料包（已完善）")

        # 写入文件
        final_file = self.run_dir / platform / "11_final_final.md"
        final_file.write_text(final_content, encoding="utf-8")

        # 生成 handoff.yaml
        handoff_path = self.write_handoff(
            platform=platform,
            step_id=step_id,
            inputs=[f"{platform}/10_polished.md"],
            outputs=[
                f"{platform}/11_final_final.md",
                f"{platform}/11_handoff.yaml"
            ],
            summary="文本去机械化，提升自然度和中文地道性（AI 生成）",
            next_instructions=[
                "并行任务：/image-prompter 可基于 wechat/09_rewritten.md 生成提示词",
                f"输入：{platform}/11_final_final.md"
            ]
        )

        # 内容真实性验证（与 polished 有明显差异）
        if final_content == polished_content:
            self.log(step_id, "警告：去机械化后内容无变化")
        else:
            self.log(step_id, "去机械化处理完成，内容已优化")

        print(f"已生成: {final_file.name}")
        print(f"已生成: {handoff_path}")
        return {"artifacts": [f"{platform}/11_final_final.md", handoff_path]}

    def step_prompts(self):
        """生成图片提示词 - 手动中断模式，让用户交互式执行 /image-prompter"""

        platform = "wechat"
        step_id = "12_prompts"

        print("\n" + "="*60)
        print("步骤 12_prompts：生成图片提示词")
        print("="*60)

        # 检查前置文件
        draft_file = self.run_dir / platform / "09_rewritten.md"
        if not draft_file.exists():
            raise FileNotFoundError(f"前置文件不存在: {draft_file}")

        print(f"\n前置文件已就绪：{draft_file}")
        print("\n" + "=" * 60)
        print("请手动执行以下步骤：")
        print("=" * 60)
        print(f"\n1. 运行命令：")
        print(f"   claude /image-prompter --input {draft_file}")
        print(f"\n2. /image-prompter 支持以下 7 种风格（阶段4选择）：")
        print(f"   ┌──────────────────────────────────────────────────────────┐")
        print(f"   │  风格 ID              名称              适用场景         │")
        print(f"   ├──────────────────────────────────────────────────────────┤")
        print(f"   │  cream-paper          奶油纸手绘       通用配图、信息图   │")
        print(f"   │  clean-tech           清洁科技图       科技数据、商业图表 │")
        print(f"   │  infographic          扁平化科普图     概念解释、原理说明 │")
        print(f"   │  handdrawn            方格纸手绘       笔记手绘、学习感   │")
        print(f"   │  healing              治愈系插画       情绪叙事、场景氛围 │")
        print(f"   │  sokamono             描边插画         清新文艺、简洁治愈 │")
        print(f"   │  minimalist-sketch    极简手绘笔记     极简笔记、思维导图 │")
        print(f"   └──────────────────────────────────────────────────────────┘")
        print(f"\n3. 按照 /image-prompter 的五阶段流程完成交互：")
        print(f"   - 阶段1：需求澄清（4个问题）")
        print(f"   - 阶段2：配图规划（拆块→清单）")
        print(f"   - 阶段3：文案定稿（Copy Spec）")
        print(f"   - 阶段4：提示词封装（从上面7种风格中选择）")
        print(f"   - 阶段5：迭代润色（如需调整）")
        print(f"\n4. 确认输出文件已生成：{self.run_dir / platform / '12_prompts.md'}")
        print("=" * 60)

        # 等待用户确认
        while True:
            response = input("\n已完成 /image-prompter 并生成 12_prompts.md？: ").strip().lower()
            if response == 'y':
                break
            elif response == 'n':
                print("\n请完成 /image-prompter 后再继续...")
                print(f"提示：运行 claude /image-prompter --input {draft_file}")

        # 验证输出文件
        prompts_file = self.run_dir / platform / "12_prompts.md"
        if not prompts_file.exists():
            raise FileNotFoundError(f"未找到输出文件: {prompts_file}")

        print(f"\n✓ 已确认输出文件: {prompts_file}")

        # 生成 handoff.yaml
        handoff_path = self.write_handoff(
            platform=platform,
            step_id=step_id,
            inputs=[f"{platform}/09_rewritten.md"],
            outputs=[
                f"{platform}/12_prompts.md",
                f"{platform}/12_handoff.yaml"
            ],
            summary="生成图片提示词（用户手动执行 /image-prompter）",
            next_instructions=[
                "下一步：调用 /image-gen 生成图片",
                f"输入：{platform}/12_prompts.md"
            ]
        )

        print(f"✓ 已生成: {handoff_path}")
        return {"artifacts": [f"{platform}/12_prompts.md", str(handoff_path)]}

    def step_images(self):
        """生成图片 - 调用 ark-image-gen v2 脚本"""
        platform = "wechat"
        step_id = "13_images"

        print("生成图片...")
        self.log(step_id, "调用 ark-image-gen v2 脚本")

        # 检查前置文件
        prompts_file = self.run_dir / platform / "12_prompts.md"
        if not prompts_file.exists():
            raise FileNotFoundError(f"前置文件不存在: {prompts_file}")

        # 获取决策
        count = self.context.get_decision("image.count", 4)
        if count is None:
            count = 4

        # 准备输出目录
        images_dir = self.run_dir / platform / "13_images"
        images_dir.mkdir(exist_ok=True)

        # 调用 ark-image-gen 脚本
        script_path = Path.home() / ".claude" / "skills" / "image-gen" / "scripts" / "generate_image.py"

        if not script_path.exists():
            print(f"脚本不存在: {script_path}")
            print("请手动执行: 调用 /image-gen 技能")

            handoff_path = self.write_handoff(
                platform=platform,
                step_id=step_id,
                inputs=[f"{platform}/12_prompts.md"],
                outputs=[f"{platform}/13_images/", f"{platform}/13_handoff.yaml"],
                summary="生成图片",
                next_instructions=["下一步：上传图片到微信 CDN"]
            )

            return {"artifacts": [f"{platform}/13_images/", handoff_path]}

        # 准备插入图片的目标文件
        final_md = self.run_dir / platform / "11_final_final.md"

        cmd = [
            sys.executable, str(script_path),
            "--prompts-file", str(prompts_file),
            "--out-dir", str(images_dir),
            "--insert-into", str(final_md),
            "--non-interactive"
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                self.log(step_id, f"脚本执行失败: {result.stderr}")
                print(f"图片生成脚本返回错误: {result.stderr}")

                strategy = self.context.get_decision("image.gen_failure_strategy", "ask_user")
                if strategy == "ask_user":
                    question = {
                        "id": "image_generation_failed",
                        "question": "图片生成失败。是否立即重试？(y=重试/n=稍后)",
                        "type": "confirm",
                        "required": True,
                    }
                    self.context.add_pending_question(question)
                    raise RuntimeError("图片生成失败，等待用户决定")
                elif strategy == "retry_before_wx_html":
                    self.context.update_decision("image.needs_retry", True)
                    self.log(step_id, "标记为在生成微信HTML前自动重试")
                else:
                    raise RuntimeError("图片生成失败")
            else:
                self.log(step_id, "脚本执行成功")

            # 检查生成的图片
            generated_files = list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.png"))
            artifacts = [f"{platform}/13_images/"] + [
                str(f.relative_to(self.run_dir)) for f in generated_files
            ]

            handoff_path = self.write_handoff(
                platform=platform,
                step_id=step_id,
                inputs=[f"{platform}/12_prompts.md"],
                outputs=artifacts,
                summary="生成图片",
                next_instructions=["下一步：上传图片到微信 CDN"]
            )

            print(f"已生成: {len(generated_files)} 张图片")
            print(f"已生成: {handoff_path}")

            # 若未生成任何图片，按照策略处理
            if len(generated_files) == 0:
                strategy = self.context.get_decision("image.gen_failure_strategy", "ask_user")
                if strategy == "ask_user":
                    question = {
                        "id": "image_generation_failed",
                        "question": "未生成任何图片。是否立即重试？(y=重试/n=稍后)",
                        "type": "confirm",
                        "required": True,
                    }
                    self.context.add_pending_question(question)
                    raise RuntimeError("图片生成为空，等待用户决定")
                elif strategy == "retry_before_wx_html":
                    self.context.update_decision("image.needs_retry", True)
                    self.log(step_id, "标记为在生成微信HTML前自动重试")
                else:
                    raise RuntimeError("图片生成失败：未生成图片")

            return {"artifacts": artifacts}

        except subprocess.TimeoutExpired:
            self.log(step_id, "图片生成超时")
            print("图片生成超时")
            raise
        except FileNotFoundError:
            print("Python 或脚本不可用，请手动执行 /ark-image-gen 技能")

            handoff_path = self.write_handoff(
                platform=platform,
                step_id=step_id,
                inputs=[f"{platform}/12_prompts.md"],
                outputs=[f"{platform}/13_images/", f"{platform}/13_handoff.yaml"],
                summary=f"生成图片（封面 {cover_ratio} + 正文 {poster_ratio} x {count-1}）",
                next_instructions=["下一步：上传图片到微信 CDN"]
            )

            return {"artifacts": [f"{platform}/13_images/", handoff_path]}

    def step_upload_images(self):
        """上传图片到微信 CDN - 调用 wechat-uploadimg 脚本"""
        platform = "wechat"
        step_id = "14_upload_images"

        print("上传图片到微信 CDN...")
        self.log(step_id, "调用 wechat-uploadimg 批量上传图片")

        images_dir = self.run_dir / platform / "13_images"
        if not images_dir.exists() or not any(images_dir.iterdir()):
            raise FileNotFoundError(f"图片目录不存在或为空: {images_dir}")

        mapping_file = self._upload_images_to_wechat(platform, step_id)
        outputs = []
        summary = "上传图片到微信 CDN"

        if mapping_file and mapping_file.exists():
            outputs.append(str(mapping_file.relative_to(self.run_dir)))

            mapping_data = json.loads(mapping_file.read_text(encoding="utf-8"))
            flat_mapping = mapping_data.get("image_mapping_flat")
            if not flat_mapping:
                flat_mapping = {}
                flat_mapping.update(mapping_data.get("cover_urls", {}))
                flat_mapping.update(mapping_data.get("poster_urls", {}))

            flat_file = self.run_dir / platform / "14_image_mapping_flat.json"
            flat_file.write_text(
                json.dumps(flat_mapping, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            outputs.append(str(flat_file.relative_to(self.run_dir)))
            summary = "上传图片到微信 CDN 并生成映射"
        else:
            summary = "图片上传失败或跳过（使用本地图片路径）"

        handoff_path = self.write_handoff(
            platform=platform,
            step_id=step_id,
            inputs=[f"{platform}/13_images/"],
            outputs=outputs + [f"{platform}/14_handoff.yaml"],
            summary=summary,
            next_instructions=[
                "下一步：md-to-wxhtml 转换为 HTML"
            ]
        )

        print(f"已生成: {handoff_path}")
        artifacts = list(outputs)
        if handoff_path not in artifacts:
            artifacts.append(handoff_path)
        return {"artifacts": artifacts}

    def step_wx_html(self):
        """生成微信 HTML - 合流验证后生成 handoff"""
        platform = "wechat"
        step_id = "15_wx_html"

        print("生成微信 HTML（合流验证）...")
        self.log(step_id, "执行合流验证和转换")

        # 若标记需要在生成 HTML 前重试图片生成，则执行一次重试
        if self.context.get_decision("image.needs_retry", False):
            self.log(step_id, "在生成微信HTML前自动重试图片生成")
            try:
                self.step_images()
                self.context.update_decision("image.needs_retry", False)
            except Exception as e:
                self.log(step_id, f"图片重试失败: {e}")

        # 合流验证：检查前置文件
        required_files = [
            Path(platform) / "11_final_final.md",
            Path(platform) / "13_images",
        ]

        missing_files = []
        for file_path in required_files:
            full_path = self.run_dir / file_path
            if not full_path.exists():
                missing_files.append(str(file_path))

        if missing_files:
            error_msg = f"合流校验失败，缺失文件: {', '.join(missing_files)}"
            self.log(step_id, error_msg)
            raise FileNotFoundError(error_msg)

        # 合流验证：检查图片文件与比例匹配
        cover_ratio = self.context.get_decision("image.cover_ratio", "16:9")
        poster_ratio = self.context.get_decision("image.poster_ratio", "16:9")
        count = self.context.get_decision("image.count", 4)

        # 标准化比例格式（支持两种：_16_9.jpg 和 _16x9.jpg）
        # 优先检查实际存在的格式
        cover_ratio_norm = cover_ratio.replace(":", "_")  # 默认 _ 格式
        poster_ratio_norm = poster_ratio.replace(":", "_")

        # 检查实际文件名格式
        images_dir = self.run_dir / platform / "13_images"
        for test_format in ["_", "x"]:
            test_file = images_dir / f"cover_{cover_ratio.replace(':', test_format)}.jpg"
            if test_file.exists():
                cover_ratio_norm = cover_ratio.replace(":", test_format)
                break

        images_dir = self.run_dir / platform / "13_images"
        cover_file = images_dir / f"cover_{cover_ratio_norm}.jpg"
        if not cover_file.exists():
            # 检查可能的变体格式
            alt_patterns = [
                f"cover{cover_ratio}.jpg",  # 原 : 格式
                f"cover{cover_ratio.replace(':', 'x')}.jpg",  # x 格式
            ]
            found = False
            for alt in alt_patterns:
                if (images_dir / alt).exists():
                    found = True
                    break
            if not found:
                error_msg = f"合流校验失败，封面图片不存在: cover_{cover_ratio_norm}.jpg"
                self.log(step_id, error_msg)
                raise FileNotFoundError(error_msg)

        # 检查正文图
        for i in range(1, count):
            poster_file = images_dir / f"poster_{i:02d}_{poster_ratio_norm}.jpg"
            if not poster_file.exists():
                # 也检查可能的变体格式
                alt_patterns = [
                    f"poster_{i:02d}_{poster_ratio}.jpg",  # 原 : 格式
                    f"poster_{i:02d}_{poster_ratio.replace(':', 'x')}.jpg",  # x 格式
                ]
                found = False
                for alt in alt_patterns:
                    if (images_dir / alt).exists():
                        found = True
                        break
                if not found:
                    error_msg = f"合流校验失败，正文图片不存在: poster_{i:02d}_{poster_ratio_norm}.jpg"
                    self.log(step_id, error_msg)
                    raise FileNotFoundError(error_msg)

        print(f"合流验证通过：前置文件和图片比例匹配检查通过（封面 {cover_ratio}，正文 {poster_ratio}）")

        # 读取图片映射（如果存在）
        image_mapping = {}
        mapping_file = None
        for candidate in ["14_image_mapping.json", "13_image_mapping.json"]:
            candidate_path = self.run_dir / platform / candidate
            if candidate_path.exists():
                mapping_file = candidate_path
                break

        if mapping_file and mapping_file.exists():
            with open(mapping_file, "r", encoding="utf-8") as f:
                mapping_data = json.load(f)
                # 合并 cover_urls 和 poster_urls
                image_mapping.update(mapping_data.get("cover_urls", {}))
                image_mapping.update(mapping_data.get("poster_urls", {}))
            self.log(step_id, f"已加载图片映射: {len(image_mapping)} 张")
            print(f"已加载图片映射: {len(image_mapping)} 张")
        else:
            self.log(step_id, "图片映射不存在，使用本地路径")
            print("图片映射不存在，使用本地路径")

        # 读取 Markdown 文件
        md_file = self.run_dir / platform / "11_final_final.md"
        md_content = md_file.read_text(encoding="utf-8")

        # ===== 关键修复：插入图片引用 =====
        # 按段落分割，在合适位置插入图片
        lines = md_content.splitlines()
        result_lines = []
        paragraph_count = 0
        poster_idx = 1  # 从第一张正文图开始

        i = 0
        while i < len(lines):
            line = lines[i]
            result_lines.append(line)

            # 统计段落（非空、非标题、非分隔线的文本行）
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                paragraph_count += 1
                # 每隔 1-2 个段落插入一张图片
                if paragraph_count >= 2 and poster_idx < count:
                    # 查找实际的图片文件名
                    actual_ratio = poster_ratio_norm
                    poster_file = images_dir / f"poster_{poster_idx:02d}_{actual_ratio}.jpg"
                    if not poster_file.exists():
                        # 尝试其他格式
                        for alt_ratio in [poster_ratio.replace(":", "_"), poster_ratio.replace(":", "x")]:
                            poster_file = images_dir / f"poster_{poster_idx:02d}_{alt_ratio}.jpg"
                            if poster_file.exists():
                                actual_ratio = alt_ratio
                                break
                        if not poster_file.exists():
                            poster_idx += 1
                            continue

                    # 确定图片引用（使用本地路径或微信 CDN URL）
                    img_filename = f"poster_{poster_idx:02d}_{actual_ratio}.jpg"
                    img_src = image_mapping.get(img_filename, f"13_images/{img_filename}")

                    # 插入图片引用（使用 RAW 块包装）
                    img_html = f"""<!--RAW-->
<section class="_editor">
    <section style="margin:10px 0;">
        <p>
            <img src="{img_src}" alt="文章配图" style="width: 100%; display: block;"/>
        </p>
    </section>
</section>
<!--/RAW-->"""
                    result_lines.append("")
                    result_lines.append(img_html)
                    result_lines.append("")
                    poster_idx += 1
                    paragraph_count = 0  # 重置计数

            i += 1

        # 更新 md_content 为包含图片引用的版本
        md_content_with_images = "\n".join(result_lines)
        self.log(step_id, f"已插入 {poster_idx - 1} 张图片引用")
        # ===== 图片引用插入完成 =====

        # 将图片引用写回原始文件（11_final_final.md 现在包含图片）
        md_file.write_text(md_content_with_images, encoding="utf-8")
        self.log(step_id, f"已将图片引用写回 {md_file.name}")

        # 调用 md-to-wx-html 脚本转换（直接使用 11_final_final.md）
        script_path = Path.home() / ".claude" / "skills" / "md-to-wxhtml" / "scripts" / "convert_md_to_wx_html.py"

        html_file = self.run_dir / platform / "15_article.html"

        if script_path.exists():
            try:
                cmd = [
                    sys.executable, str(script_path),
                    str(md_file),  # 直接使用原始文件（已包含图片引用）
                    "-o", str(html_file)
                ]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if result.returncode != 0:
                    self.log(step_id, f"HTML 转换失败: {result.stderr}")
                    print(f"HTML 转换脚本返回错误: {result.stderr}")
                else:
                    self.log(step_id, "HTML 转换成功")

            except subprocess.TimeoutExpired:
                self.log(step_id, "HTML 转换超时")
                print("HTML 转换超时")
                raise
        else:
            # 脚本不存在时，生成简化 HTML（直接使用带图片的版本）
            html_content = f"""<section style="margin: 20px;">
<p style="margin-left:8px;margin-right:8px;">
<span style="font-size:15px;color:#333;font-family:PingFangSC-Regular;">
{md_content_with_images.replace(chr(10), '<br/>').replace('### ', '<strong>')}
</span>
</p>
</section>"""
            html_file.write_text(html_content, encoding="utf-8")
            self.log(step_id, "生成简化 HTML（脚本不可用）")

        handoff_path = self.write_handoff(
            platform=platform,
            step_id=step_id,
            inputs=[
                f"{platform}/11_final_final.md",
                f"{platform}/13_images/"
            ],
            outputs=[
                f"{platform}/15_article.html",
                f"{platform}/15_handoff.yaml"
            ],
            summary="将 Markdown 转换为微信编辑器兼容的 HTML",
            next_instructions=[
                f"下一步：调用 /wechat-draftbox 上传草稿",
                f"输入：{platform}/15_article.html",
                f"图片：{platform}/13_images/"
            ]
        )

        print(f"已生成: {html_file.name}")
        print(f"已生成: {handoff_path}")
        return {"artifacts": [f"{platform}/15_article.html", handoff_path]}

    def step_draftbox(self):
        """上传到草稿箱 - 调用 wechat-draftbox v2 脚本"""
        platform = "wechat"
        step_id = "16_draftbox"

        print("上传到草稿箱...")
        self.log(step_id, "调用 wechat-draftbox v2 脚本")

        # 检查前置文件
        html_file = self.run_dir / platform / "15_article.html"
        images_dir = self.run_dir / platform / "13_images"

        if not html_file.exists():
            raise FileNotFoundError(f"前置文件不存在: {html_file}")

        if not images_dir.exists() or not any(images_dir.iterdir()):
            raise FileNotFoundError(f"前置目录不存在或为空: {images_dir}")

        # 获取账号决策
        account = self.context.get_decision("wechat.account")
        if not account:
            raise ValueError("公众号账号未设置，请在 Gate A 中选择")

        # 调用 wechat-draftbox v2 脚本
        script_path = Path.home() / ".claude" / "skills" / "wechat-draftbox" / "scripts" / "wechat_draftbox_v2.py"

        if not script_path.exists():
            print(f"脚本不存在: {script_path}")
            print("请手动执行: 调用 /wechat-draftbox 技能")

            handoff_path = self.write_handoff(
                platform=platform,
                step_id=step_id,
                inputs=[f"{platform}/15_article.html"],
                outputs=[f"{platform}/16_draft.json"],
                summary=f"上传到草稿箱（账号: {account}）",
                next_instructions=["调用 /wechat-draftbox 技能上传草稿"]
            )

            return {"artifacts": [f"{platform}/16_draft.json", handoff_path]}

        # 根据确定封面图片（根据 cover_ratio）
        cover_ratio = self.context.get_decision("image.cover_ratio", "16:9")
        cover_ratio_norm = cover_ratio.replace(":", "_")
        cover_file = images_dir / f"cover_{cover_ratio_norm}.jpg"

        # 如果封面文件不存在，回退到通用查找
        if not cover_file.exists():
            # 尝试其他格式
            for ratio_alt in [f"cover_{cover_ratio.replace(':', 'x')}.jpg", "cover_16_9.jpg", "cover_16:9.jpg"]:
                alt_path = images_dir / ratio_alt
                if alt_path.exists():
                    cover_file = alt_path
                    break

        draft_output = self.run_dir / platform / "16_draft.json"
        cmd = [
            sys.executable, str(script_path),
            "--html-file", str(html_file),
            "--cover-image", str(cover_file),  # 脚本期望 --cover-image
            "--account", account,
            "--out", str(draft_output)
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180
            )

            if result.returncode != 0:
                self.log(step_id, f"脚本执行失败: {result.stderr}")
                print(f"草稿箱上传脚本返回错误: {result.stderr}")
                raise RuntimeError(f"上传失败: {result.stderr}")
            else:
                self.log(step_id, "脚本执行成功")
                print(result.stdout)

            # 检查输出文件
            draft_result = self.run_dir / platform / "16_draft.json"

            if draft_result.exists():
                handoff_path = self.write_handoff(
                    platform=platform,
                    step_id=step_id,
                    inputs=[f"{platform}/15_article.html"],
                    outputs=[f"{platform}/16_draft.json"],
                    summary=f"上传到草稿箱（账号: {account}）",
                    next_instructions=["调用 /wechat-draftbox 技能上传草稿"]
                )
                print("上传成功")
                print(f"已生成: {handoff_path}")
                return {"artifacts": [f"{platform}/16_draft.json", handoff_path]}
            else:
                raise FileNotFoundError("草稿箱结果文件未生成")

        except subprocess.TimeoutExpired:
            self.log(step_id, "草稿箱上传超时")
            print("草稿箱上传超时")
            raise
        except FileNotFoundError:
            print("Python 或脚本不可用，请手动执行 /wechat-draftbox 技能")

            handoff_path = self.write_handoff(
                platform=platform,
                step_id=step_id,
                inputs=[f"{platform}/15_article.html"],
                outputs=[f"{platform}/16_draft.json"],
                summary=f"上传到草稿箱（账号: {account}）",
                next_instructions=["调用 /wechat-draftbox 技能上传草稿"]
            )
            return {"artifacts": [f"{platform}/16_draft.json", handoff_path]}

    def _upload_images_to_wechat(self, platform: str, step_id: str) -> Optional[Path]:
        """调用 wechat-uploadimg 批量上传图片到微信 CDN"""
        images_dir = self.run_dir / platform / "13_images"

        # 检查图片目录是否存在
        if not images_dir.exists() or not any(images_dir.iterdir()):
            print("图片目录不存在或为空，跳过上传")
            self.log(step_id, "图片目录不存在或为空，跳过上传")
            return None

        # 获取账号决策
        account = self.context.get_decision("wechat.account")
        if not account:
            print("公众号账号未设置，跳过图片上传")
            self.log(step_id, "公众号账号未设置，跳过图片上传")
            return None

        # 调用 wechat-uploadimg 脚本
        script_path = Path.home() / ".claude" / "skills" / "wechat-uploadimg" / "scripts" / "wechat_uploadimg.py"
        step_num = step_id.split("_")[0][:2]
        mapping_file = self.run_dir / platform / f"{step_num}_image_mapping.json"

        if not script_path.exists():
            print(f"wechat-uploadimg 脚本不存在: {script_path}")
            print("跳过图片上传")
            self.log(step_id, "wechat-uploadimg 脚本不存在，跳过上传")
            return None

        print("正在上传图片到微信 CDN...")
        self.log(step_id, "调用 wechat-uploadimg 批量上传图片")

        try:
            cmd = [
                sys.executable, str(script_path),
                "--account", account,
                "--images-dir", str(images_dir),
                "--output", str(mapping_file)
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )

            if result.returncode != 0:
                self.log(step_id, f"图片上传失败: {result.stderr}")
                print(f"wechat-uploadimg 返回错误: {result.stderr}")
                return None

            self.log(step_id, "图片上传成功")
            print(result.stdout)
            print(f"已生成: {mapping_file.name}")
            return mapping_file

        except subprocess.TimeoutExpired:
            self.log(step_id, "图片上传超时")
            print("图片上传超时")
            raise


def slugify(txt: str) -> str:
    """将文本转换为 URL-friendly 的 slug"""
    s = txt.lower().strip()
    s = re.sub(r"[^0-9a-z\u4e00-\u9fa5]+", "-", s)
    s = re.sub(r"-+", "-", s)
    s = s.strip("-")
    return s[:80] if s else "untitled"


def init_obsidian_project(topic: str, platforms: List[str] = None,
                          research_ref: str = None) -> Path:
    """初始化 Obsidian 文章项目

    Args:
        topic: 文章话题
        platforms: 目标平台列表 ["wechat", "xhs"]
        research_ref: 研究库引用路径，如 "00_研究库/2026-02-26-topic/index"

    Returns:
        项目目录路径
    """
    if platforms is None:
        platforms = ["wechat"]

    # 生成项目 ID
    date_str = datetime.now().strftime("%Y-%m-%d")
    short_id = datetime.now().strftime("%H%M")
    topic_slug = slugify(topic)
    project_id = f"{date_str}__{topic_slug}__{short_id}"

    # 创建项目目录
    project_dir = OBSIDIAN_PROJECTS_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    # 生成 frontmatter
    today = datetime.now().strftime("%Y-%m-%d")

    # 步骤状态模板
    steps_data = {
        "research": {"status": "done" if research_ref else "pending", "file": "00_素材与链接.md"},
        "outline": {"status": "pending", "file": "01_提纲.md"},
        "draft": {"status": "pending", "file": "02_初稿.md"},
        "rag_enhance": {"status": "pending", "file": "03_RAG增强.md"},
        "titles": {"status": "pending", "file": "04_标题方案.md"},
        "polish": {"status": "pending", "file": "05_润色稿.md"},
        "final": {"status": "pending", "file": "06_终稿.md"},
        "publish": {"status": "pending", "file": "07_发布记录.md"},
    }

    # 发布状态模板
    publish_data = {
        "wechat": {"status": "pending", "title": "", "url": ""},
        "xhs": {"status": "pending", "title": "", "url": ""},
    }

    # 创建主项目文件
    main_metadata = {
        "project_id": project_id,
        "topic": topic,
        "status": "draft",
        "platforms": platforms,
        "created": today,
        "updated": today,
        "research_ref": f"[[{research_ref}|调研资料]]" if research_ref else "",
        "steps": steps_data,
        "publish": publish_data,
        "tags": ["article-project"],
    }

    # 主项目文件内容
    main_body = f"""# {topic}

## 项目概览

- **话题**: {topic}
- **创建时间**: {today}
- **当前状态**: `draft`

## 快速导航

- [[00_素材与链接|📚 素材与链接]]
- [[01_提纲|📝 提纲]]
- [[02_初稿|✏️ 初稿]]
- [[03_RAG增强|🔍 RAG增强]]
- [[04_标题方案|🏷️ 标题方案]]
- [[05_润色稿|✨ 润色稿]]
- [[06_终稿|📄 终稿]]
- [[07_发布记录|🚀 发布记录]]

---

%% 项目备注 %%
"""

    main_file = project_dir / f"📋 {topic[:30]}.md"
    main_file.write_text(write_frontmatter(main_metadata, main_body), encoding="utf-8")

    # 从模板复制各个步骤文件
    templates = [
        ("00_素材与链接.md", "📚 素材与链接"),
        ("01_提纲.md", "📝 提纲"),
        ("02_初稿.md", "✏️ 初稿"),
        ("03_RAG增强.md", "🔍 RAG增强"),
        ("04_标题方案.md", "🏷️ 标题方案"),
        ("05_润色稿.md", "✨ 润色稿"),
        ("06_终稿.md", "📄 终稿"),
        ("07_发布记录.md", "🚀 发布记录"),
    ]

    for template_name, emoji_name in templates:
        template_path = OBSIDIAN_TEMPLATES_DIR / template_name
        if template_path.exists():
            content = template_path.read_text(encoding="utf-8")
            # 替换模板变量
            content = content.replace("{{DATE}}", today)
            if research_ref:
                content = content.replace("{{RESEARCH_LINK}}", f"[[{research_ref}|调研资料]]")
            else:
                content = content.replace("{{RESEARCH_LINK}}", "待添加")

            target_file = project_dir / f"{emoji_name}.md"
            target_file.write_text(content, encoding="utf-8")

    # 复制项目看板（如果不存在）
    baseboard_path = OBSIDIAN_PROJECTS_DIR / "📋 项目看板.base"
    if not baseboard_path.exists():
        template_baseboard = OBSIDIAN_TEMPLATES_DIR / "项目看板.base"
        if template_baseboard.exists():
            shutil.copy(template_baseboard, baseboard_path)

    print(f"✅ Obsidian 项目已创建: {project_dir}")
    print(f"   主文件: {main_file.name}")
    return project_dir


def init_run_dir(topic: str, platforms: List[str] = None, use_obsidian: bool = False,
                 research_ref: str = None) -> Path:
    """初始化运行目录

    Args:
        topic: 文章话题
        platforms: 目标平台列表，默认 ["wechat"]
        use_obsidian: 是否使用 Obsidian 模式
        research_ref: 研究库引用（Obsidian 模式）

    Returns:
        项目/运行目录路径
    """
    if platforms is None:
        platforms = ["wechat"]

    # Obsidian 模式
    if use_obsidian:
        return init_obsidian_project(topic, platforms, research_ref)

    # 传统模式
    timestamp = int(datetime.now().timestamp())
    run_id = f"{topic}_{timestamp}"

    base_dir = Path("/Users/wisewong/Documents/Developer/auto-write/runs")
    run_dir = base_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # 创建子目录
    for platform in platforms:
        (run_dir / platform).mkdir(exist_ok=True)
    (run_dir / "_log").mkdir(exist_ok=True)

    # 复制模板
    template_file = Path(__file__).parent.parent / "templates" / "run_context.template.yaml"
    context_file = run_dir / "run_context.yaml"
    shutil.copy(template_file, context_file)

    # 更新上下文
    with open(context_file, 'r', encoding='utf-8') as f:
        context = yaml.safe_load(f)

    context["run_id"] = run_id
    context["topic"] = topic
    context["platforms"] = platforms

    with open(context_file, 'w', encoding='utf-8') as f:
        yaml.dump(context, f, allow_unicode=True, default_flow_style=False)

    print(f"初始化运行目录: {run_dir}")
    return run_dir


def migrate_run_context(data: Dict[str, Any]) -> bool:
    """迁移旧版 run_context.yaml 到新结构（使用专用模块）"""
    return migrate_v1_to_v2(data)


def cmd_status(run_dir: Path):
    """显示工作流状态"""
    context = RunContext(run_dir)

    print(f"\n{'=' * 80}")
    print(f"工作流状态: {context.data.get('run_id', 'N/A')}")
    print(f"{'=' * 80}")
    print(f"话题: {context.data.get('topic', 'N/A')}")
    print(f"状态: {context.data.get('status', 'N/A')}")
    print(f"当前步骤: {context.data.get('current_step', 'N/A')}")

    # 步骤表格
    print(f"\n{'=' * 80}")
    print("步骤状态")
    print(f"{'=' * 80}")

    print(f"{'步骤ID':<12} {'状态':<12} {'产物存在性':<30} {'下一步':<25}")
    print("-" * 80)

    steps_index = context.data.get("steps_index", [])
    steps_def = context.data.get("steps", {})

    for step_id in steps_index:
        step_info = steps_def.get(step_id, {})
        state = context.data.get("steps", {}).get(step_id, {}).get("state", "UNKNOWN")

        # 检查产物是否存在
        outputs = step_info.get("outputs", [])
        existence_list = []
        for output in outputs:
            # 处理通配符路径
            if "*" in output:
                output_dir = run_dir / output.rsplit("/", 1)[0]
                if output_dir.exists():
                    files = list(output_dir.glob(output.split("/")[-1]))
                    existence_list.append(f"{output.split('/')[-1]} ({len(files)})")
                else:
                    existence_list.append(f"{output.split('/')[-1]} (0)")
            else:
                output_path = run_dir / output
                existence_list.append("✓" if output_path.exists() else "✗")
        existence_str = ", ".join(existence_list[:3]) + ("..." if len(existence_list) > 3 else "")

        # 确定下一步
        current_step = context.data.get('current_step', '')
        is_next = (state in ["PENDING", "FAILED"] and current_step == step_id) or \
                   (context.data.get('status') == 'RUNNING' and state == "RUNNING")
        next_str = "→ 下一步" if is_next else ""

        print(f"{step_id:<12} {state:<12} {existence_str:<30} {next_str:<25}")

    # 待确认问题
    pending = context.data.get("pending_questions", [])
    if pending:
        print(f"\n{'=' * 80}")
        print("待确认问题（当前阻塞点）")
        print(f"{'=' * 80}")

        # Gate ID 映射
        gate_names = {
            "account_selection": "Gate A - 公众号账号选择",
            "image_config": "Gate B - 图片配置确认",
            "image_count": "Gate B - 图片数量确认"
        }

        for i, q in enumerate(pending, 1):
            gate_name = gate_names.get(q.get("id", ""), "")
            status_indicator = ""

            # 显示对应的 confirmed 状态
            if q["id"] == "account_selection":
                confirmed = context.data.get("decisions", {}).get("wechat", {}).get("confirmed", False)
                status_indicator = "（已确认）" if confirmed else "（待确认）"
            elif q["id"] in ["image_config", "image_count"]:
                confirmed = context.data.get("decisions", {}).get("image", {}).get("confirmed", False)
                status_indicator = "（已确认）" if confirmed else "（待确认）"

            print(f"\n{i}. {gate_name} {status_indicator}")
            print(f"   问题: {q.get('question', 'N/A')}")
            if q.get("type") == "choice":
                print(f"   选项: {', '.join(q.get('options', []))}")

        # 预测的下一步
        if pending[0]["id"] == "account_selection":
            next_step = "05_draft (开始写作）"
        else:  # Gate B
            next_step = "08_prompts (生成图片提示词）"

        print(f"\n确认后将继续: {next_step}")

    print(f"{'=' * 80}\n")


def cmd_plan(run_dir: Path):
    """显示剩余执行计划"""
    context = RunContext(run_dir)

    print(f"\n{'=' * 80}")
    print(f"执行计划: {context.data.get('run_id', 'N/A')}")
    print(f"{'=' * 80}")

    # 找到当前步骤
    current_step = context.data.get('current_step', '')
    steps_index = context.data.get("steps_index", [])
    steps_def = context.data.get("steps", {})

    # 确定起始索引
    if current_step:
        try:
            start_idx = steps_index.index(current_step)
        except ValueError:
            start_idx = 0
    else:
        # 找到第一个未完成的步骤
        start_idx = 0
        for i, step_id in enumerate(steps_index):
            state = context.data.get("steps", {}).get(step_id, {}).get("state", "UNKNOWN")
            if state in ["PENDING", "FAILED"]:
                start_idx = i
                break

    print(f"\n剩余步骤（从 {steps_index[start_idx]} 开始）:")
    print(f"{'=' * 80}")

    for step_id in steps_index[start_idx:]:
        step_info = steps_def.get(step_id, {})
        state = context.data.get("steps", {}).get(step_id, {}).get("state", "UNKNOWN")

        # Runner 信息
        runner = step_info.get("runner", {})
        runner_type = runner.get("type", "unknown")
        runner_name = runner.get("name", runner.get("path", "N/A"))

        # 依赖
        depends_on = step_info.get("depends_on", [])
        deps_str = ", ".join(depends_on) if depends_on else "无"

        # 预期产物
        outputs = step_info.get("outputs", [])
        outputs_str = "\n         ".join(outputs[:3]) + ("\n         ..." if len(outputs) > 3 else "")

        # 状态标记
        state_icon = {
            "PENDING": "○",
            "RUNNING": "▶",
            "DONE": "✓",
            "FAILED": "✗",
            "WAITING_FOR_USER": "⏸"
        }.get(state, "?")

        print(f"\n{state_icon} {step_id} [{state}]")
        print(f"   Runner: {runner_type} :: {runner_name}")
        if depends_on:
            print(f"   依赖: {deps_str}")
        print(f"   预期产物:")
        print(f"         {outputs_str}")

    print(f"\n{'=' * 80}\n")


def _format_duration(seconds: Optional[int]) -> str:
    if seconds is None:
        return "-"
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours}h{minutes:02d}m{secs:02d}s"


def _safe_duration_from_timestamps(started_at: Optional[str], ended_at: Optional[str]) -> Optional[int]:
    if not started_at or not ended_at:
        return None
    try:
        start_ts = datetime.fromisoformat(started_at)
        end_ts = datetime.fromisoformat(ended_at)
    except ValueError:
        return None
    delta = int((end_ts - start_ts).total_seconds())
    return delta if delta >= 0 else None


def cmd_timings(run_dir: Path):
    """显示步骤耗时表"""
    context = RunContext(run_dir)

    print(f"\n{'=' * 80}")
    print(f"耗时统计: {context.data.get('run_id', 'N/A')}")
    print(f"{'=' * 80}")

    steps_index = context.data.get("steps_index", [])
    steps_def = context.data.get("steps", {})

    print(f"{'步骤ID':<12} {'状态':<12} {'耗时':<10} {'开始时间':<20} {'结束时间':<20}")
    print("-" * 80)

    total = 0
    total_count = 0

    for step_id in steps_index:
        step = steps_def.get(step_id, {})
        state = step.get("state", "UNKNOWN")
        started_at = step.get("started_at")
        ended_at = step.get("ended_at")
        duration = step.get("duration_sec")
        if duration is None:
            duration = _safe_duration_from_timestamps(started_at, ended_at)
        duration_str = _format_duration(duration)

        if duration is not None:
            total += duration
            total_count += 1

        started_str = started_at if started_at else "-"
        ended_str = ended_at if ended_at else "-"

        print(f"{step_id:<12} {state:<12} {duration_str:<10} {started_str:<20} {ended_str:<20}")

    print("-" * 80)
    print(f"已统计 {total_count} 个步骤，总耗时: {_format_duration(total)}")
    print(f"{'=' * 80}\n")


def cmd_doctor():
    """环境自检"""
    print(f"\n{'=' * 80}")
    print("环境自检")
    print(f"{'=' * 80}")

    all_ok = True

    # 1. 检查 .env 是否加载
    print("\n1. 环境变量检查")
    print("-" * 80)

    env_vars = [
        # 通用
        "HOME", "PATH",
        # AI 相关
        "CLAUDE_API_KEY", "OPENAI_API_KEY",
        # 微信相关
        "WECHAT_APPID", "WECHAT_APPSECRET",
        "WECHAT_APPID_MAIN", "WECHAT_APPSECRET_MAIN",
        "WECHAT_APPID_SUB", "WECHAT_APPSECRET_SUB",
        # 火山相关
        "ARK_API_KEY", "ARK_ACCESS_KEY",
    ]

    missing_vars = []
    for var in env_vars:
        if var in os.environ:
            print(f"  ✓ {var}")
        else:
            print(f"  ✗ {var} (未设置)")
            missing_vars.append(var)
            all_ok = False

    if not missing_vars:
        print("\n  所有必需环境变量均已设置")
    else:
        print(f"\n  缺失环境变量: {', '.join(missing_vars)}")

    # 2. 检查关键脚本是否可执行
    print("\n2. 关键脚本检查")
    print("-" * 80)

    skill_dir = Path(__file__).parent.parent
    scripts = [
        skill_dir / "scripts" / "orchestrator.py",
    ]

    for script in scripts:
        if script.exists():
            print(f"  ✓ {script.name}")
        else:
            print(f"  ✗ {script.name} (不存在)")
            all_ok = False

    # 3. 检查依赖
    print("\n3. Python 依赖检查")
    print("-" * 80)

    dependencies = [
        ("yaml", "PyYAML"),
        ("pathlib", "pathlib (内建)"),
    ]

    for module, name in dependencies:
        try:
            __import__(module)
            print(f"  ✓ {name}")
        except ImportError:
            print(f"  ✗ {name} (未安装)")
            all_ok = False

    # 4. 检查模板文件
    print("\n4. 模板文件检查")
    print("-" * 80)

    template_file = skill_dir / "templates" / "run_context.template.yaml"
    if template_file.exists():
        print(f"  ✓ run_context.template.yaml")
    else:
        print(f"  ✗ run_context.template.yaml (不存在)")
        all_ok = False

    # 总结
    print("\n" + "=" * 80)
    if all_ok:
        print("✓ 所有检查通过，环境正常")
        print("=" * 80 + "\n")
        exit(0)
    else:
        print("✗ 发现问题，请修复后再试")
        print("=" * 80 + "\n")
        exit(1)


def main():
    parser = argparse.ArgumentParser(description="文章创作工作流 - Orchestrator")
    parser.add_argument("--topic", help="文章话题")
    parser.add_argument("--resume", help="从现有运行目录恢复")
    parser.add_argument("--start-from", help="从指定步骤开始")
    parser.add_argument("--status", action="store_true", help="显示工作流状态")
    parser.add_argument("--plan", action="store_true", help="显示执行计划")
    parser.add_argument("--timings", action="store_true", help="显示步骤耗时统计")
    parser.add_argument("--doctor", action="store_true", help="环境自检")
    parser.add_argument("--obsidian", action="store_true", help="使用 Obsidian 存储模式")
    parser.add_argument("--research-ref", help="研究库引用路径（Obsidian 模式）")

    args = parser.parse_args()

    # 预加载 .env（支持全局 ~/.claude/.env、skills/.env、运行目录 .env）
    def load_env_file(p: Path):
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if not line or line.strip().startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and v and k not in os.environ:
                        os.environ[k] = v

    home = Path.home()
    load_env_file(home / ".claude" / "config.json") # Try config.json as well (simple parse)
    load_env_file(home / ".claude" / ".env")
    load_env_file(home / ".claude" / "skills" / ".env")

    # Doctor 命令
    if args.doctor:
        cmd_doctor()
        return

    # 状态/计划命令（需要 run_dir）
    if args.status or args.plan or args.timings:
        if args.resume:
            run_dir = Path(args.resume)
        else:
            # 尝试从当前目录查找 run_context.yaml
            run_dir = Path.cwd()
            if not (run_dir / "run_context.yaml").exists():
                parser.error("--status/--plan/--timings 需要指定 --resume 或在运行目录中执行")

        if args.status:
            cmd_status(run_dir)
        if args.plan:
            cmd_plan(run_dir)
        if args.timings:
            cmd_timings(run_dir)
        return

    # 正常执行
    if args.resume:
        run_dir = Path(args.resume)
    elif args.topic:
        run_dir = init_run_dir(args.topic, use_obsidian=args.obsidian, research_ref=args.research_ref)
    else:
        parser.error("必须指定 --topic 或 --resume（或使用 --status/--plan）")

    # 运行目录 .env （最后覆盖）
    load_env_file(run_dir / ".env")

    orchestrator = Orchestrator(run_dir)
    orchestrator.run(start_from=args.start_from)


if __name__ == "__main__":
    main()
