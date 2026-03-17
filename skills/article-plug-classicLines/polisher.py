#!/usr/bin/env python3
"""
知识库润色工具 - 使用向量服务进行检索
"""

import argparse
import json
import re
import os
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import requests

import yaml
import jieba
from collections import Counter
from pathlib import Path
import sys

# 添加向量服务客户端导入
sys.path.insert(0, str(Path(__file__).parent.parent))
from vector_service_client import get_client


# 配置
SKILL_DIR = Path(__file__).parent
VECTOR_SERVICE_URL = "http://localhost:8080"
DEFAULT_QUALITY_THRESHOLD = 5.0
DEFAULT_OUTPUT_DIR = "output"
DEFAULT_SNIPPETS_FILE = "snippets"
DEFAULT_HANDOFF_FILE = "handoff"


class ArticlePolisher:
    """知识库润色工具 - 使用向量服务进行检索"""
    def __init__(self, quality_threshold: float = DEFAULT_QUALITY_THRESHOLD):
        self.quality_threshold = quality_threshold
        self.client = get_client()
    def extract_keywords(self, text: str, top_n: int = 10) -> List[str]:
        """从文本中提取关键词"""
        import jieba
        clean_text = re.sub(r'[^\w\u4e00-\u9fff\s]', ' ', text)
        words = [w for w in jieba.lcut(clean_text) if len(w) >= 2]
        counter = Counter(words)
        STOPWORDS = {
            '的', '了', '是', '在', '和', '有', '我', '你', '他', '她', '它',
            '这', '那', '个', '也', '就', '都', '要', '不', '到', '去', 'the', 'a',
            'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with'
        }
        PREDEFINED = {
            '本质', '方法', '系统', '逻辑', '生活', 'AI', '训练', '模型', '学习',
            '产品', '创业', '心态', '转型', '效率', '战略', '体系化', '协同', '组织',
            '成长', '决策', '创新', '管理', '团队', '执行', '目标', '价值', '用户'
        }
        scored = []
        for kw in PREDEFINED:
            if kw in counter:
                scored.append((counter[kw] * 3, kw))
        for w, c in counter.most_common(30):
            if w not in PREDEFINED and w not in STOPWORDS:
                scored.append((c, w))
        scored.sort(key=lambda x: -x[0])
        return [w for _, w in scored[:top_n]]
    def polish(
        self,
        file_path: str,
        quote_count: int = 2,
        article_count: int = 3,
        output_path: Optional[str] = None
    ) -> Dict:
        """
        润色文章
        Args:
            file_path: 待润色文章路径
            quote_count: 需要插入的金句数量
            article_count: 需要插入的文章片段数量
            output_path: 输出文件路径（默认:同目录/03_polished.md)
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            original_text = f.read()
        if output_path is None:
            output_path = file_path.parent / "03_polished.md"
        else:
            output_path = Path(output_path)
        # 提取关键词
        keywords = self.extract_keywords(original_text)
        print(f"[INFO] 提取关键词: {', '.join(keywords[:10])}")
        # 构建查询语句
        query = ' '.join(keywords[:5])
        # 检索金句
        print(f"[INFO] 检索金句...")
        try:
            matched_quotes = self.client.search_quotes(query, top_k=max(quote_count * 3, 10))
        except Exception as e:
            print(f"[WARN] 金句检索失败: {e}")
            matched_quotes = []
        # 检索文章片段
        print(f"[INFO] 检索文章片段...")
        try:
            matched_articles = self.client.search_articles(query, top_k=max(article_count * 3, 10))
        except Exception as e:
            print(f"[WARN] 文章检索失败: {e}")
            matched_articles = []
        # 选择结果
        selected_quotes = matched_quotes[:quote_count]
        selected_articles = matched_articles[:article_count]
        # 生成检索证据
        retrieval_snippets = self._generate_retrieval_snippets(
            selected_quotes, selected_articles, keywords
        )
        # 基础润色（直接附加金句）
        polished_text = self._basic_polish(original_text, selected_quotes, selected_articles)
        # 保存润色结果
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(polished_text)
        print(f"[SUCCESS] 润色完成: {output_path}")
        # 保存检索证据
        snippets_path = file_path.parent / "03_retrieval_snippets.md"
        with open(snippets_path, 'w', encoding='utf-8') as f:
            f.write(retrieval_snippets)
        print(f"[SUCCESS] 检索证据: {snippets_path}")
        # 保存交接文件
        handoff_path = file_path.parent / "03_handoff.yaml"
        handoff_content = f"""step_id: "03_polish"
