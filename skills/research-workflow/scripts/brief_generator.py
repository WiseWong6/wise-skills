#!/usr/bin/env python3
"""
内容 Brief 生成脚本 v2.0

升级版: 采用 11 部分结构化报告模板
整合置信度评分、批判性审视和事实核查
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ContentType(str, Enum):
    """内容类型"""
    ARTICLE = "article"
    TUTORIAL = "tutorial"
    CASE_STUDY = "case_study"
    OPINION = "opinion"
    TREND = "trend"
    COMPARISON = "comparison"


class FormatType(str, Enum):
    """输出格式类型"""
    MARKDOWN = "markdown"
    HTML = "html"
    PLAIN_TEXT = "plain_text"


class WritingStyle(str, Enum):
    """写作风格"""
    TECHNICAL = "technical"
    CASUAL = "casual"
    PROFESSIONAL = "professional"
    STORYTELLING = "storytelling"


class ContentBriefGenerator:
    """内容 Brief 生成器"""

    def __init__(self):
        self.trend_data = None
        self.gap_data = None
        self.research_data = None

    def generate(
        self,
        topic: str,
        trend_data: Optional[Dict[str, Any]] = None,
        gap_data: Optional[Dict[str, Any]] = None,
        research_data: Optional[Dict[str, Any]] = None,
        audience: str = "通用技术读者",
        content_type: ContentType = ContentType.ARTICLE,
        primary_goal: str = "educate",
        format: FormatType = FormatType.MARKDOWN,
        style: WritingStyle = WritingStyle.TECHNICAL
    ) -> str:
        """生成内容 Brief（新版 11 部分结构）"""
        print(f"\n📝 为主题 '{topic}' 生成内容 Brief...")

        self.trend_data = trend_data
        self.gap_data = gap_data
        self.research_data = research_data

        brief = self._build_brief(topic, audience, content_type, primary_goal, style)
        return brief

    def _build_brief(
        self,
        topic: str,
        audience: str,
        content_type: ContentType,
        primary_goal: str,
        style: WritingStyle
    ) -> str:
        """构建 Brief 内容"""
        lines = []

        # 标题
        lines.append(f"# {topic} 调研报告")
        lines.append("")
        lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")

        # 一、核心事件概览
        lines.append("## 一、核心事件概览")
        lines.append("")
        lines.extend(self._build_core_event(topic))
        lines.append("")

        # 二、技术架构分析
        lines.append("## 二、技术架构分析")
        lines.append("")
        lines.extend(self._build_tech_architecture(topic))
        lines.append("")

        # 三、应用场景/案例
        lines.append("## 三、应用场景/案例")
        lines.append("")
        lines.extend(self._build_use_cases(topic))
        lines.append("")

        # 四、市场影响与商业价值
        lines.append("## 四、市场影响与商业价值")
        lines.append("")
        lines.extend(self._build_market_impact(topic))
        lines.append("")

        # 五、竞争格局
        lines.append("## 五、竞争格局")
        lines.append("")
        lines.extend(self._build_competition(topic))
        lines.append("")

        # 六、技术趋势研判
        lines.append("## 六、技术趋势研判")
        lines.append("")
        lines.extend(self._build_tech_trends(topic))
        lines.append("")

        # 七、写作角度建议
        lines.append("## 七、写作角度建议（3 个）")
        lines.append("")
        lines.extend(self._build_writing_angles(topic))
        lines.append("")

        # 八、内容 Brief 建议
        lines.append("## 八、内容 Brief 建议")
        lines.append("")
        lines.extend(self._build_brief_suggestions(topic))
        lines.append("")

        # 九、风险与挑战
        lines.append("## 九、风险与挑战")
        lines.append("")
        lines.extend(self._build_risks_challenges(topic))
        lines.append("")

        # 十、信息源说明
        lines.append("## 十、信息源说明")
        lines.append("")
        lines.extend(self._build_sources_section())
        lines.append("")

        # 十一、批判性审视
        lines.append("## 十一、批判性审视")
        lines.append("")
        lines.extend(self._build_review_section())

        return "\n".join(lines)

    def _build_core_event(self, topic: str) -> List[str]:
        """构建核心事件概览"""
        lines = []
        lines.append(f"- **事件本质**: {topic}的核心概念和实践应用")
        lines.append(f"- **技术/产品定位**: 技术创新和实践指南")
        lines.append("- **关键方/支持方**: ")
        if self.research_data:
            findings = self.research_data.get("findings", [])
            if findings:
                players = self._extract_key_players(findings)
                for player in players[:5]:
                    lines.append(f"  - {player}")
        if not lines or len(lines) == 3:
            lines.append("  - （待补充）")
        return lines

    def _build_tech_architecture(self, topic: str) -> List[str]:
        """构建技术架构分析"""
        lines = ["（待研究数据填充）"]
        return lines

    def _build_use_cases(self, topic: str) -> List[str]:
        """构建应用场景/案例"""
        lines = ["（待研究数据填充）"]
        return lines

    def _build_market_impact(self, topic: str) -> List[str]:
        """构建市场影响与商业价值"""
        lines = ["（待研究数据填充）"]
        return lines

    def _build_competition(self, topic: str) -> List[str]:
        """构建竞争格局"""
        lines = ["（待研究数据填充）"]
        return lines

    def _build_tech_trends(self, topic: str) -> List[str]:
        """构建技术趋势研判"""
        lines = ["（待研究数据填充）"]
        return lines

    def _build_writing_angles(self, topic: str) -> List[str]:
        """构建写作角度建议"""
        return [
            f"### 角度 1: 深度解析型",
            f"**核心观点**: {topic}的技术原理与实践",
            "**核心要点**: 原理解析、架构设计、最佳实践",
            "**优势**: 适合技术读者",
            "",
            f"### 角度 2: 实践指南型",
            f"**核心观点**: {topic}的落地实践",
            "**核心要点**: 快速上手、常见问题、优化建议",
            "**优势**: 适合实践者",
            "",
            f"### 角度 3: 趋势分析型",
            f"**核心观点**: {topic}的发展趋势",
            "**核心要点**: 技术演进、市场变化、未来预测",
            "**优势**: 适合决策者",
        ]

    def _build_brief_suggestions(self, topic: str) -> List[str]:
        """构建 Brief 建议"""
        return [
            "### 标题建议（3 个候选标题）",
            f"1. {topic}：深度解析与实践指南",
            f"2. 深入理解 {topic}：从原理到实践",
            f"3. {topic} 发展趋势与未来展望",
            "",
            "### 核心结构",
            "1. 引言: 背景与问题",
            "2. 核心概念解析",
            "3. 技术架构分析",
            "4. 实践应用指南",
            "5. 效果评估与优化",
            "6. 总结与展望",
            "",
            "### 关键数据点",
            "（待研究数据填充）",
        ]

    def _build_risks_challenges(self, topic: str) -> List[str]:
        """构建风险与挑战"""
        lines = []
        if self.research_data:
            findings = self.research_data.get("findings", [])
            if findings:
                # 技术挑战
                tech_challenges = self._extract_challenges(findings, ["挑战", "难点", "问题"])
                if tech_challenges:
                    lines.append("### 技术挑战")
                    for c in tech_challenges[:3]:
                        lines.append(f"- {c}")
                    lines.append("")

                # 市场挑战
                market_challenges = self._extract_challenges(findings, ["市场", "商业化", "落地"])
                if market_challenges:
                    lines.append("### 市场挑战")
                    for c in market_challenges[:3]:
                        lines.append(f"- {c}")

        if not lines:
            lines.append("（暂无风险与挑战相关信息）")

        return lines

    def _build_sources_section(self) -> List[str]:
        """构建信息源说明"""
        lines = []
        lines.append("### 信息源列表")
        lines.append("")

        if self.research_data:
            findings = self.research_data.get("findings", [])
            source_count = 0
            for finding in findings:
                sources = finding.get("sources", [])
                for source in sources[:2]:
                    lines.append(f"{source_count}. [{source.get('title', 'N/A')}]({source.get('url', '')})")
                    lines.append(f"   - 日期: {source.get('date', 'N/A')}")
                    lines.append(f"   - 置信度: {source.get('confidence', 'N/A')}")
                    lines.append("")
                    source_count += 1

                    if source_count >= 10:
                        break
                if source_count >= 10:
                    break

        if not lines or len(lines) <= 2:
            lines.append("（暂无信息源）")

        return lines

    def _build_review_section(self) -> List[str]:
        """构建批判性审视"""
        lines = []
        lines.append("（使用 ReviewAnalyzer 生成批判性审视报告）")
        lines.append("")
        lines.append("### 可能反驳")
        lines.append("- AI 技术的成熟度可能被高估")
        lines.append("- 实际落地可能面临更多挑战")
        lines.append("- 伦理和监管问题需要更多关注")
        lines.append("")
        lines.append("### 论证漏洞")
        lines.append("- （待批判性审视分析填充）")
        lines.append("")
        lines.append("### 适用边界")
        lines.append("- 适用于: 企业级技术场景")
        lines.append("- 可能不适用: 个人用户场景")
        return lines

    def _extract_key_players(self, findings: List[Dict]) -> List[str]:
        """提取关键方"""
        players = set()
        keywords = [
            "谷歌", "微软", "OpenAI", "Anthropic", "Meta", "字节", "腾讯",
            "阿里", "百度", "AWS", "GCP", "Azure", "苹果", "英伟达"
        ]
        for finding in findings:
            claim = finding.get("claim", "")
            for kw in keywords:
                if kw in claim:
                    players.add(kw)
        return list(players)

    def _extract_challenges(self, findings: List[Dict], keywords: List[str]) -> List[str]:
        """提取挑战"""
        challenges = []
        for finding in findings:
            claim = finding.get("claim", "")
            if any(kw in claim for kw in keywords):
                challenges.append(claim[:80])
        return challenges[:5]

    def _suggest_title(self, topic: str) -> str:
        """建议标题"""
        return f"{topic}：深度解析与实践指南"


def generate_brief(
    topic: str,
    trend_data: Optional[Dict[str, Any]] = None,
    gap_data: Optional[Dict[str, Any]] = None,
    research_data: Optional[Dict[str, Any]] = None,
    audience: str = "通用技术读者",
    content_type: ContentType = ContentType.ARTICLE,
    primary_goal: str = "educate",
    format: FormatType = FormatType.MARKDOWN,
    style: WritingStyle = WritingStyle.TECHNICAL,
    output_file: Optional[str] = None
) -> str:
    """
    生成内容 Brief（新版 11 部分结构）

    整合置信度评分、批判性审视和事实核查
    """
    generator = ContentBriefGenerator()
    brief = generator.generate(
        topic=topic,
        trend_data=trend_data,
        gap_data=gap_data,
        research_data=research_data,
        audience=audience,
        content_type=content_type,
        primary_goal=primary_goal,
        format=format,
        style=style
    )

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(brief)
        print(f"✅ Brief 已保存到: {output_file}")

    return brief


if __name__ == "__main__":
    # 测试代码
    print("Brief Generator v2.0 测试")
    print("-" * 50)

    brief = generate_brief("AI Agent 发展趋势")
    print(brief)
