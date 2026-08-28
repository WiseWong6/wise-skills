"""Composable, read-only analyzers used by the Skill Optimizer CLI."""

from .model import add_finding, count_findings, sort_findings

__all__ = ["add_finding", "count_findings", "sort_findings"]
