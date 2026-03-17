#!/usr/bin/env python3
"""
深度网络搜索与引用脚本 (Research Search with Citations)

基于 MCP 工具进行真实联网搜索，获取带引用和置信度的权威资料。

工具优先级：
1. Context7 - 技术文档、API 文档
2. Firecrawl - 网页搜索、爬取、社交媒体搜索、竞品分析

输出格式：JSON + Markdown

**注意：** 此脚本仅用于 CLI 测试，返回模拟数据。
真实 MCP 集成请在 Claude Code 中调用此技能，AI 将直接使用 MCP 工具。
"""

import json
import os
import re
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

# Obsidian 集成工具
try:
    from obsidian_utils import (
        get_research_path,
        ensure_obsidian_vault_exists,
        generate_obsidian_frontmatter,
        create_obsidian_index_content,
        write_frontmatter,
        get_fallback_path,
        get_obsidian_research_ref,
        check_obsidian_mode_available
    )
    OBSIDIAN_UTILS_AVAILABLE = True
except ImportError:
    OBSIDIAN_UTILS_AVAILABLE = False


class ResearchSearcher:
    """研究搜索器"""

    def __init__(self):
        self.findings = []
        self.search_timestamp = datetime.now().isoformat()
        self.tools_used = []

        # Tavily 配置（Firecrawl 降级方案）
        self.tavily_api_key = os.getenv(
            "TAVILY_API_KEY",
            "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"
        )
        self.tavily_base_url = "https://api.tavily.com"

        # zread 配置（GitHub 代码研究）
        # 仓库名映射表：从查询推断 GitHub 仓库
        self.repo_name_map = {
            "langgraph": "langchain-ai/langgraph",
            "next.js": "vercel/next.js",
            "nextjs": "vercel/next.js",
            "react": "facebook/react",
            "vue": "vuejs/core",
            "angular": "angular/angular",
            "svelte": "sveltejs/svelte",
            "tailwind": "tailwindlabs/tailwindcss",
            "typescript": "microsoft/TypeScript",
            "python": "python/cpython",
            "golang": "golang/go",
            "rust": "rust-lang/rust",
            "docker": "docker/docker-ce",
            "kubernetes": "kubernetes/kubernetes",
            "postgres": "postgres/postgres",
            "postgresql": "postgres/postgres",
            "mongodb": "mongodb/mongo",
            "redis": "redis/redis",
            "nginx": "nginx/nginx",
            "node": "nodejs/node",
            "nodejs": "nodejs/node",
            "vite": "vitejs/vite",
            "webpack": "webpack/webpack",
            "babel": "babel/babel",
            "eslint": "eslint/eslint",
            "prettier": "prettier/prettier",
            "jest": "jestjs/jest",
            "vitest": "vitest-dev/vitest",
        }

    def is_ambiguous_input(self, user_input: str) -> bool:
        """
        判断输入是模糊想法还是明确标题

        模糊输入特征：
        - 包含 "我想写"、"我想发"、"我想写一篇"
        - 包含 "感觉...挺有意思"、"最近...都在讨论"
        - 包含 "能不能...写点"、"想...写点"
        - 包含 "关于...的文章"、"关于...的内容"
        """
        # 模糊输入特征
        ambiguous_patterns = [
            "我想写", "我想发", "我想写一篇",
            "感觉.*挺有意思", "最近.*都在讨论",
            "能不能.*写点", "想.*写点",
            "关于.*的文章", "关于.*的内容"
        ]
        cleaned_input = re.sub(r'[，。！？]', '', user_input)
        return any(re.search(p, cleaned_input) for p in ambiguous_patterns)

    def parse_ambiguous_idea(self, idea: str) -> Dict[str, Any]:
        """
        解析模糊想法，提取核心话题和潜在写作角度

        在真实 AI 调用中，这会通过 AI 分析意图。
        CLI 脚本版本返回模拟结构化数据。
        """
        print(f"\n🔍 解析模糊想法: {idea}")

        # 模拟意图解析（真实版本中由 AI 完成）
        core_topic = self._extract_topic(idea)

        # 生成多个潜在写作角度
        suggested_angles = self._generate_suggested_angles(core_topic, idea)

        return {
            "core_topic": core_topic,
            "suggested_angles": suggested_angles,
            "target_audience": self._infer_audience(idea),
            "input_type": "ambiguous"
        }

    def _generate_suggested_angles(self, topic: str, idea: str) -> List[Dict[str, Any]]:
        """
        基于核心话题生成 3-5 个潜在写作角度

        CLI 版本返回模拟数据，真实版本由 AI 动态生成
        """
        # 根据话题类型生成角度
        angles_templates = [
            {
                "name": f"{topic} 使用教程",
                "type": "tutorial",
                "description": f"详细讲解 {topic} 的使用方法、最佳实践和常见陷阱"
            },
            {
                "name": f"{topic} 案例分析",
                "type": "case_study",
                "description": f"通过实际案例展示 {topic} 的应用场景和效果"
            },
            {
                "name": f"{topic} 原理深度解析",
                "type": "technical_analysis",
                "description": f"深入分析 {topic} 的技术原理、架构设计和实现细节"
            },
            {
                "name": f"{topic} 对比评测",
                "type": "comparison",
                "description": f"对比 {topic} 与其他方案的优劣，提供选择建议"
            }
        ]

        # 根据用户想法调整角度
        if "教程" in idea or "入门" in idea:
            return [angles_templates[0], angles_templates[1]]
        elif "案例" in idea or "实践" in idea:
            return [angles_templates[1], angles_templates[0]]
        elif "原理" in idea or "机制" in idea:
            return [angles_templates[2], angles_templates[0]]
        else:
            return angles_templates[:3]

    def _infer_audience(self, idea: str) -> str:
        """
        从用户想法中推断目标读者群体
        """
        if "程序员" in idea or "开发者" in idea or "开发者" in idea:
            return "程序员/开发者"
        elif "企业" in idea or "公司" in idea:
            return "企业决策者"
        elif "初学者" in idea or "新手" in idea or "入门" in idea:
            return "初学者/新手"
        else:
            return "通用技术读者"

    def search(
        self,
        query: str,
        source_types: List[str] = None,
        depth: int = 3
    ) -> Dict[str, Any]:
        """
        执行研究搜索

        Args:
            query: 研究问题/主题
            source_types: 需要的来源类型（academic, docs, news, social）
            depth: 搜索深度

        Returns:
            包含发现、来源、时间戳、新鲜度评分的研究结果
        """
        print(f"\n🔍 研究主题: {query}")

        # 确定搜索策略
        if not source_types:
            source_types = self._infer_source_types(query)

        # 执行搜索
        results = self._execute_search(query, source_types, depth)

        # 计算新鲜度评分
        results["freshness_score"] = self._calculate_freshness(results.get("findings", []))

        return results

    def _infer_source_types(self, query: str) -> List[str]:
        """
        推断需要的来源类型（多路召回架构）

        所有查询都使用相同的数据源组合，让结果自然融合
        """
        # 学术相关关键词
        academic_keywords = [
            "论文", "研究", "学术", "paper", "study",
            "机制", "对比", "benchmark", "评测",
            "实验", "数据", "统计", "临床"
        ]

        # 技术文档相关
        doc_keywords = [
            "API", "文档", "教程", "指南", "reference",
            "语法", "实现", "代码", "example"
        ]

        query_lower = query.lower()

        # 新增：代码研究关键词检测
        if self._has_code_keywords(query):
            return ["docs", "news", "code"]

        if any(kw in query_lower for kw in academic_keywords):
            return ["academic", "docs", "news"]
        elif any(kw in query_lower for kw in doc_keywords):
            return ["docs", "news"]
        # 多路召回：热榜总是可用，不区分语言
        return ["news", "docs", "hotlist"]

    def _execute_search(
        self,
        query: str,
        source_types: List[str],
        depth: int
    ) -> Dict[str, Any]:
        """
        执行实际搜索（使用 MCP 工具）

        在 Claude Code 中调用此技能时，AI 会直接使用 MCP 工具：
        1. mcp__context7__query-docs() 获取技术文档
        2. mcp__firecrawl__firecrawl_search() 搜索网页
        3. mcp__trendradar__search_hot_news() 获取中文热榜
        4. mcp__zread__search_doc() 获取 GitHub 代码（新增）
        5. 返回真实研究结果

        **注意：** 此 CLI 脚本仅返回模拟数据，用于测试。
        """
        findings = []
        self.tools_used = []

        print("⚠️  CLI 模式：返回模拟数据")
        print("💡 提示：在 Claude Code 中调用技能可获取真实数据")

        # 1. 技术文档（使用 Context7 模拟）
        if "docs" in source_types:
            print(f"\n📖 模拟：使用 Context7 获取技术文档...")
            doc_results = self._simulate_context7_search(query)
            findings.extend(doc_results)
            self.tools_used.append("Context7")

        # 2. 新闻和网页（使用 Firecrawl 模拟，带 Tavily 降级）
        if "news" in source_types or "social" in source_types or "academic" in source_types:
            print(f"\n🌐 模拟：使用 Firecrawl 搜索网页内容...")
            web_results = self._fetch_with_fallback(query, 10)
            findings.extend(web_results)
            self.tools_used.append("Firecrawl")

        # 3. GitHub 代码研究（zread）- 新增
        if "code" in source_types:
            print(f"\n💻 模拟：使用 zread 搜索 GitHub 代码...")
            code_results = self._fetch_github_code(query)
            findings.extend(code_results)
            self.tools_used.append("zread")

        # 4. Exa 搜索（代码、学术、公司研究）
        if self._should_use_exa(query, source_types):
            print(f"\n🔍 模拟：使用 Exa 进行深度搜索...")
            exa_results = self._search_with_exa(query)
            findings.extend(exa_results)
            if exa_results:
                self.tools_used.append("Exa")

        # 5. 社交媒体搜索（Agent Reach）
        if self._should_use_social_search(query):
            print(f"\n👥 模拟：使用社交媒体搜索...")
            try:
                from social_search import SocialSearcher
                social_searcher = SocialSearcher()
                social_results = social_searcher.search(query, limit=5)
                findings.extend(social_results.get("findings", []))
                if social_results.get("findings"):
                    self.tools_used.append("SocialSearch")
            except Exception as e:
                print(f"   ⚠️  社交媒体搜索降级: {str(e)}")

        # 6. 热榜数据（TrendRadar）- 多路召回：总是调用
        findings.extend(self._fetch_trendradar_hotlist(query, limit=5))
        self.tools_used.append("TrendRadar")

        # 5. 交叉验证（模拟）
        print(f"\n✓ 模拟：交叉验证...")
        verified_findings = self._cross_verify_with_websearch(findings)

        self.findings = verified_findings

        return {
            "query": query,
            "findings": verified_findings,
            "search_metadata": {
                "source_types_requested": source_types,
                "depth": depth,
                "total_findings": len(verified_findings),
                "tools_used": list(set(self.tools_used))
            },
            "research_timestamp": self.search_timestamp
        }

    def _simulate_research_lookup(self, query: str) -> List[Dict[str, Any]]:
        """
        模拟 research-lookup 调用（实际使用 MCP）

        research-lookup 使用 Perplexity Sonar 模型，自动选择：
        - Sonar Pro Search: 快速信息检索
        - Sonar Reasoning Pro: 复杂分析、对比研究
        """
        # 提取查询关键词用于示例
        topic = self._extract_topic(query)

        # 返回模拟的学术资料
        return [
            {
                "claim": f"{topic} 的核心技术机制和实现方式",
                "sources": [
                    {
                        "title": f"{topic} 官方技术文档",
                        "url": f"https://docs.example.com/{topic.replace(' ', '-').lower()}",
                        "date": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                        "confidence": "official",
                        "excerpt": "本文档详细介绍了 {topic} 的核心架构、关键API 和最佳实践。"
                    },
                    {
                        "title": f"{topic} 学术论文综述",
                        "url": f"https://arxiv.org/abs/xxxx.xxxxx",
                        "date": (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d"),
                        "confidence": "high",
                        "excerpt": f"该论文对 {topic} 进行了系统性分析，提出了改进方案。"
                    },
                    {
                        "title": f"{topic} 性能基准测试报告",
                        "url": f"https://benchmarks.example.com/{topic.replace(' ', '-')}",
                        "date": (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d"),
                        "confidence": "high",
                        "excerpt": f"基准测试显示 {topic} 在各项指标上表现优异。"
                    }
                ],
                "cross_verified": True,
                "verification_method": "research-lookup (Sonar Reasoning Pro)",
                "source_type": "academic"
            }
        ]

    def _simulate_context7_search(self, query: str) -> List[Dict[str, Any]]:
        """
        模拟 Context7 调用（实际使用 MCP）

        Context7 用于获取库的最新文档和代码示例
        """
        topic = self._extract_topic(query)

        return [
            {
                "claim": f"{topic} 的最新 API 使用方法",
                "sources": [
                    {
                        "title": f"{topic} v2.0 API Reference",
                        "url": f"https://api.example.com/docs/{topic.replace(' ', '-').lower()}/",
                        "date": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
                        "confidence": "official",
                        "excerpt": f"最新的 {topic} API 文档，包含完整的使用示例和参数说明。"
                    }
                ],
                "cross_verified": True,
                "verification_method": "Context7",
                "source_type": "docs"
            },
            {
                "claim": f"{topic} 的代码实现示例",
                "sources": [
                    {
                        "title": f"{topic} 社区最佳实践",
                        "url": f"https://github.com/example/{topic.replace(' ', '-').lower()}/",
                        "date": (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d"),
                        "confidence": "high",
                        "excerpt": f"社区提供的 {topic} 实现示例，包含多个用例场景。"
                    }
                ],
                "cross_verified": True,
                "verification_method": "Context7",
                "source_type": "docs"
            }
        ]

    # ========== Exa 搜索集成 ==========

    def _should_use_exa(self, query: str, source_types: List[str]) -> bool:
        """
        判断是否适合使用 Exa 搜索

        Exa 适合场景：
        1. 代码搜索（owner/repo 模式）
        2. 学术研究（paper, study 关键词）
        3. 公司/产品研究
        """
        query_lower = query.lower()

        # 代码相关
        code_patterns = [
            r'\w+/\w+',  # owner/repo 模式
        ]
        code_keywords = ["github", "code", "implementation", "repository"]

        # 学术相关
        academic_keywords = ["paper", "study", "research", "arxiv", "学术", "论文"]

        # 公司/产品相关
        company_keywords = [
            "anthropic", "openai", "google", "microsoft", "meta",
            "claude", "gpt", "llama", "gemini"
        ]

        # 检查代码模式
        for pattern in code_patterns:
            if re.search(pattern, query):
                return True

        # 检查关键词
        if any(kw in query_lower for kw in code_keywords + academic_keywords + company_keywords):
            return True

        # 如果 source_types 明确包含 academic
        if "academic" in source_types:
            return True

        return False

    def _search_with_exa(self, query: str) -> List[Dict[str, Any]]:
        """
        使用 Exa 进行深度搜索

        降级策略：
        1. 尝试调用 Exa MCP（实际使用时）
        2. 失败时降级到 Tavily 搜索
        3. 记录降级信息
        """
        print(f"   🔍 Exa 查询: {query}")

        try:
            # 检测查询类型
            query_type = self._detect_exa_query_type(query)
            print(f"   📌 检测到的查询类型: {query_type}")

            # CLI 模式返回模拟数据
            # 实际使用时，这里会调用 Exa MCP:
            # results = mcp__exa__web_search_exa(query) 或
            # results = mcp__exa__get_code_context_exa(repo, query)

            return self._simulate_exa_results(query, query_type)

        except Exception as e:
            print(f"   ⚠️  Exa 搜索失败，降级到 Tavily: {str(e)}")
            return self._tavily_search(query, limit=5)

    def _detect_exa_query_type(self, query: str) -> str:
        """检测 Exa 查询类型"""
        query_lower = query.lower()

        # 代码搜索
        if re.search(r'\w+/\w+', query) or any(kw in query_lower for kw in ["github", "code", "implementation"]):
            return "code"

        # 学术研究
        if any(kw in query_lower for kw in ["paper", "study", "research", "arxiv", "学术", "论文"]):
            return "academic"

        # 公司/产品
        if any(kw in query_lower for kw in ["anthropic", "openai", "claude", "gpt", "company"]):
            return "company"

        return "general"

    def _simulate_exa_results(self, query: str, query_type: str) -> List[Dict[str, Any]]:
        """模拟 Exa 搜索结果（实际使用 MCP）"""
        topic = self._extract_topic(query)

        if query_type == "code":
            return [
                {
                    "claim": f"[Exa] {topic} 的高质量代码实现",
                    "summary_zh": f"从优质开源仓库中找到的 {topic} 实现代码，包含详细注释。",
                    "sources": [{
                        "title": f"{topic} - Exa Code Search",
                        "url": f"https://github.com/search?q={topic.replace(' ', '+')}",
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "confidence": "high"
                    }],
                    "source_type": "exa",
                    "exa_type": "code",
                    "cross_verified": True
                }
            ]
        elif query_type == "academic":
            return [
                {
                    "claim": f"[Exa] {topic} 相关学术研究",
                    "summary_zh": f"Exa 找到了关于 {topic} 的最新学术论文和研究成果。",
                    "sources": [{
                        "title": f"{topic} - Academic Paper",
                        "url": f"https://arxiv.org/search/?query={topic.replace(' ', '+')}",
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "confidence": "high"
                    }],
                    "source_type": "exa",
                    "exa_type": "academic",
                    "cross_verified": True
                }
            ]
        else:
            return [
                {
                    "claim": f"[Exa] {topic} 深度搜索结果",
                    "summary_zh": f"Exa 语义搜索找到了关于 {topic} 的高质量资料。",
                    "sources": [{
                        "title": f"{topic} - Exa Search",
                        "url": f"https://exa.ai/search?q={query.replace(' ', '+')}",
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "confidence": "medium"
                    }],
                    "source_type": "exa",
                    "exa_type": query_type,
                    "cross_verified": False
                }
            ]

    # ========== 社交媒体搜索 ==========

    def _should_use_social_search(self, query: str) -> bool:
        """
        判断是否适合社交媒体搜索
        """
        social_keywords = [
            "opinion", "review", "experience", "vs", "comparison",
            "discussion", "community", "feedback", "争议",
            "观点", "体验", "评价", "对比", "讨论"
        ]
        query_lower = query.lower()
        return any(kw in query_lower for kw in social_keywords)

    # ========== 智能路由 ==========

    def _detect_query_type(self, query: str) -> str:
        """
        检测查询类型，用于智能路由
        """
        query_lower = query.lower()

        # 代码查询
        if self._has_code_keywords(query):
            return "code"

        # 学术查询
        academic_keywords = ["paper", "study", "research", "arxiv", "学术", "论文", "benchmark"]
        if any(kw in query_lower for kw in academic_keywords):
            return "academic"

        # 趋势查询
        trend_keywords = ["trend", "latest", "2025", "2026", "news", "热点"]
        if any(kw in query_lower for kw in trend_keywords):
            return "trend"

        # 教程查询
        tutorial_keywords = ["tutorial", "guide", "how-to", "入门", "教程"]
        if any(kw in query_lower for kw in tutorial_keywords):
            return "tutorial"

        # 公司/产品查询
        company_keywords = ["anthropic", "openai", "google", "company", "产品"]
        if any(kw in query_lower for kw in company_keywords):
            return "company"

        return "general"

    def _select_tools_by_query_type(self, query_type: str) -> List[str]:
        """
        根据查询类型选择工具
        """
        tool_mapping = {
            "code": ["zread", "exa", "github"],
            "academic": ["exa", "context7", "arxiv"],
            "trend": ["trendradar", "twitter", "reddit", "firecrawl"],
            "tutorial": ["youtube", "bilibili", "docs"],
            "company": ["exa", "firecrawl", "tavily"],
            "general": ["firecrawl", "context7", "trendradar"]
        }
        return tool_mapping.get(query_type, tool_mapping["general"])

    def _simulate_firecrawl_search(self, query: str) -> List[Dict[str, Any]]:
        """
        模拟 Firecrawl 调用（实际使用 MCP）

        Firecrawl 用于网页抓取、社交媒体搜索、竞品分析
        """
        topic = self._extract_topic(query)

        return [
            {
                "claim": f"{topic} 在行业中的实际应用案例",
                "sources": [
                    {
                        "title": f"{topic} 企业应用案例分析",
                        "url": f"https://blog.example.com/case-study/{topic.replace(' ', '-')}",
                        "date": (datetime.now() - timedelta(days=25)).strftime("%Y-%m-%d"),
                        "confidence": "medium",
                        "excerpt": f"某知名企业使用 {topic} 后，效率提升了 X%。"
                    },
                    {
                        "title": f"{topic} 社区讨论",
                        "url": "https://reddit.com/r/example/comments/xxxx",
                        "date": (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"),
                        "confidence": "medium",
                        "excerpt": f"开发者们对 {topic} 的实际效果进行了深入讨论。"
                    },
                    {
                        "title": f"{topic} 新闻报道",
                        "url": f"https://news.example.com/tech/{topic.replace(' ', '-')}",
                        "date": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
                        "confidence": "medium",
                        "excerpt": f"主流媒体报道 {topic} 在科技行业的应用。"
                    }
                ],
                "cross_verified": True,
                "verification_method": "Firecrawl + WebSearch",
                "source_type": "news"
            },
            {
                "claim": f"{topic} 的用户反馈和评价",
                "sources": [
                    {
                        "title": f"{topic} 用户评价汇总",
                        "url": f"https://reviews.example.com/product/{topic.replace(' ', '-')}",
                        "date": (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d"),
                        "confidence": "medium",
                        "excerpt": f"用户对 {topic} 的整体评价积极，尤其在易用性方面。"
                    }
                ],
                "cross_verified": True,
                "verification_method": "Firecrawl",
                "source_type": "social"
            }
        ]

    # ========== TrendRadar 集成（多路召回架构）==========

    def _fetch_trendradar_hotlist(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        调用 TrendRadar MCP 获取热榜数据

        在 Claude Code 中调用此技能时，AI 会直接使用 MCP 工具：
        1. mcp__trendradar__search_hot_news(query, platforms, limit)
        2. normalize_trendradar_news() 转换数据格式
        3. 返回标准化研究结果

        **注意：** 此 CLI 脚本仅返回模拟数据，用于测试。

        Args:
            query: 搜索查询
            limit: 结果数量限制

        Returns:
            标准化格式的发现列表
        """
        print(f"\n🔥 模拟：使用 TrendRadar 获取中文热榜...")
        print(f"   查询: {query}")
        print(f"   平台: 知乎、微博、B站")

        # CLI 模式返回模拟数据
        # 实际调用时，AI 会使用:
        # result = mcp__trendradar__search_hot_news(
        #     query=query,
        #     platforms=["zhihu", "weibo", "bilibili"],
        #     limit=limit
        # )
        # return normalize_trendradar_news(result)

        return self._simulate_trendradar_search(query, limit)

    def _simulate_trendradar_search(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """
        模拟 TrendRadar 搜索结果（实际使用 MCP）
        """
        topic = self._extract_topic(query)

        return [
            {
                "claim": f"[知乎] {topic} 相关讨论热度上升",
                "summary_zh": f"知乎社区对 {topic} 的讨论热度显著上升，多个高赞回答深入分析了相关话题。",
                "sources": [
                    {
                        "title": f"{topic} - 知乎热榜",
                        "url": f"https://www.zhihu.com/hot",
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "confidence": "high",
                        "excerpt": f"知乎热榜关于 {topic} 的话题讨论..."
                    }
                ],
                "cross_verified": False,
                "source_type": "trendradar",
                "platform": "zhihu",
                "freshness_status": "current"
            },
            {
                "claim": f"[微博] {topic} 话题阅读量破亿",
                "summary_zh": f"微博上关于 {topic} 的话题阅读量突破 1 亿，引发广泛讨论。",
                "sources": [
                    {
                        "title": f"{topic} - 微博热搜",
                        "url": f"https://s.weibo.com/weibo?q={topic}",
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "confidence": "high",
                        "excerpt": f"微博热搜关于 {topic} 的讨论..."
                    }
                ],
                "cross_verified": False,
                "source_type": "trendradar",
                "platform": "weibo",
                "freshness_status": "current"
            },
            {
                "claim": f"[B站] {topic} 相关视频播放量激增",
                "summary_zh": f"B站上 {topic} 相关视频播放量近期激增，UP主们纷纷制作相关内容。",
                "sources": [
                    {
                        "title": f"{topic} - B站热门",
                        "url": f"https://www.bilibili.com/v/popular/all",
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "confidence": "high",
                        "excerpt": f"B站热门关于 {topic} 的视频..."
                    }
                ],
                "cross_verified": False,
                "source_type": "trendradar",
                "platform": "bilibili",
                "freshness_status": "current"
            }
        ][:limit]

    # ========== Tavily 降级方案 ==========

    def _fetch_with_fallback(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """
        Firecrawl 降级到 Tavily

        先尝试 Firecrawl，失败时自动降级到 Tavily
        """
        try:
            # CLI 模式：直接返回模拟的 Firecrawl 结果
            # 真实环境中，这里会调用 Firecrawl MCP 工具
            # 如果到达限额，抛出异常并降级到 Tavily
            return self._simulate_firecrawl_search(query)
        except Exception as e:
            # 降级到 Tavily
            print(f"⚠️  Firecrawl 调用失败: {e}")
            print(f"🔄 降级到 Tavily...")
            return self._tavily_search(query, limit)

    def _tavily_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        使用 Tavily 搜索（Firecrawl 降级方案）

        在 Claude Code 中调用此技能时，AI 会直接调用 Tavily API
        **注意：** 此 CLI 脚本返回模拟数据
        """
        # 真实 API 调用示例（CLI 模式不执行）
        # response = requests.post(
        #     f"{self.tavily_base_url}/search",
        #     headers={
        #         "Content-Type": "application/json",
        #         "Authorization": f"Bearer {self.tavily_api_key}"
        #     },
        #     json={
        #         "query": query,
        #         "max_results": min(limit, 20),
        #         "search_depth": "basic",
        #         "include_raw_content": False,
        #         "include_answer": False
        #     },
        #     timeout=30
        # )
        # response.raise_for_status()
        # data = response.json()
        # return self._normalize_tavily_results(data.get("results", []))

        # CLI 模式：返回模拟数据
        topic = self._extract_topic(query)
        return [
            {
                "claim": f"[Tavily] {topic} 最新资讯和讨论",
                "summary_zh": f"Tavily 搜索结果显示 {topic} 相关的最新讨论和资讯。",
                "sources": [
                    {
                        "title": f"{topic} - Tavily Search",
                        "url": f"https://tavily.com/search?q={topic}",
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "confidence": "medium",
                        "excerpt": f"Tavily 搜索返回的 {topic} 相关内容摘要..."
                    }
                ],
                "cross_verified": False,
                "source_type": "tavily",
                "freshness_status": "current"
            }
        ]

    def _normalize_tavily_results(self, raw_results: List[Dict]) -> List[Dict[str, Any]]:
        """
        将 Tavily 结果转换为标准格式
        """
        return [{
            "claim": item.get("title", ""),
            "summary_zh": item.get("content", "")[:200],
            "sources": [{
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "date": datetime.now().strftime("%Y-%m-%d"),  # Tavily 不提供日期
                "confidence": "medium",
                "excerpt": item.get("content", "")[:200]
            }],
            "cross_verified": False,
            "source_type": "tavily",
            "freshness_status": "current"
        } for item in raw_results]

    # ========== zread GitHub 代码研究 ==========

    def _has_code_keywords(self, query: str) -> bool:
        """
        检测是否需要代码研究（zread）

        检测条件：
        1. 包含 GitHub 关键词
        2. 包含代码相关关键词
        3. 包含仓库名模式 (owner/repo)
        """
        github_keywords = [
            "github", "代码", "实现", "example", "demo",
            "最佳实践", "实战", "案例", "源码",
            "repository", "repo", "code"
        ]

        query_lower = query.lower()

        # 检测仓库名模式 (owner/repo)
        has_repo_pattern = bool(re.search(r'\w+/\w+', query))

        return has_repo_pattern or any(kw in query_lower for kw in github_keywords)

    def _infer_repo_name(self, query: str) -> Optional[str]:
        """
        从查询推断 GitHub 仓库名

        优先级：
        1. 直接匹配 owner/repo 模式
        2. 映射表查找
        3. 返回 None
        """
        # 1. 直接匹配仓库名模式
        repo_match = re.search(r'(\w+/\w+)', query)
        if repo_match:
            return repo_match.group(1)

        # 2. 映射表查找
        query_lower = query.lower()
        for name, repo in self.repo_name_map.items():
            if name in query_lower:
                return repo

        return None

    def _fetch_github_code(self, query: str) -> List[Dict[str, Any]]:
        """
        从 GitHub 获取代码和文档（zread 集成）

        在 Claude Code 中调用此技能时，AI 会直接使用 MCP 工具：
        1. mcp__zread__search_doc(repo, query) - 搜索代码
        2. mcp__zread__read_file(repo, path) - 读取文件
        3. mcp__zread__get_repo_structure(repo) - 获取仓库结构
        4. normalize_zread_results() 转换数据格式

        **注意：** 此 CLI 脚本返回模拟数据
        """
        # 提取仓库名
        repo = self._infer_repo_name(query)

        if not repo:
            print(f"   ⚠️  无法识别 GitHub 仓库，跳过代码研究")
            return []

        print(f"   📦 识别仓库: {repo}")

        # CLI 模式：返回模拟数据
        # 真实调用示例：
        # results = mcp__zread__search_doc(repo, query)
        # return normalize_zread_results(results)
        return self._simulate_zread_search(repo, query)

    def _simulate_zread_search(self, repo: str, query: str) -> List[Dict[str, Any]]:
        """
        模拟 zread 搜索结果（实际使用 MCP）
        """
        topic = self._extract_topic(query)

        return [
            {
                "claim": f"[GitHub/{repo}] {topic} 实现代码示例",
                "summary_zh": f"从 {repo} 仓库中找到的 {topic} 相关实现代码。",
                "sources": [
                    {
                        "title": f"{repo} - {topic} Example",
                        "url": f"https://github.com/{repo}/blob/main/examples/{topic.replace(' ', '_').lower()}.ts",
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "confidence": "high",
                        "excerpt": f"来自 {repo} 的官方示例代码，展示了 {topic} 的实际使用方法。"
                    }
                ],
                "cross_verified": True,
                "source_type": "code",
                "repo": repo,
                "freshness_status": "current"
            },
            {
                "claim": f"[GitHub/{repo}] {topic} 最佳实践文档",
                "summary_zh": f"{repo} 仓库中关于 {topic} 的最佳实践文档和说明。",
                "sources": [
                    {
                        "title": f"{repo} - Documentation",
                        "url": f"https://github.com/{repo}/blob/main/docs/{topic.replace(' ', '_').lower()}.md",
                        "date": (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d"),
                        "confidence": "high",
                        "excerpt": f"官方文档详细说明了 {topic} 的设计理念和实现细节。"
                    }
                ],
                "cross_verified": True,
                "source_type": "code",
                "repo": repo,
                "freshness_status": "current"
            }
        ]

    # ========== 原有方法 ==========

    def _cross_verify_with_websearch(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        使用 WebSearch 交叉验证发现

        在实际实现中，这将对每个发现进行快速事实核查
        """
        print(f"\n🔎 交叉验证 {len(findings)} 个发现...")

        verified_findings = []
        for i, finding in enumerate(findings, 1):
            # 模拟交叉验证
            finding["verification_score"] = finding.get("confidence", "medium")

            # 为高置信度来源添加额外验证标记
            if finding.get("confidence") == "official":
                finding["additional_verification"] = {
                    "method": "WebSearch metadata verification",
                    "checked_fields": ["publish_date", "author", "URL accessibility"],
                    "result": "passed"
                }

            verified_findings.append(finding)
            print(f"  {i}/{len(findings)} {finding.get('claim', '')[:50]}... ✓")

        return verified_findings

    def _merge_and_rank(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        融合多路召回结果

        功能：
        1. URL 去重（基于 URL 核心部分）
        2. 保留高置信度的重复项
        3. 综合评分排序

        Args:
            findings: 多路召回的原始发现列表

        Returns:
            去重、评分、排序后的发现列表
        """
        # URL 去重（保留高置信度）
        seen_urls = {}
        unique_findings = []

        for finding in findings:
            for source in finding.get("sources", []):
                url = source.get("url", "")
                if not url:
                    continue

                # 提取 URL 核心
                core_url = self._extract_url_core(url)

                if core_url in seen_urls:
                    existing_conf = seen_urls[core_url].get("confidence_score", 0)
                    current_conf = finding.get("confidence_score", 0)
                    if current_conf > existing_conf:
                        unique_findings = [f for f in unique_findings if f != seen_urls[core_url]]
                        unique_findings.append(finding)
                        seen_urls[core_url] = finding
                else:
                    unique_findings.append(finding)
                    seen_urls[core_url] = finding

        # 综合评分排序
        # 优先级：source_type (docs > code > news > tavily > hotlist) > 新鲜度 > 置信度
        def rank_score(finding: Dict) -> float:
            source_type = finding.get("source_type", "")
            # 基础分（新增 code 和 tavily）
            base_scores = {
                "docs": 100,
                "code": 95,   # GitHub 代码高优先级
                "exa": 90,    # Exa 高质量代码搜索
                "academic": 90,
                "news": 80,
                "tavily": 75, # Tavily 降级结果略低
                "trendradar": 70,
                "hotlist": 60,
                "social": 55  # 社交媒体结果
            }
            base = base_scores.get(source_type, 40)

            # 置信度加成
            conf_score = finding.get("confidence_score", 0.5) * 20

            # 新鲜度加成
            if finding.get("freshness_status") == "current":
                freshness_bonus = 10
            else:
                freshness_bonus = 0

            return base + conf_score + freshness_bonus

        unique_findings.sort(key=rank_score, reverse=True)
        return unique_findings

    def _calculate_freshness(self, findings: List[Dict[str, Any]]) -> float:
        """
        计算新鲜度评分

        评分规则：
        - TrendRadar 热榜数据：默认高新鲜度（1.0）
        - GitHub 代码：默认高新鲜度（1.0）
        - Tavily 搜索：默认高新鲜度（1.0）
        - 6 个月内：0.9-1.0
        - 6-12 个月：0.7-0.9
        - 12-24 个月：0.5-0.7
        - 超过 24 个月：0.0-0.5
        """
        if not findings:
            return 0.0

        now = datetime.now()
        total_freshness = 0
        count = 0

        for finding in findings:
            # 新增：TrendRadar、GitHub 代码、Tavily 默认高新鲜度
            if finding.get("source_type") in ("trendradar", "code", "tavily"):
                total_freshness += 1.0
                count += 1
                continue

            for source in finding.get("sources", []):
                date_str = source.get("date", "")
                if not date_str:
                    continue

                try:
                    # 解析日期
                    if re.match(r"\d{4}-\d{2}-\d{2}", date_str):
                        date = datetime.strptime(date_str, "%Y-%m-%d")
                    else:
                        continue

                    # 计算月数差
                    months_diff = (now.year - date.year) * 12 + (now.month - date.month)

                    # 评分
                    if months_diff <= 6:
                        freshness = 1.0
                    elif months_diff <= 12:
                        freshness = 0.8
                    elif months_diff <= 24:
                        freshness = 0.6
                    else:
                        freshness = 0.3

                    total_freshness += freshness
                    count += 1

                except ValueError:
                    continue

        return round(total_freshness / count, 2) if count > 0 else 0.0

    def _extract_topic(self, query: str) -> str:
        """从查询中提取主题"""
        # 移除常见查询词
        topic = query
        for word in ["研究", "调研", "分析", "搜索", "查找", "找", "关于", "的"]:
            topic = topic.replace(word, "")

        return topic.strip()

    # ========== 置信度验证方法 ==========

    OFFICIAL_DOMAINS = [
        "anthropic.com", "openai.com", "arxiv.org",
        "developer.mozilla.org", "docs.python.org", "redis.io",
        "postgresql.org", "mongodb.com", "nginx.org",
        "kubernetes.io", "docker.com"
    ]

    def _extract_domain(self, url: str) -> Optional[str]:
        """从 URL 中提取域名"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.lower().replace("www.", "")
        except Exception:
            return None

    def _is_official_domain(self, url: str) -> bool:
        """检查 URL 是否属于官方域名"""
        domain = self._extract_domain(url)
        if not domain:
            return False
        return any(domain == d or domain.endswith(f".{d}") for d in self.OFFICIAL_DOMAINS)

    def _validate_confidence(self, evidence: List[Dict], confidence: str) -> bool:
        """
        统一的置信度验证规则

        规则：
        - FACT 标签需要 ≥2 个来源
        - BELIEF 标签需要至少 1 个官方/可信来源
        - ASSUMPTION 标签不需要强制验证

        Args:
            evidence: 证据来源列表
            confidence: 置信度类型 (FACT/BELIEF/ASSUMPTION)

        Returns:
            验证通过返回 True，否则抛出 ValueError

        Raises:
            ValueError: 验证失败时抛出
        """
        if confidence == "FACT":
            if len(evidence) < 2:
                raise ValueError(
                    f"FACT 标签需要 ≥2 个来源，当前仅有 {len(evidence)} 个"
                )

        if confidence == "BELIEF":
            if not evidence:
                raise ValueError("BELIEF 标签需要至少 1 个来源")

            # 检查是否有官方来源
            official = [e for e in evidence if self._is_official_domain(e.get("url", ""))]
            if not official:
                raise ValueError(
                    f"BELIEF 标签需要至少 1 个官方来源。"
                    f"当前来源: {[e.get('url', '') for e in evidence]}"
                )

        return True

    # ========== 资讯模式方法 ==========

    def search_news(
        self,
        query: str,
        days: int = 7,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        执行资讯搜集

        Args:
            query: 搜集主题
            days: 时间范围（天）
            limit: 结果数量限制

        Returns:
            包含资讯项、评分、去重结果的字典
        """
        print(f"📰 搜集主题: {query}")
        print(f"⏱ 时间范围: 近 {days} 天")
        print(f"🎯 目标数量: {limit} 条")

        # 构建搜索查询
        search_queries = self._build_search_queries(query, mode="news")

        # 执行搜索（模拟）
        findings = self._simulate_news_search(search_queries, limit)

        # 去重
        findings = self._deduplicate_by_url(findings)

        # 评分和排序
        findings = self._score_and_sort(findings)

        # 限制结果数量
        findings = findings[:limit]

        return {
            "query": query,
            "mode": "news",
            "days": days,
            "findings": findings,
            "total_found": len(findings),
            "search_timestamp": datetime.now().isoformat()
        }

    def _build_search_queries(self, query: str, mode: str) -> List[str]:
        """构建搜索查询"""
        if mode == "news":
            # 资讯模式：英文关键词 + 时间过滤
            keywords_en = self._translate_to_english(query)
            current_month = datetime.now().strftime('%Y-%m')
            current_year = datetime.now().strftime('%Y')
            return [
                f"{keywords_en} news latest {current_month}",
                f"{keywords_en} blog posts recent",
                f"{keywords_en} updates {current_year}"
            ]
        else:
            return [query]

    def _translate_to_english(self, query: str) -> str:
        """简单关键词翻译"""
        translations = {
            "人工智能": "AI", "机器学习": "machine learning",
            "深度学习": "deep learning", "大模型": "LLM",
            "智能体": "AI agent", "代理": "agent",
            "自然语言处理": "NLP", "计算机视觉": "computer vision"
        }
        result = query
        for zh, en in translations.items():
            result = result.replace(zh, en)
        return result

    def _simulate_news_search(self, queries: List[str], limit: int) -> List[Dict[str, Any]]:
        """模拟资讯搜索（实际使用 MCP 工具）"""
        findings = []
        topic = queries[0].split()[0] if queries else "AI"

        # 生成模拟资讯项
        for i in range(min(limit, 20)):
            finding = {
                "claim": f"{topic} 最新进展 #{i+1}: 技术突破与行业应用",
                "summary_zh": f"这是关于 {topic} 的最新资讯摘要，包含技术突破、产品更新和行业动态。",
                "sources": [
                    {
                        "title": f"{topic} News #{i+1}",
                        "url": f"https://example.com/news/{i+1}",
                        "date": (datetime.now() - timedelta(days=i*2)).strftime("%Y-%m-%d"),
                        "confidence": "high" if i % 3 == 0 else "medium",
                        "excerpt": f"{topic} 相关的最新资讯内容..."
                    }
                ],
                "news_score": 7.0 + (i % 4),
                "score_breakdown": {
                    "innovation": 5 + (i % 5),
                    "practicality": 5 + ((i + 1) % 5),
                    "impact": 7 + ((i + 2) % 3)
                },
                "confidence_type": "FACT" if i % 3 == 0 else "BELIEF",
                "confidence_score": 0.7 + (i % 4) * 0.05,
                "freshness_status": "current"
            }
            findings.append(finding)

        return findings

    def _deduplicate_by_url(self, findings: List[Dict]) -> List[Dict]:
        """URL 相似度去重"""
        seen_urls = {}
        unique_findings = []

        for finding in findings:
            for source in finding.get("sources", []):
                url = source.get("url", "")
                if not url:
                    continue

                core_url = self._extract_url_core(url)

                if core_url in seen_urls:
                    existing_conf = seen_urls[core_url].get("confidence_score", 0)
                    current_conf = finding.get("confidence_score", 0)
                    if current_conf > existing_conf:
                        unique_findings = [f for f in unique_findings if f != seen_urls[core_url]]
                        unique_findings.append(finding)
                        seen_urls[core_url] = finding
                else:
                    unique_findings.append(finding)
                    seen_urls[core_url] = finding

        return unique_findings

    def _extract_url_core(self, url: str) -> str:
        """提取 URL 核心部分"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        path = parsed.path.rstrip("/")
        return f"{domain}{path}"

    def _score_and_sort(self, findings: List[Dict]) -> List[Dict]:
        """资讯评分算法（0-10 分）"""
        scored_findings = []

        for finding in findings:
            title = finding.get("claim", "")
            sources = finding.get("sources", [])

            innovation = self._calculate_innovation_score(title)
            practicality = self._calculate_practicality_score(title)
            impact = self._calculate_impact_score(sources)

            total_score = innovation * 0.3 + practicality * 0.3 + impact * 0.4

            finding["news_score"] = round(total_score, 1)
            finding["score_breakdown"] = {
                "innovation": innovation,
                "practicality": practicality,
                "impact": impact
            }
            scored_findings.append(finding)

        scored_findings.sort(key=lambda x: x.get("news_score", 0), reverse=True)
        return scored_findings

    def _calculate_innovation_score(self, title: str) -> float:
        """创新性评分"""
        keywords = [
            "new", "breakthrough", "revolutionary", "first", "novel",
            "unprecedented", "groundbreaking", "GPT-5", "Claude 4",
            "最新", "突破", "革命性"
        ]
        matches = sum(1 for kw in keywords if kw.lower() in title.lower())
        return min(5 + matches, 10)

    def _calculate_practicality_score(self, title: str) -> float:
        """实用性评分"""
        keywords = [
            "tutorial", "guide", "how-to", "practical", "use case",
            "improves", "boosts", "enhances", "reduces",
            "教程", "指南", "实践", "应用", "提升"
        ]
        matches = sum(1 for kw in keywords if kw.lower() in title.lower())
        return min(5 + matches, 10)

    def _calculate_impact_score(self, sources: List[Dict]) -> float:
        """影响力评分"""
        if not sources:
            return 5.0
        scores = {"official": 10, "high": 9, "medium": 7}
        return max(float(scores.get(s.get("confidence", "medium"), 5)) for s in sources)

    # ========== 原有方法 ==========

    def export_markdown(self, output_path: str, use_obsidian: bool = False,
                       topic: str = None, platforms: List[str] = None) -> Optional[str]:
        """
        将研究结果导出为 Markdown 格式

        Args:
            output_path: 输出文件路径（传统模式）或基础目录（Obsidian 模式）
            use_obsidian: 是否使用 Obsidian 格式
            topic: 研究主题（Obsidian 模式需要）
            platforms: 目标平台列表（Obsidian 模式需要）

        Returns:
            Obsidian 模式下返回研究引用路径，传统模式返回 None
        """
        # 计算新鲜度评分
        freshness_score = self._calculate_freshness(self.findings)

        if use_obsidian and OBSIDIAN_UTILS_AVAILABLE:
            return self._export_obsidian_markdown(output_path, topic, platforms, freshness_score)
        else:
            self._export_traditional_markdown(output_path, freshness_score)
            return None

    def _export_traditional_markdown(self, output_path: str, freshness_score: float) -> None:
        """传统 Markdown 导出"""
        md_lines = [
            f"# 研究报告",
            f"\n## 查询",
            f"{self.findings[0].get('query', 'N/A') if self.findings else 'N/A'}",
            f"\n## 研究时间",
            f"{self.search_timestamp}",
            f"\n## 工具使用",
            f", ".join(f"`{tool}`" for tool in self.tools_used),
            f"\n## 新鲜度评分",
            f"{freshness_score:.2f}/1.0",
            f"\n## 研究发现",
        ]

        for i, finding in enumerate(self.findings, 1):
            md_lines.extend([
                f"\n### {i}. {finding.get('claim', '')}",
                f"\n**来源类型：** {finding.get('source_type', 'unknown')}",
                f"\n**验证分数：** {finding.get('confidence', 'N/A')}",
                f"\n**资料来源：**",
                ""
            ])

            for j, source in enumerate(finding.get("sources", []), 1):
                md_lines.extend([
                    f"{j}. [{source.get('title', 'N/A')}]",
                    f"   - **URL：** {source.get('url', 'N/A')}",
                    f"   - **日期：** {source.get('date', 'N/A')}",
                    f"   - **置信度：** {source.get('confidence', 'N/A')}",
                    f"   - **摘要：** {source.get('excerpt', '')[:100]}{'...' if len(source.get('excerpt', '')) > 100 else ''}",
                    ""
                ])

            if finding.get("additional_verification"):
                md_lines.extend([
                    f"\n**额外验证：**",
                    f"- 方法：{finding['additional_verification']['method']}",
                    f"- 结果：{finding['additional_verification']['result']}",
                    ""
                ])

        # 写入文件
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))

        print(f"\n✅ Markdown 报告已保存到: {output_path}")

    def _export_obsidian_markdown(self, base_dir: str, topic: str,
                                  platforms: List[str], freshness_score: float) -> str:
        """
        Obsidian 格式 Markdown 导出

        Args:
            base_dir: 基础目录（用于生成完整路径）
            topic: 研究主题
            platforms: 目标平台列表
            freshness_score: 新鲜度评分

        Returns:
            Obsidian 研究引用路径
        """
        from obsidian_utils import (
            generate_obsidian_frontmatter,
            create_obsidian_index_content,
            write_frontmatter,
            get_obsidian_research_ref
        )

        # 确保目录存在
        output_dir = Path(base_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 生成 frontmatter
        frontmatter = generate_obsidian_frontmatter(
            topic=topic,
            status="completed",
            platforms=platforms or ["wechat", "xhs"],
            tools_used=self.tools_used,
            confidence_level="HIGH",
            findings_count=len(self.findings),
            freshness_score=freshness_score
        )

        # 生成正文内容
        body = create_obsidian_index_content(
            topic=topic,
            findings=self.findings,
            tools_used=self.tools_used,
            freshness_score=freshness_score
        )

        # 组合完整内容
        full_content = write_frontmatter(frontmatter, body)

        # 写入 index.md
        index_path = output_dir / "index.md"
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(full_content)

        # 同时生成 citations.md 用于引用列表
        citations_path = output_dir / "citations.md"
        self._export_citations_file(citations_path)

        print(f"\n✅ Obsidian 研究报告已保存到: {output_dir}")
        print(f"   主文件: {index_path.name}")
        print(f"   引用文件: {citations_path.name}")

        # 返回 Obsidian 引用路径
        return get_obsidian_research_ref(topic)

    def _export_citations_file(self, output_path: Path) -> None:
        """导出引用列表文件"""
        lines = ["# 引用来源", ""]

        for i, finding in enumerate(self.findings, 1):
            for j, source in enumerate(finding.get("sources", []), 1):
                lines.extend([
                    f"## [{i}.{j}] {source.get('title', 'N/A')}",
                    "",
                    f"- **URL**: {source.get('url', 'N/A')}",
                    f"- **日期**: {source.get('date', 'N/A')}",
                    f"- **置信度**: {source.get('confidence', 'N/A')}",
                    f"- **来源类型**: {finding.get('source_type', 'unknown')}",
                    "",
                    f"> {source.get('excerpt', '')}",
                    "",
                    "---",
                    ""
                ])

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


def format_output(results: Dict[str, Any], pretty: bool = True) -> str:
    """格式化输出"""
    if pretty:
        return json.dumps(results, indent=2, ensure_ascii=False)
    return json.dumps(results, ensure_ascii=False)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="内容创作调研 - 深度网络搜索与引用")

    # 互斥组：--idea 和 --news
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--idea", "-i",
        help="深度研究模式：接受明确标题或模糊想法"
    )
    mode_group.add_argument(
        "--news", "-n",
        help="资讯模式：搜集指定主题的最新资讯"
    )

    # 资讯模式专用参数
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=7,
        help="资讯时间范围（天），仅资讯模式有效（默认: 7，范围: 1-30）"
    )

    # 通用参数
    parser.add_argument(
        "--limit", "-l",
        type=int,
        help="结果数量限制（深度模式默认: 10，资讯模式默认: 50）"
    )

    # 兼容性参数（保留但标记为已弃用）
    parser.add_argument(
        "--query", "-q",
        help="[已弃用] 研究问题/主题（已被 --idea 替代，保留兼容性）"
    )
    parser.add_argument(
        "--source-types", "-s",
        nargs="*",
        choices=["academic", "docs", "news", "social"],
        help="来源类型（默认：自动推断）"
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=3,
        help="搜索深度（默认: 3）"
    )
    parser.add_argument(
        "--output", "-o",
        help="输出文件路径（默认: stdout）"
    )
    parser.add_argument(
        "--markdown", "-m",
        action="store_true",
        help="导出 Markdown 格式报告"
    )
    parser.add_argument(
        "--no-pretty",
        action="store_true",
        help="不格式化 JSON 输出"
    )
    parser.add_argument(
        "--check-ambiguous",
        action="store_true",
        help="仅检测输入是否为模糊想法（用于测试）"
    )
    parser.add_argument(
        "--obsidian",
        action="store_true",
        help="使用 Obsidian 存储模式（默认: 传统模式）"
    )
    parser.add_argument(
        "--platforms",
        nargs="+",
        default=["wechat", "xhs"],
        help="目标平台列表（Obsidian 模式使用，默认: wechat xhs）"
    )

    args = parser.parse_args()

    # 模式检测和参数验证
    if args.news:
        mode = "news"
        query = args.news
        # 验证 days 参数
        if not (1 <= args.days <= 30):
            parser.error("--days 必须在 1-30 之间")
        limit = args.limit or 50
        depth = 1  # 资讯模式使用浅层搜索
        print(f"\n📰 资讯模式：搜集 '{query}' 近 {args.days} 天的资讯")
    else:
        mode = "idea"
        # 兼容性：支持 --query 作为 --idea 的别名
        query = args.idea if args.idea else args.query
        if not query:
            parser.error("必须提供 --idea 参数（或使用 --query 保持兼容性）")
        limit = args.limit or 10
        depth = args.depth

    # 创建搜索器实例
    searcher = ResearchSearcher()

    # 资讯模式：执行资讯搜集
    if mode == "news":
        results = searcher.search_news(
            query=query,
            days=args.days,
            limit=limit
        )
        # 输出结果
        output = format_output(results, pretty=not args.no_pretty)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"\n✅ 资讯结果已保存到: {args.output}")
        else:
            print(output)
        return

    # 深度模式：检测模糊输入
    if hasattr(args, 'check_ambiguous') and args.check_ambiguous:
        is_ambig = searcher.is_ambiguous_input(query)
        print(f"\n输入: {query}")
        if is_ambig:
            print("模糊输入: 是")
        else:
            print("模糊输入: 否")
        return
    if searcher.is_ambiguous_input(query):
        print(f"\n🔍 检测到模糊输入，执行意图解析...")
        intent_result = searcher.parse_ambiguous_idea(query)

        print(f"\n✓ 解析完成:")
        print(f"  - 核心话题: {intent_result['core_topic']}")
        print(f"  - 目标读者: {intent_result['target_audience']}")
        print(f"  - 建议角度数量: {len(intent_result['suggested_angles'])}")

        for i, angle in enumerate(intent_result['suggested_angles'], 1):
            print(f"\n{ i}. 角度: {angle['name']}")
            print(f"   类型: {angle['type']}")
            print(f"   描述: {angle['description']}")

        # 导出 JSON 格式
        if args.output or not args.markdown:
            import sys
            output = json.dumps(intent_result, indent=2, ensure_ascii=False)
            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(output)
                print(f"\n✅ 意图解析结果已保存到: {args.output}")
            else:
                print(output)
        return

    # 执行标准搜索（明确标题输入）
    print(f"\n🔍 执行标准研究搜索: {query}")
    results = searcher.search(
        query=query,
        source_types=args.source_types,
        depth=depth
    )

    # 处理 Obsidian 模式路径和降级
    use_obsidian = args.obsidian
    output_path = args.output
    warning_message = ""

    if args.markdown and hasattr(searcher, 'findings') and searcher.findings:
        if use_obsidian and OBSIDIAN_UTILS_AVAILABLE:
            # 检查 Obsidian 模式是否可用
            from obsidian_utils import get_fallback_path
            output_path, use_obsidian, warning_message = get_fallback_path(query, True)
            if warning_message:
                print(f"\n{warning_message}")
        elif use_obsidian and not OBSIDIAN_UTILS_AVAILABLE:
            print("\n⚠️  Obsidian 工具模块不可用，降级到传统模式")
            use_obsidian = False
            output_path = args.output if args.output else "research_report.md"
        else:
            output_path = args.output if args.output else "research_report.md"

        # 导出 Markdown
        research_ref = searcher.export_markdown(
            output_path,
            use_obsidian=use_obsidian,
            topic=query,
            platforms=args.platforms
        )

        # Obsidian 模式下输出引用路径
        if use_obsidian and research_ref:
            print(f"\n📎 Obsidian 引用路径: [[{research_ref}]]")
        return

    # 输出 JSON 结果
    output = format_output(results, pretty=not args.no_pretty)

    if args.output and not args.markdown:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"\n✅ 结果已保存到: {args.output}")
    elif not args.markdown:
        print(output)


if __name__ == "__main__":
    main()
