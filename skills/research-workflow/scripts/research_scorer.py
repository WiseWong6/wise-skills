#!/usr/bin/env python3
"""
Research 置信度计算器

职责: 计算研究发现、趋势的置信度和时效性

移植自 write-agent/src/utils/research-scorer.ts

设计原则:
- 数据驱动,可配置
- 清晰的评分标准
- 可测试
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Literal
from dataclasses import dataclass, field
from enum import Enum


class ConfidenceType(str, Enum):
    """置信度类型"""
    FACT = "FACT"           # 有明确数据或多个来源确认的事实
    BELIEF = "BELIEF"       # 行业共识或专家观点
    CONTRADICTION = "CONTRADICTION"  # 存在矛盾
    ASSUMPTION = "ASSUMPTION"  # 基于有限信息的合理推测


class FreshnessStatus(str, Enum):
    """时效性状态"""
    CURRENT = "current"         # 当前（时效窗口内）
    NEEDS_UPDATE = "needs_update"  # 需要更新
    OUTDATED = "outdated"       # 过时


@dataclass
class Source:
    """信息来源"""
    url: str
    title: str
    date: Optional[datetime] = None
    domain: str = ""
    excerpt: str = ""
    confidence: str = "medium"  # high, medium, low


@dataclass
class Score:
    """单项评分"""
    dimension: str
    value: float
    reason: str


@dataclass
class Finding:
    """研究发现"""
    claim: str
    confidence_type: ConfidenceType = ConfidenceType.ASSUMPTION
    confidence_score: float = 0.0  # 0.0-1.0
    sources: List[Source] = field(default_factory=list)
    cross_verified: bool = False
    freshness_status: FreshnessStatus = FreshnessStatus.NEEDS_UPDATE
    scores: List[Score] = field(default_factory=list)
    source_type: str = "unknown"


@dataclass
class Trend:
    """趋势信号"""
    topic: str
    signal_strength: Literal["high", "medium", "low"] = "low"
    growth_rate: str = ""  # "+65%"
    time_window: str = ""
    confidence_score: float = 0.0


class RecencyWindow(str, Enum):
    """时效性窗口类型"""
    AI = "ai"           # AI 领域变化快，需要 60 天内的信息
    VOLATILE = "volatile"  # 快速变化领域需要 30 天内的信息
    DEFAULT = "default"   # 默认接受一年内的信息


# 时效性窗口配置 (天数)
RECENCY_WINDOWS: Dict[RecencyWindow, int] = {
    RecencyWindow.AI: 60,
    RecencyWindow.VOLATILE: 30,
    RecencyWindow.DEFAULT: 365
}

# AI 相关关键词
AI_KEYWORDS = [
    "AI", "人工智能", "机器学习", "深度学习", "LLM", "大模型",
    "GPT", "Claude", "Agent", "LangChain", "RAG", "Transformer",
    "Neural Network", "神经网络", "NLP", "计算机视觉", "AGI"
]

# 快速变化领域关键词
VOLATILE_KEYWORDS = [
    "区块链", "Web3", "crypto", "加密货币",
    "元宇宙", "VR", "AR", "XR"
]

# 权威域名列表
AUTHORITATIVE_DOMAINS = [
    "edu", "gov", "org",
    "nature.com", "science.org", "ieee.org",
    "arxiv.org", "scholar.google.com",
    "acm.org", "springer.com", "wiley.com",
    "researchgate.net", "semanticscholar.org"
]


def calculate_confidence(finding: Finding) -> float:
    """
    计算信息置信度

    Args:
        finding: 研究发现

    Returns:
        置信度评分 (0.0-1.0)
    """
    score = 0.0

    # 基础分: 来源数量 (30%)
    source_count = len(finding.sources)
    if source_count >= 3:
        score += 0.3
    elif source_count >= 2:
        score += 0.25
    elif source_count >= 1:
        score += 0.1

    # 交叉验证加分 (30%)
    if finding.cross_verified:
        score += 0.3

    # 来源质量加分 (20%)
    domain_quality = calculate_domain_quality(finding.sources)
    score += domain_quality * 0.2

    # 时效性加分 (20%)
    freshness = calculate_freshness(finding)
    score += freshness * 0.2

    return min(score, 1.0)


def calculate_freshness(finding: Finding) -> float:
    """
    计算时效性评分

    Args:
        finding: 研究发现

    Returns:
        时效性评分 (0.0-1.0)
    """
    now = datetime.now()
    sources_with_dates = [s for s in finding.sources if s.date]

    if not sources_with_dates:
        return 0.3  # 无日期信息，给较低分

    # 计算平均天数
    total_days = 0
    for source in sources_with_dates:
        if source.date:
            delta = now - source.date
            total_days += delta.days

    avg_days = total_days / len(sources_with_dates)

    # 根据主题确定时效性窗口
    window = determine_recency_window(finding.claim)
    max_days = RECENCY_WINDOWS[window]

    # 计算评分 (越新越高)
    if avg_days <= max_days * 0.25:
        return 1.0
    elif avg_days <= max_days * 0.5:
        return 0.8
    elif avg_days <= max_days:
        return 0.6
    elif avg_days <= max_days * 1.5:
        return 0.4
    elif avg_days <= max_days * 2:
        return 0.2
    else:
        return 0.1


def determine_recency_window(topic: str) -> RecencyWindow:
    """确定时效性窗口类型"""
    lower = topic.lower()

    for keyword in AI_KEYWORDS:
        if keyword.lower() in lower:
            return RecencyWindow.AI

    for keyword in VOLATILE_KEYWORDS:
        if keyword.lower() in lower:
            return RecencyWindow.VOLATILE

    return RecencyWindow.DEFAULT


def calculate_domain_quality(sources: List[Source]) -> float:
    """计算域名质量"""
    if not sources:
        return 0.0

    quality_score = 0.0
    for source in sources:
        for authDomain in AUTHORITATIVE_DOMAINS:
            if authDomain in source.domain:
                quality_score += 0.5
                break

    return min(quality_score / len(sources), 1.0)


def calculate_signal_strength(trend: Trend) -> Literal["high", "medium", "low"]:
    """
    计算趋势信号强度

    Args:
        trend: 趋势数据

    Returns:
        信号强度
    """
    # 基于增长率和置信度判断
    growth_match = re.match(r'([+\-]?\d+)', trend.growth_rate)
    if not growth_match:
        return "low"

    try:
        growth = int(growth_match.group(1))
    except ValueError:
        return "low"

    confidence = trend.confidence_score

    if confidence >= 0.8 and abs(growth) >= 50:
        return "high"
    elif confidence >= 0.6 and abs(growth) >= 20:
        return "medium"
    else:
        return "low"


def needs_cross_verification(claim: str) -> bool:
    """
    判断信息是否需要交叉验证

    Args:
        claim: 声明内容

    Returns:
        是否需要交叉验证
    """
    # 数字、百分比、具体数据需要验证
    needs_verification_patterns = [
        r'\d+%',
        r'\d+\s*(万|亿|千|million|billion)',
        r'增长.*\d+',
        r'下降.*\d+',
        r'研究表明',
        r'数据显示',
        r'统计显示',
        r'报告指出',
    ]

    return any(re.search(pattern, claim) for pattern in needs_verification_patterns)


def detect_contradictions(findings: List[Finding]) -> bool:
    """
    检测信息矛盾

    Args:
        findings: 多个研究发现

    Returns:
        是否存在矛盾
    """
    # 简化版: 检查相反的关键词
    contradict_pairs = [
        ("增长", "下降"),
        ("成功", "失败"),
        ("有效", "无效"),
        ("支持", "反对"),
        ("上升", "下跌"),
        ("增加", "减少"),
    ]

    claims = [f.claim.lower() for f in findings]

    for word1, word2 in contradict_pairs:
        has_word1 = any(word1 in c for c in claims)
        has_word2 = any(word2 in c for c in claims)
        if has_word1 and has_word2:
            return True

    return False


def infer_confidence_type(finding: Finding) -> ConfidenceType:
    """
    推断置信度类型

    Args:
        finding: 研究发现

    Returns:
        置信度类型
    """
    if detect_contradictions([finding]):
        return ConfidenceType.CONTRADICTION

    if len(finding.sources) == 0:
        return ConfidenceType.ASSUMPTION

    if finding.cross_verified and finding.confidence_score >= 0.8:
        return ConfidenceType.FACT

    if len(finding.sources) >= 1:
        return ConfidenceType.BELIEF

    return ConfidenceType.ASSUMPTION


def score_finding(
    finding: Finding,
    dimensions: List[str] = None
) -> List[Score]:
    """
    统一评分流水线

    Args:
        finding: 研究发现
        dimensions: 评分维度列表

    Returns:
        多维度评分数组
    """
    if dimensions is None:
        dimensions = ["innovation", "practicality", "impact", "freshness", "confidence"]

    scores = []

    for dimension in dimensions:
        score = _score_by_dimension(finding, dimension)
        scores.append(score)

    return scores


def _score_by_dimension(finding: Finding, dimension: str) -> Score:
    """按维度评分"""
    if dimension == "innovation":
        return _score_innovation(finding)
    elif dimension == "practicality":
        return _score_practicality(finding)
    elif dimension == "impact":
        return _score_impact(finding)
    elif dimension == "freshness":
        freshness = calculate_freshness(finding)
        return Score(
            dimension="freshness",
            value=freshness,
            reason=f"时效性评分：{freshness * 100:.0f}%"
        )
    elif dimension == "confidence":
        confidence = calculate_confidence(finding)
        return Score(
            dimension="confidence",
            value=confidence,
            reason=f"置信度评分：{confidence * 100:.0f}%"
        )
    else:
        return Score(dimension=dimension, value=0.5, reason="未知维度")


def _score_innovation(finding: Finding) -> Score:
    """创新性评分"""
    innovation_keywords = [
        "新", "首次", "突破", "创新", "革命性", "颠覆",
        "novel", "breakthrough", "revolutionary", "first", "pioneering",
        "groundbreaking", "unprecedented", "开创", "首创"
    ]

    has_innovation = any(
        kw.lower() in finding.claim.lower()
        for kw in innovation_keywords
    )

    score = 0.8 if has_innovation else 0.3

    return Score(
        dimension="innovation",
        value=score,
        reason="包含创新性关键词" if has_innovation else "常规信息"
    )


def _score_practicality(finding: Finding) -> Score:
    """实用性评分"""
    practicality_keywords = [
        "应用", "落地", "实践", "解决", "效果", "工具", "方案",
        "implementation", "practical", "solve", "implement", "tool",
        "solution", "部署", "使用", "方法"
    ]

    has_practicality = any(
        kw.lower() in finding.claim.lower()
        for kw in practicality_keywords
    )

    score = 0.7 if has_practicality else 0.4

    return Score(
        dimension="practicality",
        value=score,
        reason="有实际应用价值" if has_practicality else "理论性内容"
    )


def _score_impact(finding: Finding) -> Score:
    """影响力评分"""
    domain_quality = calculate_domain_quality(finding.sources)
    cross_verified = finding.cross_verified

    score = domain_quality * 0.5
    if cross_verified:
        score += 0.3

    reason = f"来源质量：{domain_quality * 100:.0f}%"
    if cross_verified:
        reason += " + 交叉验证"

    return Score(
        dimension="impact",
        value=min(score, 1.0),
        reason=reason
    )


def format_confidence_label(finding: Finding) -> str:
    """
    格式化置信度标签

    Args:
        finding: 研究发现

    Returns:
        格式化的置信度标签，如 "[FACT | conf: 0.92]"
    """
    conf_type = finding.confidence_type.value
    conf_score = finding.confidence_score

    return f"[{conf_type} | conf: {conf_score:.2f}]"


def format_source_citation(source: Source) -> str:
    """
    格式化来源引用

    Args:
        source: 信息来源

    Returns:
        格式化的引用，如 "→ [Business Insider](https://...) — (Hugh Langley, 2026-02-26)"
    """
    title = source.title or "N/A"
    url = source.url or ""
    date_str = source.date.strftime("%Y-%m-%d") if source.date else "未知日期"

    return f"→ [{title}]({url}) — ({date_str})"


def enrich_finding_with_scores(finding: Finding) -> Finding:
    """
    为研究发现添加评分

    Args:
        finding: 研究发现

    Returns:
        添加了评分的研究发现
    """
    # 计算置信度
    finding.confidence_score = calculate_confidence(finding)

    # 推断置信度类型
    finding.confidence_type = infer_confidence_type(finding)

    # 计算时效性
    freshness = calculate_freshness(finding)
    if freshness >= 0.6:
        finding.freshness_status = FreshnessStatus.CURRENT
    elif freshness >= 0.3:
        finding.freshness_status = FreshnessStatus.NEEDS_UPDATE
    else:
        finding.freshness_status = FreshnessStatus.OUTDATED

    # 计算多维度评分
    finding.scores = score_finding(finding)

    return finding


# ========== 批量处理函数 ==========

def process_findings(findings: List[Dict[str, Any]]) -> List[Finding]:
    """
    处理研究发现列表

    Args:
        findings: 原始研究发现字典列表

    Returns:
        处理后的 Finding 对象列表
    """
    processed = []

    for f in findings:
        # 解析来源
        sources = []
        for s in f.get("sources", []):
            source = Source(
                url=s.get("url", ""),
                title=s.get("title", ""),
                domain=s.get("domain", ""),
                excerpt=s.get("excerpt", ""),
                confidence=s.get("confidence", "medium")
            )
            # 解析日期
            if s.get("date"):
                try:
                    source.date = datetime.fromisoformat(s["date"].replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass
            sources.append(source)

        # 创建 Finding
        finding = Finding(
            claim=f.get("claim", ""),
            sources=sources,
            cross_verified=f.get("cross_verified", False),
            source_type=f.get("source_type", "unknown")
        )

        # 计算评分
        finding = enrich_finding_with_scores(finding)
        processed.append(finding)

    return processed


def generate_confidence_report(findings: List[Finding]) -> str:
    """
    生成置信度报告

    Args:
        findings: 研究发现列表

    Returns:
        Markdown 格式的置信度报告
    """
    lines = ["## 置信度报告", ""]

    # 统计
    type_counts = {t.value: 0 for t in ConfidenceType}
    for f in findings:
        type_counts[f.confidence_type.value] += 1

    lines.append("### 置信度分布")
    lines.append("")
    for t, count in type_counts.items():
        if count > 0:
            lines.append(f"- **{t}**: {count} 条")
    lines.append("")

    # 详细列表
    lines.append("### 详细评分")
    lines.append("")

    for i, f in enumerate(findings, 1):
        label = format_confidence_label(f)
        lines.append(f"{i}. {label} {f.claim[:60]}{'...' if len(f.claim) > 60 else ''}")

        if f.sources:
            for s in f.sources[:2]:  # 只显示前两个来源
                lines.append(f"   {format_source_citation(s)}")

        # 显示评分
        if f.scores:
            scores_str = " | ".join(f"{s.dimension}: {s.value:.0%}" for s in f.scores[:3])
            lines.append(f"   _{scores_str}_")

        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    # 测试代码
    print("Research Scorer 测试")
    print("-" * 50)

    # 创建测试数据
    test_sources = [
        Source(
            url="https://example.com/article1",
            title="AI Agent 发展报告",
            domain="arxiv.org",
            date=datetime.now() - timedelta(days=30),
            confidence="high"
        ),
        Source(
            url="https://example.com/article2",
            title="2026 AI 趋势分析",
            domain="nature.com",
            date=datetime.now() - timedelta(days=15),
            confidence="high"
        )
    ]

    test_finding = Finding(
        claim="谷歌 50% 的代码已由 AI 生成并人工审核",
        sources=test_sources,
        cross_verified=True,
        source_type="news"
    )

    # 计算评分
    test_finding = enrich_finding_with_scores(test_finding)

    print(f"Claim: {test_finding.claim}")
    print(f"Confidence: {test_finding.confidence_score:.2f}")
    print(f"Type: {test_finding.confidence_type.value}")
    print(f"Freshness: {test_finding.freshness_status.value}")
    print(f"Label: {format_confidence_label(test_finding)}")
    print()

    # 显示评分
    print("Scores:")
    for s in test_finding.scores:
        print(f"  {s.dimension}: {s.value:.2f} - {s.reason}")
