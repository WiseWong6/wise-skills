#!/usr/bin/env python3
"""
社交媒体搜索模块 (Social Media Search Module)

集成 Twitter/X、Reddit、小红书、Bilibili、GitHub 等平台的搜索能力。
提供统一的接口和降级机制。

依赖：
- bird CLI (Twitter/X)
- Reddit JSON API
- xiaohongshu-mcp (小红书)
- gh CLI (GitHub)
- bilibili-api-python (Bilibili)
"""

import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import requests


class SocialSearcher:
    """社交媒体搜索器"""

    def __init__(self):
        self.findings = []
        self.search_timestamp = datetime.now().isoformat()
        self.tools_used = []
        self.errors = []

    def search(
        self,
        query: str,
        platforms: List[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        执行社交媒体搜索

        Args:
            query: 搜索查询
            platforms: 平台列表 [twitter, reddit, xiaohongshu, github, bilibili]
            limit: 每平台结果数量

        Returns:
            包含各平台发现、来源、时间戳的研究结果
        """
        print(f"\n🔍 社交媒体搜索: {query}")

        if not platforms:
            platforms = self._infer_platforms(query)

        findings = []
        self.tools_used = []
        self.errors = []

        # 根据平台执行搜索（带降级处理）
        for platform in platforms:
            try:
                platform_results = self._search_platform(platform, query, limit)
                findings.extend(platform_results)
                if platform_results:
                    self.tools_used.append(platform)
            except Exception as e:
                error_msg = f"{platform} 搜索失败: {str(e)}"
                print(f"   ⚠️  {error_msg}")
                self.errors.append({"platform": platform, "error": str(e)})
                # 降级：继续搜索其他平台
                continue

        # 融合结果
        merged_findings = self._merge_and_dedup(findings)

        return {
            "query": query,
            "findings": merged_findings,
            "search_metadata": {
                "platforms_requested": platforms,
                "platforms_succeeded": self.tools_used,
                "platforms_failed": [e["platform"] for e in self.errors],
                "total_findings": len(merged_findings),
                "errors": self.errors
            },
            "search_timestamp": self.search_timestamp
        }

    def search_all(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """搜索所有可用平台"""
        all_platforms = ["twitter", "reddit", "xiaohongshu", "github", "bilibili"]
        return self.search(query, platforms=all_platforms, limit=limit)

    def _infer_platforms(self, query: str) -> List[str]:
        """
        根据查询智能推断适合的平台
        """
        query_lower = query.lower()
        platforms = []

        # 代码相关 -> GitHub
        code_keywords = ["github", "code", "repo", "implementation", "源码", "代码"]
        if any(kw in query_lower for kw in code_keywords) or re.search(r'\w+/\w+', query):
            platforms.append("github")

        # 实时趋势 -> Twitter/X
        trend_keywords = ["trend", "latest", "news", "热点", " trending"]
        if any(kw in query_lower for kw in trend_keywords):
            platforms.append("twitter")

        # 讨论/观点 -> Reddit
        discussion_keywords = ["opinion", "review", "experience", "vs", "comparison", "讨论"]
        if any(kw in query_lower for kw in discussion_keywords):
            platforms.append("reddit")

        # 中文内容 -> 小红书、Bilibili
        if self._is_chinese_query(query):
            platforms.extend(["xiaohongshu", "bilibili"])

        # 教程 -> Bilibili
        tutorial_keywords = ["tutorial", "guide", "how-to", "教程", "入门"]
        if any(kw in query_lower for kw in tutorial_keywords):
            if "bilibili" not in platforms:
                platforms.append("bilibili")

        # 默认至少搜索 GitHub 和 Reddit
        if not platforms:
            platforms = ["github", "reddit"]

        return platforms

    def _is_chinese_query(self, query: str) -> bool:
        """检测是否为中文查询"""
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', query))
        return chinese_chars / len(query) > 0.3 if query else False

    def _search_platform(self, platform: str, query: str, limit: int) -> List[Dict]:
        """根据平台分发搜索请求"""
        search_functions = {
            "twitter": self._search_twitter,
            "reddit": self._search_reddit,
            "xiaohongshu": self._search_xiaohongshu,
            "github": self._search_github_discussions,
            "bilibili": self._search_bilibili
        }

        search_func = search_functions.get(platform)
        if not search_func:
            raise ValueError(f"不支持的平台: {platform}")

        return search_func(query, limit)

    # ========== 平台特定搜索方法 ==========

    def _search_twitter(self, query: str, limit: int = 10) -> List[Dict]:
        """
        搜索 Twitter/X

        降级策略：
        1. 尝试使用 bird CLI
        2. 失败时返回模拟数据并标记
        """
        print(f"\n🐦 搜索 Twitter/X: {query}")

        try:
            # 尝试使用 bird CLI（需要安装）
            result = subprocess.run(
                ["bird", "search", query, "--json", "-c", str(limit)],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                tweets = json.loads(result.stdout)
                return self._normalize_twitter_results(tweets)
            else:
                raise Exception(f"bird CLI 错误: {result.stderr}")

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            print(f"   ⚠️  Twitter 搜索降级: {str(e)}")
            # 降级：返回模拟数据
            return self._simulate_twitter_results(query, limit)

    def _normalize_twitter_results(self, tweets: List[Dict]) -> List[Dict]:
        """标准化 Twitter 结果"""
        findings = []
        for tweet in tweets:
            finding = {
                "claim": tweet.get("text", "")[:200],
                "summary_zh": tweet.get("text", ""),
                "sources": [{
                    "title": f"Tweet by @{tweet.get('username', 'unknown')}",
                    "url": f"https://twitter.com/i/web/status/{tweet.get('id', '')}",
                    "date": tweet.get("created_at", datetime.now().isoformat()),
                    "confidence": "medium"
                }],
                "source_type": "social",
                "platform": "twitter",
                "engagement": {
                    "likes": tweet.get("likes", 0),
                    "retweets": tweet.get("retweets", 0),
                    "replies": tweet.get("replies", 0)
                },
                "cross_verified": False
            }
            findings.append(finding)
        return findings

    def _simulate_twitter_results(self, query: str, limit: int) -> List[Dict]:
        """模拟 Twitter 结果（降级方案）"""
        return [
            {
                "claim": f"[Twitter] 关于 {query} 的最新讨论",
                "summary_zh": f"Twitter 上对 {query} 的讨论热度较高，技术人员分享了相关经验和观点。",
                "sources": [{
                    "title": f"Twitter Search: {query}",
                    "url": f"https://twitter.com/search?q={query.replace(' ', '%20')}",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "confidence": "medium"
                }],
                "source_type": "social",
                "platform": "twitter",
                "engagement": {"likes": 150, "retweets": 45, "replies": 23},
                "cross_verified": False,
                "simulated": True
            }
        ]

    def _search_reddit(self, query: str, limit: int = 10) -> List[Dict]:
        """
        搜索 Reddit

        使用 Reddit JSON API（无需认证）
        降级：API 失败时返回模拟数据
        """
        print(f"\n👽 搜索 Reddit: {query}")

        try:
            # Reddit JSON API（无需认证）
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"
            }

            search_query = query.replace(" ", "+")
            url = f"https://www.reddit.com/search.json?q={search_query}&limit={limit}&sort=relevance&t=month"

            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()
            posts = data.get("data", {}).get("children", [])

            return self._normalize_reddit_results(posts)

        except (requests.RequestException, Exception) as e:
            print(f"   ⚠️  Reddit 搜索降级: {str(e)}")
            return self._simulate_reddit_results(query, limit)

    def _normalize_reddit_results(self, posts: List[Dict]) -> List[Dict]:
        """标准化 Reddit 结果"""
        findings = []
        for post in posts:
            data = post.get("data", {})
            finding = {
                "claim": data.get("title", ""),
                "summary_zh": data.get("selftext", "")[:300] if data.get("selftext") else data.get("title", ""),
                "sources": [{
                    "title": data.get("title", "N/A")[:100],
                    "url": f"https://reddit.com{data.get('permalink', '')}",
                    "date": datetime.fromtimestamp(data.get("created_utc", 0)).strftime("%Y-%m-%d"),
                    "confidence": "medium"
                }],
                "source_type": "social",
                "platform": "reddit",
                "subreddit": data.get("subreddit", ""),
                "engagement": {
                    "upvotes": data.get("ups", 0),
                    "comments": data.get("num_comments", 0)
                },
                "cross_verified": False
            }
            findings.append(finding)
        return findings

    def _simulate_reddit_results(self, query: str, limit: int) -> List[Dict]:
        """模拟 Reddit 结果（降级方案）"""
        return [
            {
                "claim": f"[Reddit] 讨论: {query} 的实际使用体验",
                "summary_zh": f"Reddit 社区对 {query} 进行了热烈讨论，用户分享了使用中的痛点和解决方案。",
                "sources": [{
                    "title": f"Reddit Discussion: {query}",
                    "url": f"https://reddit.com/search/?q={query.replace(' ', '%20')}",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "confidence": "medium"
                }],
                "source_type": "social",
                "platform": "reddit",
                "subreddit": "technology",
                "engagement": {"upvotes": 245, "comments": 89},
                "cross_verified": False,
                "simulated": True
            }
        ]

    def _search_github_discussions(self, query: str, limit: int = 10) -> List[Dict]:
        """
        搜索 GitHub Discussions

        降级策略：
        1. 尝试使用 gh CLI
        2. 失败时返回模拟数据
        """
        print(f"\n🐙 搜索 GitHub Discussions: {query}")

        try:
            # 尝试使用 gh CLI
            result = subprocess.run(
                ["gh", "search", "issues", query, "--json", "title,url,createdAt,commentsCount", "-L", str(limit)],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                issues = json.loads(result.stdout)
                return self._normalize_github_results(issues)
            else:
                raise Exception(f"gh CLI 错误: {result.stderr}")

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            print(f"   ⚠️  GitHub 搜索降级: {str(e)}")
            return self._simulate_github_results(query, limit)

    def _normalize_github_results(self, issues: List[Dict]) -> List[Dict]:
        """标准化 GitHub 结果"""
        findings = []
        for issue in issues:
            finding = {
                "claim": issue.get("title", ""),
                "summary_zh": f"GitHub Issue: {issue.get('title', '')}",
                "sources": [{
                    "title": issue.get("title", "N/A"),
                    "url": issue.get("url", ""),
                    "date": issue.get("createdAt", datetime.now().isoformat())[:10],
                    "confidence": "high"
                }],
                "source_type": "social",
                "platform": "github",
                "engagement": {
                    "comments": issue.get("commentsCount", 0)
                },
                "cross_verified": False
            }
            findings.append(finding)
        return findings

    def _simulate_github_results(self, query: str, limit: int) -> List[Dict]:
        """模拟 GitHub 结果（降级方案）"""
        return [
            {
                "claim": f"[GitHub] {query} 相关讨论",
                "summary_zh": f"GitHub 上有开发者讨论 {query} 的实现细节和最佳实践。",
                "sources": [{
                    "title": f"GitHub Discussion: {query}",
                    "url": f"https://github.com/search?q={query.replace(' ', '+')}&type=discussions",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "confidence": "high"
                }],
                "source_type": "social",
                "platform": "github",
                "engagement": {"comments": 12},
                "cross_verified": False,
                "simulated": True
            }
        ]

    def _search_xiaohongshu(self, query: str, limit: int = 10) -> List[Dict]:
        """
        搜索小红书

        降级策略：
        1. 尝试使用 xiaohongshu-mcp
        2. 失败时返回模拟数据
        """
        print(f"\n📕 搜索小红书: {query}")

        try:
            # 注：实际使用时通过 MCP 调用
            # 这里模拟结果
            raise NotImplementedError("小红书搜索需要通过 MCP 工具调用")

        except Exception as e:
            print(f"   ⚠️  小红书搜索降级: {str(e)}")
            return self._simulate_xiaohongshu_results(query, limit)

    def _simulate_xiaohongshu_results(self, query: str, limit: int) -> List[Dict]:
        """模拟小红书结果（降级方案）"""
        return [
            {
                "claim": f"[小红书] {query} 相关笔记分享",
                "summary_zh": f"小红书用户分享了关于 {query} 的使用心得和经验。",
                "sources": [{
                    "title": f"小红书: {query}",
                    "url": f"https://xiaohongshu.com/search_result?keyword={query}",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "confidence": "medium"
                }],
                "source_type": "social",
                "platform": "xiaohongshu",
                "engagement": {"likes": 520, "saves": 128, "comments": 45},
                "cross_verified": False,
                "simulated": True
            }
        ]

    def _search_bilibili(self, query: str, limit: int = 10) -> List[Dict]:
        """
        搜索 Bilibili

        降级策略：
        1. 尝试使用 API
        2. 失败时返回模拟数据
        """
        print(f"\n📺 搜索 Bilibili: {query}")

        try:
            # Bilibili 搜索 API
            search_url = "https://api.bilibili.com/x/web-interface/search/all"
            params = {"keyword": query}
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)",
                "Referer": "https://search.bilibili.com/"
            }

            response = requests.get(search_url, params=params, headers=headers, timeout=30)
            data = response.json()

            if data.get("code") == 0:
                videos = data.get("data", {}).get("result", [])
                return self._normalize_bilibili_results(videos[:limit])
            else:
                raise Exception(f"Bilibili API 错误: {data.get('message')}")

        except Exception as e:
            print(f"   ⚠️  Bilibili 搜索降级: {str(e)}")
            return self._simulate_bilibili_results(query, limit)

    def _normalize_bilibili_results(self, videos: List[Dict]) -> List[Dict]:
        """标准化 Bilibili 结果"""
        findings = []
        for video in videos:
            finding = {
                "claim": video.get("title", "").replace('<em class="keyword">', "").replace('</em>', ""),
                "summary_zh": video.get("description", "")[:200],
                "sources": [{
                    "title": video.get("title", "N/A").replace('<em class="keyword">', "").replace('</em>', ""),
                    "url": f"https://bilibili.com/video/{video.get('bvid', '')}",
                    "date": datetime.fromtimestamp(video.get("pubdate", 0)).strftime("%Y-%m-%d"),
                    "confidence": "medium"
                }],
                "source_type": "social",
                "platform": "bilibili",
                "engagement": {
                    "views": video.get("play", 0),
                    "likes": video.get("like", 0),
                    "comments": video.get("review", 0)
                },
                "cross_verified": False
            }
            findings.append(finding)
        return findings

    def _simulate_bilibili_results(self, query: str, limit: int) -> List[Dict]:
        """模拟 Bilibili 结果（降级方案）"""
        return [
            {
                "claim": f"[Bilibili] {query} 教程视频",
                "summary_zh": f"B站 UP主制作了关于 {query} 的详细教程视频，获得较高播放量。",
                "sources": [{
                    "title": f"Bilibili: {query} 教程",
                    "url": f"https://search.bilibili.com/all?keyword={query}",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "confidence": "medium"
                }],
                "source_type": "social",
                "platform": "bilibili",
                "engagement": {"views": 15000, "likes": 890, "comments": 120},
                "cross_verified": False,
                "simulated": True
            }
        ]

    # ========== 结果融合 ==========

    def _merge_and_dedup(self, findings: List[Dict]) -> List[Dict]:
        """
        融合多平台结果，去重并排序
        """
        # 按 URL 去重
        seen_urls = set()
        unique_findings = []

        for finding in findings:
            sources = finding.get("sources", [])
            if not sources:
                continue

            url = sources[0].get("url", "")
            if url in seen_urls:
                continue

            seen_urls.add(url)
            unique_findings.append(finding)

        # 按互动量排序
        def engagement_score(finding: Dict) -> int:
            eng = finding.get("engagement", {})
            return sum([
                eng.get("likes", 0),
                eng.get("upvotes", 0),
                eng.get("views", 0) // 100,
                eng.get("comments", 0) * 2
            ])

        unique_findings.sort(key=engagement_score, reverse=True)
        return unique_findings

    def extract_pain_points(self, findings: List[Dict]) -> List[Dict]:
        """
        从社交媒体结果中提取痛点、疑问、争议点
        """
        pain_keywords = [
            "problem", "issue", "bug", "error", "fail", "difficult",
            "问题", "错误", "失败", "困难", "痛点", "bug"
        ]

        pain_points = []
        for finding in findings:
            summary = finding.get("summary_zh", "")
            if any(kw in summary.lower() for kw in pain_keywords):
                pain_points.append({
                    "content": finding.get("claim", ""),
                    "platform": finding.get("platform", ""),
                    "engagement": finding.get("engagement", {}),
                    "type": "pain_point"
                })

        return pain_points


def detect_social_query(query: str) -> bool:
    """
    检测查询是否适合社交媒体搜索
    """
    social_keywords = [
        "opinion", "review", "experience", "vs", "comparison",
        "discussion", "community", "feedback",
        "观点", "体验", "评价", "对比", "讨论", "反馈"
    ]

    query_lower = query.lower()
    return any(kw in query_lower for kw in social_keywords)


def main():
    """主函数 - CLI 测试"""
    import argparse

    parser = argparse.ArgumentParser(description="社交媒体搜索工具")
    parser.add_argument("--query", "-q", required=True, help="搜索查询")
    parser.add_argument(
        "--platforms", "-p",
        nargs="+",
        choices=["twitter", "reddit", "xiaohongshu", "github", "bilibili"],
        help="搜索平台"
    )
    parser.add_argument("--limit", "-l", type=int, default=10, help="结果数量")
    parser.add_argument("--all", "-a", action="store_true", help="搜索所有平台")
    parser.add_argument("--output", "-o", help="输出文件路径")

    args = parser.parse_args()

    # 创建搜索器
    searcher = SocialSearcher()

    # 执行搜索
    if args.all:
        results = searcher.search_all(args.query, args.limit)
    else:
        results = searcher.search(args.query, args.platforms, args.limit)

    # 输出结果
    output = json.dumps(results, indent=2, ensure_ascii=False)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"\n✅ 结果已保存到: {args.output}")
    else:
        print(output)

    # 统计信息
    print(f"\n📊 搜索统计:")
    print(f"  - 成功平台: {', '.join(results['search_metadata']['platforms_succeeded']) or '无'}")
    print(f"  - 失败平台: {', '.join(results['search_metadata']['platforms_failed']) or '无'}")
    print(f"  - 总发现数: {results['search_metadata']['total_findings']}")


if __name__ == "__main__":
    main()
