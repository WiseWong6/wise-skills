#!/usr/bin/env python3
"""
Article Create RAG - 基于本地文章库生成文章

支持两种模式：
1. 主题+关键词直接生成
2. 基于外部调研内容 + 本地文章库

字数约束：固定 1500-2000 字
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import yaml
from pathlib import Path
from typing import List, Dict, Optional

import requests


# 向量检索服务客户端
sys.path.insert(0, str(Path(__file__).parent.parent))
from vector_service_client import get_client, search_articles

# 配置
SKILL_DIR = Path(__file__).parent
ARK_API_KEY = os.environ.get("ARK_API_KEY")
ARK_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding")
ARK_MODEL = os.environ.get("ANTHROPIC_MODEL", "ark-code-latest")

MIN_WORDS = 1500
MAX_WORDS = 2000


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="基于本地文章库生成文章或提纲")
    parser.add_argument("--topic", help="文章主题")
    parser.add_argument("--keywords", help="关键词（逗号分隔）")
    parser.add_argument("--research", help="外部调研内容文件路径（模式2）")
    parser.add_argument("--draft", help="初稿文件路径（模式3：RAG 增强模式）")
    parser.add_argument("--enhance", action="store_true", help="RAG 增强模式，对已有草稿进行增强和润色")
    parser.add_argument("--run-dir", help="Orchestrator 提供的运行目录")
    parser.add_argument("--output-path", default="generated_article.md", help="输出文件相对路径")
    parser.add_argument("--count", type=int, default=5, help="从文章库召回的片段数量")
    parser.add_argument("--outline", action="store_true", help="生成提纲模式（输出 2-3 个差异化提纲方案）")
    return parser.parse_args()


def search_article_library(keywords: List[str], count: int = 5) -> List[Dict]:
    """
    使用向量检索服务在文章库中检索相关片段

    Args:
        keywords: 关键词列表
        count: 返回结果数量

    Returns:
        检索到的文章片段列表，包含相关性分数
        格式: [{"文章标题": "...", "公众号": "...", "内容": "...", "relevance": 3}, ...]
    """
    try:
        # 用关键词构建查询
        query = " ".join(keywords)

        # 调用向量服务检索（只搜索文章库）
        results = search_articles(query, top_k=count)

        # 转换为现有格式
        formatted = []
        for r in results:
            # 从 metadata 中提取信息
            metadata = r.get("metadata", {})
            formatted.append({
                "文章标题": metadata.get("source_title", r.get("source", "")),
                "公众号": metadata.get("source_account", r.get("author", "")),
                "内容": r.get("content", ""),
                "relevance": int(r.get("score", 1) * 10),  # 归一化分数
            })

        print(f"向量检索到 {len(formatted)} 条文章库结果")
        return formatted

    except Exception as e:
        sys.stderr.write(f"向量检索失败: {e}\n")
        sys.stderr.write("请确保向量服务正在运行: http://localhost:8080\n")
        return []


def extract_keywords_from_research(research_content: str) -> List[str]:
    """
    从调研内容中提取核心概念关键词

    策略:
    1. 提取专业术语（大写开头的英文单词/短语）
    2. 提取中文关键词（2-4字的中文字符）
    3. 按词频统计，返回最常见的关键词

    Args:
        research_content: 调研文件内容

    Returns:
        关键词列表（最多5个）
    """
    from collections import Counter

    keywords = []

    # 1. 提取专业术语（大写开头的英文单词/短语，如 Claude, AI, LLM）
    technical_terms = re.findall(r'\b[A-Z][a-zA-Z]+\b', research_content)

    # 2. 提取中文关键词（2-4字的中文字符）
    chinese_keywords = re.findall(r'[\u4e00-\u9fff]{2,4}', research_content)

    # 3. 合并所有候选关键词
    all_candidates = technical_terms + chinese_keywords

    # 4. 过滤停用词（避免无意义的高频词）
    stopwords = {
        '内容', '文章', '标题', '说明', '介绍', '总结', '分析',
        '这个', '那个', '可以', '需要', '应该', '如果', '但是',
        'and', 'the', 'for', 'with', 'this', 'that'
    }
    filtered = [kw for kw in all_candidates if kw.lower() not in stopwords]

    # 5. 词频统计，选择高频词作为核心概念
    keyword_freq = Counter(filtered)

    # 返回最常见的 5 个关键词
    top_keywords = [kw for kw, count in keyword_freq.most_common(5)]

    return top_keywords


def call_ark_api(prompt: str) -> str:
    """
    调用火山 Ark API 生成文章

    Args:
        prompt: 完整的提示词

    Returns:
        生成的文章内容
    """
    if not ARK_API_KEY:
        sys.stderr.write("错误：未设置 ARK_API_KEY 环境变量\n")
        sys.exit(1)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ARK_API_KEY}"
    }

    data = {
        "model": ARK_MODEL,
        "max_tokens": 4096,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    try:
        response = requests.post(
            f"{ARK_BASE_URL}/v1/messages",
            headers=headers,
            json=data,
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        return result["content"][0]["text"]
    except Exception as e:
        sys.stderr.write(f"API 调用失败: {e}\n")
        sys.exit(1)


def truncate_by_keyword_priority(text: str, keywords: List[str], max_chars: int) -> str:
    """
    基于关键词优先级截断文本

    算法:
    1. 将文本按段落分割（按\n\n分割）
    2. 统计每个段落的关键词匹配次数
    3. 按匹配次数排序段落
    4. 优先保留高匹配段落，直到达到max_chars限制

    Args:
        text: 原始文本
        keywords: 关键词列表
        max_chars: 最大字符数

    Returns:
        截断后的文本
    """
    if len(text) <= max_chars:
        return text

    # 按段落分割
    paragraphs = text.split("\n\n")

    # 计算每个段落的关键词匹配次数
    paragraph_scores = []
    for i, para in enumerate(paragraphs):
        score = sum(para.lower().count(kw.lower()) for kw in keywords)
        paragraph_scores.append((i, score, para))

    # 按匹配次数排序（降序）
    paragraph_scores.sort(key=lambda x: x[1], reverse=True)

    # 优先保留高匹配段落
    result = []
    current_length = 0

    for idx, score, para in paragraph_scores:
        para_length = len(para) + 2  # +2 用于\n\n分隔符

        if current_length + para_length <= max_chars:
            result.append((idx, para))
            current_length += para_length
        else:
            # 如果还有空间，尝试截断当前段落
            remaining_space = max_chars - current_length
            if remaining_space > 50:  # 至少保留50个字符
                truncated_para = para[:remaining_space-3] + "..."
                result.append((idx, truncated_para))
                current_length += len(truncated_para)
            break

    # 按原始顺序重新排列
    result.sort(key=lambda x: x[0])

    return "\n\n".join(para for idx, para in result)


def format_snippets(snippets: List[Dict], research_content: Optional[str] = None,
                   keywords: Optional[List[str]] = None, max_total_chars: int = 96000) -> str:
    """
    格式化素材片段用于 prompt，支持智能截断

    Args:
        snippets: 文章库片段列表
        research_content: 外部调研内容（可选）
        keywords: 关键词列表（用于优先级截断）
        max_total_chars: 总字符数限制（默认96000，为prompt模板预留空间）

    Returns:
        格式化的素材字符串
    """
    parts = []
    current_length = 0
    truncation_info = []  # 记录截断信息

    # 处理调研内容
    if research_content:
        research_header = "### 外部调研\n"
        # 为调研内容分配20%的空间，最多2000字符
        research_available = min(max_total_chars // 5, 2000)

        if len(research_content) > research_available:
            truncation_info.append(f"调研内容从{len(research_content)}字符截断至{research_available}字符")

        if keywords:
            research_text = truncate_by_keyword_priority(research_content, keywords, research_available)
        else:
            research_text = research_content[:research_available]

        parts.append(research_header)
        parts.append(research_text)
        parts.append("")
        current_length += len(research_header) + len(research_text) + 1

    # 处理文章库片段
    if snippets:
        snippet_header = "### 本地文章库\n"
        parts.append(snippet_header)
        current_length += len(snippet_header)

        # 计算剩余可用空间
        remaining_space = max_total_chars - current_length

        # 按相关性分数排序（如果存在）
        if snippets and "relevance" in snippets[0]:
            snippets = sorted(snippets, key=lambda x: x.get("relevance", 0), reverse=True)

        # 为每个片段分配空间（按相关性加权）
        total_relevance = sum(s.get("relevance", 1) for s in snippets)

        for i, snippet in enumerate(snippets):
            title = snippet.get("文章标题", "")
            author = snippet.get("公众号", "")
            content = snippet.get("内容", "")
            original_length = len(content)

            # 计算这个片段的可用空间
            relevance = snippet.get("relevance", 1)
            snippet_available = int(remaining_space * (relevance / total_relevance))

            # 确保至少有200字符
            snippet_available = max(snippet_available, 200)

            # 格式化基础信息
            base_info = f"- [{title}] ({author})\n  内容摘要: "
            base_length = len(base_info)

            # 内容的可用空间
            content_available = snippet_available - base_length

            if content_available > 0:
                if keywords:
                    excerpt = truncate_by_keyword_priority(content, keywords, content_available)
                else:
                    excerpt = content[:content_available]

                if original_length > content_available:
                    truncation_info.append(f"文章'{title}'从{original_length}字符截断至{content_available}字符")

                snippet_text = base_info + excerpt

                parts.append(snippet_text)
                parts.append("")

                current_length += len(snippet_text) + 1
                remaining_space = max_total_chars - current_length

                if remaining_space <= 0:
                    break

    # 输出截断警告
    if truncation_info:
        sys.stderr.write("\n[截断警告]\n")
        for info in truncation_info:
            sys.stderr.write(f"  - {info}\n")
        sys.stderr.write("\n")

    return "\n".join(parts)


def generate_article(
    topic: str,
    snippets: List[Dict],
    research_content: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    min_words: int = MIN_WORDS,
    max_words: int = MAX_WORDS
) -> str:
    """
    生成文章

    Args:
        topic: 文章主题
        snippets: 文章库片段列表
        research_content: 外部调研内容（可选）
        keywords: 关键词列表（用于智能截断）
        min_words: 最小字数
        max_words: 最大字数

    Returns:
        生成的 Markdown 文章
    """
    # 格式化素材（带智能截断）
    snippets_formatted = format_snippets(
        snippets,
        research_content,
        keywords=keywords,
        max_total_chars=96000  # 为prompt模板预留空间
    )

    # 构建提示词
    prompt = f"""你是专业的内容创作专家，基于提供的素材创作一篇高质量文章。

