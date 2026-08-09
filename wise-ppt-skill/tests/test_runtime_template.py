from __future__ import annotations

import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
RUNTIME = SKILL_ROOT / "runtime"


class RuntimeTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (RUNTIME / "app-template.html").read_text(encoding="utf-8")
        cls.runtime = (RUNTIME / "deck-runtime.js").read_text(encoding="utf-8")

    def test_single_html_runtime_has_no_frame_or_thumbnail_dependency(self) -> None:
        lowered = self.source.casefold()
        self.assertNotIn("<iframe", lowered)
        self.assertNotIn("thumb-", lowered)
        self.assertNotIn("screenshot.sh", lowered)
        self.assertNotIn("var shots", lowered)
        self.assertNotIn("var acts", lowered)
        self.assertIn('data-document-mode="single-html"', self.source)
        self.assertNotIn('<section class="slide"', self.source)
        self.assertIn('id="track"', self.source)

    def test_board_clones_live_slides_safely(self) -> None:
        self.assertNotIn("cloneNode(true)", self.source)
        for token in (
            "cloneNode(true)",
            "querySelectorAll('script')",
            "clone.inert=true",
            "setAttribute('aria-hidden','true')",
            "copyCanvasPixels",
            "dataset.canvasCopied='true'",
        ):
            self.assertIn(token, self.runtime)

    def test_template_has_one_external_runtime_authority(self) -> None:
        self.assertEqual(self.source.count('src="assets/deck-runtime.js"'), 1)
        self.assertNotIn("function initialize()", self.source)
        self.assertNotIn("global.WisePPT", self.source)

    def test_runtime_uses_slide_metadata_and_semantic_emphasis(self) -> None:
        for attribute in (
            "dataset.pageTitle",
            "dataset.pageSummary",
            "dataset.sectionId",
            "dataset.sectionTitle",
            "dataset.emphasisMode",
            "dataset.emphasisRef",
            "dataset.emphasisRoles",
        ):
            self.assertIn(attribute, self.runtime)
        self.assertIn("emphasisColor", self.runtime)
        self.assertIn("renderer:'svg'", self.runtime)
        self.assertIn("registerSlideTask", self.runtime)

    def test_navigation_print_and_readiness_contracts_exist(self) -> None:
        for token in (
            "ArrowRight",
            "ArrowLeft",
            "PageDown",
            "PageUp",
            "Home",
            "End",
            "Escape",
            "touchstart",
            "touchend",
            "?print=1",
            "data-deck-ready",
        ):
            if token == "?print=1":
                self.assertIn("get('print')==='1'", self.runtime)
            elif token == "data-deck-ready":
                self.assertIn("dataset.deckReady", self.runtime)
            else:
                self.assertIn(token, self.runtime)

    def test_fullscreen_text_selection_and_copy_contract_exists(self) -> None:
        for token in (
            "user-select: text",
            "user-select:none!important",
        ):
            self.assertIn(token, self.source if "none" in token else (RUNTIME.parent / "themes/paper-ink/assets/shared.css").read_text(encoding="utf-8"))
        for token in (
            "hasTextSelection",
            "hasEditableTarget",
            "navigationIsReserved",
            "dataset.copyCheck='pass'",
            "文本选区被翻页快捷键抢占",
        ):
            self.assertIn(token, self.runtime)

    def test_runtime_exposes_theme_type_scale_for_canvas_and_charts(self) -> None:
        self.assertIn("typeSize:typeSize", self.runtime)
        self.assertIn("--type-", self.runtime)

    def test_board_title_uses_the_shared_sans_type_role(self) -> None:
        self.assertIn('data-deck-title="Wise PPT · 分镜示例"', self.source)
        self.assertIn(
            ".board-head h1{font-family:var(--sans);font-size:var(--type-subheading);font-weight:300}",
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
