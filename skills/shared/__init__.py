"""
Shared utilities for article skills.
"""

from .style_recommender import (
    normalize_style,
    recommend_style,
    get_style_description,
    is_valid_style,
)
from .handoff_utils import (
    HandoffFields,
    generate_handoff,
    write_handoff_yaml,
)

__all__ = [
    "normalize_style",
    "recommend_style",
    "get_style_description",
    "is_valid_style",
    "HandoffFields",
    "generate_handoff",
    "write_handoff_yaml",
]
