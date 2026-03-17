#!/usr/bin/env python3
"""
趋势与热点分析脚本 (Trend Analysis Script)

使用 Firecrawl 和 WebSearch 检测行业弱信号、分析增长趋势、预测时间窗口。

输出格式：JSON

**注意：** 此脚本仅用于 CLI 测试，返回模拟数据。
真实 MCP 集成请在 Claude Code 中调用此技能，AI 将直接使用 MCP 工具。
"""

import json
import re
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Any


class TrendAnalyzer:
    """趋势分析器"""

    def __init__(self):
        self.trends = []
        self.emerging_signals = []
        self.declining_topics = []

    def _is_chinese_query(self, query: str) -> bool:
        """
        检测查询是否为中文

        Args:
            query: 查询字符串

        Returns:
            如果查询包含中文字符返回 True
        """
        return any('\u4e00' <= char <= '\u9fff' for char in query)

    def analyze(self, domain: str, time_range: str = "month", limit: int = 10) -> Dict[str, Any]:
        """
        分析指定领域的趋势

        Args:
            domain: 行业/领域
            time_range: 时间范围 (week, month, quarter)
            limit: 返回趋势数量限制

        Returns:
            包含趋势、新兴信号、衰退话题的分析结果
        """
        print(f"\n🔍 分析 {domain} 在 {self._parse_time_range(time_range)} 的趋势...")

        # 注意：在实际调用时，将使用 MCP 工具
        # 这里提供模拟结构展示预期输出
        results = self._simulate_trend_analysis(domain, time_range, limit)

        return results

    def _parse_time_range(self, time_range: str) -> str:
        """解析时间范围"""
        now = datetime.now()
        if time_range == "week":
            return f"{(now - timedelta(days=7)).strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}"
        elif time_range == "month":
            return f"{(now - timedelta(days=30)).strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}"
        elif time_range == "quarter":
            return f"{(now - timedelta(days=90)).strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}"
        return time_range

    def _simulate_trend_analysis(self, domain: str, time_range: str, limit: int) -> Dict[str, Any]:
        """
        模拟趋势分析（实际使用 MCP 工具）

        在 Claude Code 中调用此技能时，AI 会直接使用 MCP 工具：
        1. mcp__firecrawl__firecrawl_search() 搜索社交媒体和新闻
        2. mcp__trendradar__analyze_trends() 分析中文热榜趋势（新增）
        3. 分析讨论频次、增长速率、时间窗口
        4. 返回真实趋势数据

        **注意：** 此 CLI 脚本仅返回模拟数据，用于测试。
        """
        print("⚠️  CLI 模式：返回模拟数据")
        print("💡 提示：在 Claude Code 中调用技能可获取真实数据")

        # 新增：中文查询使用 TrendRadar
        if self._is_chinese_query(domain):
            print(f"\n🔥 模拟：使用 TrendRadar 分析中文热榜趋势...")
            # 实际调用时使用：
            # trendradar_result = mcp__trendradar__analyze_trends()
            # 结合 sample_trends 进行分析

        # 模拟数据 - 实际中会从 MCP 工具获取
        sample_trends = self._get_sample_trends(domain, limit)

        self.trends = sample_trends
        self.emerging_signals = self._detect_emerging_signals(sample_trends)
        self.declining_topics = self._detect_declining_topics(domain)

        tools_used = ["firecrawl_search", "WebSearch"]
        if self._is_chinese_query(domain):
            tools_used.append("TrendRadar")

        return {
            "trends": self.trends,
            "emerging_signals": self.emerging_signals,
            "declining_topics": self.declining_topics,
            "analysis_metadata": {
                "domain": domain,
                "time_range": time_range,
                "time_window": self._parse_time_range(time_range),
                "timestamp": datetime.now().isoformat(),
                "tools_used": tools_used
            }
        }

    def _get_sample_trends(self, domain: str, limit: int) -> List[Dict[str, Any]]:
        """获取示例趋势数据"""
        # 根据领域返回相关趋势
        trend_templates = {
            "AI": [
                {
                    "topic": "AI Agent 编排",
                    "signal_strength": "high",
                    "growth_rate": "+65%",
                    "time_window": "2025-12 ~ 2026-02",
                    "sources": ["Reddit r/LocalLLaMA", "Twitter/X", "GitHub trending", "DevCommunity"],
                    "key_insights": [
                        "企业采用率快速上升",
                        "开源工具激增",
                        "Claude、GPT-4o 等模型竞争加剧"
                    ],
                    "search_volume": "25000+",
                    "engagement_score": 8.7
                },
                {
                    "topic": "多模态 AI 应用",
                    "signal_strength": "high",
                    "growth_rate": "+82%",
                    "time_window": "2025-10 ~ 2026-02",
                    "sources": ["Product Hunt", "Y Combinator", "News"],
                    "key_insights": [
                        "图文生成、视频分析集成",
                        "企业级工具涌现",
                        "成本优化成为关键议题"
                    ],
                    "search_volume": "18000+",
                    "engagement_score": 8.3
                },
                {
                    "topic": "AI 测试与质量保障",
                    "signal_strength": "medium",
                    "growth_rate": "+45%",
                    "time_window": "2025-11 ~ 2026-01",
                    "sources": ["Dev.to", "Stack Overflow trending", "GitHub repositories"],
                    "key_insights": [
                        "测试自动化工具成熟",
                        "LLM 评测标准建立",
                        "企业重视 AI 安全性"
                    ],
                    "search_volume": "8500+",
                    "engagement_score": 7.2
                },
                {
                    "topic": "边缘计算与本地 AI",
                    "signal_strength": "medium",
                    "growth_rate": "+58%",
                    "time_window": "2025-09 ~ 2026-01",
                    "sources": ["Tech blogs", "Hardware news", "Developer forums"],
                    "key_insights": [
                        "隐私和数据主权驱动",
                        "硬件加速方案普及",
                        "成本优势明显"
                    ],
                    "search_volume": "6500+",
                    "engagement_score": 7.5
                }
            ],
            "保险": [
                {
                    "topic": "保险理赔自动化",
                    "signal_strength": "high",
                    "growth_rate": "+72%",
                    "time_window": "2025-10 ~ 2026-02",
                    "sources": ["保险行业报告", "Reddit", "LinkedIn"],
                    "key_insights": [
                        "AI OCR + NLP 处理材料",
                        "秒级审核成为可能",
                        "降本增效显著"
                    ],
                    "search_volume": "12000+",
                    "engagement_score": 8.1
                },
                {
                    "topic": "智能核保",
                    "signal_strength": "high",
                    "growth_rate": "+88%",
                    "time_window": "2025-11 ~ 2026-01",
                    "sources": ["HealthTech news", "AI 医疗报告", "Research papers"],
                    "key_insights": [
                        "基因数据 + AI 风险评估",
                        "个性化保单设计",
                        "核保从实验走向应用"
                    ],
                    "search_volume": "9500+",
                    "engagement_score": 8.4
                },
                {
                    "topic": "数字健康与保险结合",
                    "signal_strength": "medium",
                    "growth_rate": "+55%",
                    "time_window": "2025-09 ~ 2026-01",
                    "sources": ["Insurance innovation", "Tech startups", "Consumer apps"],
                    "key_insights": [
                        "可穿戴设备数据联动",
                        "预防式健康管理",
                        "用户数据隐私合规挑战"
                    ],
                    "search_volume": "7800+",
                    "engagement_score": 7.6
                }
            ]
        }

        # 返回匹配领域的趋势
        for key in trend_templates:
            if key.lower() in domain.lower() or domain.lower() in key.lower():
                return trend_templates[key][:limit]

        # 默认返回通用技术趋势
        return trend_templates["AI"][:limit]

    def _detect_emerging_signals(self, trends: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """检测新兴信号"""
        emerging = []
        for trend in trends:
            if trend.get("signal_strength") == "high" and trend.get("growth_rate", "").startswith("+"):
                emerging.append({
                    "signal": trend["topic"],
                    "confidence": "high" if trend.get("engagement_score", 0) > 8 else "medium",
                    "early_mentions": trend.get("sources", [])[:2],
                    "prediction_window": "3-6 months"
                })
        return emerging

    def _detect_declining_topics(self, domain: str) -> List[str]:
        """检测衰退话题"""
        # 基于领域返回衰退话题
        declining_map = {
            "AI": ["纯文本 GPT 竞争", "单一模型架构", "非结构化 Prompt"],
            "保险": ["传统纸质理赔", "线下-only 服务", "标准化产品策略"]
        }
        for key in declining_map:
            if key.lower() in domain.lower() or domain.lower() in key.lower():
                return declining_map[key]
        return ["传统 workflow", "手动流程"]


def format_output(results: Dict[str, Any], pretty: bool = True) -> str:
    """格式化输出"""
    if pretty:
        return json.dumps(results, indent=2, ensure_ascii=False)
    return json.dumps(results, ensure_ascii=False)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="内容创作调研 - 趋势与热点分析")
    parser.add_argument(
        "--domain", "-d",
        required=True,
        help="行业/领域 (如: AI, 保险, 科技, 医疗)"
    )
    parser.add_argument(
        "--time-range", "-t",
        choices=["week", "month", "quarter"],
        default="month",
        help="时间范围 (默认: month)"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=10,
        help="返回趋势数量限制 (默认: 10)"
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

    # 执行趋势分析
    analyzer = TrendAnalyzer()
    results = analyzer.analyze(
        domain=args.domain,
        time_range=args.time_range,
        limit=args.limit
    )

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
