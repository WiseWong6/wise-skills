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
        self.assertIn('<section class="slide"', self.source)

    def test_board_clones_live_slides_safely(self) -> None:
        for source in (self.source, self.runtime):
            self.assertIn("cloneNode(true)", source)
            self.assertIn("querySelectorAll('script')", source)
            self.assertIn("clone.inert=true", source)
            self.assertIn("setAttribute('aria-hidden','true')", source)
            self.assertIn("copyCanvasPixels", source)
            self.assertIn("dataset.canvasCopied='true'", source)

    def test_runtime_uses_slide_metadata_and_local_page_script(self) -> None:
        for attribute in (
            "data-page-title",
            "data-page-summary",
            "data-section-id",
            "data-section-title",
        ):
            self.assertIn(attribute, self.source)
        self.assertIn("document.currentScript.closest('.slide')", self.source)
        self.assertIn("WisePPT.markSlideReady(slide)", self.source)
        self.assertIn("renderer:'svg'", self.source)

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
                self.assertIn("get('print')==='1'", self.source)
            elif token == "data-deck-ready":
                self.assertIn("dataset.deckReady", self.source)
            else:
                self.assertIn(token, self.source)


if __name__ == "__main__":
    unittest.main()
