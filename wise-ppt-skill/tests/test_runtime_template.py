from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
RUNTIME = SKILL_ROOT / "runtime"
EXAMPLE = SKILL_ROOT / "themes" / "paper-ink" / "examples" / "wise-ppt-story-six-page"
ACCEPTANCE = SKILL_ROOT.parent / "output" / "wise-ppt-v2-acceptance" / "index.html"


class RuntimeTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (RUNTIME / "app-template.html").read_text(encoding="utf-8")
        cls.runtime = (RUNTIME / "deck-runtime.js").read_text(encoding="utf-8")
        cls.shell = (RUNTIME / "deck-shell.css").read_text(encoding="utf-8")
        cls.stage_fit = (RUNTIME / "stage-fit.js").read_text(encoding="utf-8")
        cls.export_pdf = (RUNTIME / "export-pdf.sh").read_text(encoding="utf-8")
        cls.acceptance = ACCEPTANCE.read_text(encoding="utf-8")

    def test_runtime_shell_has_no_frame_or_thumbnail_dependency(self) -> None:
        lowered = self.source.casefold()
        self.assertNotIn("<iframe", lowered)
        self.assertNotIn("thumb-", lowered)
        self.assertNotIn("screenshot.sh", lowered)
        self.assertNotIn("var shots", lowered)
        self.assertNotIn("var acts", lowered)
        self.assertIn('data-runtime="wise-ppt-deck"', self.source)
        self.assertIn('data-typography-mode="mixed"', self.source)
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
        self.assertNotIn("<style>", self.source)

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
                self.assertIn("get('print') === '1'", self.runtime)
            elif token == "data-deck-ready":
                self.assertIn("dataset.deckReady", self.runtime)
            else:
                self.assertIn(token, self.runtime)

    def test_pdf_export_does_not_accept_a_stale_existing_output(self) -> None:
        self.assertIn('TMP_PDF="$TMP_ROOT/rendered.pdf"', self.export_pdf)
        self.assertIn('--print-to-pdf="$TMP_PDF"', self.export_pdf)
        self.assertIn('mv "$TMP_PDF" "$OUT"', self.export_pdf)
        self.assertNotIn('--print-to-pdf="$OUT"', self.export_pdf)

    def test_fullscreen_text_selection_and_copy_contract_exists(self) -> None:
        for token in (
            "user-select: text",
            "user-select: none !important",
        ):
            self.assertIn(token, self.shell if "none" in token else (RUNTIME.parent / "themes/paper-ink/assets/slide-components.css").read_text(encoding="utf-8"))
        for token in (
            "hasTextSelection",
            "hasEditableTarget",
            "navigationIsReserved",
            "dataset.copyCheck='pass'",
            "文本选区被翻页快捷键抢占",
            "dataset.selectionCheck = 'pass'",
            "dataset.inputCheck = 'pass'",
            "dataset.contenteditableCheck = 'pass'",
        ):
            self.assertIn(token, self.runtime)

    def test_runtime_exposes_theme_type_scale_for_canvas_and_charts(self) -> None:
        self.assertIn("typeSize: typeSize", self.runtime)
        self.assertIn("--type-", self.runtime)

    def test_acceptance_echart_uses_one_parseable_page_dataset(self) -> None:
        container_ids = re.findall(r'data-dataset-id="([^"]+)"', self.acceptance)
        blocks = re.findall(
            r'<script\s+type="application/json"\s+data-wise-ppt-dataset="([^"]+)"[^>]*>(.*?)</script>',
            self.acceptance,
            flags=re.DOTALL,
        )
        self.assertEqual(container_ids, ["dataset.validation-gates"])
        self.assertEqual([dataset_id for dataset_id, _ in blocks], container_ids)
        dataset = json.loads(blocks[0][1])
        self.assertEqual(dataset["dimensions"], ["phase", "checks"])
        self.assertEqual([row["checks"] for row in dataset["source"]], [8, 12, 9, 7, 11])
        self.assertIn("WisePPT.readDataset(slide,target)", self.acceptance)
        self.assertIn("dataset:dataset", self.acceptance)

    def test_echart_dataset_reader_and_gate_behave_at_runtime(self) -> None:
        harness = r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync(process.argv[1], 'utf8');