## 主题
{topic}

## 素材来源
{snippets_formatted}

## 要求
1. 字数范围：{min_words}-{max_words}字（严格控制在范围内，不要超出）
2. 结构清晰：标题 → 问题引入 → 核心观点 → 案例支撑 → 总结
3. 观点整合：有机融合多个来源，避免简单堆砌
4. 语言自然：用真人表达方式，避免"AI味"
5. 事实准确：不编造数据、不杜撰来源
6. 重要观点和金句必须标注来源

请创作文章："""

    # 检查prompt长度
    if len(prompt) > 98304:
        sys.stderr.write(f"警告：prompt长度({len(prompt)})超过API限制(98304)，将自动截断\n")
        # 简单截断（不应该发生，因为format_snippets已经处理）
        prompt = prompt[:98300] + "..."

    # 调用 API 生成
    article = call_ark_api(prompt)
    return article


def enhance_article(
    draft: str,
    snippets: List[Dict],
    keywords: Optional[List[str]] = None
) -> str:
    """
    RAG 增强已有草稿

    Args:
        draft: 初稿内容
        snippets: 文章库片段列表
        keywords: 关键词列表（用于智能截断）

    Returns:
        增强后的 Markdown 文章
    """
    # 格式化检索片段（带智能截断）
    snippets_formatted = format_snippets(
        snippets,
        None,  # 没有 research_content
        keywords=keywords,
        max_total_chars=96000
    )

    # 构建提示词
    prompt = f"""你是专业的内容编辑，基于本地文章库检索到的素材对初稿进行增强和润色。

