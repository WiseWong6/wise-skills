#!/usr/bin/env python3
"""
Obsidian 集成工具模块

提供与 Obsidian Vault 集成的工具函数，支持研究库输出到 Obsidian 目录。
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List


# 尝试从 .env 文件加载环境变量
def _load_env_file():
    """从 .env 文件加载环境变量"""
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # 只设置未定义的环境变量
                    if key not in os.environ:
                        os.environ[key] = value


# 模块加载时自动加载 .env
_load_env_file()


# Obsidian Vault 路径配置
DEFAULT_OBSIDIAN_VAULT = Path.home() / "Documents" / "Obsidian Vault"
OBSIDIAN_RESEARCH_DIR = "00_研究库"

# 传统路径配置
TRADITIONAL_RESEARCH_BASE = Path.home() / ".claude" / "skills" / "research-workflow" / "research"


def slugify_topic(topic: str) -> str:
    """将话题转换为 URL 友好的 slug"""
    # 移除非字母数字字符，替换为空格
    slug = re.sub(r'[^\w\s-]', '', topic)
    # 替换空格为连字符
    slug = re.sub(r'[-\s]+', '-', slug)
    # 转小写
    return slug.lower().strip('-')


def get_research_path(topic: str, use_obsidian: bool = False) -> str:
    """
    获取研究输出路径

    Args:
        topic: 研究主题
        use_obsidian: 是否使用 Obsidian 模式

    Returns:
        研究输出目录路径
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    topic_slug = slugify_topic(topic)
    research_id = f"{date_str}-{topic_slug}"

    if use_obsidian:
        # Obsidian 模式: ~/Documents/Obsidian Vault/00_研究库/{YYYY-MM-DD}-{topic}/
        vault_path = _get_obsidian_vault_path()
        return str(vault_path / OBSIDIAN_RESEARCH_DIR / research_id)
    else:
        # 传统模式: ~/.claude/skills/research-workflow/research/{domain}/{YYYY-MM-DD-HHMM}/
        # 从 topic 推断 domain
        domain = _infer_domain(topic)
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
        return str(TRADITIONAL_RESEARCH_BASE / domain / timestamp)


def _get_obsidian_vault_path() -> Path:
    """获取 Obsidian Vault 路径"""
    # 优先从环境变量读取
    env_path = os.getenv("OBSIDIAN_VAULT_PATH")
    if env_path:
        return Path(env_path)
    return DEFAULT_OBSIDIAN_VAULT


def should_use_obsidian_mode() -> bool:
    """
    检查是否应该使用 Obsidian 模式

    Returns:
        True 如果应该使用 Obsidian 模式
    """
    use_obsidian = os.getenv("USE_OBSIDIAN_MODE", "").lower()
    if use_obsidian in ("true", "1", "yes"):
        return True
    if use_obsidian in ("false", "0", "no", ""):
        return False
    return False


def _infer_domain(topic: str) -> str:
    """从话题推断领域"""
    topic_lower = topic.lower()

    # 领域关键词映射
    domain_map = {
        "ai": ["ai", "人工智能", "机器学习", "深度学习", "llm", "大模型", "agent", "智能体"],
        "tech": ["编程", "代码", "开发", "软件", "技术", "框架", "工具"],
        "business": ["商业", "创业", "管理", "运营", "营销", "产品"],
        "life": ["生活", "健康", "旅行", "美食", "家居"],
        "finance": ["金融", "投资", "理财", "股票", "基金"],
    }

    for domain, keywords in domain_map.items():
        if any(kw in topic_lower for kw in keywords):
            return domain

    return "general"


def ensure_obsidian_vault_exists() -> bool:
    """
    确保 Obsidian Vault 目录存在

    Returns:
        True 如果 Vault 存在或创建成功，False 如果不存在
    """
    vault_path = _get_obsidian_vault_path()

    if not vault_path.exists():
        return False

    # 确保研究库目录存在
    research_dir = vault_path / OBSIDIAN_RESEARCH_DIR
    research_dir.mkdir(parents=True, exist_ok=True)

    return True


