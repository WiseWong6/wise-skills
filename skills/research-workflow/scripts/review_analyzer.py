#!/usr/bin/env python3
"""
批判性审视分析器

职责: 对研究结果进行深度分析和批判性审视

移植自 write-agent/src/agents/article/nodes/03_review.node.ts

分析框架:
1. 核心内容 - 搞清楚"是什么"
2. 批判性审视 - 搞清楚"有什么问题"
3. 价值提取 - 搞清楚"有什么用"
4. 信息源评估 - 搞清楚"可不可信"
"""

import os
import re
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ReviewResult:
    """审视结果"""
    core_content: Dict[str, Any] = field(default_factory=dict)
    critical_review: Dict[str, Any] = field(default_factory=dict)
    value_extraction: Dict[str, Any] = field(default_factory=dict)
    source_evaluation: Dict[str, Any] = field(default_factory=dict)
    generated_at: str = ""
    is_fallback: bool = False


class ReviewAnalyzer:
    """批判性审视分析器"""

    def __init__(self):
        self.review_result = None

    def analyze(self, research_content: str, findings: List[Dict] = None) -> ReviewResult:
        """
        执行四维分析

        Args:
            research_content: 研究内容 Markdown
            findings: 研究发现列表（可选）

        Returns:
            ReviewResult 对象
        """
        self.review_result = ReviewResult(
            generated_at=datetime.now().isoformat()
        )

        # 1. 核心内容分析
        self.review_result.core_content = self._analyze_core_content(research_content)

        # 2. 批判性审视
        self.review_result.critical_review = self._analyze_critical(research_content)

        # 3. 价值提取
        self.review_result.value_extraction = self._analyze_value(research_content)

        # 4. 信息源评估
        self.review_result.source_evaluation = self._evaluate_sources(findings or [])

        return self.review_result

    def _analyze_core_content(self, content: str) -> Dict[str, Any]:
        """
        分析核心内容 - 搞清楚"是什么"

        分析维度:
        - 核心论点: 用一句话概括文章的核心论点
        - 关键概念: 作者用了哪些关键概念？这些概念是怎么定义的？
        - 论证结构: 论证是怎么展开的？各部分如何衔接？
        """
        # 提取标题
        title = self._extract_title(content)

        # 提取核心论点（从摘要或第一段）
        core_claim = self._extract_core_claim(content)

        # 提取关键概念
        key_concepts = self._extract_key_concepts(content)

        # 分析论证结构
        argument_structure = self._analyze_argument_structure(content)

        return {
            "title": title,
            "core_claim": core_claim,
            "key_concepts": key_concepts,
            "argument_structure": argument_structure
        }

    def _analyze_critical(self, content: str) -> Dict[str, Any]:
        """
        批判性审视 - 搞清楚"有什么问题"

        分析维度:
        - 可能反驳: 主要的反对意见可能是什么？
        - 论证漏洞: 论证有没有漏洞、跳跃或偏颇之处？
        - 适用边界: 观点在什么情况下成立？什么情况下不成立？
        - 回避问题: 作者有没有刻意回避或淡化什么问题？
        """
        # 检测论证漏洞
        argument_gaps = self._detect_argument_gaps(content)

        # 推断可能的反驳
        potential_rebuttals = self._infer_potential_rebuttals(content)

        # 识别适用边界
        boundaries = self._identify_boundaries(content)

        # 检测回避的问题
        avoided_issues = self._detect_avoided_issues(content)

        return {
            "potential_rebuttals": potential_rebuttals,
            "argument_gaps": argument_gaps,
            "boundaries": boundaries,
            "avoided_issues": avoided_issues
        }

    def _analyze_value(self, content: str) -> Dict[str, Any]:
        """
        价值提取 - 搞清楚"有什么用"

        分析维度:
        - 思考框架: 提出了什么可复用的思考框架或方法论？
        - 认知改变: 这篇文章可能改变读者的什么认知？
        - 写作价值: 对后续写作有什么启发？（结构、技巧、风格）
        """
        # 提取思考框架
        frameworks = self._extract_frameworks(content)

        # 识别认知改变点
        cognitive_shifts = self._identify_cognitive_shifts(content)

        # 提取写作启发
        writing_inspiration = self._extract_writing_inspiration(content)

        return {
            "frameworks": frameworks,
            "cognitive_shifts": cognitive_shifts,
            "writing_inspiration": writing_inspiration
        }

    def _evaluate_sources(self, findings: List[Dict]) -> Dict[str, Any]:
        """
        信息源评估 - 搞清楚"可不可信"

        评估维度:
        - 信息源列表: 主要参考的搜索结果（标题 + URL）
        - 置信度评估: 标注信息来源的置信度（FACT/BELIEF/ASSUMPTION）
        """
        sources = []
        confidence_summary = {"FACT": 0, "BELIEF": 0, "ASSUMPTION": 0, "CONTRADICTION": 0}

        for finding in findings:
            for source in finding.get("sources", []):
                sources.append({
                    "title": source.get("title", ""),
                    "url": source.get("url", ""),
                    "date": source.get("date", ""),
                    "confidence": finding.get("confidence_type", "ASSUMPTION")
                })

            # 统计置信度
            conf_type = finding.get("confidence_type", "ASSUMPTION")
            if conf_type in confidence_summary:
                confidence_summary[conf_type] += 1

        return {
            "sources": sources[:10],  # 限制为前 10 个
            "confidence_summary": confidence_summary,
            "total_findings": len(findings),
            "total_sources": len(sources)
        }

    # ========== 辅助方法 ==========

    def _extract_title(self, content: str) -> str:
        """提取标题"""
        lines = content.split("\n")
        for line in lines:
            if line.startswith("# "):
                return line[2:].strip()
        return "未知标题"

    def _extract_core_claim(self, content: str) -> str:
        """提取核心论点"""
        # 查找摘要部分
        sections = content.split("## ")
        for section in sections:
            if section.startswith("核心洞察") or section.startswith("摘要") or section.startswith("概览"):
                lines = section.split("\n")
                # 取第一个非空行
                for line in lines[1:]:
                    if line.strip() and not line.startswith("#"):
                        return line.strip()[:200]

        # 如果没有摘要，取第一段
        paragraphs = content.split("\n\n")
        for p in paragraphs:
            if p.strip() and not p.startswith("#"):
                return p.strip()[:200]

        return "未能提取核心论点"

    def _extract_key_concepts(self, content: str) -> List[Dict[str, str]]:
        """提取关键概念"""
        concepts = []

        # 查找概念框架部分
        if "## 概念框架" in content or "## 关键概念" in content:
            sections = re.split(r'## (?:概念框架|关键概念)', content)
            if len(sections) > 1:
                concept_section = sections[1].split("##")[0]

                # 提取列表项
                for line in concept_section.split("\n"):
                    if line.strip().startswith("- ") or line.strip().startswith("* "):
                        concept_text = line.strip()[2:]
                        # 尝试分离概念名和定义
                        if "：" in concept_text or ":" in concept_text:
                            parts = re.split(r'[：:]', concept_text, 1)
                            concepts.append({
                                "name": parts[0].strip(),
                                "definition": parts[1].strip() if len(parts) > 1 else ""
                            })
                        else:
                            concepts.append({
                                "name": concept_text[:50],
                                "definition": ""
                            })

        return concepts[:5]  # 限制为前 5 个

    def _analyze_argument_structure(self, content: str) -> Dict[str, Any]:
        """分析论证结构"""
        # 提取所有二级标题
        sections = re.findall(r'## (.+)', content)

        # 识别论证模式
        patterns = []
        if any("背景" in s or "问题" in s for s in sections):
            patterns.append("问题导向")
        if any("案例" in s or "实例" in s for s in sections):
            patterns.append("案例驱动")
        if any("对比" in s or "比较" in s for s in sections):
            patterns.append("对比分析")
        if any("趋势" in s or "预测" in s for s in sections):
            patterns.append("趋势分析")

        return {
            "sections": sections[:10],
            "patterns": patterns,
            "section_count": len(sections)
        }

    def _detect_argument_gaps(self, content: str) -> List[str]:
        """检测论证漏洞"""
        gaps = []

        # 检测常见的论证问题
        gap_patterns = [
            (r'因此[^。]*。', "可能存在因果跳跃"),
            (r'显然[^。]*。', "使用'显然'可能掩盖论证不足"),
            (r'众所周知[^。]*。', "引用'众所周知'可能缺乏具体证据"),
            (r'一定[^。]*。', "使用'一定'可能过于绝对"),
            (r'必须[^。]*。', "使用'必须'可能过于武断"),
        ]

        for pattern, message in gap_patterns:
            matches = re.findall(pattern, content)
            if matches:
                gaps.append(f"{message}（发现 {len(matches)} 处）")

        # 检测数据缺失
        if not re.search(r'\d+%', content) and not re.search(r'\d+亿', content):
            gaps.append("缺少具体数据支撑")

        # 检测引用缺失
        if content.count('[') < 3:
            gaps.append("引用来源较少")

        return gaps[:5]

    def _infer_potential_rebuttals(self, content: str) -> List[str]:
        """推断可能的反驳"""
        rebuttals = []

        # 基于内容主题推断反驳
        if "AI" in content or "人工智能" in content:
            rebuttals.extend([
                "AI 技术的成熟度可能被高估",
                "实际落地可能面临更多挑战",
                "伦理和监管问题需要更多关注"
            ])

        if "趋势" in content or "预测" in content:
            rebuttals.extend([
                "预测可能受当前认知局限",
                "黑天鹅事件可能改变趋势",
                "不同地区发展可能不同步"
            ])

        if "成功" in content or "案例" in content:
            rebuttals.extend([
                "成功案例可能存在幸存者偏差",
                "失败案例可能被忽略",
                "可复制性需要验证"
            ])

        return rebuttals[:5]

    def _identify_boundaries(self, content: str) -> Dict[str, List[str]]:
        """识别适用边界"""
        boundaries = {
            "applicable": [],
            "not_applicable": []
        }

        # 查找边界条件关键词
        applicable_patterns = [
            r'适用于([^。，]+)',
            r'在([^。，]+)情况下',
            r'当([^。，]+)时',
        ]

        for pattern in applicable_patterns:
            matches = re.findall(pattern, content)
            boundaries["applicable"].extend(matches[:3])

        # 推断不适用情况
        if "企业" in content:
            boundaries["not_applicable"].append("个人用户场景可能不适用")
        if "大型" in content:
            boundaries["not_applicable"].append("中小型场景可能不适用")
        if "技术" in content:
            boundaries["not_applicable"].append("非技术背景读者可能难以理解")

        return boundaries

    def _detect_avoided_issues(self, content: str) -> List[str]:
        """检测回避的问题"""
        avoided = []

        # 检测常见被回避的话题
        sensitive_topics = [
            ("成本", "成本分析"),
            ("风险", "风险评估"),
            ("失败", "失败案例"),
            ("局限", "局限性"),
            ("争议", "争议点"),
            ("竞争", "竞争分析"),
        ]

        for keyword, topic in sensitive_topics:
            if keyword not in content:
                avoided.append(f"未涉及{topic}")

        return avoided[:5]

    def _extract_frameworks(self, content: str) -> List[Dict[str, str]]:
        """提取思考框架"""
        frameworks = []

        # 查找方法论/框架部分
        if "## 方法论" in content or "## 框架" in content or "## 思考框架" in content:
            sections = re.split(r'## (?:方法论|框架|思考框架)', content)
            if len(sections) > 1:
                framework_section = sections[1].split("##")[0]

                for line in framework_section.split("\n"):
                    if line.strip().startswith("- ") or line.strip().startswith("* "):
                        frameworks.append({
                            "name": line.strip()[2:50],
                            "description": ""
                        })

        # 如果没有显式的框架，尝试从结构推断
        if not frameworks:
            sections = re.findall(r'## (.+)', content)
            if len(sections) >= 3:
                frameworks.append({
                    "name": "隐含结构框架",
                    "description": " → ".join(sections[:5])
                })

        return frameworks[:3]

    def _identify_cognitive_shifts(self, content: str) -> List[str]:
        """识别认知改变点"""
        shifts = []

        # 查找认知相关内容
        shift_patterns = [
            r'认知([^。，]{5,30})',
            r'理解([^。，]{5,30})',
            r'发现([^。，]{5,30})',
            r'启示([^。，]{5,30})',
        ]

        for pattern in shift_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                shift = f"可能改变对{match.strip()}的认知"
                if shift not in shifts:
                    shifts.append(shift)

        return shifts[:5]

    def _extract_writing_inspiration(self, content: str) -> Dict[str, List[str]]:
        """提取写作启发"""
        inspiration = {
            "structure": [],
            "techniques": [],
            "style": []
        }

        # 分析结构启发
        sections = re.findall(r'## (.+)', content)
        if len(sections) >= 3:
            inspiration["structure"].append(f"多层级结构：{' → '.join(sections[:5])}")

        # 分析技巧启发
        if "案例" in content:
            inspiration["techniques"].append("案例驱动叙述")
        if "数据" in content:
            inspiration["techniques"].append("数据支撑观点")
        if "对比" in content:
            inspiration["techniques"].append("对比强化论证")

        # 分析风格启发
        if re.search(r'[！？]', content):
            inspiration["style"].append("使用反问增强互动")
        if content.count("你") > 3:
            inspiration["style"].append("第二人称增强代入感")

        return inspiration

    def generate_report(self, result: ReviewResult = None) -> str:
        """
        生成 Markdown 格式的审视报告

        Args:
            result: ReviewResult 对象，如果为 None 则使用最后一次分析结果

        Returns:
            Markdown 格式的报告
        """
        if result is None:
            result = self.review_result

        if result is None:
            return "# 批判性审视报告\n\n无分析结果"

        lines = [
            "# 批判性审视报告",
            "",
            f"> 生成时间: {result.generated_at}",
            "",
            "---",
            "",
            '## 一、核心内容（搞清楚"是什么"）',
            "",
            "### 核心论点",
            "",
            f"{result.core_content.get('core_claim', '未能提取')}",
            "",
            "### 关键概念",
            "",
        ]

        for concept in result.core_content.get("key_concepts", []):
            lines.append(f"- **{concept['name']}**: {concept.get('definition', '（待定义）')}")

        if not result.core_content.get("key_concepts"):
            lines.append("_未识别到明确的关键概念_")

        lines.extend([
            "",
            "### 论证结构",
            "",
            f"- 论证模式: {', '.join(result.core_content.get('argument_structure', {}).get('patterns', ['未识别']))}",
            f"- 章节数量: {result.core_content.get('argument_structure', {}).get('section_count', 0)}",
            "",
            "---",
            "",
            '## 二、批判性审视（搞清楚"有什么问题"）',
            "",
            "### 可能反驳",
            "",
        ])

        for rebuttal in result.critical_review.get("potential_rebuttals", []):
            lines.append(f"- {rebuttal}")

        if not result.critical_review.get("potential_rebuttals"):
            lines.append("_未识别到明显的反驳点_")

        lines.extend([
            "",
            "### 论证漏洞",
            "",
        ])

        for gap in result.critical_review.get("argument_gaps", []):
            lines.append(f"- ⚠️ {gap}")

        if not result.critical_review.get("argument_gaps"):
            lines.append("_未检测到明显的论证漏洞_")

        lines.extend([
            "",
            "### 适用边界",
            "",
        ])

        boundaries = result.critical_review.get("boundaries", {})
        if boundaries.get("applicable"):
            lines.append("**适用条件:**")
            for cond in boundaries["applicable"]:
                lines.append(f"- {cond}")

        if boundaries.get("not_applicable"):
            lines.append("**可能不适用:**")
            for cond in boundaries["not_applicable"]:
                lines.append(f"- {cond}")

        lines.extend([
            "",
            "### 回避的问题",
            "",
        ])

        for issue in result.critical_review.get("avoided_issues", []):
            lines.append(f"- ⚠️ {issue}")

        if not result.critical_review.get("avoided_issues"):
            lines.append("_未检测到明显回避的问题_")

        lines.extend([
            "",
            "---",
            "",
            '## 三、价值提取（搞清楚"有什么用"）',
            "",
            "### 思考框架",
            "",
        ])

        for fw in result.value_extraction.get("frameworks", []):
            lines.append(f"- **{fw['name']}**: {fw.get('description', '')}")

        if not result.value_extraction.get("frameworks"):
            lines.append("_未识别到明确的思考框架_")

        lines.extend([
            "",
            "### 认知改变",
            "",
        ])

        for shift in result.value_extraction.get("cognitive_shifts", []):
            lines.append(f"- {shift}")

        if not result.value_extraction.get("cognitive_shifts"):
            lines.append("_未识别到明确的认知改变点_")

        lines.extend([
            "",
            "### 写作启发",
            "",
        ])

        writing = result.value_extraction.get("writing_inspiration", {})
        for category, items in writing.items():
            if items:
                category_names = {"structure": "结构", "techniques": "技巧", "style": "风格"}
                lines.append(f"**{category_names.get(category, category)}:**")
                for item in items:
                    lines.append(f"- {item}")
                lines.append("")

        lines.extend([
            "---",
            "",
            '## 四、信息源评估（搞清楚"可不可信"）',
            "",
            "### 置信度分布",
            "",
        ])

        conf = result.source_evaluation.get("confidence_summary", {})
        for conf_type, count in conf.items():
            if count > 0:
                lines.append(f"- **{conf_type}**: {count} 条")

        lines.extend([
            "",
            f"### 统计",
            "",
            f"- 研究发现: {result.source_evaluation.get('total_findings', 0)} 条",
            f"- 信息来源: {result.source_evaluation.get('total_sources', 0)} 个",
            "",
            "---",
            "",
        ])

        if result.is_fallback:
            lines.extend([
                "> ⚠️ **注意**: 此报告为降级模式生成，部分分析可能不完整。",
                "",
            ])

        return "\n".join(lines)