## 初稿
{draft}

## 可用的检索素材（来自本地文章库）
{snippets_formatted}

## 增强要求
1. 保持初稿的核心观点和结构不变
2. 用检索素材补充数据/案例/引用，增强论证力度
3. 优化表达和论证逻辑
4. **只能在检索素材范围内补充，不得杜撰**
5. 补充的内容必须标注来源

请输出增强后的文章："""

    # 检查prompt长度
    if len(prompt) > 98304:
        sys.stderr.write(f"警告：prompt长度({len(prompt)})超过API限制(98304)，将自动截断\n")
        prompt = prompt[:98300] + "..."

    # 调用 API 生成
    enhanced = call_ark_api(prompt)

    # 添加增强说明
    enhancement_note = f"""

---

## 增强说明

本次 RAG 增强基于本地文章库检索到的 {len(snippets)} 条相关片段，主要用于：
- 补充数据/案例
- 优化表达和论证
- 保持原有结构和观点不变
"""

    return enhanced + enhancement_note


def format_retrieval_snippets(snippets: List[Dict]) -> str:
    """
    格式化检索证据片段（用于溯源）

    Args:
        snippets: 检索到的文章片段列表

    Returns:
        格式化后的片段文本
    """
    if not snippets:
        return "# 检索证据片段\n\n未检索到相关片段"

    parts = ["# 检索证据片段\n"]
    current_author = None

    for snippet in snippets:
        title = snippet.get("文章标题", "")
        content = snippet.get("内容", "")
        author = snippet.get("作者", "")

        # 新的作者分组
        if author != current_author:
            current_author = author
            parts.append(f"\n## 来源：{author}\n")

        # 截取内容摘要（最多200字）
        excerpt = content[:200] + "..." if len(content) > 200 else content
        parts.append(f"- [{title}]\n  {excerpt}\n")

    parts.append(f"\n共检索到 {len(snippets)} 条相关片段")
    return "\n".join(parts)


def count_chinese_words(text: str) -> int:
    """
    统计中文字数（去除空格、换行等）

    Args:
        text: 文本内容

    Returns:
        字数
    """
    # 移除 Markdown 特殊字符
    cleaned = re.sub(r'[#*_`\[\]\(\)\-]', '', text)
    # 移除空白字符
    cleaned = re.sub(r'\s+', '', cleaned)
    return len(cleaned)


def save_handoff(run_dir: Path, output_path: str, input_file: Optional[str] = None):
    """
    生成 handoff.yaml（当作为 article-workflow 子技能时）

    Args:
        run_dir: 运行目录
        output_path: 输出文件路径
        input_file: 输入文件路径
    """
    handoff_path = run_dir / "wechat" / "02_handoff.yaml"
    handoff_path.parent.mkdir(parents=True, exist_ok=True)

    handoff_content = {
        "step_id": "02_rag",
        "inputs": [input_file] if input_file else [],
        "outputs": [output_path, "wechat/02_handoff.yaml"],
        "summary": "基于调研资料和本地文章库生成草稿（1500-2000字）",
        "next_instructions": [
            "下一步：title-gen 生成标题方案"
        ],
        "open_questions": []
    }

    with open(handoff_path, "w", encoding="utf-8") as f:
        yaml.dump(handoff_content, f, allow_unicode=True, default_flow_style=False)

    print(f"生成 handoff: {handoff_path}")


def save_handoff_enhance(run_dir: Path, output_path: str, input_file: str):
    """
    生成增强模式的 handoff.yaml

    Args:
        run_dir: 运行目录
        output_path: 输出文件路径
        input_file: 输入文件路径（初稿）
    """
    handoff_path = run_dir / "wechat" / "05_handoff.yaml"
    handoff_path.parent.mkdir(parents=True, exist_ok=True)

    # 提取相对路径
    input_rel = Path(input_file).relative_to(run_dir) if Path(input_file).is_absolute() else Path(input_file)

    handoff_content = {
        "step_id": "05_rag_enhance",
        "inputs": [str(input_rel)],
        "outputs": [
            output_path,
            "wechat/05_retrieval_snippets.md",
            "wechat/05_handoff.yaml"
        ],
        "summary": "使用本地文章库对初稿进行 RAG 增强和润色",
        "next_instructions": [
            "下一步：title-gen 生成标题方案",
            "只能引用 snippets 中的内容，不得杜撰来源"
        ],
        "open_questions": []
    }

    with open(handoff_path, "w", encoding="utf-8") as f:
        yaml.dump(handoff_content, f, allow_unicode=True, default_flow_style=False)

    print(f"生成 handoff: {handoff_path}")


# ========== 提纲生成功能 ==========

def slugify(text: str) -> str:
    """生成 slug（简短标识）"""
    words = re.findall(r'[\u4e00-\u9fa5]+|[a-zA-Z]+', text)
    s = "".join(words[:5])
    s = s.lower().replace(" ", "-")
    s = re.sub(r'[^a-z0-9\u4e00-\u9fa5-]+', '', s)
    return s[:50] or "untitled"


def generate_outlines(
    content: str,
    output_dir: Path,
    snippets: List[Dict] = None
) -> List[Path]:
    """
    生成 2-3 个差异化提纲方案

    Args:
        content: 素材内容
        output_dir: 输出目录
        snippets: RAG 检索到的片段

    Returns:
        提纲文件路径列表
    """
    # 分析素材
    headers = re.findall(r'^#+\s+(.+)$', content, re.MULTILINE)
    core_points = headers[:3] if headers else ["[待定核心论点1]", "[待定核心论点2]", "[待定核心论点3]"]

    # 定义方案差异
    strategies = [
        {
            "id": "a",
            "name": "深度解析版",
            "style": "理性分析型",
            "angle": "技术原理",
            "length": "2500-3000字",
            "structure": "是什么 → 解决什么 → 怎么做到 → 意味着什么"
        },
        {
            "id": "b",
            "name": "精简速读版",
            "style": "故事驱动型",
            "angle": "用户影响",
            "length": "1500-2000字",
            "structure": "场景代入 → 问题揭示 → 分析原因 → 给出判断"
        },
        {
            "id": "c",
            "name": "思辨讨论版",
            "style": "对话评论型",
            "angle": "争议思辨",
            "length": "2000-2500字",
            "structure": "争什么 → 各方观点 → 我的判断"
        }
    ]

    outlines = []
    for strategy in strategies:
        outline = _generate_single_outline(content, core_points, strategy, snippets)
        outline_file = output_dir / f"outline-{strategy['id']}.md"
        outline_file.write_text(outline, encoding='utf-8')
        outlines.append(outline_file)

    return outlines


def _generate_single_outline(
    content: str,
    core_points: List[str],
    strategy: Dict,
    snippets: List[Dict] = None
) -> str:
    """生成单个提纲"""
    # 检索增强提示
    rag_hint = ""
    if snippets:
        sources = [s.get("公众号", "未知") for s in snippets[:3]]
        rag_hint = f"\n【参考来源】{', '.join(set(sources))}"

    outline = f"""===== 方案 {strategy['id'].upper()}：{strategy['name']} =====