def get_obsidian_research_ref(topic: str) -> str:
    """
    获取 Obsidian 格式的研究库引用路径

    Args:
        topic: 研究主题

    Returns:
        Obsidian wikilink 格式的引用路径，如 "00_研究库/2026-02-26-ai-agent-trends/index"
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    topic_slug = slugify_topic(topic)
    research_id = f"{date_str}-{topic_slug}"
    return f"{OBSIDIAN_RESEARCH_DIR}/{research_id}/index"


def generate_obsidian_frontmatter(
    topic: str,
    status: str = "completed",
    platforms: List[str] = None,
    tools_used: List[str] = None,
    confidence_level: str = "HIGH",
    article_refs: List[str] = None,
    findings_count: int = 0,
    freshness_score: float = 0.0
) -> Dict[str, Any]:
    """
    生成 Obsidian 格式的 YAML frontmatter

    Args:
        topic: 研究主题
        status: 研究状态 (in_progress | completed)
        platforms: 目标平台列表
        tools_used: 使用的工具列表
        confidence_level: 置信度级别 (HIGH | MEDIUM | LOW)
        article_refs: 引用此研究的文章项目列表
        findings_count: 研究发现数量
        freshness_score: 新鲜度评分

    Returns:
        frontmatter 字典
    """
    today = datetime.now().strftime("%Y-%m-%d")
    date_str = datetime.now().strftime("%Y-%m-%d")
    topic_slug = slugify_topic(topic)
    research_id = f"{date_str}-{topic_slug}"

    if platforms is None:
        platforms = ["wechat", "xhs"]

    if tools_used is None:
        tools_used = []

    if article_refs is None:
        article_refs = []

    return {
        "research_id": research_id,
        "topic": topic,
        "status": status,
        "platforms": platforms,
        "created": today,
        "updated": today,
        "tools_used": tools_used,
        "confidence_level": confidence_level,
        "article_refs": article_refs,
        "metadata": {
            "findings_count": findings_count,
            "freshness_score": round(freshness_score, 2),
            "version": "2.8.0"
        },
        "tags": ["research", "content-brief"] + _infer_tags(topic)
    }


def _infer_tags(topic: str) -> List[str]:
    """从话题推断标签"""
    topic_lower = topic.lower()
    tags = []

    tag_map = {
        "ai": ["ai", "人工智能", "机器学习", "深度学习", "llm", "大模型"],
        "agent": ["agent", "智能体"],
        "programming": ["编程", "代码", "开发", "软件"],
        "tech": ["技术", "框架", "工具"],
    }

    for tag, keywords in tag_map.items():
        if any(kw in topic_lower for kw in keywords):
            tags.append(tag)

    return tags


def format_obsidian_wikilink(target: str, display: Optional[str] = None) -> str:
    """
    格式化 Obsidian wikilink

    Args:
        target: 链接目标
        display: 显示文本（可选）

    Returns:
        格式化后的 wikilink，如 [[target|display]] 或 [[target]]
    """
    if display:
        return f"[[{target}|{display}]]"
    return f"[[{target}]]"


def create_obsidian_index_content(
    topic: str,
    findings: List[Dict[str, Any]],
    tools_used: List[str],
    freshness_score: float,
    related_articles: List[str] = None
) -> str:
    """
    创建 Obsidian 格式的 index.md 内容

    Args:
        topic: 研究主题
        findings: 研究发现列表
        tools_used: 使用的工具列表
        freshness_score: 新鲜度评分
        related_articles: 相关文章项目列表

    Returns:
        Markdown 内容
    """
    lines = [
        f"# {topic} - 研究报告",
        "",
        "## 研究概览",
        "",
        f"- **研究主题**: {topic}",
        f"- **研究发现**: {len(findings)} 条",
        f"- **新鲜度评分**: {freshness_score:.2f}/1.0",
        f"- **研究时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 使用工具",
        "",
    ]

    for tool in tools_used:
        lines.append(f"- {tool}")

    lines.extend([
        "",
        "## 核心发现",
        "",
    ])

    # 添加研究发现摘要
    for i, finding in enumerate(findings[:10], 1):  # 只显示前10条
        claim = finding.get('claim', '')
        source_type = finding.get('source_type', 'unknown')
        lines.append(f"{i}. **{claim[:80]}{'...' if len(claim) > 80 else ''}** ({source_type})")

    if len(findings) > 10:
        lines.append(f"\n... 共 {len(findings)} 条发现，详见下方详细列表")

    lines.extend([
        "",
        "## 详细发现",
        "",
    ])

    # 添加详细发现
    for i, finding in enumerate(findings, 1):
        lines.extend([
            f"### {i}. {finding.get('claim', '')}",
            "",
            f"**来源类型**: {finding.get('source_type', 'unknown')}",
            f"**置信度**: {finding.get('confidence', 'N/A')}",
            "",
            "**资料来源**:",
            "",
        ])

        for j, source in enumerate(finding.get("sources", []), 1):
            lines.extend([
                f"{j}. [{source.get('title', 'N/A')}]({source.get('url', '')})",
                f"   - 日期: {source.get('date', 'N/A')}",
                f"   - 置信度: {source.get('confidence', 'N/A')}",
            ])

        lines.append("")

    # 添加反向链接部分
    if related_articles:
        lines.extend([
            "",
            "## 引用此研究的文章",
            "",
        ])
        for article in related_articles:
            lines.append(f"- {format_obsidian_wikilink(article)}")

    lines.extend([
        "",
        "---",
        "",
        "%% 研究备注 %%",
        "",
    ])

    return "\n".join(lines)


def write_frontmatter(metadata: Dict[str, Any], body: str) -> str:
    """
    将 frontmatter 和正文组合成完整的 Markdown 内容

    Args:
        metadata: frontmatter 元数据字典
        body: Markdown 正文

    Returns:
        完整的 Markdown 内容
    """
    import yaml

    # 使用 yaml.dump 生成 frontmatter
    frontmatter = yaml.dump(metadata, allow_unicode=True, sort_keys=False, default_flow_style=False)

    return f"---\n{frontmatter}---\n\n{body}"


def check_obsidian_mode_available() -> tuple[bool, str]:
    """
    检查 Obsidian 模式是否可用

    Returns:
        (是否可用, 状态信息)
    """
    vault_path = _get_obsidian_vault_path()

    if not vault_path.exists():
        return False, f"Obsidian Vault 不存在: {vault_path}"

    research_dir = vault_path / OBSIDIAN_RESEARCH_DIR
    if not research_dir.exists():
        try:
            research_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return False, f"无法创建研究库目录: {e}"

    return True, f"Obsidian 模式可用: {vault_path}"


def get_fallback_path(topic: str, original_use_obsidian: bool) -> tuple[str, bool, str]:
    """
    获取降级后的路径

    Args:
        topic: 研究主题
        original_use_obsidian: 原始是否尝试使用 Obsidian 模式

    Returns:
        (最终路径, 是否使用了 Obsidian 模式, 警告信息)
    """
    if original_use_obsidian:
        available, message = check_obsidian_mode_available()
        if available:
            return get_research_path(topic, True), True, ""
        else:
            # 降级到传统模式
            fallback_path = get_research_path(topic, False)
            warning = f"⚠️  {message}\n   已自动降级到传统路径: {fallback_path}"
            return fallback_path, False, warning
    else:
        return get_research_path(topic, False), False, ""


if __name__ == "__main__":
    # 测试代码
    print("Obsidian 工具模块测试")
    print("-" * 50)

    topic = "AI Agent 发展趋势"

    # 测试路径生成
    print(f"\n主题: {topic}")
    print(f"传统路径: {get_research_path(topic, False)}")
    print(f"Obsidian 路径: {get_research_path(topic, True)}")

    # 测试 Vault 检查
    available, message = check_obsidian_mode_available()
    print(f"\nObsidian 模式: {message}")

    # 测试 frontmatter 生成
    frontmatter = generate_obsidian_frontmatter(
        topic=topic,
        status="completed",
        platforms=["wechat", "xhs"],
        tools_used=["firecrawl", "exa", "twitter", "github"],
        confidence_level="HIGH",
        findings_count=15,
        freshness_score=0.85
    )
    print(f"\nFrontmatter 生成成功: {frontmatter['research_id']}")
