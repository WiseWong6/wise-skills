from __future__ import annotations

import re
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
RUNTIME = SKILL_ROOT / "runtime"


class RuntimeTemplateTests(unittest.TestCase):
    def test_six_runtime_pages_use_the_paper_ink_contract(self) -> None:
        pages = {
            "01": ("paper-ink.comparison.dual-panel", "wise-ppt.why-comparison"),
            "02": ("paper-ink.flow.pipeline", "wise-ppt.workflow"),
            "03": ("paper-ink.radial.three-way", "wise-ppt.design-principles"),
            "04": ("paper-ink.comparison.paired-bands", "wise-ppt.layout-atlas"),
            "05": ("paper-ink.radial.annotated-hero", "wise-ppt.component-atlas"),
            "06": ("paper-ink.scaffold.contact", "wise-ppt.contact"),
        }
        for number, (layout, block_id) in pages.items():
            source = (RUNTIME / "frames" / f"shot-{number}.html").read_text(encoding="utf-8")
            thumb = RUNTIME / "frames" / f"thumb-{number}.png"
            self.assertTrue(thumb.is_file(), f"missing thumbnail for shot {number}")
            self.assertIn('data-theme="paper-ink"', source)
            self.assertIn(f'data-layout="{layout}"', source)
            self.assertIn(f'data-block-id="{block_id}"', source)
            self.assertIn('class="stage" id="body" data-balance="structural"', source)
            self.assertIn('class="doc tl"', source)
            self.assertIn('class="folio"', source)
            self.assertIn('class="caption"', source)
            self.assertIn('../../themes/paper-ink/assets/shared.css', source)
            self.assertIn('../../themes/paper-ink/assets/particles.js', source)
            self.assertIn('font-size:30px', source.replace(' ', ''))
            self.assertIn('stageFit();', source)

    def test_runtime_has_six_coherent_story_entries(self) -> None:
        source = (RUNTIME / "app-template.html").read_text(encoding="utf-8")
        for label in (
            "AI做PPT总是千篇一律",
            "它如何把内容变成演示",
            "设计是一种阅读顺序",
            "版式图册：可参考，也可跳过",
            "PPT 组件：可调用，也可不用",
        ):
            self.assertIn(label, source)
        self.assertIn("AI缺的不是生成页面的能力，而是好的设计标准。", source)
        self.assertIn("提供成熟的表达组件，并由页面内容决定是否调用。", source)
        self.assertIn("关注 @歪斯Wise，及时获取更新资讯。", source)
        self.assertEqual(source.count("['g"), 11)
        page01 = (RUNTIME / "frames" / "shot-01.html").read_text(encoding="utf-8")
        self.assertIn("ICON、EMOJI滥用", page01)
        page06 = (RUNTIME / "frames" / "shot-06.html").read_text(encoding="utf-8")
        self.assertNotIn("SCAN · 微信搜一搜 歪斯Wise", page06)
        self.assertIn("Wise PPT · 分镜示例", source)
        self.assertIn('font-family: "Han Sans", "Source Han Sans SC", "思源黑体"', source)
        self.assertIn("font-weight: 300", source)

    def test_runtime_controls_hide_until_activity(self) -> None:
        source = (RUNTIME / "app-template.html").read_text(encoding="utf-8")
        pager_css = re.search(r"#pager\s*\{(?P<rules>.*?)\n\s*\}", source, re.S)
        self.assertIsNotNone(pager_css)
        self.assertIn("background:rgba(223,224,217,.84)", re.sub(r"\s+", "", pager_css.group("rules")))
        self.assertIn("opacity:1", re.sub(r"\s+", "", pager_css.group("rules")))
        self.assertIn("body.idle #pager { opacity: 0; }", source)
        self.assertIn("#toggle {\n    position: fixed; right: 28px; bottom: 64px;", source)
        self.assertIn("background: rgba(223,224,217,.84);", re.search(r"#toggle\s*\{(?P<rules>.*?)\n\s*\}", source, re.S).group("rules"))
        self.assertIn("#toggle svg { width: 16px; height: 16px;", source)

    def test_runtime_navigation_does_not_swap_unready_prefetch(self) -> None:
        source = (RUNTIME / "app-template.html").read_text(encoding="utf-8")
        self.assertIn("function trackFrame(frame)", source)
        self.assertIn("prefetch.dataset.ready === 'true'", source)
        self.assertIn("function loadFrame(frame, url)", source)
        self.assertIn("var pending = null;", source)
        self.assertIn("loadFrame(prefetch, url);", source)
        self.assertIn("requestAnimationFrame(function()", source)
        self.assertIn("e.source === view.contentWindow || e.source === prefetch.contentWindow", source)

    def test_runtime_frame_supports_copy_and_frame_keys(self) -> None:
        source = (RUNTIME / "app-template.html").read_text(encoding="utf-8")
        frame_css = re.search(r"#deck \.view, #deck \.prefetch\s*\{(?P<rules>.*?)\n\s*\}", source, re.S)
        self.assertIsNotNone(frame_css)
        self.assertNotIn("pointer-events:none", re.sub(r"\s+", "", frame_css.group("rules")))
        self.assertIn('id="view" title="slide" tabindex="-1"', source)
        self.assertIn('id="prefetch" title="preload" tabindex="-1"', source)
        frame_input = (RUNTIME / "frames" / "frame-input.js").read_text(encoding="utf-8")
        self.assertIn("window.parent.postMessage", frame_input)
        self.assertIn("Cmd/Ctrl+C", frame_input)
        shared_css = (SKILL_ROOT / "themes" / "paper-ink" / "assets" / "shared.css").read_text(encoding="utf-8")
        self.assertIn("user-select: text", shared_css)
        for number in ("01", "02", "03", "04", "05", "06"):
            frame = (RUNTIME / "frames" / f"shot-{number}.html").read_text(encoding="utf-8")
            self.assertIn('<script src="frame-input.js"></script>', frame)

    def test_source_template_stays_playable(self) -> None:
        source = (RUNTIME / "app-template.html").read_text(encoding="utf-8")
        self.assertIn("function enterDeck(idx)", source)
        self.assertIn("card.addEventListener('click', function() { enterDeck(idx); });", source)
        self.assertIn("enterDeck(start - 1);", source)
        self.assertIn("CONFIG.framesDir + '/' + CONFIG.framePrefix", source)


if __name__ == "__main__":
    unittest.main()
