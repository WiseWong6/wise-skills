#!/usr/bin/env python3
"""
事实核查器

职责: 对研究发现进行事实核查，确保内容准确性

判定标准:
- pass: 事实准确，有明确证据支持
- warn: 不可验证/缺来源/疑似夸大
- fail: 事实错误或严重误导

移植自 write-agent/src/agents/article/nodes/09_fact_check.node.ts
"""

import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Literal
from dataclasses import dataclass, field
from enum import Enum


class Verdict(str, Enum):
    """判定结果"""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class Severity(str, Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class FactCheckItem:
    """事实核查项"""
    claim: str                          # 被核查的事实性陈述
    verdict: Verdict = Verdict.WARN     # 判定结果
    severity: Severity = Severity.LOW   # 风险等级
    reason: str = ""                    # 判定理由
    search_query: str = ""              # 建议检索词
    evidence_urls: List[str] = field(default_factory=list)  # 核验参考链接
    original_context: str = ""          # 原始上下文


@dataclass
class FactCheckResult:
    """事实核查结果"""
    items: List[FactCheckItem] = field(default_factory=list)
    overall: Verdict = Verdict.PASS
    stats: Dict[str, int] = field(default_factory=dict)
    requires_decision: bool = False
    generated_at: str = ""
    checked_count: int = 0


class FactChecker:
    """事实核查器"""

    def __init__(self):
        self.result = None

        # 需要核查的模式
        self.fact_patterns = [
            # 数字和百分比
            (r'\d+(?:\.\d+)?%', "百分比数据"),
            (r'\d+\s*(?:万|亿|千|million|billion|trillion)', "数量级数据"),
            (r'(?:增长|下降|提升|降低)\s*(?:了\s*)?\d+', "变化数据"),
            # 时间相关
            (r'\d{4}\s*年\s*\d{1,2}\s*月', "具体日期"),
            (r'(?:最近|今年|去年|前年)', "时间引用"),
            # 研究引用
            (r'(?:研究|报告|调查)(?:表明|显示|指出|发现)', "研究引用"),
            (r'据(?:统计|调查|报告)', "数据引用"),
            # 绝对性陈述
            (r'(?:所有|全部|每个|任何)\s*\w+(?:都|均)', "绝对性陈述"),
            (r'(?:从未|总是|一定|必然)', "绝对性陈述"),
            # 比较和排名
            (r'(?:第一|最大|最小|最多|最少|领先)', "排名声明"),
            (r'(?:超过|突破|达到)\s*\d+', "阈值声明"),
        ]

        # 常见错误模式
        self.error_patterns = [
            # 未来日期
            (r'(202[7-9]|20[3-9]\d)\s*年', "未来日期", Severity.HIGH),
            # 不存在的版本号
            (r'(?:Claude|GPT|Gemini)\s*[4-9]\.\d', "可疑版本号", Severity.HIGH),
            (r'Claude\s*Opus\s*[5-9]', "可疑模型版本", Severity.HIGH),
            # 过于绝对
            (r'(?:永远|不可能|绝对|一定)\s*(?:不会|无法)', "过度绝对", Severity.MEDIUM),
            # 缺乏限定
            (r'(?:证明|证实|确定)\s*(?:了\s*)?(?:所有|一切)', "缺乏限定", Severity.MEDIUM),
        ]

    def check(self, content: str, findings: List[Dict] = None) -> FactCheckResult:
        """
        执行事实核查

        Args:
            content: 待核查内容
            findings: 研究发现列表（可选）

        Returns:
            FactCheckResult 对象
        """
        self.result = FactCheckResult(
            generated_at=datetime.now().isoformat()
        )

        # 1. 提取需要核查的陈述
        claims = self._extract_claims(content)

        # 2. 对每个陈述进行核查
        for claim in claims:
            item = self._check_claim(claim, findings)
            self.result.items.append(item)

        # 3. 计算总体判定
        self._compute_overall()

        return self.result

    def _extract_claims(self, content: str) -> List[str]:
        """提取需要核查的陈述"""
        claims = []
        sentences = re.split(r'[。！？\n]', content)

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or len(sentence) < 10:
                continue

            # 检查是否匹配任何需要核查的模式
            for pattern, desc in self.fact_patterns:
                if re.search(pattern, sentence):
                    if sentence not in claims:
                        claims.append(sentence)
                    break

        return claims[:20]  # 限制为前 20 条

    def _check_claim(self, claim: str, findings: List[Dict] = None) -> FactCheckItem:
        """核查单个陈述"""
        item = FactCheckItem(
            claim=claim,
            original_context=claim[:100]
        )

        # 1. 检查错误模式
        for pattern, desc, severity in self.error_patterns:
            match = re.search(pattern, claim)
            if match:
                item.verdict = Verdict.FAIL
                item.severity = severity
                item.reason = f"检测到{desc}：'{match.group()}'"
                item.search_query = self._generate_search_query(claim)
                return item

        # 2. 检查来源支持
        source_support = self._check_source_support(claim, findings or [])

        if source_support >= 2:
            item.verdict = Verdict.PASS
            item.severity = Severity.LOW
            item.reason = f"有 {source_support} 个来源支持"
        elif source_support == 1:
            item.verdict = Verdict.WARN
            item.severity = Severity.LOW
            item.reason = "仅有 1 个来源，建议交叉验证"
        else:
            # 3. 检查是否需要验证
            if self._needs_verification(claim):
                item.verdict = Verdict.WARN
                item.severity = Severity.MEDIUM
                item.reason = "缺少来源支持，需要验证"
                item.search_query = self._generate_search_query(claim)
            else:
                item.verdict = Verdict.PASS
                item.severity = Severity.LOW
                item.reason = "一般性陈述，无需特别验证"

        return item

    def _check_source_support(self, claim: str, findings: List[Dict]) -> int:
        """检查来源支持数量"""
        support_count = 0
        claim_keywords = set(re.findall(r'[\w]+', claim.lower()))

        for finding in findings:
            finding_claim = finding.get("claim", "").lower()
            finding_keywords = set(re.findall(r'[\w]+', finding_claim))

            # 计算关键词重叠度
            overlap = len(claim_keywords & finding_keywords)
            if overlap >= 3:  # 至少 3 个关键词重叠
                support_count += len(finding.get("sources", []))

        return support_count

    def _needs_verification(self, claim: str) -> bool:
        """判断是否需要验证"""
        verification_needed = [
            r'\d+%',
            r'\d+\s*(?:万|亿)',
            r'(?:第一|最大|领先)',
            r'(?:研究|报告).*(?:表明|显示)',
            r'(?:证明|证实|发现)',
        ]

        for pattern in verification_needed:
            if re.search(pattern, claim):
                return True

        return False

    def _generate_search_query(self, claim: str) -> str:
        """生成搜索查询"""
        # 提取关键词
        keywords = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', claim)

        # 优先保留数字和专有名词
        important = []
        for kw in keywords:
            if re.search(r'\d', kw) or len(kw) > 4:
                important.append(kw)

        # 取前 5 个重要关键词
        query_keywords = important[:5] if important else keywords[:5]

        return " ".join(query_keywords)

    def _compute_overall(self):
        """计算总体判定"""
        stats = {"pass": 0, "warn": 0, "fail": 0}

        for item in self.result.items:
            stats[item.verdict.value] += 1

        self.result.stats = stats
        self.result.checked_count = len(self.result.items)

        # 总体判定规则
        if stats["fail"] > 0:
            self.result.overall = Verdict.FAIL
        elif stats["warn"] > 0:
            self.result.overall = Verdict.WARN
        else:
            self.result.overall = Verdict.PASS

        # 是否需要人工决策
        high_risk_count = sum(
            1 for item in self.result.items
            if item.verdict == Verdict.FAIL or
               (item.verdict == Verdict.WARN and item.severity != Severity.LOW)
        )
        self.result.requires_decision = high_risk_count > 0

    def generate_report(self, result: FactCheckResult = None) -> str:
        """
        生成 Markdown 格式的事实核查报告

        Args:
            result: FactCheckResult 对象

        Returns:
            Markdown 格式的报告
        """
        if result is None:
            result = self.result

        if result is None:
            return "# 事实核查报告\n\n无核查结果"

        lines = [
            "# 事实核查报告",
            "",
            f"> 生成时间: {result.generated_at}",
            "",
            "---",
            "",
            "## 总体判定",
            "",
        ]

        # 判定图标
        verdict_icons = {
            Verdict.PASS: "✅",
            Verdict.WARN: "⚠️",
            Verdict.FAIL: "❌"
        }
        icon = verdict_icons.get(result.overall, "❓")
        lines.append(f"**{icon} {result.overall.value.upper()}**")
        lines.append("")

        # 统计
        lines.append("### 统计")
        lines.append("")
        lines.append(f"- **pass**: {result.stats.get('pass', 0)} 条")
        lines.append(f"- **warn**: {result.stats.get('warn', 0)} 条")
        lines.append(f"- **fail**: {result.stats.get('fail', 0)} 条")
        lines.append(f"- **核查总数**: {result.checked_count} 条")
        lines.append("")

        if result.requires_decision:
            lines.append("⚠️ **需要人工确认（软阻断）**")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## 详细核查",
            "",
        ])

        # 按严重程度分组
        fail_items = [i for i in result.items if i.verdict == Verdict.FAIL]
        warn_items = [i for i in result.items if i.verdict == Verdict.WARN]
        pass_items = [i for i in result.items if i.verdict == Verdict.PASS]

        # 失败项
        if fail_items:
            lines.append("### ❌ 失败项 (FAIL)")
            lines.append("")
            for i, item in enumerate(fail_items, 1):
                lines.append(f"#### {i}. {item.claim[:60]}{'...' if len(item.claim) > 60 else ''}")
                lines.append("")
                lines.append(f"- **判定**: fail ({item.severity.value})")
                lines.append(f"- **理由**: {item.reason}")
                if item.search_query:
                    lines.append(f"- **建议检索**: `{item.search_query}`")
                lines.append("")

        # 警告项
        if warn_items:
            lines.append("### ⚠️ 警告项 (WARN)")
            lines.append("")
            for i, item in enumerate(warn_items, 1):
                lines.append(f"{i}. **{item.claim[:50]}{'...' if len(item.claim) > 50 else ''}**")
                lines.append(f"   - 判定: warn ({item.severity.value})")
                lines.append(f"   - 理由: {item.reason}")
                lines.append("")

        # 通过项（摘要）
        if pass_items:
            lines.append("### ✅ 通过项 (PASS)")
            lines.append("")
            lines.append(f"共 {len(pass_items)} 条陈述通过核查")
            lines.append("")

        return "\n".join(lines)


def check_content_facts(content: str, findings: List[Dict] = None) -> FactCheckResult:
    """
    便捷函数：对内容进行事实核查

    Args:
        content: 待核查内容
        findings: 研究发现列表

    Returns:
        FactCheckResult 对象
    """
    checker = FactChecker()
    return checker.check(content, findings)


if __name__ == "__main__":
    # 测试代码
    print("Fact Checker 测试")
    print("-" * 50)

    test_content = """
    根据最新研究，2026年2月5日，Anthropic发布了Claude Opus 4.6模型。

    调查显示，50%的企业已经在使用AI Agent技术。

    研究表明，AI Agent可以提升100%的工作效率。

    Claude Code是目前最强大的AI编程助手。

    据统计，全球AI市场规模将在2030年达到1万亿美元。
    """

    test_findings = [
        {
            "claim": "Claude Code是Anthropic的AI编程助手",
            "sources": [{"url": "https://anthropic.com", "title": "Claude Code"}]
        }
    ]

    checker = FactChecker()
    result = checker.check(test_content, test_findings)

    print(checker.generate_report(result))
