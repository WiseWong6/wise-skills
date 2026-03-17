"""
向量检索服务客户端

统一的向量检索接口，供 article-create-rag 和 article-plug-classicLines 使用
"""

import os
import requests
from typing import List, Dict, Optional

# 服务地址
VECTOR_SERVICE_URL = os.environ.get("VECTOR_SERVICE_URL", "http://localhost:8080")


class VectorServiceClient:
    """向量检索服务客户端"""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or VECTOR_SERVICE_URL

    def search(
        self,
        query: str,
        top_k: int = 10,
        source: Optional[str] = None
    ) -> List[Dict]:
        """
        语义检索

        Args:
            query: 查询文本
            top_k: 返回结果数量
            source: 来源过滤（"金句库" 或 "文章库"）

        Returns:
            检索结果列表，格式：
            [
                {
                    "id": "...",
                    "content": "...",
                    "source": "金句库",
                    "category": "...",
                    "score": 0.95,
                    "metadata": {...}
                },
                ...
            ]
        """
        payload = {
            "query": query,
            "top_k": top_k
        }

        if source:
            payload["filter"] = {"source": source}

        try:
            response = requests.post(
                f"{self.base_url}/search",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except Exception as e:
            print(f"向量检索失败: {e}")
            return []

    def search_articles(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        检索文章库

        Args:
            query: 查询文本
            top_k: 返回结果数量

        Returns:
            文章片段列表，兼容 article-create-rag 格式
        """
        results = self.search(query, top_k, source="文章库")

        # 转换为 article-create-rag 兼容格式
        formatted = []
        for r in results:
            metadata = r.get("metadata", {})
            formatted.append({
                "文章标题": metadata.get("source_title", ""),
                "公众号": metadata.get("author", metadata.get("source_account", "")),
                "内容": r.get("content", ""),
                "relevance": int(r.get("score", 0) * 10),
                "source": "文章库",
            })
        return formatted

    def search_quotes(
        self,
        query: str,
        top_k: int = 10,
        quality_threshold: float = 5.0
    ) -> List[Dict]:
        """
        检索金句库

        Args:
            query: 查询文本
            top_k: 返回结果数量
            quality_threshold: 质量分阈值

        Returns:
            金句列表，兼容 article-plug-classicLines 格式
        """
        results = self.search(query, top_k, source="金句库")

        # 过滤质量分
        filtered = []
        for r in results:
            metadata = r.get("metadata", {})
            quality = metadata.get("quality_score", {}).get("overall", 0)
            if quality >= quality_threshold:
                filtered.append({
                    "content": r.get("content", ""),
                    "metadata": {
                        "author": metadata.get("author", metadata.get("source_account", "")),
                        "title": metadata.get("source_title", ""),
                        "quality": quality,
                        "url": metadata.get("source_url", ""),
                        "category": metadata.get("category", ""),
                    },
                    "score": r.get("score", 0),
                })
        return filtered

    def health_check(self) -> bool:
        """检查服务健康状态"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def get_stats(self) -> Dict:
        """获取服务统计信息"""
        try:
            response = requests.get(f"{self.base_url}/stats", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"获取统计信息失败: {e}")
            return {}


# 全局客户端实例
_client: Optional[VectorServiceClient] = None


def get_client() -> VectorServiceClient:
    """获取全局客户端实例"""
    global _client
    if _client is None:
        _client = VectorServiceClient()
    return _client


def search_articles(query: str, top_k: int = 5) -> List[Dict]:
    """便捷函数：检索文章库"""
    return get_client().search_articles(query, top_k)


def search_quotes(query: str, top_k: int = 10, quality_threshold: float = 5.0) -> List[Dict]:
    """便捷函数：检索金句库"""
    return get_client().search_quotes(query, top_k, quality_threshold)


if __name__ == "__main__":
    # 测试
    client = get_client()

    print("检查服务状态...")
    if client.health_check():
        print("✓ 服务正常")
    else:
        print("✗ 服务不可用")
        exit(1)

    print("\n服务统计:")
    stats = client.get_stats()
    print(f"  总向量数: {stats.get('total', 0)}")
    print(f"  按来源: {stats.get('by_source', {})}")

    print("\n测试检索金句库...")
    results = client.search_quotes("管理", top_k=3)
    for r in results:
        print(f"  - [{r['metadata']['author']}] {r['content'][:50]}...")

    print("\n测试检索文章库...")
    results = client.search_articles("人工智能", top_k=3)
    for r in results:
        print(f"  - [{r['公众号']}] {r['文章标题']}")