const rootClasses = new Set();
const root = {
  dataset: {},
  classList: {
    add(name) { rootClasses.add(name); },
    contains(name) { return rootClasses.has(name); }
  }
};
function fontFace(family) {
  return {
    type: 5,
    style: { getPropertyValue(name) {
      if (name === 'font-family') return family;
      if (name === 'font-style') return 'normal';
      if (name === 'font-weight') return '400';
      return '';
    } }
  };
}
const document = {
  documentElement: root,
  currentScript: { src: 'file:///runtime/deck-runtime.js' },
  readyState: 'loading',
  styleSheets: [{ cssRules: ['Han Sans', 'Han Serif', 'Courier Prime', 'Brush'].map(fontFace) }],
  fonts: {
    ready: Promise.resolve(),
    load() { return Promise.resolve([{ status: 'loaded' }]); },
    check() { return true; }
  },
  querySelector(selector) { return selector.startsWith('link[data-wise-runtime-style=') ? {} : null; },
  querySelectorAll() { return []; },
  addEventListener() {},
  dispatchEvent() {},
  head: { appendChild() {} }
};
const window = { location: { search: '' }, WisePPTStageFit: {} };
window.window = window;
const context = {
  window, document, URL, URLSearchParams,
  CSSRule: { FONT_FACE_RULE: 5 },
  CustomEvent: function () {},
  getComputedStyle() { return { getPropertyValue() { return ''; } }; },
  console, setTimeout, clearTimeout, Map, WeakMap, Promise,
  Object, Array, Number, String, Boolean, Error, JSON
};
vm.runInNewContext(source, context);
const api = window.WisePPT;
function assert(condition, message) { if (!condition) throw new Error(message); }
function expectThrow(action, pattern, message) {
  let error;
  try { action(); } catch (caught) { error = caught; }
  assert(error && pattern.test(error.message), message + ': ' + (error && error.message));
}
function block(id, payload) {
  return {
    textContent: payload,
    getAttribute(name) {
      if (name === 'type') return 'application/json';
      if (name === 'data-wise-ppt-dataset') return id;
      return null;
    }
  };
}
function fixture(blocks) {
  const element = {
    dataset: { datasetId: 'dataset.validation-gates' },
    getAttribute(name) { return name === 'data-dataset-id' ? this.dataset.datasetId : null; }
  };
  const slide = {
    dataset: {},
    classList: { contains(name) { return name === 'slide'; } },
    contains(node) { return node === element; },
    querySelector() { return element; },
    querySelectorAll(selector) { return selector === 'img' ? [] : blocks; },
    getBoundingClientRect() { return {}; }
  };
  return { slide, element };
}
const payload = JSON.stringify({ dimensions: ['phase', 'checks'], source: [{ phase: '内容', checks: 8 }] });
const valid = block('dataset.validation-gates', payload);
const parsed = api.parseDatasetBlock(valid, 'dataset.validation-gates');
assert(parsed.source[0].checks === 8, 'dataset JSON should parse');
expectThrow(
  () => api.parseDatasetBlock(block('dataset.validation-gates', '{bad'), 'dataset.validation-gates'),
  /JSON 解析失败/,
  'malformed JSON must fail'
);
const absent = fixture([]);
expectThrow(
  () => api.readDataset(absent.slide, absent.element),
  /必须且只能声明一次/,
  'missing dataset block must fail'
);
const duplicate = fixture([valid, valid]);
expectThrow(
  () => api.readDataset(duplicate.slide, duplicate.element),
  /实际 2 个/,
  'duplicate dataset blocks must fail'
);
let initCalls = 0;
let setOptionCalls = 0;
window.echarts = {
  init() {
    initCalls += 1;
    let finished;
    return {
      on(name, callback) { if (name === 'finished') finished = callback; },
      setOption() { setOptionCalls += 1; finished(); }
    };
  }
};
const missing = fixture([]);
expectThrow(
  () => api.createEChart(missing.slide, missing.element, { dataset: JSON.parse(payload) }),
  /必须且只能声明一次/,
  'createEChart must reject a missing page dataset'
);
assert(missing.slide.dataset.renderError, 'missing dataset must mark the page failed');
const mismatch = fixture([valid]);
expectThrow(
  () => api.createEChart(mismatch.slide, mismatch.element, { dataset: { dimensions: ['phase', 'checks'], source: [{ phase: '内容', checks: 99 }] } }),
  /不一致/,
  'createEChart must reject a mismatched option dataset'
);
assert(mismatch.slide.dataset.renderError, 'mismatched dataset must mark the page failed');
assert(initCalls === 0 && setOptionCalls === 0, 'dataset gates must run before chart initialization');
const missingOption = fixture([valid]);
expectThrow(
  () => api.createEChart(missingOption.slide, missingOption.element, {}),
  /option 缺少 dataset/,
  'createEChart must require option.dataset'
);
assert(missingOption.slide.dataset.renderError, 'missing option.dataset must mark the page failed');
const accepted = fixture([valid]);
api.createEChart(accepted.slide, accepted.element, {
  dataset: { source: [{ checks: 8, phase: '内容' }], dimensions: ['phase', 'checks'] }
});
assert(initCalls === 1 && setOptionCalls === 1, 'matching dataset should reach setOption once');
"""
        completed = subprocess.run(
            ["node", "-e", harness, str(RUNTIME / "deck-runtime.js")],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_echart_dataset_gate_precedes_set_option(self) -> None:
        create_echart = self.runtime[
            self.runtime.index("function createEChart") : self.runtime.index("var ICON_PATHS")
        ]
        for token in (
            "readDataset(slide, element)",
            "hasOwnProperty.call(option, 'dataset')",
            "datasetsEqual(option.dataset, declaredDataset)",
            "markSlideError(slide, error)",
        ):
            self.assertIn(token, create_echart)
        self.assertLess(create_echart.index("readDataset(slide, element)"), create_echart.index("chart.setOption(option)"))

    def test_board_title_uses_the_shared_sans_type_role(self) -> None:
        self.assertIn('data-deck-title="{{DECK_TITLE}}"', self.source)
        self.assertIn(".board-head h1", self.shell)
        self.assertIn("font-family: var(--sans)", self.shell)
        self.assertIn("font-size: var(--type-subheading)", self.shell)
        self.assertIn("font-weight: 300", self.shell)

    def test_stage_fit_has_one_runtime_specific_authority(self) -> None:
        self.assertIn("visualViewport", self.stage_fit)
        self.assertIn("Math.min", self.stage_fit)
        self.assertIn("fitDeck", self.stage_fit)
        self.assertIn("fitGallery", self.stage_fit)
        self.assertIn("noop-in-deck", self.stage_fit)
        self.assertIn("noop-in-gallery", self.stage_fit)
        self.assertIn("WisePPTStageFit.fitDeck", self.runtime)
        self.assertNotIn("function stageFit", self.runtime)

    def test_font_gate_loads_declared_family_and_weight(self) -> None:
        self.assertIn("document.fonts.load(spec, sample)", self.runtime)
        self.assertIn("font.status !== 'loaded'", self.runtime)
        self.assertIn("document.fonts.check(spec, sample)", self.runtime)
        self.assertIn("dataset.fontCheck = 'pass'", self.runtime)

    def test_escape_selftest_dispatches_real_keyboard_event(self) -> None:
        self.assertIn("dispatchKey(global, 'Escape')", self.runtime)
        self.assertIn("new KeyboardEvent('keydown'", self.runtime)
        self.assertIn("dataset.escCheck = 'pass'", self.runtime)

    def test_presentation_controls_use_local_svg_and_safe_area(self) -> None:
        self.assertIn('data-icon="gallery"', self.source)
        self.assertIn("createIcon", self.runtime)
        self.assertIn("dataset.controlsCheck = 'pass'", self.runtime)
        self.assertIn("min-width: 40px", self.shell)
        self.assertNotIn("Font Awesome", self.source + self.runtime + self.shell)


if __name__ == "__main__":
    unittest.main()
