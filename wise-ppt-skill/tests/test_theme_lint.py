from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
LINT_PATH = SKILL_ROOT / "themes/paper-ink/scripts/lint.py"
SHARED_CSS = SKILL_ROOT / "themes/paper-ink/assets/shared.css"
SPEC = importlib.util.spec_from_file_location("paper_ink_lint", LINT_PATH)
assert SPEC and SPEC.loader
LINT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LINT)


def lint_source(source: str) -> tuple[list[str], list[str]]:
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "index.html"
        path.write_text(source, encoding="utf-8")
        return LINT.lint_file(path)


BASE = """<!doctype html>
<html data-document-mode="single-html"><head><style>{style}</style></head><body>
<div class="doc tl">DOC</div><div class="folio">01</div><div class="caption">结论</div>
</body></html>
"""


class ThemeTypographyLintTests(unittest.TestCase):
    def test_shared_type_scale_has_one_authority_per_role(self) -> None:
        css = SHARED_CSS.read_text(encoding="utf-8")
        for role in LINT.TYPE_ROLES:
            self.assertEqual(css.count(f"--type-{role}:"), 1, role)
        self.assertIn(".stage > .caption { font-size: var(--type-caption); }", css)
        self.assertIn("font-size: var(--type-meta);", css)

    def test_semantic_type_token_passes(self) -> None:
        fails, _ = lint_source(BASE.format(style=".caption{font-size:var(--type-caption)}"))
        self.assertFalse([item for item in fails if item.startswith("L10")])

    def test_raw_css_and_svg_sizes_fail(self) -> None:
        source = BASE.format(style=".caption{font-size:36px}").replace(
            '<div class="caption">', '<svg><text font-size="14">X</text></svg><div class="caption">'
        )
        fails, _ = lint_source(source)
        self.assertGreaterEqual(len([item for item in fails if item.startswith("L10")]), 2)

    def test_raw_canvas_and_echarts_sizes_fail(self) -> None:
        source = BASE.format(style=".caption{font-size:var(--type-caption)}") + """
<script>ctx.font='18px sans-serif';
var option={label:{fontSize:14}};</script>
"""
        fails, _ = lint_source(source)
        self.assertGreaterEqual(len([item for item in fails if item.startswith("L10")]), 2)

    def test_unknown_type_token_fails(self) -> None:
        fails, _ = lint_source(BASE.format(style=".caption{font-size:var(--type-random)}"))
        self.assertTrue(any("未声明字阶" in item for item in fails))

    def test_dynamic_svg_size_bypass_fails(self) -> None:
        source = BASE.format(style=".caption{font-size:var(--type-caption)}") + """
<script>txt(0,0,'x',{'font-size': important ? 34 : 28});</script>
"""
        fails, _ = lint_source(source)
        self.assertTrue(any("动态字号绕过字阶" in item for item in fails))

    def test_gallery_and_examples_do_not_bypass_type_scale(self) -> None:
        targets = sorted((SKILL_ROOT / "themes/paper-ink/gallery").glob("*/index.html"))
        targets += sorted((SKILL_ROOT / "themes/paper-ink/gallery").glob("*/frames/*.html"))
        targets += sorted((SKILL_ROOT / "themes/paper-ink/examples").glob("*/index.html"))
        for path in targets:
            with self.subTest(path=path):
                fails, _ = LINT.lint_file(path)
                self.assertFalse([item for item in fails if item.startswith("L10")])


if __name__ == "__main__":
    unittest.main()
