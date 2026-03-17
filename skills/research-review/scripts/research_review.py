#!/usr/bin/env python3
"""
调研报告审计脚本 (Research Review Script)

对 research-workflow 生成的调研报告进行完整性、质量、逻辑检查。
支持联网核查，评审结果追加到原文件。
支持成品文章事实核查模式 (--article)

使用方式:
    # 调研报告审计（原有功能）
    python3 research_review.py /path/to/00_research.md

    # 成品文章事实核查（新增功能）
    python3 research_review.py /path/to/article.md --article
"""

import argparse
import json
import re
import sys
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple


# ========== 数据结构定义 ==========

@dataclass
class Fact:
    """事实声明"""
    id: int
    text: str
    fact_type: str  # financial, temporal, entity, prediction, other
    context: str = ""  # 原文上下文

@dataclass
class VerificationResult:
    """事实核查结果"""
    fact: Fact
    status: str  # verified / disputed / unverified / error
    correction: str = ""  # 修正内容（如有）
    sources: List[Dict[str, str]] = field(default_factory=list)
    data_timestamp: str = ""  # 数据来源时间
    notes: str = ""  # 核查备注


# ========== 常量定义 ==========

# 官方域名列表（用于验证 FACT/BELIEF 标签）
OFFICIAL_DOMAINS = [
    "anthropic.com",
    "openai.com",
    "arxiv.org",
    "developer.mozilla.org",
    "docs.python.org",
    "redis.io",
    "postgresql.org",
    "mongodb.com",
    "nginx.org",
    "kubernetes.io",
    "docker.com",
]

# 必需的章节标题
REQUIRED_SECTIONS = [
    "## 核心发现",
    "## 来源统计",
]

# 置信度类型定义
CONFIDENCE_TYPES = {
    "FACT": {"min_sources": 2, "require_official": False, "description": "多源验证的事实"},
    "BELIEF": {"min_sources": 1, "require_official": True, "description": "单一权威来源"},
    "ASSUMPTION": {"min_sources": 0, "require_official": False, "description": "基于线索的推测"},
}


# ========== 辅助函数 ==========

def extract_domain(url: str) -> Optional[str]:
    """从 URL 中提取域名"""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.lower().replace("www.", "")
    except Exception:
        return None


def is_official_domain(url: str) -> bool:
    """检查 URL 是否属于官方域名"""
    domain = extract_domain(url)
    if not domain:
        return False
    return any(domain == d or domain.endswith(f".{d}") for d in OFFICIAL_DOMAINS)


def parse_confidence_tag(text: str) -> Optional[Tuple[str, float]]:
    """
    解析置信度标签

    格式: [FACT | BELIEF | ASSUMPTION, conf: 0.xx]
    返回: (类型, 置信度分数)
    """
    match = re.search(r'\[(FACT|BELIEF|ASSUMPTION|CONTRADICTION)\s*,?\s*conf:\s*([\d.]+)\]', text)
    if match:
        conf_type = match.group(1)
        conf_score = float(match.group(2))
        return conf_type, conf_score
    return None


# ========== 检查函数 ==========

def check_completeness(content: str, report_path: Path) -> Dict[str, Any]:
    """
    完整性检查

    检查项:
    - 核心论点是否覆盖
    - 反面观点是否提及
    - 数据来源是否明确
    """
    issues = []

    # 检查必需章节
    for section in REQUIRED_SECTIONS:
        if section not in content:
            issues.append(f"缺少必需章节: {section}")

    # 检查核心发现
    if "## 核心发现" in content:
        # 提取核心发现部分
        match = re.search(r'## 核心发现\s*(.*?)(?=\n##|\Z)', content, re.DOTALL)
        if match:
            findings = match.group(1)
            # 统计发现数量
            finding_count = len(re.findall(r'^[ \t]*[-*]\s+', findings, re.MULTILINE))
            if finding_count == 0:
                issues.append("核心发现部分没有实际的发现项")
        else:
            issues.append("无法解析核心发现部分")

    # 检查反面观点
    if "反面" not in content and "反对" not in content and "争议" not in content:
        issues.append("缺少反面观点或争议说明")

    # 检查来源引用
    url_count = len(re.findall(r'https?://[^\s\)]+', content))
    if url_count == 0:
        issues.append("没有任何来源 URL")
    elif url_count < 3:
        issues.append(f"来源 URL 过少（仅有 {url_count} 个）")

    # 计算完整性得分
    score = max(0, 10 - len(issues))
    status = "PASS" if score >= 8 else "WARN" if score >= 5 else "FAIL"

    return {
        "status": status,
        "score": score,
        "issues": issues,
        "summary": f"发现 {len(issues)} 个问题"
    }


