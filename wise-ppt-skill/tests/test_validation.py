from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True

from _ppt_contracts import (  # noqa: E402
    CORE_PRIMITIVES,
    JsonSchemaValidator,
    load_json,
    resolve_theme,
    validate_all,
    validate_content_target,
    validate_core_purity,
    validate_coverage_target,
    validate_gallery,
    validate_plan_target,
    validate_render_target,
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class FixtureRepo:
    """A second, minimal theme proving that Core is not paper-ink-specific."""

    THEME_ID = "minimal-neutral"
    GALLERY_VARIANTS = ("baseline", "domain")

    def __init__(self, base: Path):
        self.root = base / "skill"
        self.deck = base / "deck"
        self.root.mkdir(parents=True)
        self.deck.mkdir(parents=True)
        shutil.copytree(REPO_ROOT / "core" / "schemas", self.root / "core" / "schemas")
        self._write_theme()
        self._write_component_catalog()
        self.content = self._content_document()
        self.plan = self._plan_document()
        self.render = self._render_document()
        self.flush()

    @property
    def layout_manifest_path(self) -> Path:
        return self.root / "themes" / self.THEME_ID / "layout-manifest.json"

    @property
    def html_path(self) -> Path:
        return self.deck / "frames" / "page.one.html"

    def _write_theme(self) -> None:
        write_json(
            self.root / "themes" / "registry.json",
            {
                "schema_version": "1.0",
                "default_theme_id": self.THEME_ID,
                "themes": [
                    {
                        "theme_id": self.THEME_ID,
                        "name": "Minimal",
                        "path": f"themes/{self.THEME_ID}/theme.json",
                        "layout_manifest": f"themes/{self.THEME_ID}/layout-manifest.json",
                        "enabled": True,
                    }
                ],
            },
        )
        write_json(
            self.root / "themes" / self.THEME_ID / "theme.json",
            {
                "schema_version": "1.0",
                "theme_id": self.THEME_ID,
                "name": "Minimal",
                "layout_manifest": f"themes/{self.THEME_ID}/layout-manifest.json",
                "atlas_catalog": f"themes/{self.THEME_ID}/atlas-catalog.json",
                "providers": ["typography", "svg", "echarts", "atlas", "native-html"],
                "runtimes": {"echarts": {"major": 5}},
                "galleries": {
                    variant: f"themes/{self.THEME_ID}/gallery/{variant}/index.html"
                    for variant in self.GALLERY_VARIANTS
                },
            },
        )
        layouts = []
        for index in range(1, 3):
            stem = f"layout-{index:03d}.html"
            example_stems = {
                "baseline": stem,
                "domain": f"domain-{stem}",
            }
            layout_id = "demo.argument.sequence" if index == 1 else f"demo.layout.{index:03d}"
            layouts.append(
                {
                    "layout_id": layout_id,
                    "display_code": f"L{index:03d}",
                    "name": f"Layout {index:03d}",
                    "family": "demo",
                    "description": "Manifest-only deterministic fixture",
                    "roles": ["explain"],
                    "relations": ["sequence"],
                    "core_primitives": ["linear-sequence"],
                    "primitives": ["linear-sequence"],
                    "densities": ["balanced"],
                    "capacity": {
                        "semantic_units": {"min": 2, "max": 4},
                        "primary_items": {"min": 2, "max": 4},
                        "overflow_policy": "split-page",
                    },
                    "slots": [
                        {
                            "slot_id": "main",
                            "purpose": "main",
                            "required": True,
                            "min_items": 2,
                            "max_items": 4,
                            "allowed_providers": ["svg", "echarts", "atlas"],
                        },
                        {
                            "slot_id": "takeaway",
                            "purpose": "takeaway",
                            "required": True,
                            "min_items": 1,
                            "max_items": 1,
                            "allowed_providers": ["typography"],
                        },
                    ],
                    "renderers": ["svg", "echarts", "atlas", "typography"],
                    "examples": {
                        variant: f"themes/{self.THEME_ID}/gallery/{variant}/frames/{example_stems[variant]}"
                        for variant in self.GALLERY_VARIANTS
                    },
                    "selection_notes": "sequence + explain + balanced；仅提供候选事实，不做语义打分。",
                    "anti_patterns": ["do not copy blindly"],
                }
            )
            for variant in self.GALLERY_VARIANTS:
                frame = (
                    self.root
                    / "themes"
                    / self.THEME_ID
                    / "gallery"
                    / variant
                    / "frames"
                    / example_stems[variant]
                )
                frame.parent.mkdir(parents=True, exist_ok=True)
                frame.write_text(f"<!doctype html><title>{variant}-{index}</title>\n", encoding="utf-8")
        for variant in self.GALLERY_VARIANTS:
            index_path = self.root / "themes" / self.THEME_ID / "gallery" / variant / "index.html"
            index_path.write_text("<!doctype html><title>gallery</title>\n", encoding="utf-8")
        write_json(
            self.layout_manifest_path,
            {
                "schema_version": "1.0",
                "theme_id": self.THEME_ID,
                "layout_count": 2,
                "gallery_variants": list(self.GALLERY_VARIANTS),
                "core_primitive_ids": sorted(CORE_PRIMITIVES),
                "density_levels": ["balanced"],
                "provider_ids": ["typography", "svg", "echarts", "atlas"],
                "layouts": layouts,
            },
        )

    def _write_component_catalog(self) -> None:
        write_json(
            self.root / "themes" / self.THEME_ID / "atlas-catalog.json",
            {
                "schema_version": "1.0",
                "components": [{
                "component_id": "atlas.process-flow.vertical",
                "name": "纵向流程",
                "description": "结构组件候选",
                "roles": ["explain"],
                "relations": ["sequence"],
                "densities": ["balanced"],
                "providers": ["atlas"],
                "selection_notes": "只描述 manifest 支持范围。",
                }],
            },
        )

    @staticmethod
    def _content_document() -> dict:
        return {
            "schema_version": "1.0",
            "brief": {
                "title": "Retention",
                "objective": "Explain the result",
                "audience": "Product team",
                "scenario": "Review",
                "language": "zh-CN",
                "page_limits": {"min": 1, "max": 3, "requested": 1},
                "must_include": ["retention"],
                "must_avoid": [],
                "gaps": [],
            },
            "sources": [
                {
                    "id": "src.brief",
                    "kind": "raw_text",
                    "title": "User brief",
                    "locator": "inline:user",
                    "synthetic": False,
                }
            ],
            "content_items": [
                {
                    "id": "item.metric",
                    "kind": "metric",
                    "statement": "Retention reached 55",
                    "priority": "must",
                    "status": "sourced",
                    "status_note": "Provided by user",
                    "source_refs": ["src.brief"],
                    "atomic_values": [
                        {"id": "atom.rate", "label": "Retention", "value": 55, "unit": "%"}
                    ],
                    "relations": [],
                }
            ],
        }

    @staticmethod
    def _plan_document() -> dict:
        return {
            "schema_version": "1.0",
            "content_file": "content.json",
            "thesis": "The release improved retention",
            "narrative_type": "argument-evidence",
            "page_budget": {
                "min": 1,
                "max": 3,
                "target": 1,
                "reason": "One atomic claim",
                "drivers": [
                    {"type": "independent_claim", "count": 1, "reason": "One standalone result"}
                ],
            },
            "confirmation": {"mode": "adaptive", "decision": "proceed", "triggers": [], "questions": []},
            "sections": [
                {
                    "section_id": "section.main",
                    "title": "Result",
                    "purpose": "Explain the result",
                    "page_refs": ["page.one"],
                }
            ],
            "pages": [
                {
                    "page_id": "page.one",
                    "order": 1,
                    "section_id": "section.main",
                    "role": "explain",
                    "assertion_title": "Retention reached 55%",
                    "audience_question": "What changed?",
                    "takeaway": "The release moved the metric",
                    "content_refs": ["item.metric", "atom.rate"],
                    "evidence_refs": [],
                    "relation_shape": {"primary": "sequence", "secondary": [], "reason": "Show cause then result"},
                    "spatial_primitive": "linear-sequence",
                    "density_intent": "balanced",
                    "blocks": [
                        {
                            "block_id": "block.main",
                            "purpose": "Show metric progression",
                            "importance": "primary",
                            "semantic_form": "diagram",
                            "content_refs": ["item.metric", "atom.rate"],
                        },
                        {
                            "block_id": "block.takeaway",
                            "purpose": "State conclusion",
                            "importance": "support",
                            "semantic_form": "headline",
                            "content_refs": ["item.metric"],
                        },
                    ],
                }
            ],
            "coverage_decisions": [
                {
                    "content_ref": "item.metric",
                    "disposition": "include",
                    "page_refs": ["page.one"],
                    "reason": "Core claim",
                },
                {
                    "content_ref": "atom.rate",
                    "disposition": "include",
                    "page_refs": ["page.one"],
                    "reason": "Exact value",
                },
            ],
        }

    @staticmethod
    def _render_document() -> dict:
        return {
            "schema_version": "2.0",
            "content_file": "content.json",
            "deck_plan_file": "deck-plan.json",
            "theme_id": FixtureRepo.THEME_ID,
            "pages": [
                {
                    "page_id": "page.one",
                    "output_file": "frames/page.one.html",
                    "layout_decision": {
                        "source": "gallery",
                        "reuse_mode": "adapt",
                        "layout_id": "demo.argument.sequence",
                        "candidate_evaluations": [
                            {
                                "layout_id": "demo.argument.sequence",
                                "verdict": "fit",
                                "reason": "关系、阅读顺序、区域和容量均满足当前页面需求。",
                            }
                        ],
                    },
                    "density": "balanced",
                    "rationale": "内容是两个连续语义单元，用线性主区加结论槽位表达因果。",
                    "capacity_status": "fit",
                    "core_primitive": "linear-sequence",
                    "html_attributes": {
                        "data-page-id": "page.one",
                        "data-page-role": "explain",
                        "data-theme": FixtureRepo.THEME_ID,
                        "data-layout-source": "gallery",
                        "data-layout": "demo.argument.sequence",
                        "data-density": "balanced",
                        "data-reuse-mode": "adapt",
                    },
                    "slots": [
                        {
                            "slot_id": "main",
                            "block_id": "block.main",
                            "visual_role": "primary",
                            "component_decision": {
                                "action": "replace",
                                "reason": "用语义 SVG 替换样张中的通用主组件。",
                            },
                            "renderer": {
                                "provider": "svg",
                                "component": "sequence-path",
                                "content_refs": ["item.metric", "atom.rate"],
                                "theme_adapter": f"{FixtureRepo.THEME_ID}.svg",
                            },
                        },
                        {
                            "slot_id": "takeaway",
                            "block_id": "block.takeaway",
                            "visual_role": "support",
                            "component_decision": {
                                "action": "keep",
                                "reason": "结论文字槽位与样张组件完全匹配。",
                            },
                            "renderer": {
                                "provider": "typography",
                                "component": "takeaway",
                                "content_refs": ["item.metric"],
                                "theme_adapter": f"{FixtureRepo.THEME_ID}.typography",
                            },
                        },
                    ],
                }
            ],
        }

    def flush(self) -> None:
        write_json(self.deck / "content.json", self.content)
        write_json(self.deck / "deck-plan.json", self.plan)
        write_json(self.deck / "render-plan.json", self.render)
        self.html_path.parent.mkdir(parents=True, exist_ok=True)
        self.html_path.write_text(
            """<!doctype html>
<main data-page-id="page.one" data-page-role="explain" data-theme="minimal-neutral"
      data-layout-source="gallery" data-layout="demo.argument.sequence"
      data-density="balanced" data-reuse-mode="adapt">
  <section data-block-id="block.main" data-provider="svg" data-component="sequence-path"
           data-content-ref="item.metric atom.rate">Retention 55%</section>
  <section data-block-id="block.takeaway" data-provider="typography" data-component="takeaway"
           data-content-ref="item.metric">The release moved the metric</section>
</main>
""",
            encoding="utf-8",
        )


class JsonSchemaSubsetTests(unittest.TestCase):
    def test_valid_and_invalid_schema_fixtures(self) -> None:
        schema = FIXTURES / "schema" / "simple.schema.json"
        validator = JsonSchemaValidator(schema)
        valid = validator.validate(load_json(FIXTURES / "schema" / "valid.json"))
        invalid = validator.validate(load_json(FIXTURES / "schema" / "invalid.json"))
        self.assertTrue(valid.ok, [issue.format() for issue in valid.issues])
        self.assertFalse(invalid.ok)
        codes = {issue.code for issue in invalid.errors}
        self.assertIn("schema.required", codes)
        self.assertIn("schema.pattern", codes)
        self.assertIn("schema.maximum", codes)
        self.assertIn("schema.uniqueItems", codes)
        self.assertIn("schema.additionalProperties", codes)


class ContractValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.fixture = FixtureRepo(Path(self.temporary.name))

    def assert_has_code(self, result, code: str) -> None:
        self.assertIn(code, {issue.code for issue in result.errors}, [issue.format() for issue in result.issues])

    def test_valid_all_pipeline_and_cli(self) -> None:
        result = validate_all(self.fixture.deck, self.fixture.root)
        self.assertTrue(result.ok, [issue.format() for issue in result.issues])
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "validate.py"),
                "all",
                str(self.fixture.deck),
                "--root",
                str(self.fixture.root),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("PASS all", completed.stdout)

    def test_content_schema_failure_and_missing_schema_are_clear(self) -> None:
        self.fixture.content["content_items"][0]["priority"] = "urgent"
        self.fixture.flush()
        invalid = validate_content_target(self.fixture.deck, self.fixture.root)
        self.assert_has_code(invalid, "schema.enum")
        (self.fixture.root / "core" / "schemas" / "content.schema.json").unlink()
        missing = validate_content_target(self.fixture.deck, self.fixture.root)
        self.assert_has_code(missing, "config.schema")

    def test_default_theme_and_unknown_theme(self) -> None:
        self.assertEqual(resolve_theme(self.fixture.root).theme_id, FixtureRepo.THEME_ID)
        self.fixture.render["theme_id"] = "missing-theme"
        self.fixture.flush()
        result = validate_render_target(self.fixture.deck, self.fixture.root)
        self.assert_has_code(result, "render.unknown_theme")

    def test_plan_rejects_ghost_deck(self) -> None:
        page = self.fixture.plan["pages"][0]
        page["content_refs"] = []
        page["blocks"] = []
        self.fixture.plan["coverage_decisions"] = []
        self.fixture.flush()
        result = validate_plan_target(self.fixture.deck, self.fixture.root)
        self.assert_has_code(result, "plan.ghost_deck")
        self.assert_has_code(result, "plan.ghost_page")

    def test_must_item_and_atom_coverage(self) -> None:
        page = self.fixture.plan["pages"][0]
        page["content_refs"].remove("atom.rate")
        page["blocks"][0]["content_refs"].remove("atom.rate")
        self.fixture.plan["coverage_decisions"] = [self.fixture.plan["coverage_decisions"][0]]
        self.fixture.render["pages"][0]["slots"][0]["renderer"]["content_refs"].remove("atom.rate")
        self.fixture.flush()
        result = validate_coverage_target(self.fixture.deck, self.fixture.root)
        self.assert_has_code(result, "coverage.must_missing_plan")
        self.assert_has_code(result, "coverage.must_missing_block")
        self.assert_has_code(result, "coverage.must_decision")
        self.assert_has_code(result, "coverage.must_missing_render")

    def test_render_rejects_copy_only_rationale(self) -> None:
        page = self.fixture.render["pages"][0]
        page["layout_decision"]["reuse_mode"] = "copy"
        for slot in page["slots"]:
            slot["component_decision"]["action"] = "keep"
        page["rationale"] = "直接照抄模板，不做任何内容关系判断。"
        page["html_attributes"]["data-reuse-mode"] = "copy"
        html = self.fixture.html_path.read_text(encoding="utf-8").replace(
            'data-reuse-mode="adapt"', 'data-reuse-mode="copy"'
        )
        self.fixture.flush()
        self.fixture.html_path.write_text(html, encoding="utf-8")
        result = validate_render_target(self.fixture.deck, self.fixture.root)
        self.assert_has_code(result, "render.rationale")

    def test_copy_requires_keep_and_adapt_requires_replace(self) -> None:
        page = self.fixture.render["pages"][0]
        page["layout_decision"]["reuse_mode"] = "copy"
        page["html_attributes"]["data-reuse-mode"] = "copy"
        self.fixture.flush()
        copy_result = validate_render_target(self.fixture.deck, self.fixture.root)
        self.assert_has_code(copy_result, "render.component_decision")

        page["layout_decision"]["reuse_mode"] = "adapt"
        page["html_attributes"]["data-reuse-mode"] = "adapt"
        for slot in page["slots"]:
            slot["component_decision"]["action"] = "keep"
        self.fixture.flush()
        adapt_result = validate_render_target(self.fixture.deck, self.fixture.root)
        self.assert_has_code(adapt_result, "render.component_decision")

    def test_render_rejects_unsupported_provider_and_overflow(self) -> None:
        page = self.fixture.render["pages"][0]
        renderer = page["slots"][0]["renderer"]
        renderer["provider"] = "table"
        html = self.fixture.html_path.read_text(encoding="utf-8").replace(
            'data-provider="svg"', 'data-provider="table"'
        )
        manifest = load_json(self.fixture.layout_manifest_path)
        manifest["layouts"][0]["capacity"]["semantic_units"]["max"] = 1
        manifest["layouts"][0]["slots"][0]["max_items"] = 1
        write_json(self.fixture.layout_manifest_path, manifest)
        self.fixture.flush()
        self.fixture.html_path.write_text(html, encoding="utf-8")
        result = validate_render_target(self.fixture.deck, self.fixture.root)
        self.assert_has_code(result, "render.unsupported_provider")
        self.assert_has_code(result, "render.slot_overflow")
        self.assert_has_code(result, "render.capacity_overflow")

    def test_render_enforces_core_primitive_chain(self) -> None:
        page = self.fixture.render["pages"][0]
        page["core_primitive"] = "focus-field"
        self.fixture.flush()
        result = validate_render_target(self.fixture.deck, self.fixture.root)
        self.assert_has_code(result, "render.core_primitive_mismatch")
        self.assert_has_code(result, "render.unsupported_core_primitive")

    def test_custom_layout_does_not_require_gallery_registration(self) -> None:
        page = self.fixture.render["pages"][0]
        page["layout_decision"] = {
            "source": "custom",
            "reuse_mode": "custom",
            "layout_id": "custom.page.one",
            "candidate_evaluations": [
                {
                    "layout_id": "demo.argument.sequence",
                    "verdict": "reject",
                    "reason": "现有版式不能承载此页需要的独立自定义区域结构。",
                }
            ],
            "custom_contract": {
                "reading_order": ["main", "takeaway"],
                "capacity": {
                    "semantic_units": {"min": 2, "max": 4},
                    "primary_items": {"min": 2, "max": 4},
                },
                "regions": [
                    {
                        "slot_id": "main",
                        "block_id": "block.main",
                        "visual_role": "primary",
                        "min_items": 2,
                        "max_items": 4,
                    },
                    {
                        "slot_id": "takeaway",
                        "block_id": "block.takeaway",
                        "visual_role": "support",
                        "min_items": 1,
                        "max_items": 1,
                    },
                ],
            },
        }
        for slot in page["slots"]:
            slot["component_decision"]["action"] = "select"
        page["html_attributes"]["data-layout-source"] = "custom"
        page["html_attributes"]["data-layout"] = "custom.page.one"
        page["html_attributes"]["data-reuse-mode"] = "custom"
        (self.fixture.root / "themes" / self.fixture.THEME_ID / "atlas-catalog.json").unlink()
        self.fixture.flush()
        html = self.fixture.html_path.read_text(encoding="utf-8")
        html = html.replace('data-layout-source="gallery"', 'data-layout-source="custom"')
        html = html.replace('data-layout="demo.argument.sequence"', 'data-layout="custom.page.one"')
        html = html.replace('data-reuse-mode="adapt"', 'data-reuse-mode="custom"')
        self.fixture.html_path.write_text(html, encoding="utf-8")
        result = validate_render_target(self.fixture.deck, self.fixture.root)
        self.assertTrue(result.ok, [issue.format() for issue in result.issues])
        self.assertNotIn("render.unsupported_layout", {issue.code for issue in result.errors})

    def test_render_v2_contract_fixtures_cover_copy_adapt_and_custom(self) -> None:
        fixture_root = FIXTURES / "render-v2"
        for case in ("gallery-copy", "gallery-adapt", "custom"):
            with self.subTest(case=case):
                page = load_json(fixture_root / case / "page.json")
                self.fixture.render["pages"] = [page]
                self.fixture.flush()
                attrs = page["html_attributes"]
                html = self.fixture.html_path.read_text(encoding="utf-8")
                html = html.replace(
                    'data-layout-source="gallery"',
                    f'data-layout-source="{attrs["data-layout-source"]}"',
                )
                html = html.replace(
                    'data-layout="demo.argument.sequence"',
                    f'data-layout="{attrs["data-layout"]}"',
                )
                html = html.replace(
                    'data-reuse-mode="adapt"',
                    f'data-reuse-mode="{attrs["data-reuse-mode"]}"',
                )
                self.fixture.html_path.write_text(html, encoding="utf-8")
                result = validate_render_target(self.fixture.deck, self.fixture.root)
                self.assertTrue(result.ok, [issue.format() for issue in result.issues])

    def test_gallery_structure_changes_require_custom(self) -> None:
        baseline = copy.deepcopy(self.fixture.render["pages"][0])

        cases = {}
        reordered = copy.deepcopy(baseline)
        reordered["slots"].reverse()
        cases["reordered-slot"] = reordered

        added = copy.deepcopy(baseline)
        extra = copy.deepcopy(added["slots"][1])
        extra["slot_id"] = "extra"
        added["slots"].append(extra)
        cases["added-slot"] = added

        embedded_contract = copy.deepcopy(baseline)
        embedded_contract["layout_decision"]["custom_contract"] = {
            "reading_order": ["main", "takeaway"],
            "capacity": {"semantic_units": {"min": 2, "max": 4}},
            "regions": [],
        }
        cases["embedded-custom-contract"] = embedded_contract

        for case, page in cases.items():
            with self.subTest(case=case):
                self.fixture.render["pages"] = [page]
                self.fixture.flush()
                result = validate_render_target(self.fixture.deck, self.fixture.root)
                self.assert_has_code(result, "render.gallery_structure_changed")

    def test_echarts_series_is_not_limited_by_local_catalog(self) -> None:
        page = self.fixture.render["pages"][0]
        renderer = page["slots"][0]["renderer"]
        renderer.update(
            {
                "provider": "echarts",
                "component": "radar",
                "data_ref": "item.metric",
                "encode": {"indicator": "metric", "value": "atom.rate"},
            }
        )
        (self.fixture.root / "themes" / self.fixture.THEME_ID / "atlas-catalog.json").unlink()
        self.fixture.flush()
        html = self.fixture.html_path.read_text(encoding="utf-8")
        html = html.replace('data-provider="svg"', 'data-provider="echarts"')
        html = html.replace('data-component="sequence-path"', 'data-component="radar"')
        self.fixture.html_path.write_text(html, encoding="utf-8")
        result = validate_render_target(self.fixture.deck, self.fixture.root)
        self.assertTrue(result.ok, [issue.format() for issue in result.issues])

        renderer.pop("data_ref")
        renderer["encode"] = {}
        self.fixture.flush()
        self.fixture.html_path.write_text(html, encoding="utf-8")
        invalid = validate_render_target(self.fixture.deck, self.fixture.root)
        self.assert_has_code(invalid, "render.echarts_data_ref")
        self.assert_has_code(invalid, "render.echarts_encode")

    def test_unknown_atlas_component_is_rejected_only_when_atlas_is_used(self) -> None:
        page = self.fixture.render["pages"][0]
        renderer = page["slots"][0]["renderer"]
        renderer.update({"provider": "atlas", "component": "不存在的组件"})
        self.fixture.flush()
        html = self.fixture.html_path.read_text(encoding="utf-8")
        html = html.replace('data-provider="svg"', 'data-provider="atlas"')
        html = html.replace('data-component="sequence-path"', 'data-component="不存在的组件"')
        self.fixture.html_path.write_text(html, encoding="utf-8")
        result = validate_render_target(self.fixture.deck, self.fixture.root)
        self.assert_has_code(result, "render.unknown_component")

    def test_render_plan_v1_frames_remains_valid(self) -> None:
        page = self.fixture.render["pages"][0]
        decision = page.pop("layout_decision")
        page["layout_id"] = decision["layout_id"]
        page["reuse_mode"] = decision["reuse_mode"]
        page["reuse_source"] = decision["layout_id"]
        page["theme_primitives"] = [page["core_primitive"]]
        page["html_attributes"].pop("data-layout-source")
        for slot in page["slots"]:
            slot.pop("component_decision")
        self.fixture.render["schema_version"] = "1.0"
        self.fixture.flush()
        result = validate_render_target(self.fixture.deck, self.fixture.root)
        self.assertTrue(result.ok, [issue.format() for issue in result.issues])

    def test_render_plan_v2_single_html_requires_canonical_index_entry(self) -> None:
        render = copy.deepcopy(self.fixture.render)
        render["document_mode"] = "single-html"
        render["output_file"] = "deck.html"
        page = render["pages"][0]
        page.pop("output_file")
        page["html_attributes"].update(
            {
                "data-page-title": "Retention reached 55%",
                "data-page-summary": "The release moved the metric",
                "data-section-id": "section.main",
                "data-section-title": "Main",
            }
        )
        result = JsonSchemaValidator(
            REPO_ROOT / "core" / "schemas" / "render-plan.schema.json"
        ).validate(render, "render-plan.json")
        self.assert_has_code(result, "schema.const")

    def test_render_checks_canonical_page_and_component_data_attributes(self) -> None:
        html = self.fixture.html_path.read_text(encoding="utf-8")
        html = html.replace('data-theme="minimal-neutral"', 'data-theme-id="minimal-neutral"')
        html = html.replace('data-component="takeaway"', 'data-component-id="takeaway"')
        self.fixture.html_path.write_text(html, encoding="utf-8")
        result = validate_render_target(self.fixture.deck, self.fixture.root)
        self.assert_has_code(result, "render.html_page_data")
        self.assert_has_code(result, "render.html_component_data")

    def test_gallery_uses_declared_count_and_variant_names(self) -> None:
        valid = validate_gallery(self.fixture.root, FixtureRepo.THEME_ID)
        self.assertTrue(valid.ok, [issue.format() for issue in valid.issues])
        missing = (
            self.fixture.root
            / "themes"
            / FixtureRepo.THEME_ID
            / "gallery"
            / "domain"
            / "frames"
            / "domain-layout-002.html"
        )
        missing.unlink()
        invalid = validate_gallery(self.fixture.root, FixtureRepo.THEME_ID)
        self.assert_has_code(invalid, "gallery.variant_count")
        self.assert_has_code(invalid, "gallery.example_missing")

    def test_paper_ink_gallery_matches_its_declared_contract(self) -> None:
        manifest = load_json(REPO_ROOT / "themes" / "paper-ink" / "layout-manifest.json")
        theme = load_json(REPO_ROOT / "themes" / "paper-ink" / "theme.json")
        self.assertEqual(manifest["layout_count"], 63)
        self.assertEqual(len(manifest["layouts"]), 63)
        self.assertEqual(set(theme["galleries"]), {"general", "ai"})
        result = validate_gallery(REPO_ROOT, "paper-ink")
        self.assertTrue(result.ok, [issue.format() for issue in result.issues])

    def test_gallery_validates_core_primitive_registry(self) -> None:
        manifest = load_json(self.fixture.layout_manifest_path)
        manifest["core_primitive_ids"].remove("radial-burst")
        manifest["layouts"][0]["core_primitives"] = ["not-a-core-primitive"]
        write_json(self.fixture.layout_manifest_path, manifest)
        result = validate_gallery(self.fixture.root, FixtureRepo.THEME_ID)
        self.assert_has_code(result, "gallery.core_primitive_ids")
        self.assert_has_code(result, "gallery.unknown_core_primitive")

    def test_gallery_rejects_empty_and_non_object_layouts(self) -> None:
        manifest = load_json(self.fixture.layout_manifest_path)
        manifest["layouts"].append("not-an-object")
        manifest["layout_count"] = 3
        write_json(self.fixture.layout_manifest_path, manifest)
        malformed = validate_gallery(self.fixture.root, FixtureRepo.THEME_ID)
        self.assert_has_code(malformed, "config.gallery")

        manifest["layouts"] = []
        manifest["layout_count"] = 0
        write_json(self.fixture.layout_manifest_path, manifest)
        empty = validate_gallery(self.fixture.root, FixtureRepo.THEME_ID)
        self.assert_has_code(empty, "gallery.layout_count")
        self.assert_has_code(empty, "gallery.empty")

    def test_content_relation_target_must_exist_and_not_self_reference(self) -> None:
        item = self.fixture.content["content_items"][0]
        item["relations"] = [
            {"type": "supports", "target_ref": "item.metric", "reason": "Self loop"},
            {"type": "depends_on", "target_ref": "item.missing", "reason": "Missing target"},
            {"type": "supports", "target_ref": [], "reason": "Wrong JSON type"},
        ]
        self.fixture.flush()
        result = validate_content_target(self.fixture.deck, self.fixture.root)
        self.assert_has_code(result, "content.self_relation")
        self.assert_has_code(result, "content.unknown_relation_target")
        self.assert_has_code(result, "content.invalid_relation_target")

    def test_duplicate_assertion_and_takeaway_are_rejected(self) -> None:
        duplicate = copy.deepcopy(self.fixture.plan["pages"][0])
        duplicate["page_id"] = "page.two"
        duplicate["order"] = 2
        duplicate["assertion_title"] += "。"
        duplicate["takeaway"] += "!"
        duplicate["blocks"][0]["block_id"] = "block.two.main"
        duplicate["blocks"][1]["block_id"] = "block.two.takeaway"
        self.fixture.plan["pages"].append(duplicate)
        self.fixture.plan["sections"][0]["page_refs"].append("page.two")
        self.fixture.plan["page_budget"]["target"] = 2
        self.fixture.flush()
        result = validate_plan_target(self.fixture.deck, self.fixture.root)
        self.assert_has_code(result, "plan.duplicate_assertion")
        self.assert_has_code(result, "plan.duplicate_takeaway")

    def test_blank_ghost_deck_text_is_rejected(self) -> None:
        page = self.fixture.plan["pages"][0]
        page["assertion_title"] = "   "
        page["takeaway"] = "\u3000"
        self.fixture.flush()
        result = validate_plan_target(self.fixture.deck, self.fixture.root)
        self.assert_has_code(result, "plan.blank_assertion")
        self.assert_has_code(result, "plan.blank_takeaway")

    def test_page_budget_requires_a_countable_driver(self) -> None:
        self.fixture.plan["page_budget"]["drivers"] = []
        self.fixture.flush()
        result = validate_plan_target(self.fixture.deck, self.fixture.root)
        self.assert_has_code(result, "schema.minItems")

    def test_all_adaptive_confirmation_triggers_are_derived(self) -> None:
        baseline_content = copy.deepcopy(self.fixture.content)
        baseline_plan = copy.deepcopy(self.fixture.plan)

        def reset() -> None:
            self.fixture.content = copy.deepcopy(baseline_content)
            self.fixture.plan = copy.deepcopy(baseline_plan)

        cases = []

        reset()
        self.fixture.content["brief"]["objective"] = "   "
        cases.append(
            (
                "missing_objective_or_audience",
                copy.deepcopy(self.fixture.content),
                copy.deepcopy(self.fixture.plan),
            )
        )

        reset()
        self.fixture.content["content_items"].append(
            {
                "id": "item.other",
                "kind": "metric",
                "statement": "A conflicting source says 40",
                "priority": "should",
                "status": "sourced",
                "status_note": "Provided by user",
                "source_refs": ["src.brief"],
                "atomic_values": [],
                "relations": [],
            }
        )
        self.fixture.content["content_items"][0]["relations"] = [
            {"type": "contradicts", "target_ref": "item.other", "reason": "Sources disagree"}
        ]
        cases.append(("source_conflict", copy.deepcopy(self.fixture.content), copy.deepcopy(self.fixture.plan)))

        reset()
        self.fixture.plan["page_budget"]["drivers"].append(
            {"type": "page_limit", "count": 4, "reason": "Must claims need four pages"}
        )
        cases.append(("must_content_overflow", copy.deepcopy(self.fixture.content), copy.deepcopy(self.fixture.plan)))

        reset()
        self.fixture.content["content_items"][0]["status"] = "placeholder"
        self.fixture.content["content_items"][0]["status_note"] = "Waiting for verified value"
        cases.append(
            (
                "must_infer_or_placeholder_or_remove",
                copy.deepcopy(self.fixture.content),
                copy.deepcopy(self.fixture.plan),
            )
        )

        reset()
        self.fixture.content["brief"]["page_limits"]["requested"] = None
        self.fixture.plan["page_budget"]["max"] = 16
        self.fixture.plan["page_budget"]["target"] = 16
        cases.append(("raw_prose_16_plus", copy.deepcopy(self.fixture.content), copy.deepcopy(self.fixture.plan)))

        for trigger, content, plan in cases:
            with self.subTest(trigger=trigger):
                self.fixture.content = content
                self.fixture.plan = plan
                self.fixture.flush()
                result = validate_plan_target(self.fixture.deck, self.fixture.root)
                self.assertTrue(
                    any(issue.code == "plan.confirmation_trigger" and trigger in issue.message for issue in result.errors),
                    [issue.format() for issue in result.issues],
                )

    def test_adaptive_confirmation_rejects_spurious_pause(self) -> None:
        self.fixture.plan["confirmation"] = {
            "mode": "adaptive",
            "decision": "needs_confirmation",
            "triggers": ["source_conflict"],
            "questions": ["Which source should win?"],
        }
        self.fixture.flush()
        result = validate_plan_target(self.fixture.deck, self.fixture.root)
        self.assert_has_code(result, "plan.confirmation_spurious_trigger")
        self.assert_has_code(result, "plan.confirmation_decision")

    def test_core_rejects_theme_tokens_and_display_shortcodes(self) -> None:
        clean = validate_core_purity(self.fixture.root)
        self.assertTrue(clean.ok, [issue.format() for issue in clean.issues])
        leak = self.fixture.root / "core" / "references" / "leak.md"
        leak.parent.mkdir(parents=True, exist_ok=True)
        leak.write_text("paper-ink uses #191917 and sample B12\n", encoding="utf-8")
        invalid = validate_core_purity(self.fixture.root)
        self.assert_has_code(invalid, "core.theme_token")
        self.assert_has_code(invalid, "core.legacy_code")

    def test_catalog_filters_manifest_metadata_without_semantic_scoring(self) -> None:
        layout_cmd = [
            sys.executable,
            str(SCRIPTS / "catalog.py"),
            "layouts",
            "--root",
            str(self.fixture.root),
            "--role",
            "explain",
            "--relation",
            "sequence",
            "--density",
            "balanced",
            "--provider",
            "svg",
            "--primitive",
            "linear-sequence",
            "--name",
            "Layout 001",
            "--compact",
        ]
        layout_run = subprocess.run(layout_cmd, check=False, capture_output=True, text=True)
        self.assertEqual(layout_run.returncode, 0, layout_run.stderr)
        layout_payload = json.loads(layout_run.stdout)
        self.assertEqual(layout_payload["count"], 1)
        self.assertEqual(layout_payload["items"][0]["id"], "demo.argument.sequence")
        self.assertEqual(layout_payload["items"][0]["core_primitives"], ["linear-sequence"])
        self.assertEqual(layout_payload["semantic_decision"], "not-performed")

        component_run = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "catalog.py"),
                "components",
                "--root",
                str(self.fixture.root),
                "--role",
                "explain",
                "--relation",
                "sequence",
                "--density",
                "balanced",
                "--provider",
                "atlas",
                "--name",
                "纵向",
                "--compact",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(component_run.returncode, 0, component_run.stderr)
        component_payload = json.loads(component_run.stdout)
        self.assertEqual(component_payload["count"], 1)
        self.assertEqual(component_payload["items"][0]["id"], "atlas.process-flow.vertical")

        echarts_run = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "catalog.py"),
                "components",
                "--root",
                str(self.fixture.root),
                "--provider",
                "echarts",
                "--task",
                "trend",
                "--compact",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(echarts_run.returncode, 2, echarts_run.stdout + echarts_run.stderr)
        self.assertIn("ECharts 请查官方文档", echarts_run.stderr)


class SingleHtmlContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.deck = Path(self.temporary.name) / "single-html-deck"
        shutil.copytree(FIXTURES / "single-html-deck", self.deck)
        self.html = self.deck / "index.html"

    @staticmethod
    def error_codes(result) -> set[str]:
        return {issue.code for issue in result.errors}

    def validate(self):
        return validate_render_target(self.deck, REPO_ROOT)

    def test_render_plan_v11_single_html_is_valid(self) -> None:
        result = self.validate()
        self.assertTrue(result.ok, [issue.format() for issue in result.issues])

    def test_render_plan_v11_requires_canonical_index_entry(self) -> None:
        render_path = self.deck / "render-plan.json"
        render = load_json(render_path)
        render["output_file"] = "deck.html"
        write_json(render_path, render)
        self.assertIn("schema.oneOf", self.error_codes(self.validate()))

    def test_render_plan_v11_requires_layout_source_metadata(self) -> None:
        render_path = self.deck / "render-plan.json"
        render = load_json(render_path)
        render["pages"][0]["html_attributes"].pop("data-layout-source")
        write_json(render_path, render)
        self.assertIn("schema.oneOf", self.error_codes(self.validate()))

    def test_single_html_rejects_duplicate_page_id(self) -> None:
        source = self.html.read_text(encoding="utf-8").replace(
            'data-page-id="page.example-dense-ui"',
            'data-page-id="page.example-flow-kpi"',
            1,
        )
        self.html.write_text(source, encoding="utf-8")
        codes = self.error_codes(self.validate())
        self.assertIn("render.duplicate_html_page", codes)
        self.assertIn("render.html_page_missing", codes)

    def test_single_html_rejects_cross_slide_source_id(self) -> None:
        source = self.html.read_text(encoding="utf-8").replace(
            '<div class="stage">',
            '<div class="stage" id="shared-source">',
        )
        self.html.write_text(source, encoding="utf-8")
        self.assertIn("render.duplicate_source_id", self.error_codes(self.validate()))

    def test_single_html_rejects_missing_page(self) -> None:
        source = self.html.read_text(encoding="utf-8")
        source = re.sub(
            r'<section class="slide" data-page-id="page[.]example-dense-ui".*?</section>\s*</div></div>',
            '</div></div>',
            source,
            count=1,
            flags=re.S,
        )
        self.html.write_text(source, encoding="utf-8")
        self.assertIn("render.html_page_missing", self.error_codes(self.validate()))

    def test_single_html_rejects_content_owned_by_wrong_slide(self) -> None:
        source = self.html.read_text(encoding="utf-8").replace(
            'data-content-ref="item.delivery-process"',
            'data-content-ref="item.product-ui-state"',
            1,
        )
        self.html.write_text(source, encoding="utf-8")
        self.assertIn("render.html_content_refs", self.error_codes(self.validate()))

    def test_six_formal_examples_are_single_html_v11_goldens(self) -> None:
        examples = REPO_ROOT / "themes" / "paper-ink" / "examples"
        decks = sorted(path for path in examples.iterdir() if path.is_dir())
        self.assertEqual(len(decks), 6)
        for deck in decks:
            with self.subTest(deck=deck.name):
                render = load_json(deck / "render-plan.json")
                source = (deck / "index.html").read_text(encoding="utf-8").casefold()
                self.assertEqual(render["schema_version"], "1.1")
                self.assertEqual(render["document_mode"], "single-html")
                self.assertEqual(render["output_file"], "index.html")
                self.assertTrue(all("output_file" not in page for page in render["pages"]))
                self.assertNotIn("<iframe", source)
                self.assertNotIn("thumb-", source)
                self.assertFalse((deck / "frames").exists())
                result = validate_all(deck, REPO_ROOT)
                self.assertTrue(result.ok, [issue.format() for issue in result.issues])


if __name__ == "__main__":
    unittest.main()
