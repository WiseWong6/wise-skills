from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
RUNTIME = SKILL_ROOT / "runtime"
EXAMPLE = SKILL_ROOT / "themes" / "paper-ink" / "examples" / "wise-ppt-story-six-page"


class RuntimeTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (RUNTIME / "app-template.html").read_text(encoding="utf-8")
        cls.runtime = (RUNTIME / "deck-runtime.js").read_text(encoding="utf-8")

    def test_runtime_shell_has_no_frame_or_thumbnail_dependency(self) -> None:
        lowered = self.source.casefold()
        self.assertNotIn("<iframe", lowered)
        self.assertNotIn("thumb-", lowered)
        self.assertNotIn("screenshot.sh", lowered)
        self.assertNotIn("var shots", lowered)
        self.assertNotIn("var acts", lowered)
        self.assertIn('data-runtime="wise-ppt"', self.source)
        self.assertNotIn('<section class="slide"', self.source)
        self.assertIn("{{SLIDES}}", self.source)
        self.assertIn("WISE_PPT_SLIDES_START", self.source)
        self.assertIn("WISE_PPT_SLIDES_END", self.source)
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
        self.assertEqual(self.source.count('src="{{RUNTIME_SCRIPT_SRC}}"'), 1)
        self.assertNotIn("function initialize()", self.source)
        self.assertNotIn("global.WisePPT", self.source)

    def test_six_page_example_is_generated_from_the_runtime_shell(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SKILL_ROOT / "scripts" / "build_deck.py"), str(EXAMPLE), "--check"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        output = (EXAMPLE / "index.html").read_text(encoding="utf-8")
        self.assertEqual(output.count("WISE_PPT_SLIDES_START"), 1)
        self.assertEqual(output.count("WISE_PPT_SLIDES_END"), 1)
        self.assertIn("Generated shell", output)
        self.assertNotRegex(output, r"\{\{[A-Z_]+\}\}")

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
        self.assertIn('data-deck-title="{{DECK_TITLE}}"', self.source)
        self.assertIn(
            ".board-head h1{font-family:var(--sans);font-size:var(--type-subheading);font-weight:300}",
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