def check_coverage_quality(content: str, report_path: Path) -> Dict[str, Any]:
    """
    覆盖质量评估

    检查项:
    - 来源分布（官方文档、权威来源、普通来源）
    - 时效性（最新发布时间）
    - 交叉验证（同一事实是否有多个来源）
    """
    # 提取所有 URL
    urls = re.findall(r'https?://[^\s\)]+', content)

    # 分类来源
    official_count = 0
    high_count = 0
    medium_count = 0

    for url in urls:
        if is_official_domain(url):
            official_count += 1
        elif any(d in url for d in ["github.com", "medium.com", "stackoverflow.com"]):
            high_count += 1
        else:
            medium_count += 1

    total = len(urls)
    if total == 0:
        return {
            "status": "FAIL",
            "score": 0,
            "summary": "没有任何来源",
            "details": {"total": 0, "official": 0, "high": 0, "medium": 0}
        }

    # 计算得分
    official_ratio = official_count / total
    high_ratio = high_count / total

    # 官方来源占 30% 以上得高分
    score = 5.0
    if official_ratio >= 0.3:
        score += 3.0
    elif official_ratio >= 0.1:
        score += 1.5

    # 高质量来源占 30% 以上加分
    if high_ratio >= 0.3:
        score += 2.0
    elif high_ratio >= 0.1:
        score += 1.0

    score = min(score, 10.0)

    status = "PASS" if score >= 7 else "WARN" if score >= 5 else "FAIL"

    return {
        "status": status,
        "score": round(score, 1),
        "summary": f"共 {total} 个来源（官方: {official_count}, 高质量: {high_count}）",
        "details": {
            "total": total,
            "official": official_count,
            "high": high_count,
            "medium": medium_count
        }
    }


def check_confidence_labels(content: str, report_path: Path) -> Dict[str, Any]:
    """
    置信度标签验证

    检查项:
    - FACT 标签是否有 ≥2 个来源
    - BELIEF 标签是否有官方来源
    - 置信度分数是否与类型匹配
    """
    # 查找所有置信度标签
    lines = content.splitlines()
    issues = []
    valid_count = 0
    total_count = 0

    for i, line in enumerate(lines, 1):
        result = parse_confidence_tag(line)
        if not result:
            continue

        total_count += 1
        conf_type, conf_score = result

        # 检查类型定义
        if conf_type not in CONFIDENCE_TYPES:
            issues.append(f"行 {i}: 未知置信度类型 '{conf_type}'")
            continue

        type_def = CONFIDENCE_TYPES[conf_type]

        # 检查置信度分数范围
        if conf_type == "FACT" and conf_score < 0.9:
            issues.append(f"行 {i}: FACT 标签的置信度分数应 ≥ 0.9，当前 {conf_score}")
        elif conf_type == "BELIEF" and (conf_score < 0.6 or conf_score > 0.8):
            issues.append(f"行 {i}: BELIEF 标签的置信度分数应在 0.6-0.8，当前 {conf_score}")
        elif conf_type == "ASSUMPTION" and conf_score > 0.5:
            issues.append(f"行 {i}: ASSUMPTION 标签的置信度分数应 ≤ 0.5，当前 {conf_score}")

        # 检查来源数量（向前查找附近几行的 URL）
        context_lines = 5
        context_start = max(0, i - context_lines)
        context_end = min(len(lines), i + context_lines)
        context = "\n".join(lines[context_start:context_end])

        urls_in_context = re.findall(r'https?://[^\s\)]+', context)

        # FACT 需要 ≥2 个来源
        if conf_type == "FACT" and len(urls_in_context) < type_def["min_sources"]:
            issues.append(f"行 {i}: FACT 标签需要 ≥2 个来源，上下文仅找到 {len(urls_in_context)} 个")

        # BELIEF 需要官方来源
        if conf_type == "BELIEF" and type_def["require_official"]:
            has_official = any(is_official_domain(url) for url in urls_in_context)
            if not has_official:
                issues.append(f"行 {i}: BELIEF 标签需要至少 1 个官方来源，上下文未找到")

        if not any(f"行 {i}:" in issue for issue in issues):
            valid_count += 1

    # 计算得分
    if total_count == 0:
        return {
            "status": "WARN",
            "score": 5.0,
            "summary": "没有找到置信度标签",
            "issues": ["建议为所有发现添加置信度标签"],
            "total_count": 0,
            "valid_count": 0
        }

    score = (valid_count / total_count) * 10
    status = "PASS" if score >= 8 else "WARN" if score >= 6 else "FAIL"

    return {
        "status": status,
        "score": round(score, 1),
        "summary": f"{valid_count}/{total_count} 个标签有效",
        "issues": issues,
        "total_count": total_count,
        "valid_count": valid_count
    }