【风格定位】{strategy['style']}
【叙事骨架】{strategy['structure']}
【开头策略】根据素材选择反差/悬念/数据冲击

【正文结构】
1. [引言]：{core_points[0] if len(core_points) > 0 else '[待定]'}
2. [展开]：{core_points[1] if len(core_points) > 1 else '[待定]'} [共鸣点]
3. [深入]：{core_points[2] if len(core_points) > 2 else '[待定]'} [好奇点]
4. [分析]：进一步论证与案例 [冲突点]
5. [总结]：观点升华与行动建议 [升华点]

【结尾策略】金句升华/开放问题/行动呼吁
【预估篇幅】{strategy['length']}
【方案优势】{strategy['angle']}角度切入，适合{strategy['style']}读者
【写作提示】重点展开核心论点，补充具体案例和数据{rag_hint}

---
素材预览：
{content[:300] + "..." if len(content) > 300 else content}
---
"""
    return outline


# ========== 主函数 ==========

def main():
    """主函数"""
    args = parse_args()

    # 确定运行模式和输出路径
    run_dir = None
    output_path = args.output_path

    if args.run_dir:
        run_dir = Path(args.run_dir)
        full_output_path = run_dir / output_path
        full_output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        full_output_path = Path(args.output_path)

    # 模式3：RAG 增强模式
    if args.enhance:
        if not args.draft:
            sys.stderr.write("错误：--enhance 模式需要提供 --draft 参数\n")
            sys.exit(1)

        draft_path = Path(args.draft)
        if not draft_path.exists():
            sys.stderr.write(f"错误：初稿文件不存在: {args.draft}\n")
            sys.exit(1)

        with open(draft_path, "r", encoding="utf-8") as f:
            draft_content = f.read()

        # 从初稿中提取关键词
        keywords = extract_keywords_from_research(draft_content)
        print(f"从初稿提取关键词: {keywords}")

        # 检索文章库
        print(f"检索关键词: {keywords}")
        snippets = search_article_library(keywords, args.count)
        print(f"找到 {len(snippets)} 条相关片段")

        if not snippets:
            sys.stderr.write(f"\n⚠️  本地文章库中没有相关内容\n")
            sys.stderr.write(f"   提取的关键词: {keywords}\n")
            sys.stderr.write(f"   将返回原初稿...\n\n")
            enhanced_content = draft_content
        else:
            # RAG 增强
            print(f"进行 RAG 增强...")
            enhanced_content = enhance_article(draft_content, snippets, keywords)

        # 保存增强后的文章
        with open(full_output_path, "w", encoding="utf-8") as f:
            f.write(enhanced_content)
        print(f"增强后的文章已保存: {full_output_path}")

        # 保存检索证据片段
        if run_dir:
            retrieval_path = run_dir / "05_retrieval_snippets.md"
            with open(retrieval_path, "w", encoding="utf-8") as f:
                f.write(format_retrieval_snippets(snippets))
            print(f"检索证据片段已保存: {retrieval_path}")

            # 生成 handoff
            save_handoff_enhance(run_dir, output_path, args.draft)

        return

    # 模式2：外部调研 + 文章库
    research_content = None
    if args.research:
        research_path = Path(args.research)
        if not research_path.exists():
            sys.stderr.write(f"错误：调研文件不存在: {args.research}\n")
            sys.exit(1)

        with open(research_path, "r", encoding="utf-8") as f:
            research_content = f.read()

        # 提取关键词
        keywords = extract_keywords_from_research(research_content)
        print(f"从调研内容提取关键词: {keywords}")
    elif args.keywords:
        keywords = [kw.strip() for kw in args.keywords.split(",")]
    else:
        sys.stderr.write("错误：需要提供 --keywords 或 --research 参数\n")
        sys.exit(1)

    # 检索文章库
    print(f"检索关键词: {keywords}")
    snippets = search_article_library(keywords, args.count)
    print(f"找到 {len(snippets)} 条相关片段")

    if not snippets:
        sys.stderr.write(f"\n⚠️  本地文章库中没有关于 '{args.topic or keywords[0]}' 的相关内容\n")
        sys.stderr.write(f"   提取的关键词: {keywords}\n")
        sys.stderr.write(f"   建议：\n")
        sys.stderr.write(f"   1. 检查文章库是否包含相关内容（文章库路径: {ARTICLE_LIB_PATH}）\n")
        sys.stderr.write(f"   2. 尝试使用 --keywords 手动指定更通用的术语\n")
        sys.stderr.write(f"   3. 或者先不使用 RAG，仅基于调研报告生成\n\n")

    # 提纲模式
    if args.outline:
        topic = args.topic or "根据素材生成提纲"

        # 构建素材内容
        content = research_content or f"# {topic}\n\n基于关键词: {', '.join(keywords)}"

        # 确定输出目录
        if run_dir:
            outline_dir = run_dir / "outlines"
        else:
            # 使用 slug 生成目录
            from datetime import datetime
            slug = slugify(topic)
            date_str = datetime.now().strftime("%Y/%m/%d")
            outline_dir = Path.cwd() / "posts" / date_str / slug

        outline_dir.mkdir(parents=True, exist_ok=True)

        # 保存素材
        source_file = outline_dir / "source-1.md"
        source_file.write_text(content, encoding='utf-8')
        print(f"✓ 素材已保存到: {outline_dir}")

        # 生成提纲
        outlines = generate_outlines(content, outline_dir, snippets)
        print(f"✓ 已生成 {len(outlines)} 个提纲方案:")
        for o in outlines:
            print(f"  - {o.name}")

        return

    # 生成文章（默认模式）
    topic = args.topic or "根据素材生成文章"
    print(f"生成文章: {topic} ({MIN_WORDS}-{MAX_WORDS}字)")

    article = generate_article(topic, snippets, research_content, keywords, MIN_WORDS, MAX_WORDS)

    # 保存文章
    with open(full_output_path, "w", encoding="utf-8") as f:
        f.write(article)

    print(f"文章已保存: {full_output_path}")

    # 统计字数
    word_count = count_chinese_words(article)
    print(f"实际字数: {word_count}")

    if word_count < MIN_WORDS or word_count > MAX_WORDS:
        print(f"警告：字数不在目标范围内 ({MIN_WORDS}-{MAX_WORDS})")

    # 生成 handoff（如果是 orchestrator 调用）
    if run_dir and args.research:
        save_handoff(run_dir, output_path, args.research)
    elif run_dir:
        save_handoff(run_dir, output_path)


if __name__ == "__main__":
    main()
