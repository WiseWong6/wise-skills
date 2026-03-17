#!/usr/bin/env python3
"""
竞品与内容缺口分析脚本 (Content Gap Analysis Script)

使用 Firecrawl 分析竞品内容覆盖情况，发现未覆盖的主题和差异化角度。

输出格式：JSON

**注意：** 此脚本仅用于 CLI 测试，返回模拟数据。
真实 MCP 集成请在 Claude Code 中调用此技能，AI 将直接使用 MCP 工具。
"""

import json
import re
from collections import Counter
from typing import Dict, List, Any
from datetime import datetime


class ContentGapAnalyzer:
    """内容缺口分析器"""

    def __init__(self):
        self.coverage_gaps = []
        self.keyword_gaps = []
        self.format_gaps = []

    def analyze(
        self,
        competitors: List[str],
        your_content: List[str] = None,
        platform: str = "general"
    ) -> Dict[str, Any]:
        """
        分析竞品内容缺口

        Args:
            competitors: 竞品账号/网站列表
            your_content: 你的内容列表（可选）
            platform: 平台类型（公众号, 博客, 小红书, general）

        Returns:
            包含内容缺口、关键词缺口、格式缺口的分析结果
        """
        print(f"\n📊 分析 {len(competitors)} 个竞品的内容缺口...")

        # 注意：在实际调用时，将使用 MCP 工具
        # 这里提供模拟结构展示预期输出
        results = self._simulate_gap_analysis(competitors, your_content, platform)

        return results

    def _simulate_gap_analysis(
        self,
        competitors: List[str],
        your_content: List[str],
        platform: str
    ) -> Dict[str, Any]:
        """
        模拟缺口分析（实际使用 MCP 工具）

        在 Claude Code 中调用此技能时，AI 会直接使用 MCP 工具：
        1. mcp__firecrawl__firecrawl_scrape() 爬取竞品网站内容
        2. 分析主题分布和关键词使用
        3. 对比自身内容库，找出未覆盖区域
        4. 返回真实缺口数据

        **注意：** 此 CLI 脚本仅返回模拟数据，用于测试。
        """
        print("⚠️  CLI 模式：返回模拟数据")
        print("💡 提示：在 Claude Code 中调用技能可获取真实数据")

        # 模拟数据 - 实际中会从 Firecrawl 获取
        sample_gaps = self._get_sample_gaps(competitors, platform)

        self.coverage_gaps = sample_gaps
        self.keyword_gaps = self._analyze_keyword_gaps(sample_gaps)
        self.format_gaps = self._analyze_format_gaps(platform, sample_gaps)

        return {
            "coverage_gaps": self.coverage_gaps,
            "keyword_gaps": self.keyword_gaps,
            "format_gaps": self.format_gaps,
            "analysis_metadata": {
                "competitors_analyzed": len(competitors),
                "platform": platform,
                "your_content_provided": your_content is not None,
                "timestamp": datetime.now().isoformat(),
                "tools_used": ["firecrawl_scrape", "firecrawl_search"]
            }
        }

    def _get_sample_gaps(
        self,
        competitors: List[str],
        platform: str
    ) -> List[Dict[str, Any]]:
        """获取示例缺口数据"""
        # 根据竞品数量和平台类型返回相关缺口
        gaps = []
        num_competitors = len(competitors)

        # AI 领域缺口示例
        for i, comp in enumerate(competitors, 1):
            if "AI" in comp or "tech" in comp or "claude" in comp or "gpt" in comp:
                gaps.append({
                    "competitor": comp,
                    "topic": "AI Agent 最佳实践指南",
                    "your_coverage": "部分覆盖",
                    "competitors_covered": [c for c in competitors if c != comp][:3],
                    "opportunity_score": round(8.5 - (i * 0.5), 1),
                    "suggested_angles": [
                        "从工程化架构角度讲解 Agent 设计",
                        "结合企业实际部署案例对比",
                        "深入分析多模态 Agent 的优劣势",
                        "提供成本优化的具体方案"
                    ],
                    "missing_aspects": [
                        "企业级安全与合规",
                        "测试策略与质量保障",
                        "运维监控与故障恢复",
                        "数据隐私与主权保护"
                    ]
                })
            elif "保险" in comp or "insurance" in comp or "claims" in comp:
                gaps.append({
                    "competitor": comp,
                    "topic": "保险产品数字化营销",
                    "your_coverage": "未覆盖",
                    "competitors_covered": [c for c in competitors if c != comp][:2],
                    "opportunity_score": round(9.0 - (i * 0.3), 1),
                    "suggested_angles": [
                        "从用户真实理赔体验切入",
                        "对比传统保险与数字保险的痛点",
                        "分析不同年龄段用户的保险需求差异",
                        "探讨保险与健康管理APP的联动场景"
                    ],
                    "missing_aspects": [
                        "用户体验中心的设计",
                        "AI 智能核保的效率对比",
                        "理赔流程的透明度分析",
                        "个性化保险方案设计"
                    ]
                })

        return gaps

    def _analyze_keyword_gaps(self, gaps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """分析关键词缺口"""
        keyword_gaps = []
        keyword_counter = Counter()

        for gap in gaps:
            for angle in gap.get("suggested_angles", []):
                # 提取关键词（简单实现）
                keywords = re.findall(r"[\u4e00-\u9fa5]+", angle)
                for kw in keywords:
                    keyword_counter[kw] += 1

        # 找出高频未覆盖关键词
        for kw, count in keyword_counter.most_common(10):
            keyword_gaps.append({
                "keyword": kw,
                "competitor_usage_count": count,
                "your_usage_count": 0,
                "opportunity_level": "high" if count >= len(gaps) - 1 else "medium"
            })

        return keyword_gaps

    def _analyze_format_gaps(
        self,
        platform: str,
        gaps: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """分析格式缺口"""
        format_gaps = []

        # 根据平台分析内容格式机会
        if platform in ["公众号", "小红书"]:
            format_gaps.append({
                "format_type": "视频内容",
                "your_coverage": "低",
                "competitor_coverage": "高",
                "suggestion": "增加短视频教程和实操演示"
            })
            format_gaps.append({
                "format_type": "图文结合",
                "your_coverage": "中",
                "competitor_coverage": "高",
                "suggestion": "优化信息图和长图的使用"
            })
        elif platform == "博客":
            format_gaps.append({
                "format_type": "交互式内容",
                "your_coverage": "低",
                "competitor_coverage": "中",
                "suggestion": "添加代码沙箱、在线演示"
            })
            format_gaps.append({
                "format_type": "系列文章",
                "your_coverage": "中",
                "competitor_coverage": "高",
                "suggestion": "将主题组织成系列，增强读者粘性"
            })

        return format_gaps

    def prioritize_gaps(self, gaps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """对缺口按机会评分排序"""
        return sorted(gaps, key=lambda x: x.get("opportunity_score", 0), reverse=True)


def format_output(results: Dict[str, Any], pretty: bool = True) -> str:
    """格式化输出"""
    if pretty:
        return json.dumps(results, indent=2, ensure_ascii=False)
    return json.dumps(results, ensure_ascii=False)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="内容创作调研 - 竞品与内容缺口分析")
    parser.add_argument(
        "--competitors", "-c",
        required=True,
        nargs="+",
        help="竞品账号/网站列表 (如: 公众号A 公众号B)"
    )
    parser.add_argument(
        "--your-content", "-y",
        nargs="*",
        help="你的内容主题列表 (可选，用于对比分析)"
    )
    parser.add_argument(
        "--platform", "-p",
        choices=["公众号", "博客", "小红书", "general"],
        default="general",
        help="平台类型 (默认: general)"
    )
    parser.add_argument(
        "--output", "-o",
        help="输出文件路径 (默认: stdout)"
    )
    parser.add_argument(
        "--no-pretty",
        action="store_true",
        help="不格式化 JSON 输出"
    )

    args = parser.parse_args()

    # 执行缺口分析
    analyzer = ContentGapAnalyzer()
    results = analyzer.analyze(
        competitors=args.competitors,
        your_content=args.your_content if args.your_content else None,
        platform=args.platform
    )

    # 排序输出
    if results.get("coverage_gaps"):
        results["coverage_gaps"] = analyzer.prioritize_gaps(results["coverage_gaps"])

    # 输出结果
    output = format_output(results, pretty=not args.no_pretty)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"\n✅ 结果已保存到: {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