def generate_review_report(
    report_path: Path,
    completeness: Dict[str, Any],
    coverage: Dict[str, Any],
    confidence: Dict[str, Any]
) -> str:
    """生成评审报告"""
    overall_score = (completeness["score"] + coverage["score"] + confidence["score"]) / 3

    # 确定总体状态
    if overall_score >= 8:
        overall_status = "✅ PASS"
    elif overall_score >= 6:
        overall_status = "⚠️ WARN"
    else:
        overall_status = "❌ FAIL"

    report = f"""

---

## 调研评审报告

### 评审元数据
- **评审时间**: {datetime.now().isoformat()}
- **评审状态**: {overall_status}
- **评审文件**: {report_path.name}

### 评审摘要
- **完整性**: {completeness['score']}/10 - {completeness['status']}
- **覆盖质量**: {coverage['score']}/10 - {coverage['status']}
- **置信度标签**: {confidence['score']}/10 - {confidence['status']}
- **综合评分**: {overall_score:.1f}/10

### 1. 完整性检查
**状态**: {completeness['status']} ({completeness['score']}/10)
**摘要**: {completeness['summary']}

"""

    if completeness["issues"]:
        report += "**问题列表**:\n"
        for issue in completeness["issues"]:
            report += f"- {issue}\n"
    else:
        report += "✓ 完整性检查通过\n"

    report += f"""

### 2. 覆盖质量评估
**状态**: {coverage['status']} ({coverage['score']}/10)
**摘要**: {coverage['summary']}

**来源分布**:
| 类型 | 数量 | 占比 |
|------|------|------|
| official | {coverage['details']['official']} | {coverage['details']['official']/max(coverage['details']['total'],1)*100:.0f}% |
| high | {coverage['details']['high']} | {coverage['details']['high']/max(coverage['details']['total'],1)*100:.0f}% |
| medium | {coverage['details']['medium']} | {coverage['details']['medium']/max(coverage['details']['total'],1)*100:.0f}% |

### 3. 置信度标签验证
**状态**: {confidence['status']} ({confidence['score']}/10)
**摘要**: {confidence['summary']}

"""

    if confidence["issues"]:
        report += "**问题列表**:\n"
        for issue in confidence["issues"]:
            report += f"- {issue}\n"
    else:
        report += "✓ 置信度标签验证通过\n"

    report += "\n### 4. 改进建议\n"

    suggestions = []

    if completeness["score"] < 8:
        suggestions.append("- [高优先级] 补充缺失的必需章节")

    if coverage["details"]["total"] < 5:
        suggestions.append("- [中优先级] 增加更多来源引用")

    if coverage["details"]["official"] == 0:
        suggestions.append("- [中优先级] 添加官方文档或权威来源")

    if confidence["total_count"] > 0 and confidence["valid_count"] < confidence["total_count"]:
        suggestions.append("- [中优先级] 修正置信度标签问题")

    if not suggestions:
        suggestions.append("- [低优先级] 考虑增加反面观点讨论")
        suggestions.append("- [低优先级] 添加更多交叉验证")

    for suggestion in suggestions:
        report += f"{suggestion}\n"

    report += "\n---\n"

    return report


# ========== 文章事实核查类 ==========