inputs:
  - "{file_path.name}"
  - "03_retrieval_snippets.md"
outputs:
  - "03_polished.md"
  - "03_handoff.yaml"
summary: "基于向量服务检索和金句润色文章，匹配到{len(selected_quotes)}条金句,{len(selected_articles)}条文章片段"
next_instructions:
  - "只能引用 snippets 中的内容,不得杜撰来源"
  - "保持文章事实点和结构不变"
open_questions: []
"""
        with open(handoff_path, 'w', encoding='utf-8') as f:
            f.write(handoff_content)
        print(f"[SUCCESS] 交接文件: {handoff_path}")
        return {
            'original_path': str(file_path),
            'polished_path': str(output_path),
            'snippets_path': str(snippets_path),
            'handoff_path': str(handoff_path),
            'matched_quotes': selected_quotes,
            'matched_articles': selected_articles,
            'keywords': keywords
        }
    def _generate_retrieval_snippets(
        self,
        quotes: List[Dict],
        articles: List[Dict],
        keywords: List[str]
    ) -> str:
        """生成检索证据片段"""
        lines = [
            "## 检索证据\n",
            f"**检索关键词**: {', '.join(keywords)}\n",
            f"**检索时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            "---\n"
        ]
        if quotes:
            lines.append("\n### 来源：金句库\n")
            for quote in quotes:
                content = quote.get('content', '')
                author = quote.get('source_account', quote.get('author', '未知'))
                title = quote.get('source_title', '无题')
                quality = quote.get('quality_score', {}).get('overall', 0)
                lines.append(f"<!-- 来源：金句库 作者：{author} 质量：{quality} -->")
                lines.append(content)
                lines.append(f"（来自《{title}》）\n")
        if articles:
            if quotes:
                lines.append("")
            lines.append("\n### 来源：文章库\n")
            for article in articles:
                content = article.get('content', '')[:200] + '...'
                title = article.get('source_title', article.get('文章标题', '无题'))
                author = article.get('公众号', article.get('source_account', '未知'))
                lines.append(f"<!-- 来源：文章库 《{title}》 {author} -->")
                lines.append(content)
        return '\n'.join(lines)
    def _basic_polish(
        self,
        original_text: str,
        quotes: List[Dict],
        articles: List[Dict]
    ) -> str:
        """基础润色 - 附加金句和文章片段"""
        result = original_text
        if quotes:
            result += "\n\n---\n\n## 金句摘录\n"
            for quote in quotes:
                content = quote.get('content', '')
                author = quote.get('source_account', '未知')
                result += f"\n> {content}"
                result += f"> —— {author}\n"
        if articles:
            result += "\n\n## 相关文章\n"
            for article in articles:
                content = article.get('content', '')[:150] + '...'
                title = article.get('source_title', article.get('文章标题', '无题'))
                result += f"\n> {content}...（来自《{title}》）"
        result += "\n\n---\n"
        result += f"\n<!-- 润色时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        result += "\n<!-- 本润色由 article-plug-classicLines skill 生成 -->"
        return result


def main():
        parser = argparse.ArgumentParser(description='知识库润色工具')
        parser.add_argument('file_path', help='待润色文章文件路径')
        parser.add_argument('-o', '--output', help='输出文件路径（默认:同目录/03_polished.md)')
        parser.add_argument('-n', '--quote-count', type=int, default=2, help='金句数量(默认2)')
        parser.add_argument('-a', '--article-count', type=int, default=3, help='文章片段数量(默认3)')
        parser.add_argument('-q', '--quality', type=float, default=DEFAULT_QUALITY_THRESHOLD, help='质量阈值(默认使用配置)')
        args = parser.parse_args()
        polisher = ArticlePolisher(quality_threshold=args.quality or DEFAULT_QUALITY_THRESHOLD)
        try:
            result = polisher.polish(
                file_path=args.file_path,
                quote_count=args.quote_count,
                article_count=args.article_count,
                output_path=args.output
            )
            print("\n" + "="*50)
            print("润色结果摘要")
            print("="*50)
            print(f"原文: {result['original_path']}")
            print(f"润色后: {result['polished_path']}")
            print(f"检索证据: {result['snippets_path']}")
            print(f"匹配金句: {len(result['matched_quotes'])}条")
            print(f"匹配文章: {len(result['matched_articles'])}条")
            print(f"使用关键词: {', '.join(result['keywords'][:10])}")
        except Exception as e:
            print(f"[ERROR] 润色失败: {e}")
            import traceback
            traceback.print_exc()
            exit(1)
if __name__ == "__main__":
    main()
