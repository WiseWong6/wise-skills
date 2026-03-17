"""
Style Recommender - 写作风格推荐模块

根据内容自动推荐写作风格。
"""

from typing import Tuple

# 风格映射（中文 <-> 英文）
STYLE_ALIASES = {
    # 中文 -> 英文内部标识
    "成长": "growth",
    "知识": "knowledge",
    "商业": "business",
    "地气": "casual",
    # 英文 -> 中文显示名
    "growth": "成长",
    "knowledge": "知识",
    "business": "商业",
    "casual": "地气",
}

# 风格描述
STYLE_DESCRIPTIONS = {
    "growth": "成长风格 - 个人经历、成长故事、情感共鸣",
    "knowledge": "知识风格 - 干货分享、教程指南、方法论",
    "business": "商业风格 - 行业分析、商业洞察、专业视角",
    "casual": "地气风格 - 接地气、口语化、生活化表达",
}

# 风格关键词
STYLE_KEYWORDS = {
    "growth": ["成长", "经历", "故事", "感受", "改变", "突破", "收获", "感悟", "蜕变"],
    "knowledge": ["方法", "步骤", "教程", "技巧", "干货", "指南", "原理", "框架", "拆解"],
    "business": ["商业", "行业", "市场", "策略", "产品", "运营", "增长", "案例", "趋势"],
    "casual": ["我", "真实", "接地气", "踩坑", "避坑", "分享", "日常", "生活", "经验"],
}


def normalize_style(style: str) -> str:
    """
    将中文/英文风格名统一为内部英文标识

    Args:
        style: 风格名称（中文或英文）

    Returns:
        内部英文标识
    """
    if not style:
        return "business"  # 默认商业风格

    style = style.strip()

    # 如果已经是英文标识
    if style in STYLE_ALIASES:
        return style

    # 从中文转换
    return STYLE_ALIASES.get(style, "business")


def get_style_description(style: str) -> str:
    """
    获取风格的中文描述

    Args:
        style: 风格标识（中文或英文）

    Returns:
        风格描述字符串
    """
    internal_id = normalize_style(style)
    return STYLE_DESCRIPTIONS.get(internal_id, f"未知风格: {style}")


def is_valid_style(style: str) -> bool:
    """
    检查风格是否有效

    Args:
        style: 风格名称

    Returns:
        是否为有效风格
    """
    if not style:
        return False

    style = style.strip()

    # 检查英文标识
    if style in STYLE_ALIASES:
        return True

    # 检查中文名
    if style in ["成长", "知识", "商业", "地气"]:
        return True

    return False


def recommend_style(content: str) -> Tuple[str, str]:
    """
    根据内容自动推荐写作风格

    Args:
        content: 文本内容

    Returns:
        (推荐风格标识, 推荐理由)
    """
    if not content:
        return "business", "默认使用商业风格"

    scores = {
        "growth": 0,
        "knowledge": 0,
        "business": 0,
        "casual": 0,
    }

    # 统计关键词出现次数
    for style_id, keywords in STYLE_KEYWORDS.items():
        for keyword in keywords:
            count = content.count(keyword)
            scores[style_id] += count

    # 找出最高分
    max_style = max(scores, key=scores.get)
    max_score = scores[max_style]

    # 如果没有明显特征，默认商业风格
    if max_score == 0:
        return "business", "未检测到明显风格特征，使用默认商业风格"

    # 生成推荐理由
    matched_keywords = [
        kw for kw in STYLE_KEYWORDS[max_style]
        if kw in content
    ]

    reason = f"检测到风格关键词: {', '.join(matched_keywords[:3])}"
    return max_style, reason