def generate_fallback_review(content: str) -> ReviewResult:
    """
    LLM 失败时的降级策略

    Args:
        content: 研究内容

    Returns:
        基础的 ReviewResult 对象
    """
    analyzer = ReviewAnalyzer()
    result = analyzer.analyze(content)
    result.is_fallback = True
    return result


if __name__ == "__main__":
    # 测试代码
    print("Review Analyzer 测试")
    print("-" * 50)

    test_content = """
# AI Agent 发展趋势研究报告

## 核心洞察

AI Agent 正在从单一任务执行向多智能体协作演进，这一趋势将重塑企业自动化格局。

## 概念框架

- **Agent**: 能够感知环境、做出决策并采取行动的智能体
- **多智能体系统**: 多个 Agent 协作完成复杂任务的系统
- **编排层**: 协调多个 Agent 工作的中间层

## 技术趋势

### 1. 从单任务到多任务

传统的 AI Agent 只能完成单一任务，而新一代 Agent 正在具备多任务处理能力。

### 2. 从独立到协作

多个 Agent 之间的协作正在成为主流，通过编排层协调工作。

## 案例分析

Claude Code Agent Teams 实现了多 Agent 并行开发，显著提升了开发效率。

## 数据支撑

根据调研，50% 的企业已在探索 AI Agent 应用。
"""

    analyzer = ReviewAnalyzer()
    result = analyzer.analyze(test_content)

    print(analyzer.generate_report(result))
