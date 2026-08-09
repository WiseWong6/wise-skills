from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True

from _ppt_contracts import (  # noqa: E402
    JsonSchemaValidator,
    _recipe_fingerprint,
    validate_content_target,
    validate_delivery_target,
    validate_gallery,
    validate_plan_target,
    validate_render_plan_target,
    validate_render_target,
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class DeckFixture:
    def __init__(self, directory: Path):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.content = {
            "contract_version": 2,
            "brief": {
                "title": "留存复盘",
                "objective": "说明本轮改版的留存结果",
                "audience": "产品团队",
                "scenario": "内部复盘会",
                "language": "zh-CN",
                "user_constraints": [
                    {
                        "constraint_id": "constraint.one-page",
                        "type": "page_limit",
                        "exact_pages": 1,
                        "source_refs": ["src.user"],
                    }
                ],
                "gaps": [],
            },
            "sources": [
                {
                    "id": "src.user",
                    "kind": "user_statement",
                    "title": "用户说明",
                    "locator": "inline:user",
                    "synthetic": False,
                }
            ],
            "assets": [],
            "content_items": [
                {
                    "id": "item.metric",
                    "epistemic_role": "fact",
                    "content_form": "metric",
                    "statement": "本轮留存达到 55%",
                    "priority": "must",
                    "status": "sourced",
                    "status_note": "用户明确提供",
                    "source_refs": ["src.user"],
                    "atomic_values": [
                        {"id": "atom.rate", "label": "留存率", "value": 55, "unit": "%"}
                    ],
                    "structured_data": {
                        "rows": [
                            {"label": "改版前", "value": 42},
                            {"label": "改版后", "value": 55},
                        ]
                    },
                    "relations": [],
                }
            ],
        }
        self.plan = {
            "contract_version": 2,
            "content_file": "content.json",
            "thesis": "本轮改版提升了留存",
            "narrative_type": "argument-evidence",
            "planning_basis": {
                "mode": "user-constrained",
                "scenario": "内部复盘会",
                "scenario_origin": "user",
                "user_constraint_refs": ["constraint.one-page"],
                "research_source_refs": [],
                "assumptions": [],
                "reason": "用户明确要求一页，单个结果也适合一页讲清。",
            },
            "page_budget": {
                "target": 1,
                "basis": [
                    {
                        "type": "user_constraint",
                        "constraint_refs": ["constraint.one-page"],
                        "reason": "用户明确要求一页。",
                    },
                    {
                        "type": "content_structure",
                        "content_refs": ["item.metric", "atom.rate"],
                        "reason": "只有一个独立结果。",
                    },
                ],
                "reason": "一页足以建立判断并给出数字证据。",
            },
            "confirmation": {
                "mode": "adaptive",
                "decision": "proceed",
                "assessments": [],
                "user_questions": [],
            },
            "sections": [
                {
                    "section_id": "section.result",
                    "title": "结果",
                    "purpose": "说明留存结果",
                    "page_refs": ["page.result"],
                }
            ],
            "pages": [
                {
                    "page_id": "page.result",
                    "order": 1,
                    "section_id": "section.result",
                    "role": "prove",
                    "assertion_title": "本轮留存达到 55%",
                    "audience_question": "改版带来了什么结果？",
                    "takeaway": "留存从 42% 提升到 55%。",
                    "content_refs": ["item.metric", "atom.rate"],
                    "evidence_refs": ["item.metric", "atom.rate"],
                    "relation_shape": {
                        "primary": "focus",
                        "secondary": ["evidence"],
                        "reason": "一个结果和一个关键数字构成焦点证据。",
                    },
                    "spatial_primitive": "focus-field",
                    "blocks": [
                        {
                            "block_id": "block.main",
                            "purpose": "显示核心结果",
                            "importance": "primary",
                            "semantic_form": "metrics",
                            "content_refs": ["item.metric", "atom.rate"],
                        }
                    ],
                }
            ],
            "coverage_decisions": [
                {
                    "content_ref": "item.metric",
                    "disposition": "include",
                    "page_refs": ["page.result"],
                    "reason": "核心事实。",
                },
                {
                    "content_ref": "atom.rate",
                    "disposition": "include",
                    "page_refs": ["page.result"],
                    "reason": "必须显示的数字。",
                },
            ],
        }
        self.render = {
            "contract_version": 2,
            "content_file": "content.json",
            "deck_plan_file": "deck-plan.json",
            "theme_id": "paper-ink",
            "typography_mode": "mixed",
            "output_file": "index.html",
            "pages": [
                {
                    "page_id": "page.result",
                    "layout_decision": {
                        "source": "custom",
                        "candidate_evaluations": [
                            {
                                "recipe_id": "paper-ink.data.kpi-band",
                                "verdict": "reject",
                                "reason": "本页需要自定义单焦点结构，完整横带会制造多余区域。",
                            }
                        ],
                        "custom_contract": {
                            "reading_order": ["main"],
                            "regions": [
                                {
                                    "slot_id": "main",
                                    "block_id": "block.main",
                                    "visual_role": "primary",
                                    "min_items": 1,
                                    "max_items": 2,
                                }
                            ],
                        },
                    },
                    "rationale": "单个结果只需要一个明确焦点，不需要额外结构。",
                    "emphasis": {
                        "mode": "none",
                        "reason": "页面已经只有一个焦点，不需要额外强调。",
                    },
                    "slots": [
                        {
                            "slot_id": "main",
                            "block_id": "block.main",
                            "visual_role": "primary",
                            "renderer": {
                                "renderer_kind": "typography",
                                "component_source": "native",
                                "component_id": "hero-metric",
                                "content_refs": ["item.metric", "atom.rate"],
                                "theme_adapter_id": "paper-ink.typography",
                            },
                        }
                    ],
                }
            ],
        }
        self.flush()

    def html(self, component: str | None = None, *, root: str = "wise-ppt-deck") -> str:
        component = component or (
            '<div data-block-id="block.main" data-renderer-kind="typography" '
            'data-component-source="native" data-component-id="hero-metric" '
            'data-theme-adapter-id="paper-ink.typography" '
            'data-content-ref="item.metric atom.rate">55%</div>'
        )
        return (
            "<!doctype html>"
            f'<html data-runtime="{root}" data-typography-mode="mixed"><body>'
            '<section class="slide" data-page-id="page.result" '
            'data-layout-source="custom">'
            f"{component}</section></body></html>"
        )

    def flush(self, *, html: bool = True) -> None:
        write_json(self.directory / "content.json", self.content)
        write_json(self.directory / "deck-plan.json", self.plan)
        write_json(self.directory / "render-plan.json", self.render)
        if html:
            (self.directory / "index.html").write_text(self.html(), encoding="utf-8")

    def gallery_render(self) -> None:
        self.render["pages"][0] = {
            "page_id": "page.result",
            "layout_decision": {
                "source": "gallery",
                "recipe_id": "paper-ink.data.kpi-band",
                "candidate_evaluations": [
                    {
                        "recipe_id": "paper-ink.data.kpi-band",
                        "verdict": "exact_fit",
                        "reason": "关键数字、焦点关系、槽位容量与阅读顺序全部匹配。",
                    }
                ],
                "payload": {
                    "bindings": [
                        {
                            "slot_id": "kpis",
                            "content_refs": ["item.metric", "atom.rate"],
                        },
                        {
                            "slot_id": "support",
                            "content_refs": ["item.metric"],
                        },
                        {
                            "slot_id": "takeaway",
                            "content_refs": ["item.metric"],
                        },
                    ]
                },
            },
            "rationale": "现成 KPI 横带完整满足页面表达，直接绑定内容。",
            "emphasis": {
                "mode": "none",
                "reason": "横带已经把关键数字放在唯一焦点。",
            },
        }
        component = (
            '<svg data-slot-id="kpis" data-renderer-kind="svg" '
            'data-component-source="native" '
            'data-component-id="native.paper-ink.data.kpi-band.kpis" '
            'data-content-ref="item.metric atom.rate"><text>55%</text></svg>'
            '<p data-slot-id="support" data-renderer-kind="typography" '
            'data-component-source="native" '
            'data-component-id="native.paper-ink.data.kpi-band.support" '
            'data-content-ref="item.metric">留存从 42% 提升</p>'
            '<p data-slot-id="takeaway" data-renderer-kind="typography" '
            'data-component-source="native" '
            'data-component-id="native.paper-ink.data.kpi-band.takeaway" '
            'data-content-ref="item.metric">本轮改版提升了留存</p>'
        )
        self.flush(html=False)
        (self.directory / "index.html").write_text(
            "<!doctype html>"
            '<html data-runtime="wise-ppt-deck" data-typography-mode="mixed"><body>'
            '<section class="slide" data-page-id="page.result" '
            'data-layout-source="gallery" data-recipe-id="paper-ink.data.kpi-band">'
            f"{component}</section></body></html>",
            encoding="utf-8",
        )

    def composition_render(self) -> None:
        self.plan["pages"][0]["blocks"].extend(
            [
                {
                    "block_id": "block.support",
                    "purpose": "补充结果背景",
                    "importance": "support",
                    "semantic_form": "prose",
                    "content_refs": ["item.metric"],
                },
                {
                    "block_id": "block.takeaway",
                    "purpose": "收束页面结论",
                    "importance": "support",
                    "semantic_form": "prose",
                    "content_refs": ["item.metric"],
                },
            ]
        )
        self.render["pages"][0] = {
            "page_id": "page.result",
            "layout_decision": {
                "source": "composition",
                "recipe_id": "paper-ink.data.kpi-band",
                "candidate_evaluations": [
                    {
                        "recipe_id": "paper-ink.data.kpi-band",
                        "verdict": "structure_fit",
                        "reason": "三段区域和阅读顺序匹配，但主数据组件需要替换。",
                    }
                ],
            },
            "rationale": "保留横带结构，替换主数据组件以满足字段映射。",
            "emphasis": {
                "mode": "none",
                "reason": "结构本身已形成单一焦点。",
            },
            "slots": [
                {
                    "slot_id": "kpis",
                    "block_id": "block.main",
                    "visual_role": "primary",
                    "renderer": {
                        "renderer_kind": "canvas",
                        "component_source": "native",
                        "component_id": "custom-kpi-canvas",
                        "content_refs": ["item.metric", "atom.rate"],
                        "theme_adapter_id": "paper-ink.canvas",
                    },
                },
                {
                    "slot_id": "support",
                    "block_id": "block.support",
                    "visual_role": "support",
                    "renderer": {
                        "renderer_kind": "typography",
                        "component_source": "native",
                        "component_id": "native.paper-ink.data.kpi-band.support",
                        "content_refs": ["item.metric"],
                        "theme_adapter_id": "paper-ink.typography",
                    },
                },
                {
                    "slot_id": "takeaway",
                    "block_id": "block.takeaway",
                    "visual_role": "support",
                    "renderer": {
                        "renderer_kind": "typography",
                        "component_source": "native",
                        "component_id": "native.paper-ink.data.kpi-band.takeaway",
                        "content_refs": ["item.metric"],
                        "theme_adapter_id": "paper-ink.typography",
                    },
                },
            ],
        }
        self.flush()


class V2ValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.fixture = DeckFixture(Path(self.temporary.name) / "deck")

    def codes(self, result) -> set[str]:
        return {issue.code for issue in result.errors}

    def assert_ok(self, result) -> None:
        self.assertTrue(result.ok, "\n".join(issue.format() for issue in result.issues))

    def assert_code(self, result, code: str) -> None:
        self.assertIn(code, self.codes(result), "\n".join(issue.format() for issue in result.issues))

    def test_schema_validator_accepts_v2_content(self) -> None:
        validator = JsonSchemaValidator(REPO_ROOT / "core/schemas/content.schema.json")
        self.assert_ok(validator.validate(self.fixture.content))

    def test_valid_custom_pipeline(self) -> None:
        self.assert_ok(validate_content_target(self.fixture.directory, REPO_ROOT))
        self.assert_ok(validate_plan_target(self.fixture.directory, REPO_ROOT))
        self.assert_ok(validate_render_plan_target(self.fixture.directory, REPO_ROOT))
        self.assert_ok(validate_render_target(self.fixture.directory, REPO_ROOT))

    def test_old_contract_version_fails_explicitly(self) -> None:
        self.fixture.content["contract_version"] = 1
        self.fixture.flush()
        self.assert_code(
            validate_content_target(self.fixture.directory, REPO_ROOT), "contract.version"
        )

    def test_missing_contract_version_fails_explicitly(self) -> None:
        del self.fixture.plan["contract_version"]
        self.fixture.flush()
        self.assert_code(validate_plan_target(self.fixture.directory, REPO_ROOT), "contract.version")

    def test_no_page_or_duration_constraint_uses_scenario_recommendation(self) -> None:
        self.fixture.content["brief"]["user_constraints"] = []
        self.fixture.plan["planning_basis"] = {
            "mode": "scenario-recommended",
            "scenario": "内部复盘会",
            "scenario_origin": "inferred",
            "user_constraint_refs": [],
            "research_source_refs": [],
            "assumptions": ["观众需要先看结果再讨论原因"],
            "reason": "根据内部复盘场景和单一结果量，推荐一页讲清。",
        }
        self.fixture.plan["page_budget"]["basis"] = [
            {
                "type": "content_structure",
                "content_refs": ["item.metric", "atom.rate"],
                "reason": "只有一个独立结论。",
            }
        ]
        self.fixture.flush()
        self.assert_ok(validate_plan_target(self.fixture.directory, REPO_ROOT))

    def test_user_constrained_mode_without_page_or_duration_is_rejected(self) -> None:
        self.fixture.content["brief"]["user_constraints"] = []
        self.fixture.plan["planning_basis"]["user_constraint_refs"] = []
        self.fixture.plan["page_budget"]["basis"] = self.fixture.plan["page_budget"]["basis"][1:]
        self.fixture.flush()
        self.assert_code(
            validate_plan_target(self.fixture.directory, REPO_ROOT), "plan.basis_mode"
        )

    def test_derived_mode_cannot_replace_scenario_recommendation(self) -> None:
        self.fixture.content["brief"]["user_constraints"] = []
        self.fixture.plan["planning_basis"].update(
            {
                "mode": "derived",
                "scenario_origin": "inferred",
                "user_constraint_refs": [],
                "assumptions": ["观众需要先看结果再讨论原因"],
            }
        )
        self.fixture.plan["page_budget"]["basis"] = self.fixture.plan["page_budget"][
            "basis"
        ][1:]
        self.fixture.flush()
        self.assert_code(
            validate_plan_target(self.fixture.directory, REPO_ROOT), "plan.basis_mode"
        )

    def test_constraint_range_conflict(self) -> None:
        constraint = self.fixture.content["brief"]["user_constraints"][0]
        constraint.pop("exact_pages")
        constraint.update({"min_pages": 4, "max_pages": 2})
        self.fixture.flush()
        self.assert_code(
            validate_content_target(self.fixture.directory, REPO_ROOT),
            "content.constraint_range",
        )

    def test_every_page_has_exactly_one_primary_block(self) -> None:
        self.fixture.plan["pages"][0]["blocks"].append(
            {
                "block_id": "block.second",
                "purpose": "第二焦点",
                "importance": "primary",
                "semantic_form": "headline",
                "content_refs": ["item.metric"],
            }
        )
        self.fixture.flush()
        self.assert_code(validate_plan_target(self.fixture.directory, REPO_ROOT), "plan.primary_block")

    def test_coverage_requires_atomic_value_decision(self) -> None:
        self.fixture.plan["coverage_decisions"].pop()
        self.fixture.flush()
        self.assert_code(validate_plan_target(self.fixture.directory, REPO_ROOT), "coverage.missing")

    def test_should_atom_does_not_need_a_separate_coverage_decision(self) -> None:
        self.fixture.content["content_items"][0]["priority"] = "should"
        self.fixture.plan["coverage_decisions"] = [
            self.fixture.plan["coverage_decisions"][0]
        ]
        self.fixture.flush()
        self.assert_ok(validate_plan_target(self.fixture.directory, REPO_ROOT))

    def test_must_content_cannot_be_omitted(self) -> None:
        self.fixture.plan["coverage_decisions"][0].update(
            {"disposition": "omit", "page_refs": []}
        )
        self.fixture.flush()
        self.assert_code(validate_plan_target(self.fixture.directory, REPO_ROOT), "coverage.must")

    def test_unresolved_must_content_forces_plain_question(self) -> None:
        self.fixture.content["content_items"][0].update(
            {"status": "placeholder", "status_note": "还不知道准确数字"}
        )
        self.fixture.plan["confirmation"] = {
            "mode": "adaptive",
            "decision": "needs_confirmation",
            "assessments": [
                {
                    "trigger": "must_content_unresolved",
                    "affected_refs": ["item.metric"],
                    "impact": "conclusion",
                    "resolution": "needs_user_choice",
                    "reason": "关键数字尚未确认，会改变页面结论。",
                }
            ],
            "user_questions": ["目前还没有准确留存率，这会改变结论。请告诉我该用哪个数字？"],
        }
        self.fixture.flush()
        self.assert_ok(validate_plan_target(self.fixture.directory, REPO_ROOT))
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT),
            "render.gate_confirmation",
        )

    def test_unresolved_must_without_pause_is_rejected(self) -> None:
        self.fixture.content["content_items"][0].update(
            {"status": "placeholder", "status_note": "还不知道准确数字"}
        )
        self.fixture.flush()
        self.assert_code(
            validate_plan_target(self.fixture.directory, REPO_ROOT),
            "confirmation.must_unresolved",
        )

    def test_inferred_must_without_user_decision_is_rejected(self) -> None:
        self.fixture.content["content_items"][0].update(
            {"status": "inferred", "status_note": "根据上下文估算，用户尚未确认"}
        )
        self.fixture.flush()
        self.assert_code(
            validate_plan_target(self.fixture.directory, REPO_ROOT),
            "confirmation.must_unresolved",
        )
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT),
            "render.gate_confirmation",
        )

    def test_every_source_conflict_needs_an_assessment(self) -> None:
        opposing = copy.deepcopy(self.fixture.content["content_items"][0])
        opposing.update(
            {
                "id": "item.metric-alt",
                "statement": "另一口径为 51%",
                "priority": "should",
                "atomic_values": [],
                "relations": [
                    {
                        "type": "contradicts",
                        "target_ref": "item.metric",
                        "reason": "统计窗口不同。",
                    }
                ],
            }
        )
        self.fixture.content["content_items"].append(opposing)
        self.fixture.plan["coverage_decisions"].append(
            {
                "content_ref": "item.metric-alt",
                "disposition": "defer",
                "page_refs": [],
                "reason": "保留冲突口径，等待评估。",
            }
        )
        self.fixture.flush()
        self.assert_code(
            validate_plan_target(self.fixture.directory, REPO_ROOT),
            "confirmation.source_conflict",
        )

        self.fixture.plan["confirmation"]["assessments"] = [
            {
                "trigger": "source_conflict",
                "affected_refs": ["item.metric", "item.metric-alt"],
                "impact": "none",
                "resolution": "present_both",
                "reason": "两种口径可以并列说明且不改变结论。",
            }
        ]
        self.fixture.flush()
        self.assert_ok(validate_plan_target(self.fixture.directory, REPO_ROOT))

    def test_confirmation_affected_refs_must_exist(self) -> None:
        self.fixture.plan["confirmation"]["assessments"] = [
            {
                "trigger": "ambiguous_context",
                "affected_refs": ["item.missing"],
                "impact": "none",
                "resolution": "proceed",
                "reason": "缺口不影响当前结论。",
            }
        ]
        self.fixture.flush()
        self.assert_code(
            validate_plan_target(self.fixture.directory, REPO_ROOT),
            "confirmation.affected_ref",
        )

    def test_question_rejects_internal_jargon(self) -> None:
        self.fixture.plan["confirmation"] = {
            "mode": "adaptive",
            "decision": "needs_confirmation",
            "assessments": [
                {
                    "trigger": "ambiguous_context",
                    "affected_refs": ["item.metric"],
                    "impact": "emphasis",
                    "resolution": "needs_user_choice",
                    "reason": "两种用途会改变重点。",
                }
            ],
            "user_questions": ["renderer 字段应该选哪个？"],
        }
        self.fixture.flush()
        self.assert_code(
            validate_plan_target(self.fixture.directory, REPO_ROOT),
            "confirmation.question_jargon",
        )

    def test_question_rejects_vague_user_language(self) -> None:
        for question in ("选哪个？", "你决定一下？", "要继续吗？"):
            with self.subTest(question=question):
                self.fixture.plan["confirmation"] = {
                    "mode": "adaptive",
                    "decision": "needs_confirmation",
                    "assessments": [
                        {
                            "trigger": "ambiguous_context",
                            "affected_refs": ["item.metric"],
                            "impact": "emphasis",
                            "resolution": "needs_user_choice",
                            "reason": "两种用途会改变重点。",
                        }
                    ],
                    "user_questions": [question],
                }
                self.fixture.flush()
                self.assert_code(
                    validate_plan_target(self.fixture.directory, REPO_ROOT),
                    "confirmation.question_context",
                )

    def test_question_explains_situation_impact_and_choice(self) -> None:
        self.fixture.plan["confirmation"] = {
            "mode": "adaptive",
            "decision": "needs_confirmation",
            "assessments": [
                {
                    "trigger": "ambiguous_context",
                    "affected_refs": ["item.metric"],
                    "impact": "emphasis",
                    "resolution": "needs_user_choice",
                    "reason": "两种用途会改变重点。",
                }
            ],
            "user_questions": [
                "管理层和执行团队关注的重点不同。你希望这份演示主要给哪一类人看？"
            ],
        }
        self.fixture.flush()
        self.assert_ok(validate_plan_target(self.fixture.directory, REPO_ROOT))

    def test_question_count_is_at_most_three(self) -> None:
        self.fixture.plan["confirmation"] = {
            "mode": "adaptive",
            "decision": "needs_confirmation",
            "assessments": [
                {
                    "trigger": "ambiguous_context",
                    "affected_refs": ["item.metric"],
                    "impact": "emphasis",
                    "resolution": "needs_user_choice",
                    "reason": "不同场景会改变重点。",
                }
            ],
            "user_questions": ["选 A？", "选 B？", "选 C？", "选 D？"],
        }
        self.fixture.flush()
        self.assert_code(
            validate_plan_target(self.fixture.directory, REPO_ROOT),
            "confirmation.question_count",
        )

    def test_nonimpacting_conflict_does_not_pause(self) -> None:
        self.fixture.plan["confirmation"] = {
            "mode": "adaptive",
            "decision": "needs_confirmation",
            "assessments": [
                {
                    "trigger": "source_conflict",
                    "affected_refs": ["item.metric"],
                    "impact": "none",
                    "resolution": "needs_user_choice",
                    "reason": "两种口径可以并列且不影响结论。",
                }
            ],
            "user_questions": ["要展示哪一种口径？"],
        }
        self.fixture.flush()
        self.assert_code(
            validate_plan_target(self.fixture.directory, REPO_ROOT),
            "confirmation.unnecessary_pause",
        )

    def test_gallery_exact_fit_is_valid_and_has_no_composition(self) -> None:
        self.fixture.gallery_render()
        self.assert_ok(validate_render_plan_target(self.fixture.directory, REPO_ROOT))
        self.assert_ok(validate_render_target(self.fixture.directory, REPO_ROOT))

    def test_exact_fit_must_terminate_in_gallery(self) -> None:
        decision = self.fixture.render["pages"][0]["layout_decision"]
        decision["candidate_evaluations"][0]["verdict"] = "exact_fit"
        self.fixture.flush()
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT),
            "render.gallery_termination",
        )

    def test_gallery_payload_requires_manifest_slot(self) -> None:
        self.fixture.gallery_render()
        self.fixture.render["pages"][0]["layout_decision"]["payload"]["bindings"][0][
            "slot_id"
        ] = "unknown"
        self.fixture.flush()
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT),
            "render.payload_slot",
        )

    def test_gallery_payload_requires_every_recipe_slot(self) -> None:
        self.fixture.gallery_render()
        self.fixture.render["pages"][0]["layout_decision"]["payload"]["bindings"].pop()
        self.fixture.flush()
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT),
            "render.payload_slot",
        )

    def test_gallery_exact_fit_must_match_recipe_semantics(self) -> None:
        mutations = (
            ("role", "hook", "render.recipe_role"),
            ("relation", "sequence", "render.recipe_relation"),
            ("primitive", "linear-sequence", "render.recipe_primitive"),
        )
        for field, value, expected_code in mutations:
            with self.subTest(field=field):
                self.fixture.gallery_render()
                page = self.fixture.plan["pages"][0]
                if field == "role":
                    page["role"] = value
                elif field == "relation":
                    page["relation_shape"]["primary"] = value
                else:
                    page["spatial_primitive"] = value
                self.fixture.flush()
                self.assert_code(
                    validate_render_plan_target(self.fixture.directory, REPO_ROOT),
                    expected_code,
                )

    def test_structure_fit_must_match_recipe_semantics(self) -> None:
        self.fixture.composition_render()
        self.fixture.plan["pages"][0]["relation_shape"]["primary"] = "sequence"
        self.fixture.flush()
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT),
            "render.recipe_relation",
        )

    def test_gallery_payload_keeps_recipe_reading_order(self) -> None:
        self.fixture.gallery_render()
        bindings = self.fixture.render["pages"][0]["layout_decision"]["payload"][
            "bindings"
        ]
        bindings[1], bindings[2] = bindings[2], bindings[1]
        self.fixture.flush()
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT),
            "render.payload_order",
        )

    def test_gallery_exact_fit_has_no_structure_fit_candidate(self) -> None:
        self.fixture.gallery_render()
        self.fixture.render["pages"][0]["layout_decision"]["candidate_evaluations"].append(
            {
                "recipe_id": "paper-ink.evidence.specimen-card",
                "verdict": "structure_fit",
                "reason": "另一结构只有局部匹配，不应在完整命中后继续组合。",
            }
        )
        self.fixture.flush()
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT),
            "render.gallery_termination",
        )

    def test_composition_keeps_all_gallery_slots(self) -> None:
        self.fixture.composition_render()
        self.assert_ok(validate_render_plan_target(self.fixture.directory, REPO_ROOT))
        self.fixture.render["pages"][0]["slots"].pop()
        self.fixture.flush()
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT),
            "render.composition_slots",
        )

    def test_composition_rejects_unchanged_default_components(self) -> None:
        self.fixture.composition_render()
        first = self.fixture.render["pages"][0]["slots"][0]["renderer"]
        first.update(
            {
                "renderer_kind": "svg",
                "component_source": "native",
                "component_id": "native.paper-ink.data.kpi-band.kpis",
                "theme_adapter_id": "paper-ink.svg",
            }
        )
        self.fixture.flush()
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT),
            "render.composition_redundant",
        )

    def test_composition_maps_each_block_once(self) -> None:
        self.fixture.composition_render()
        self.fixture.render["pages"][0]["slots"][1]["block_id"] = "block.main"
        self.fixture.flush()
        result = validate_render_plan_target(self.fixture.directory, REPO_ROOT)
        self.assert_code(result, "render.block_duplicate")
        self.assert_code(result, "render.block_coverage")

    def test_composition_keeps_recipe_reading_order(self) -> None:
        self.fixture.composition_render()
        slots = self.fixture.render["pages"][0]["slots"]
        slots[1], slots[2] = slots[2], slots[1]
        self.fixture.flush()
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT),
            "render.composition_order",
        )

    def test_semantic_emphasis_must_point_to_rendered_content(self) -> None:
        self.fixture.render["pages"][0]["emphasis"] = {
            "mode": "semantic-focus",
            "content_ref": "item.missing",
            "member_roles": ["status"],
            "reason": "测试未知强调内容。",
        }
        self.fixture.flush()
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT),
            "render.emphasis_ref",
        )

    def test_custom_requires_all_candidates_rejected(self) -> None:
        self.fixture.render["pages"][0]["layout_decision"]["candidate_evaluations"][0][
            "verdict"
        ] = "structure_fit"
        self.fixture.flush()
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT),
            "render.custom_reject",
        )

    def test_unregistered_renderer_source_pair_fails(self) -> None:
        renderer = self.fixture.render["pages"][0]["slots"][0]["renderer"]
        renderer.update(
            {
                "renderer_kind": "typography",
                "component_source": "echarts",
                "theme_adapter_id": "paper-ink.echarts",
            }
        )
        self.fixture.flush()
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT),
            "render.capability_pair",
        )

    def test_echarts_dataset_and_encode_are_checked(self) -> None:
        self.fixture.composition_render()
        renderer = self.fixture.render["pages"][0]["slots"][0]["renderer"]
        renderer.update(
            {
                "renderer_kind": "canvas",
                "component_source": "echarts",
                "component_id": "echarts.kpi-trend",
                "theme_adapter_id": "paper-ink.echarts",
                "data_binding": {
                    "data_ref": {
                        "content_id": "item.metric",
                        "json_pointer": "/structured_data/rows",
                    },
                    "dataset_id": "dataset.retention",
                    "encode": {"x": "label", "y": "value"},
                },
            }
        )
        self.fixture.flush()
        self.assert_ok(validate_render_plan_target(self.fixture.directory, REPO_ROOT))
        renderer["data_binding"]["encode"]["y"] = "missing"
        self.fixture.flush()
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT), "render.encode"
        )

    def test_echarts_json_pointer_must_exist(self) -> None:
        self.fixture.composition_render()
        renderer = self.fixture.render["pages"][0]["slots"][0]["renderer"]
        renderer.update(
            {
                "renderer_kind": "canvas",
                "component_source": "echarts",
                "component_id": "echarts.kpi-trend",
                "theme_adapter_id": "paper-ink.echarts",
                "data_binding": {
                    "data_ref": {
                        "content_id": "item.metric",
                        "json_pointer": "/structured_data/missing",
                    },
                    "dataset_id": "dataset.retention",
                    "encode": {"x": "label", "y": "value"},
                },
            }
        )
        self.fixture.flush()
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT), "render.data_ref"
        )

    def test_data_binding_content_is_listed_on_the_renderer(self) -> None:
        self.fixture.composition_render()
        renderer = self.fixture.render["pages"][0]["slots"][0]["renderer"]
        renderer["data_binding"] = {
            "data_ref": {
                "content_id": "item.metric",
                "json_pointer": "/structured_data/rows",
            },
            "dataset_id": "dataset.retention",
            "encode": {"x": "label", "y": "value"},
        }
        renderer["content_refs"] = ["atom.rate"]
        self.fixture.flush()
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT), "render.data_ref"
        )

    def test_atlas_component_id_is_verified(self) -> None:
        catalog = self.fixture.directory / "atlas.json"
        write_json(catalog, {"components": [{"component_id": "atlas.valid"}]})
        previous = os.environ.get("PPT_COMPONENT_ATLAS_CATALOG")
        os.environ["PPT_COMPONENT_ATLAS_CATALOG"] = str(catalog)
        self.addCleanup(
            lambda: os.environ.__setitem__("PPT_COMPONENT_ATLAS_CATALOG", previous)
            if previous is not None
            else os.environ.pop("PPT_COMPONENT_ATLAS_CATALOG", None)
        )
        renderer = self.fixture.render["pages"][0]["slots"][0]["renderer"]
        renderer.update(
            {
                "renderer_kind": "svg",
                "component_source": "ppt-component-atlas",
                "component_id": "atlas.missing",
                "theme_adapter_id": "paper-ink.svg",
            }
        )
        self.fixture.flush()
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT),
            "render.atlas_component",
        )
        renderer["component_id"] = "atlas.valid"
        self.fixture.flush()
        self.assert_ok(validate_render_plan_target(self.fixture.directory, REPO_ROOT))

    def add_reconstructed_image(self) -> None:
        source_bytes = b"source screenshot bytes"
        output_bytes = b"<svg xmlns='http://www.w3.org/2000/svg'><text>rebuilt</text></svg>"
        (self.fixture.directory / "source.png").write_bytes(source_bytes)
        asset_dir = self.fixture.directory / "assets"
        asset_dir.mkdir(exist_ok=True)
        (asset_dir / "rebuilt.svg").write_bytes(output_bytes)
        self.fixture.content["assets"] = [
            {
                "asset_id": "asset.source",
                "role": "source",
                "media_type": "image/png",
                "locator": "source.png",
                "sha256": sha(source_bytes),
                "source_refs": ["src.user"],
                "reconstruction_required": True,
            },
            {
                "asset_id": "asset.rebuilt",
                "role": "reconstructed",
                "creation_mode": "reconstruct",
                "media_type": "image/svg+xml",
                "locator": "assets/rebuilt.svg",
                "sha256": sha(output_bytes),
                "source_refs": ["src.user"],
                "derived_from": ["asset.source"],
                "reconstruction_method": "redraw",
                "reconstruction_reason": "按主题线稿规范重绘原始截图。",
                "fact_change_risk": "none",
                "usage": "解释原始界面证据",
                "disclosure": "重构示意",
            },
        ]
        self.fixture.content["content_items"][0]["asset_refs"] = [
            "asset.source",
            "asset.rebuilt",
        ]
        self.fixture.content["content_items"][0]["epistemic_role"] = "evidence"
        renderer = self.fixture.render["pages"][0]["slots"][0]["renderer"]
        renderer.update(
            {
                "renderer_kind": "image",
                "component_source": "native",
                "component_id": "reconstructed-evidence",
                "theme_adapter_id": "paper-ink.image",
                "material_treatment": {
                    "mode": "reconstruct",
                    "source_asset_refs": ["asset.source"],
                    "strategy": "redraw",
                    "output_asset_ref": "asset.rebuilt",
                    "reason": "按纸墨主题重绘，不直接插入原始截图。",
                },
            }
        )
        component = (
            '<img src="assets/rebuilt.svg" data-asset-ref="asset.rebuilt" '
            'data-material-mode="reconstruction" data-disclosure="重构示意" '
            'data-block-id="block.main" data-renderer-kind="image" '
            'data-component-source="native" data-component-id="reconstructed-evidence" '
            'data-theme-adapter-id="paper-ink.image" '
            'data-content-ref="item.metric atom.rate">55%'
        )
        self.fixture.flush(html=False)
        (self.fixture.directory / "index.html").write_text(
            self.fixture.html(component), encoding="utf-8"
        )

    def test_reconstructed_image_with_provenance_is_valid(self) -> None:
        self.add_reconstructed_image()
        self.assert_ok(validate_content_target(self.fixture.directory, REPO_ROOT))
        self.assert_ok(validate_render_target(self.fixture.directory, REPO_ROOT))

    def test_reconstructed_image_cannot_share_source_fingerprint(self) -> None:
        self.add_reconstructed_image()
        self.fixture.content["assets"][1]["sha256"] = self.fixture.content["assets"][0]["sha256"]
        self.fixture.flush(html=False)
        self.assert_code(
            validate_content_target(self.fixture.directory, REPO_ROOT),
            "asset.same_fingerprint",
        )

    def test_asset_sha_must_match_the_local_file(self) -> None:
        self.add_reconstructed_image()
        self.fixture.content["assets"][0]["sha256"] = "0" * 64
        self.fixture.flush(html=False)
        self.assert_code(
            validate_content_target(self.fixture.directory, REPO_ROOT),
            "asset.fingerprint",
        )

    def test_raw_image_cannot_enter_final_html(self) -> None:
        self.add_reconstructed_image()
        html_path = self.fixture.directory / "index.html"
        html_path.write_text(
            html_path.read_text(encoding="utf-8")
            .replace("assets/rebuilt.svg", "source.png")
            .replace("asset.rebuilt", "asset.source"),
            encoding="utf-8",
        )
        self.assert_code(
            validate_render_target(self.fixture.directory, REPO_ROOT),
            "asset.html_unregistered",
        )

    def test_reconstructed_image_requires_disclosure(self) -> None:
        self.add_reconstructed_image()
        self.fixture.content["assets"][1].pop("disclosure")
        self.fixture.flush(html=False)
        self.assert_code(
            validate_content_target(self.fixture.directory, REPO_ROOT), "asset.disclosure"
        )

    def test_explanatory_reconstruction_does_not_require_disclosure(self) -> None:
        self.add_reconstructed_image()
        self.fixture.content["content_items"][0]["epistemic_role"] = "fact"
        self.fixture.content["assets"][1].pop("disclosure")
        self.fixture.flush(html=False)
        html_path = self.fixture.directory / "index.html"
        html_path.write_text(
            self.fixture.html(
                '<img src="assets/rebuilt.svg" data-asset-ref="asset.rebuilt" '
                'data-material-mode="reconstruction" data-block-id="block.main" '
                'data-renderer-kind="image" data-component-source="native" '
                'data-component-id="reconstructed-evidence" '
                'data-theme-adapter-id="paper-ink.image" '
                'data-content-ref="item.metric atom.rate">55%'
            ),
            encoding="utf-8",
        )
        self.assert_ok(validate_content_target(self.fixture.directory, REPO_ROOT))
        self.assert_ok(validate_render_target(self.fixture.directory, REPO_ROOT))

    def test_reconstruct_requires_fact_change_risk(self) -> None:
        self.add_reconstructed_image()
        self.fixture.content["assets"][1].pop("fact_change_risk")
        self.fixture.flush(html=False)
        self.assert_code(
            validate_content_target(self.fixture.directory, REPO_ROOT), "asset.fact_change_risk"
        )

    def test_possible_fact_change_requires_plain_confirmation_and_stops_render(self) -> None:
        self.add_reconstructed_image()
        self.fixture.content["assets"][1]["fact_change_risk"] = "possible"
        self.fixture.plan["confirmation"] = {
            "mode": "adaptive",
            "decision": "needs_confirmation",
            "assessments": [
                {
                    "trigger": "reconstruction_fact_risk",
                    "affected_refs": ["asset.rebuilt"],
                    "impact": "conclusion",
                    "resolution": "needs_user_choice",
                    "reason": "重新绘制可能改变截图中的关键界面事实。",
                }
            ],
            "user_questions": [
                "这张截图重新绘制后可能改变关键细节，会影响结论。你希望我只保留能确认的内容，还是等你补充资料？"
            ],
        }
        self.fixture.flush(html=False)
        self.assert_ok(validate_plan_target(self.fixture.directory, REPO_ROOT))
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT),
            "render.gate_confirmation",
        )

    def test_possible_fact_change_cannot_silently_proceed(self) -> None:
        self.add_reconstructed_image()
        self.fixture.content["assets"][1]["fact_change_risk"] = "possible"
        self.fixture.flush(html=False)
        self.assert_code(
            validate_plan_target(self.fixture.directory, REPO_ROOT),
            "confirmation.reconstruction_fact_risk",
        )
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT),
            "render.gate_confirmation",
        )

    def test_image_output_must_belong_to_rendered_content(self) -> None:
        self.add_reconstructed_image()
        self.fixture.content["content_items"][0]["asset_refs"] = ["asset.source"]
        self.fixture.flush(html=False)
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT),
            "asset.content_link",
        )

    def test_css_background_cannot_insert_source_image(self) -> None:
        self.add_reconstructed_image()
        html_path = self.fixture.directory / "index.html"
        html_path.write_text(
            html_path.read_text(encoding="utf-8").replace(
                "</section>",
                '<div style="background-image:url(source.png)">原图</div></section>',
            ),
            encoding="utf-8",
        )
        self.assert_code(
            validate_render_target(self.fixture.directory, REPO_ROOT), "asset.raw_media"
        )

    def test_svg_image_cannot_insert_source_image(self) -> None:
        self.add_reconstructed_image()
        html_path = self.fixture.directory / "index.html"
        html_path.write_text(
            html_path.read_text(encoding="utf-8").replace(
                "</section>", '<svg><image href="source.png"/></svg></section>'
            ),
            encoding="utf-8",
        )
        self.assert_code(
            validate_render_target(self.fixture.directory, REPO_ROOT), "asset.raw_media"
        )

    def test_svg_xlink_image_cannot_insert_source_image(self) -> None:
        self.add_reconstructed_image()
        html_path = self.fixture.directory / "index.html"
        html_path.write_text(
            html_path.read_text(encoding="utf-8").replace(
                "</section>",
                '<svg xmlns:xlink="http://www.w3.org/1999/xlink"><image xlink:href="source.png"/></svg></section>',
            ),
            encoding="utf-8",
        )
        self.assert_code(
            validate_render_target(self.fixture.directory, REPO_ROOT), "asset.raw_media"
        )

    def test_picture_srcset_cannot_insert_source_image(self) -> None:
        self.add_reconstructed_image()
        html_path = self.fixture.directory / "index.html"
        html_path.write_text(
            html_path.read_text(encoding="utf-8").replace(
                "</section>",
                '<picture><source srcset="source.png 1x, assets/rebuilt.svg 2x"></picture></section>',
            ),
            encoding="utf-8",
        )
        self.assert_code(
            validate_render_target(self.fixture.directory, REPO_ROOT), "asset.raw_media"
        )

    def test_local_css_cannot_insert_source_image(self) -> None:
        self.add_reconstructed_image()
        css_path = self.fixture.directory / "escape.css"
        css_path.write_text(".slide { background-image: url('source.png'); }", encoding="utf-8")
        html_path = self.fixture.directory / "index.html"
        html_path.write_text(
            html_path.read_text(encoding="utf-8").replace(
                "<body>", '<head><link rel="stylesheet" href="escape.css"></head><body>'
            ),
            encoding="utf-8",
        )
        self.assert_code(
            validate_render_target(self.fixture.directory, REPO_ROOT), "asset.raw_media"
        )

    def test_linked_parent_css_cannot_hide_source_image(self) -> None:
        self.add_reconstructed_image()
        css_path = self.fixture.directory.parent / "escape.css"
        css_path.write_text(
            f".slide {{ background-image: url('{self.fixture.directory.name}/source.png'); }}",
            encoding="utf-8",
        )
        html_path = self.fixture.directory / "index.html"
        html_path.write_text(
            html_path.read_text(encoding="utf-8").replace(
                "<body>", '<head><link rel="stylesheet" href="../escape.css"></head><body>'
            ),
            encoding="utf-8",
        )
        self.assert_code(
            validate_render_target(self.fixture.directory, REPO_ROOT), "asset.raw_media"
        )

    def test_style_block_cannot_insert_source_image(self) -> None:
        self.add_reconstructed_image()
        html_path = self.fixture.directory / "index.html"
        html_path.write_text(
            html_path.read_text(encoding="utf-8").replace(
                "<body>", "<head><style>.slide{background:url(source.png)}</style></head><body>"
            ),
            encoding="utf-8",
        )
        self.assert_code(
            validate_render_target(self.fixture.directory, REPO_ROOT), "asset.raw_media"
        )

    def test_unregistered_local_css_image_is_rejected(self) -> None:
        self.add_reconstructed_image()
        rogue = self.fixture.directory / "assets" / "rogue.png"
        rogue.write_bytes(b"\x89PNG\r\n\x1a\nnot registered")
        css_path = self.fixture.directory / "escape.css"
        css_path.write_text(".slide { background: url('assets/rogue.png'); }", encoding="utf-8")
        html_path = self.fixture.directory / "index.html"
        html_path.write_text(
            html_path.read_text(encoding="utf-8").replace(
                "<body>", '<head><link rel="stylesheet" href="escape.css"></head><body>'
            ),
            encoding="utf-8",
        )
        self.assert_code(
            validate_render_target(self.fixture.directory, REPO_ROOT),
            "asset.html_unregistered",
        )

    def add_generated_image(self) -> None:
        output_bytes = b"<svg xmlns='http://www.w3.org/2000/svg'><text>generated</text></svg>"
        asset_dir = self.fixture.directory / "assets"
        asset_dir.mkdir(exist_ok=True)
        (asset_dir / "generated.svg").write_bytes(output_bytes)
        self.fixture.content["assets"] = [
            {
                "asset_id": "asset.generated",
                "role": "reconstructed",
                "creation_mode": "generate",
                "media_type": "image/svg+xml",
                "locator": "assets/generated.svg",
                "sha256": sha(output_bytes),
                "source_refs": ["src.user"],
                "generator": "codex-gpt-image-2",
                "generation_reason": "为抽象留存概念生成主题一致的说明图。",
                "usage": "概念说明插图",
            }
        ]
        self.fixture.content["content_items"][0]["asset_refs"] = ["asset.generated"]
        renderer = self.fixture.render["pages"][0]["slots"][0]["renderer"]
        renderer.update(
            {
                "renderer_kind": "image",
                "component_source": "codex-host",
                "component_id": "generated-concept",
                "theme_adapter_id": "paper-ink.image",
                "material_treatment": {
                    "mode": "generate",
                    "output_asset_ref": "asset.generated",
                    "reason": "使用 Codex 宿主内置图片能力生成概念说明图。",
                },
            }
        )
        component = (
            '<img src="assets/generated.svg" data-asset-ref="asset.generated" '
            'data-material-mode="generation" data-block-id="block.main" '
            'data-renderer-kind="image" data-component-source="codex-host" '
            'data-component-id="generated-concept" '
            'data-theme-adapter-id="paper-ink.image" '
            'data-content-ref="item.metric atom.rate">55%'
        )
        self.fixture.flush(html=False)
        (self.fixture.directory / "index.html").write_text(
            self.fixture.html(component), encoding="utf-8"
        )

    def test_codex_host_generated_concept_image_is_valid(self) -> None:
        self.add_generated_image()
        self.assert_ok(validate_content_target(self.fixture.directory, REPO_ROOT))
        self.assert_ok(validate_render_target(self.fixture.directory, REPO_ROOT))

    def test_generated_image_cannot_carry_evidence(self) -> None:
        self.add_generated_image()
        self.fixture.content["content_items"][0]["epistemic_role"] = "evidence"
        self.fixture.flush(html=False)
        self.assert_code(
            validate_content_target(self.fixture.directory, REPO_ROOT),
            "asset.generated_evidence",
        )

    def test_generate_mode_requires_codex_host(self) -> None:
        self.add_generated_image()
        self.fixture.render["pages"][0]["slots"][0]["renderer"]["component_source"] = "native"
        self.fixture.flush(html=False)
        self.assert_code(
            validate_render_plan_target(self.fixture.directory, REPO_ROOT),
            "asset.generate_source",
        )

    def test_html_rejects_legacy_attributes(self) -> None:
        path = self.fixture.directory / "index.html"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                'data-layout-source="custom"',
                'data-layout-source="custom" data-density="dense"',
            ),
            encoding="utf-8",
        )
        self.assert_code(validate_render_target(self.fixture.directory, REPO_ROOT), "html.legacy_attribute")

    def test_html_requires_v2_runtime_marker(self) -> None:
        path = self.fixture.directory / "index.html"
        path.write_text(self.fixture.html(root="wise-ppt"), encoding="utf-8")
        self.assert_code(validate_render_target(self.fixture.directory, REPO_ROOT), "html.runtime_marker")

    def test_html_rejects_external_runtime_resources(self) -> None:
        path = self.fixture.directory / "index.html"
        html = path.read_text(encoding="utf-8").replace(
            "<body>", '<head><script src="https://example.com/app.js"></script></head><body>'
        )
        path.write_text(html, encoding="utf-8")
        self.assert_code(validate_render_target(self.fixture.directory, REPO_ROOT), "html.external_resource")

    def test_html_rejects_missing_local_runtime_resource(self) -> None:
        path = self.fixture.directory / "index.html"
        html = path.read_text(encoding="utf-8").replace(
            "<body>", '<head><script src="assets/missing.js"></script></head><body>'
        )
        path.write_text(html, encoding="utf-8")
        self.assert_code(
            validate_render_target(self.fixture.directory, REPO_ROOT),
            "html.local_resource_missing",
        )

    def test_html_recursively_checks_css_imports_and_urls(self) -> None:
        assets = self.fixture.directory / "assets"
        assets.mkdir()
        (assets / "root.css").write_text(
            '@import "nested.css";\n', encoding="utf-8"
        )
        (assets / "nested.css").write_text(
            '@font-face{font-family:Test;src:url("missing.woff2")}',
            encoding="utf-8",
        )
        path = self.fixture.directory / "index.html"
        html = path.read_text(encoding="utf-8").replace(
            "<body>", '<head><link rel="stylesheet" href="assets/root.css"></head><body>'
        )
        path.write_text(html, encoding="utf-8")
        self.assert_code(
            validate_render_target(self.fixture.directory, REPO_ROOT),
            "html.local_resource_missing",
        )

    def test_echarts_html_dataset_matches_content_data_ref(self) -> None:
        self.fixture.composition_render()
        renderer = self.fixture.render["pages"][0]["slots"][0]["renderer"]
        renderer.update(
            {
                "renderer_kind": "canvas",
                "component_source": "echarts",
                "component_id": "echarts.kpi-trend",
                "theme_adapter_id": "paper-ink.echarts",
                "data_binding": {
                    "data_ref": {
                        "content_id": "item.metric",
                        "json_pointer": "/structured_data/rows",
                    },
                    "dataset_id": "dataset.retention",
                    "encode": {"x": "label", "y": "value"},
                },
            }
        )
        self.fixture.flush(html=False)

        def write_echarts_html(dataset_id: str, dataset: object) -> None:
            data = json.dumps(dataset, ensure_ascii=False)
            (self.fixture.directory / "index.html").write_text(
                "<!doctype html>"
                '<html data-runtime="wise-ppt-deck" data-typography-mode="mixed"><body>'
                '<section class="slide" data-page-id="page.result" '
                'data-layout-source="composition" data-recipe-id="paper-ink.data.kpi-band">'
                '<div data-block-id="block.main" data-renderer-kind="canvas" '
                'data-component-source="echarts" data-component-id="echarts.kpi-trend" '
                'data-theme-adapter-id="paper-ink.echarts" '
                'data-content-ref="item.metric atom.rate" '
                f'data-dataset-id="{dataset_id}">55%</div>'
                '<p data-block-id="block.support" data-renderer-kind="typography" '
                'data-component-source="native" '
                'data-component-id="native.paper-ink.data.kpi-band.support" '
                'data-theme-adapter-id="paper-ink.typography" '
                'data-content-ref="item.metric">留存说明</p>'
                '<p data-block-id="block.takeaway" data-renderer-kind="typography" '
                'data-component-source="native" '
                'data-component-id="native.paper-ink.data.kpi-band.takeaway" '
                'data-theme-adapter-id="paper-ink.typography" '
                'data-content-ref="item.metric">留存提升</p>'
                '<script type="application/json" '
                f'data-wise-ppt-dataset="dataset.retention">{data}</script>'
                "</section></body></html>",
                encoding="utf-8",
            )

        expected = self.fixture.content["content_items"][0]["structured_data"]["rows"]
        write_echarts_html("dataset.retention", expected)
        self.assert_ok(validate_render_target(self.fixture.directory, REPO_ROOT))

        write_echarts_html("dataset.wrong", expected)
        self.assert_code(
            validate_render_target(self.fixture.directory, REPO_ROOT),
            "html.echarts_dataset_id",
        )

        write_echarts_html("dataset.retention", [{"label": "改版后", "value": 999}])
        self.assert_code(
            validate_render_target(self.fixture.directory, REPO_ROOT),
            "html.echarts_dataset_mismatch",
        )

    def test_html_requires_visible_atomic_value(self) -> None:
        path = self.fixture.directory / "index.html"
        path.write_text(path.read_text(encoding="utf-8").replace("55%", "结果"), encoding="utf-8")
        self.assert_code(
            validate_render_target(self.fixture.directory, REPO_ROOT),
            "coverage.atomic_value_missing",
        )

    def test_html_gallery_must_keep_default_renderer(self) -> None:
        self.fixture.gallery_render()
        path = self.fixture.directory / "index.html"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "native.paper-ink.data.kpi-band.kpis", "changed-component"
            ),
            encoding="utf-8",
        )
        self.assert_code(validate_render_target(self.fixture.directory, REPO_ROOT), "html.gallery_default")

    def test_delivery_requires_pdf(self) -> None:
        self.assert_code(
            validate_delivery_target(self.fixture.directory, REPO_ROOT),
            "delivery.pdf_missing",
        )

    def test_delivery_pdf_page_count_matches_html(self) -> None:
        pdf = self.fixture.directory / f"{self.fixture.directory.name}.pdf"
        pdf.write_bytes(b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\n%%EOF")
        self.assert_ok(validate_delivery_target(self.fixture.directory, REPO_ROOT))


class GalleryContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "skill"
        self._build_root()

    def _build_root(self) -> None:
        write_json(
            self.root / "themes/registry.json",
            {
                "default_theme_id": "paper-ink",
                "themes": [
                    {
                        "theme_id": "paper-ink",
                        "name": "Paper Ink",
                        "path": "themes/paper-ink/theme.json",
                        "enabled": True,
                    }
                ],
            },
        )
        write_json(
            self.root / "themes/paper-ink/theme.json",
            {
                "theme_id": "paper-ink",
                "galleries": {
                    "general": "gallery/paper-ink/general/index.html",
                    "ai": "gallery/paper-ink/ai/index.html",
                },
                "adapters": [],
            },
        )
        write_json(
            self.root / "capabilities/registry.json",
            {
                "contract_version": 2,
                "renderer_kinds": [
                    {"renderer_kind": "svg", "description": "SVG"}
                ],
                "component_sources": [
                    {
                        "component_source": "native",
                        "description": "Native",
                        "allowed_renderer_kinds": ["svg"],
                    }
                ],
                "capabilities": [
                    {
                        "capability_id": "layout-gallery",
                        "capability_kind": "layout-catalog",
                        "manifest": "capabilities/layouts/gallery-manifest.json",
                        "reference": "capabilities/references/layout-gallery.md",
                    }
                ],
            },
        )
        recipe = {
            "recipe_id": "paper-ink.test.one",
            "display_code": "T1",
            "name": "测试",
            "family": "测试",
            "description": "单槽位测试",
            "roles": ["prove"],
            "relations": ["focus"],
            "primitives": ["hero"],
            "reading_order": ["main"],
            "structure_contract": {
                "region_count": 1,
                "required_slot_ids": ["main"],
                "core_primitives": ["focus-field"],
            },
            "slots": [
                {
                    "slot_id": "main",
                    "purpose": "主信息",
                    "required": True,
                    "visual_role": "primary",
                    "min_items": 1,
                    "max_items": 1,
                    "allowed_renderer_kinds": ["svg"],
                    "allowed_component_sources": ["native"],
                    "default_renderer": {
                        "renderer_kind": "svg",
                        "component_source": "native",
                        "component_id": "native.test.one.main",
                    },
                }
            ],
            "examples": {
                "general": "gallery/paper-ink/general/frames/layout-t1.html",
                "ai": "gallery/paper-ink/ai/frames/layout-t1.html",
            },
            "selection_notes": "完全匹配时直接使用。",
            "anti_patterns": ["不要改结构"],
        }
        recipe["structure_fingerprint"] = _recipe_fingerprint(recipe)
        write_json(
            self.root / "capabilities/layouts/gallery-manifest.json",
            {
                "contract_version": 2,
                "capability_id": "layout-gallery",
                "name": "Gallery",
                "description": "Test",
                "recipe_count": 1,
                "recipes": [recipe],
            },
        )
        for variant in ("general", "ai"):
            runtime = self.root / "runtime/stage-fit.js"
            runtime.parent.mkdir(parents=True, exist_ok=True)
            runtime.write_text("window.WisePPTStageFit = {};", encoding="utf-8")
            index = self.root / f"gallery/paper-ink/{variant}/index.html"
            index.parent.mkdir(parents=True, exist_ok=True)
            index.write_text(
                '<!doctype html><html data-runtime="wise-ppt-gallery"><head>'
                '<script src="../../../runtime/stage-fit.js"></script></head></html>',
                encoding="utf-8",
            )
            frame = self.root / f"gallery/paper-ink/{variant}/frames/layout-t1.html"
            frame.parent.mkdir(parents=True, exist_ok=True)
            frame.write_text(
                '<!doctype html><html data-runtime="wise-ppt-specimen"><head>'
                '<script src="../../../../runtime/stage-fit.js"></script></head><body>'
                '<section class="slide"></section></body></html>',
                encoding="utf-8",
            )

    def assert_code(self, result, code: str) -> None:
        self.assertIn(code, {issue.code for issue in result.errors})

    def test_gallery_v2_contract_passes(self) -> None:
        result = validate_gallery(self.root)
        self.assertTrue(result.ok, "\n".join(issue.format() for issue in result.issues))

    def test_gallery_fingerprint_is_recomputed(self) -> None:
        path = self.root / "capabilities/layouts/gallery-manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["recipes"][0]["reading_order"] = ["changed"]
        write_json(path, manifest)
        self.assert_code(validate_gallery(self.root), "gallery.fingerprint")

    def test_gallery_rejects_old_contract_version(self) -> None:
        path = self.root / "capabilities/layouts/gallery-manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["contract_version"] = 1
        write_json(path, manifest)
        self.assert_code(validate_gallery(self.root), "config.gallery")

    def test_gallery_examples_must_live_in_public_layer(self) -> None:
        path = self.root / "capabilities/layouts/gallery-manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        old = self.root / "themes/paper-ink/gallery/general/frames/layout-t1.html"
        old.parent.mkdir(parents=True, exist_ok=True)
        old.write_text(
            '<!doctype html><html data-runtime="wise-ppt-specimen"><head>'
            '<script src="../../../../../runtime/stage-fit.js"></script></head><body>'
            '<section class="slide"></section></body></html>',
            encoding="utf-8",
        )
        manifest["recipes"][0]["examples"]["general"] = (
            "themes/paper-ink/gallery/general/frames/layout-t1.html"
        )
        write_json(path, manifest)
        self.assert_code(validate_gallery(self.root), "gallery.example_path")

    def test_gallery_rejects_missing_local_resource(self) -> None:
        frame = self.root / "gallery/paper-ink/general/frames/layout-t1.html"
        source = frame.read_text(encoding="utf-8").replace(
            "</head>", '<link rel="stylesheet" href="missing.css"></head>'
        )
        frame.write_text(source, encoding="utf-8")
        self.assert_code(
            validate_gallery(self.root),
            "gallery.local_resource_missing",
        )

    def test_theme_adapter_pairs_must_be_public_capabilities(self) -> None:
        path = self.root / "themes/paper-ink/theme.json"
        theme = json.loads(path.read_text(encoding="utf-8"))
        theme["adapters"] = [
            {
                "adapter_id": "paper-ink.invalid",
                "renderer_kinds": ["svg"],
                "component_sources": ["codex-host"],
            }
        ]
        write_json(path, theme)
        self.assert_code(validate_gallery(self.root), "theme.adapter_capability")


if __name__ == "__main__":
    unittest.main()