class ArticleFactChecker:
    """成品文章事实核查器"""

    FACT_TYPE_LABELS = {
        "financial": "财务数据",
        "temporal": "时间/日期",
        "entity": "人物/公司",
        "prediction": "预测/推测",
        "other": "其他"
    }

    STATUS_LABELS = {
        "verified": "✅ 准确",
        "disputed": "❌ 错误",
        "unverified": "⚠️ 需核实",
        "error": "❓ 核查失败"
    }

    def __init__(self, content: str, article_path: Path):
        self.content = content
        self.article_path = article_path
        self.facts: List[Fact] = []
        self.results: List[VerificationResult] = []

    def extract_facts(self) -> List[Fact]:
        """
        使用启发式规则提取关键事实声明

        提取策略：
        1. 数字+单位模式（财务数据、百分比）
        2. 日期/年份模式
        3. 公司/人物声明
        4. 预测性词汇
        """
        facts = []
        lines = self.content.splitlines()
        fact_id = 0

        # 跳过 Markdown 元数据（Frontmatter）
        content_start = 0
        if lines and lines[0].strip() == "---":
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    content_start = i + 1
                    break

        for i, line in enumerate(lines[content_start:], content_start):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("["):
                continue

            # 提取财务数据（数字+货币单位/百分比）
            financial_patterns = [
                r'(\d+\.?\d*)\s*(亿美元|亿美元|亿元|万亿元|%)',
                r'估值约?\s*(\d+\.?\d*)\s*(亿美元|亿美元|亿元)',
                r'营收\s*(\d+\.?\d*)\s*(亿美元|亿美元|亿元)',
                r'增长\s*(\d+\.?\d*)%',
            ]
            for pattern in financial_patterns:
                matches = re.finditer(pattern, line)
                for match in matches:
                    fact_id += 1
                    facts.append(Fact(
                        id=fact_id,
                        text=match.group(0),
                        fact_type="financial",
                        context=line[:200]
                    ))

            # 提取时间/日期
            temporal_patterns = [
                r'(20\d{2})\s*年\s*(\d{1,2})\s*月',
                r'(20\d{2})\s*年',
                r'(20\d{2})[-/](\d{1,2})[-/](\d{1,2})',
                r'截至\s*(20\d{2})',
            ]
            for pattern in temporal_patterns:
                matches = re.finditer(pattern, line)
                for match in matches:
                    # 避免重复
                    text = match.group(0)
                    if not any(f.text == text for f in facts):
                        fact_id += 1
                        facts.append(Fact(
                            id=fact_id,
                            text=text,
                            fact_type="temporal",
                            context=line[:200]
                        ))

            # 提取人物/公司声明
            entity_patterns = [
                r'(马斯克|Elon Musk|SpaceX|特斯拉|Tesla|OpenAI|Anthropic)[^。，]{0,50}(表示|称|宣布|透露)',
                r'(CEO|创始人|董事长)[^。，]{0,30}(表示|称|宣布)',
            ]
            for pattern in entity_patterns:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    text = match.group(0)
                    if not any(f.text == text for f in facts):
                        fact_id += 1
                        facts.append(Fact(
                            id=fact_id,
                            text=text,
                            fact_type="entity",
                            context=line[:200]
                        ))

            # 提取预测/推测
            prediction_keywords = ["预计", "预测", "将", "可能", "有望", "或将在"]
            for keyword in prediction_keywords:
                if keyword in line and len(line) > 20:
                    # 提取包含关键词的短语
                    idx = line.find(keyword)
                    phrase = line[max(0, idx-10):min(len(line), idx+50)]
                    if not any(f.text == phrase for f in facts):
                        fact_id += 1
                        facts.append(Fact(
                            id=fact_id,
                            text=phrase,
                            fact_type="prediction",
                            context=line[:200]
                        ))
                    break  # 每行只取一个预测

        self.facts = facts
        return facts

    def preview_facts(self) -> str:
        """生成事实列表预览"""
        if not self.facts:
            return "未提取到事实声明。"

        preview = f"\n📋 共提取到 {len(self.facts)} 个事实声明：\n\n"
        preview += "| ID | 类型 | 声明内容 | 上下文 |\n"
        preview += "|----|------|---------|--------|\n"

        for fact in self.facts:
            type_label = self.FACT_TYPE_LABELS.get(fact.fact_type, fact.fact_type)
            text_short = fact.text[:40] + "..." if len(fact.text) > 40 else fact.text
            context_short = fact.context[:50] + "..." if len(fact.context) > 50 else fact.context
            preview += f"| {fact.id} | {type_label} | {text_short} | {context_short} |\n"

        preview += "\n是否继续核查这些事实？(y/n): "
        return preview

    def verify_fact(self, fact: Fact) -> VerificationResult:
        """
        联网验证单个事实

        使用 WebSearch MCP 工具进行搜索验证
        """
        # 构建搜索查询（包含当前年份确保时效性）
        current_year = datetime.now().year
        query = f"{fact.text} {current_year} {current_year - 1}"

        try:
            # 调用 WebSearch MCP 工具
            # 注意：这里通过 subprocess 调用 claude 命令使用 WebSearch
            result = self._call_web_search(query)

            if not result:
                return VerificationResult(
                    fact=fact,
                    status="error",
                    notes="搜索未返回结果"
                )

            # 分析搜索结果
            return self._analyze_search_result(fact, result)

        except Exception as e:
            return VerificationResult(
                fact=fact,
                status="error",
                notes=f"核查过程出错: {str(e)}"
            )

    def _call_web_search(self, query: str) -> Optional[str]:
        """调用 WebSearch 工具"""
        try:
            # 使用 claude mcp web-search 命令
            cmd = [
                "claude", "mcp", "call", "web-search",
                "--input", json.dumps({"query": query})
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return result.stdout
            return None
        except Exception:
            return None

    def _analyze_search_result(self, fact: Fact, search_result: str) -> VerificationResult:
        """分析搜索结果，判断事实准确性"""
        # 简单启发式分析
        result_lower = search_result.lower()
        fact_lower = fact.text.lower()

        # 提取关键数字进行比较
        fact_numbers = re.findall(r'\d+\.?\d*', fact_lower)

        # 检查是否有矛盾信息
        contradiction_indicators = ["错误", "辟谣", "不实", "假的", "incorrect", "false"]
        has_contradiction = any(ind in result_lower for ind in contradiction_indicators)

        # 检查是否有确认信息
        confirmation_indicators = ["确认", "报道", "数据显示", "according to", "reported"]
        has_confirmation = any(ind in result_lower for ind in confirmation_indicators)

        # 提取数据来源时间
        data_timestamp = ""
        year_match = re.search(r'(20\d{2})\s*年', search_result)
        if year_match:
            data_timestamp = year_match.group(1)

        # 提取来源链接
        sources = []
        url_matches = re.findall(r'https?://[^\s\)]+', search_result)
        for url in url_matches[:3]:  # 最多取3个来源
            sources.append({"url": url, "title": "搜索结果来源"})

        # 判断状态
        if has_contradiction:
            status = "disputed"
            correction = "发现矛盾信息，建议核实"
        elif has_confirmation and fact_numbers:
            # 检查数字是否匹配
            result_numbers = re.findall(r'\d+\.?\d*', result_lower[:2000])
            if any(fn in result_numbers for fn in fact_numbers):
                status = "verified"
                correction = ""
            else:
                status = "unverified"
                correction = "数字信息需进一步核实"
        else:
            status = "unverified"
            correction = ""

        return VerificationResult(
            fact=fact,
            status=status,
            correction=correction,
            sources=sources,
            data_timestamp=data_timestamp,
            notes=f"搜索返回 {len(search_result)} 字符"
        )

    def verify_all(self) -> List[VerificationResult]:
        """核查所有事实"""
        print(f"\n🔍 开始核查 {len(self.facts)} 个事实声明...")

        for i, fact in enumerate(self.facts, 1):
            print(f"  [{i}/{len(self.facts)}] 核查: {fact.text[:50]}...")
            result = self.verify_fact(fact)
            self.results.append(result)

        print(f"✅ 核查完成")
        return self.results

    def generate_report(self) -> str:
        """生成事实核查报告"""
        if not self.results:
            return ""

        # 统计
        verified = sum(1 for r in self.results if r.status == "verified")
        disputed = sum(1 for r in self.results if r.status == "disputed")
        unverified = sum(1 for r in self.results if r.status == "unverified")
        errors = sum(1 for r in self.results if r.status == "error")

        report = f"""
---

## 事实核查报告

### 核查摘要
- **核查时间**: {datetime.now().isoformat()}
- **总声明数**: {len(self.results)}
- **准确**: {verified} | **错误**: {disputed} | **需核实**: {unverified} | **核查失败**: {errors}

### 核查明细

| 原文声明 | 类型 | 结果 | 修正内容 | 数据来源时间 |
|---------|------|------|---------|-------------|
"""

        for result in self.results:
            fact = result.fact
            type_label = self.FACT_TYPE_LABELS.get(fact.fact_type, fact.fact_type)
            status_label = self.STATUS_LABELS.get(result.status, result.status)

            text_short = fact.text[:40] + "..." if len(fact.text) > 40 else fact.text
            correction = result.correction if result.correction else "-"
            timestamp = result.data_timestamp if result.data_timestamp else "-"

            report += f"| {text_short} | {type_label} | {status_label} | {correction} | {timestamp} |\n"

        # 添加详细核查结果
        report += "\n### 详细核查结果\n\n"

        for result in self.results:
            fact = result.fact
            status_label = self.STATUS_LABELS.get(result.status, result.status)

            report += f"#### #{fact.id} - {status_label}\n\n"
            report += f"**原文声明**: {fact.text}\n\n"
            report += f"**类型**: {self.FACT_TYPE_LABELS.get(fact.fact_type, fact.fact_type)}\n\n"
            report += f"**上下文**: {fact.context}\n\n"

            if result.correction:
                report += f"**修正建议**: {result.correction}\n\n"

            if result.data_timestamp:
                report += f"**数据来源时间**: {result.data_timestamp}\n\n"

            if result.sources:
                report += "**参考来源**:\n"
                for src in result.sources:
                    report += f"- [{src.get('title', '来源')}]({src['url']})\n"
                report += "\n"

            if result.notes:
                report += f"**备注**: {result.notes}\n\n"

            report += "---\n\n"

        # 数据时效性提醒
        current_year = datetime.now().year
        report += f"\n### 数据时效性说明\n\n"
        report += f"> 📅 **核查基准时间**: {datetime.now().strftime('%Y年%m月%d日')}\n\n"
        report += f"> 本文事实核查基于公开可获取的最新信息。部分数据可能随时间变化，"
        report += f"建议读者关注最新官方发布。\n\n"

        report += "---\n"

        return report

    def save_report(self, report: str) -> Path:
        """保存核查报告到文件"""
        output_path = self.article_path.with_suffix('.fact_check.md')
        output_path.write_text(report, encoding="utf-8")
        return output_path

    def run(self) -> Tuple[bool, Optional[Path]]:
        """
        运行完整的事实核查流程

        Returns:
            (success, report_path)
        """
        # 1. 提取事实
        self.extract_facts()

        if not self.facts:
            print("⚠️ 未提取到任何事实声明")
            return False, None

        # 2. 展示预览
        preview = self.preview_facts()
        print(preview)

        # 3. 等待用户确认（在 CLI 环境中）
        try:
            response = input().strip().lower()
            if response not in ('y', 'yes', '是', '确认'):
                print("已取消核查")
                return False, None
        except EOFError:
            # 非交互式环境，自动继续
            print("非交互式环境，自动继续核查...")

        # 4. 执行核查
        self.verify_all()

        # 5. 生成报告
        report = self.generate_report()

        # 6. 保存报告
        output_path = self.save_report(report)
        print(f"\n✅ 事实核查报告已保存: {output_path}")

        return True, output_path


def main():
    parser = argparse.ArgumentParser(
        description="调研报告审计脚本 / 成品文章事实核查工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 调研报告审计（原有功能）
  python3 research_review.py ./00_research.md

  # 成品文章事实核查（新增功能）
  python3 research_review.py ./article.md --article
        """
    )
    parser.add_argument("input_file", type=str, help="输入文件路径")
    parser.add_argument("--dry-run", action="store_true", help="只检查不追加报告")
    parser.add_argument("--article", action="store_true", help="文章事实核查模式（而非调研报告审计）")

    args = parser.parse_args()

    # 读取文件
    input_path = Path(args.input_file).expanduser()
    if not input_path.exists():
        print(f"❌ 错误: 文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    content = input_path.read_text(encoding="utf-8")

    # 根据模式执行不同逻辑
    if args.article:
        # 文章事实核查模式
        print(f"📄 文章事实核查: {input_path.name}")
        print(f"   大小: {len(content)} 字符")

        checker = ArticleFactChecker(content, input_path)
        success, report_path = checker.run()

        if success:
            sys.exit(0)
        else:
            sys.exit(1)
    else:
        # 调研报告审计模式（原有功能）
        print(f"📋 审计报告: {input_path.name}")
        print(f"   大小: {len(content)} 字符")

        # 执行检查
        completeness = check_completeness(content, input_path)
        coverage = check_coverage_quality(content, input_path)
        confidence = check_confidence_labels(content, input_path)

        # 生成报告
        review_report = generate_review_report(input_path, completeness, coverage, confidence)

        # 输出到标准输出
        print(review_report)

        # 追加到原文件
        if not args.dry_run:
            input_path.write_text(content + review_report, encoding="utf-8")
            print(f"✅ 评审报告已追加到: {input_path}")

        # 根据综合评分决定退出码
        overall_score = (completeness["score"] + coverage["score"] + confidence["score"]) / 3
        if overall_score < 6:
            sys.exit(1)  # FAIL
        elif overall_score < 8:
            sys.exit(2)  # WARN
        else:
            sys.exit(0)  # PASS


if __name__ == "__main__":
    main()
