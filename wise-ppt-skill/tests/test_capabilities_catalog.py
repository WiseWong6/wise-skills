from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "capabilities" / "layouts" / "gallery-manifest.json"
REGISTRY = ROOT / "capabilities" / "registry.json"
CATALOG = ROOT / "scripts" / "catalog.py"
GEO_JSON = ROOT / "capabilities" / "vendors" / "geo" / "guangdong-geo.json"
GEO_SCRIPT = ROOT / "capabilities" / "vendors" / "geo" / "guangdong-geo.js"

RENDERER_KINDS = {
    "typography",
    "table",
    "image",
    "native-html",
    "svg",
    "canvas",
}
COMPONENT_SOURCES = {
    "native",
    "echarts",
    "ppt-component-atlas",
    "codex-host",
}
LEGACY_KEYS = {
    "theme_id",
    "layout_count",
    "layouts",
    "layout_id",
    "core_primitive_ids",
    "density_levels",
    "densities",
    "provider_ids",
    "allowed_providers",
    "renderers",
    "capacity",
    "semantic_units",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in collect_keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in collect_keys(item)}
    return set()


class CapabilityRegistryTests(unittest.TestCase):
    def test_registry_declares_orthogonal_axes_and_public_capabilities(self) -> None:
        registry = load_json(REGISTRY)
        self.assertEqual(registry["contract_version"], 2)
        renderers = {item["renderer_kind"] for item in registry["renderer_kinds"]}
        sources = {item["component_source"] for item in registry["component_sources"]}
        self.assertEqual(renderers, RENDERER_KINDS)
        self.assertEqual(sources, COMPONENT_SOURCES)

        capabilities = {item["capability_id"]: item for item in registry["capabilities"]}
        gallery = capabilities["layout-gallery"]
        self.assertEqual(gallery["capability_kind"], "layout-catalog")
        self.assertNotIn("component_source", gallery)
        echarts = capabilities["echarts"]
        self.assertEqual(echarts["runtime"], "capabilities/vendors/echarts/echarts.min.js")
        self.assertEqual(echarts["version"], "6.1.0")
        self.assertEqual(echarts["license"], "Apache-2.0")


class GalleryManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = load_json(MANIFEST)

    def test_root_and_recipe_identity(self) -> None:
        manifest = self.manifest
        self.assertEqual(manifest["contract_version"], 2)
        self.assertEqual(manifest["capability_id"], "layout-gallery")
        recipes = manifest["recipes"]
        self.assertEqual(manifest["recipe_count"], len(recipes))
        self.assertEqual(len(recipes), 63)
        self.assertEqual(len({item["recipe_id"] for item in recipes}), len(recipes))
        self.assertEqual(len({item["display_code"] for item in recipes}), len(recipes))
        self.assertFalse(collect_keys(manifest) & LEGACY_KEYS)

    def test_each_recipe_has_a_stable_structure_contract(self) -> None:
        for recipe in self.manifest["recipes"]:
            slots = recipe["slots"]
            reading_order = [slot["slot_id"] for slot in slots]
            self.assertEqual(recipe["reading_order"], reading_order)
            self.assertEqual(recipe["structure_contract"]["region_count"], len(slots))
            self.assertEqual(
                recipe["structure_contract"]["required_slot_ids"],
                [slot["slot_id"] for slot in slots if slot["required"]],
            )
            self.assertEqual(
                sum(slot["visual_role"] == "primary" for slot in slots),
                1,
                recipe["recipe_id"],
            )

            fingerprint_slots = [
                {
                    key: slot[key]
                    for key in (
                        "slot_id",
                        "required",
                        "visual_role",
                        "min_items",
                        "max_items",
                    )
                }
                for slot in slots
            ]
            payload = {
                "reading_order": recipe["reading_order"],
                "structure_contract": recipe["structure_contract"],
                "slots": fingerprint_slots,
            }
            encoded = json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            expected = "sha256:" + hashlib.sha256(encoded).hexdigest()
            self.assertEqual(recipe["structure_fingerprint"], expected)

    def test_slots_keep_capacity_only_at_slot_level(self) -> None:
        for recipe in self.manifest["recipes"]:
            for slot in recipe["slots"]:
                self.assertLessEqual(slot["min_items"], slot["max_items"])
                self.assertTrue(set(slot["allowed_renderer_kinds"]) <= RENDERER_KINDS)
                self.assertTrue(set(slot["allowed_component_sources"]) <= COMPONENT_SOURCES)
                default = slot["default_renderer"]
                self.assertIn(default["renderer_kind"], slot["allowed_renderer_kinds"])
                self.assertIn(default["component_source"], slot["allowed_component_sources"])
                self.assertTrue(default["component_id"])

    def test_examples_and_copy_are_public_and_count_free(self) -> None:
        for recipe in self.manifest["recipes"]:
            self.assertTrue(
                recipe["examples"]["general"].startswith(
                    "gallery/paper-ink/general/frames/"
                )
            )
            self.assertTrue(
                recipe["examples"]["ai"].startswith("gallery/paper-ink/ai/frames/")
            )
            prose = " ".join(
                [recipe["selection_notes"], *recipe.get("anti_patterns", [])]
            ).casefold()
            for forbidden in ("语义单元", "容量落在", "density", "semantic unit"):
                self.assertNotIn(forbidden, prose, recipe["recipe_id"])
            for forbidden in ("证据原件", "证据原图", "原截图"):
                self.assertNotIn(forbidden, prose, recipe["recipe_id"])

    def test_gallery_runtime_assets_are_local_and_geo_data_is_preloaded(self) -> None:
        geo = load_json(GEO_JSON)
        expected_script = (
            "window.WISE_GUANGDONG_GEO = "
            + json.dumps(geo, ensure_ascii=False, separators=(",", ":"))
            + ";\n"
        )
        self.assertEqual(GEO_SCRIPT.read_text(encoding="utf-8"), expected_script)

        remote_resource = re.compile(
            r"(?:src|href)\s*=\s*[\"'](?:https?:)?//|fetch\(\s*[\"'](?:https?:)?//",
            re.IGNORECASE,
        )
        for corpus in ("general", "ai"):
            frames = ROOT / "gallery" / "paper-ink" / corpus / "frames"
            for frame in frames.glob("*.html"):
                source = frame.read_text(encoding="utf-8")
                self.assertIsNone(remote_resource.search(source), frame)
            map_frame = (frames / "layout-c4.html").read_text(encoding="utf-8")
            self.assertIn("capabilities/vendors/geo/guangdong-geo.js", map_frame)
            self.assertIn("window.WISE_GUANGDONG_GEO", map_frame)


class PublicCatalogTests(unittest.TestCase):
    def run_catalog(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CATALOG), *args, "--root", str(ROOT)],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_layout_query_uses_public_axes_and_records_every_candidate(self) -> None:
        result = self.run_catalog(
            "layouts",
            "--role",
            "prove",
            "--relation",
            "evidence",
            "--primitive",
            "evidence-annotation",
            "--renderer-kind",
            "svg",
            "--component-source",
            "native",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["evaluated_count"], 63)
        self.assertEqual(len(payload["candidate_evaluations"]), 63)
        self.assertGreater(payload["count"], 0)
        self.assertEqual(payload["count"], len(payload["items"]))
        self.assertTrue(
            all(item["result"] in {"fit", "reject"} for item in payload["candidate_evaluations"])
        )
        self.assertNotIn("theme_id", payload)
        self.assertNotIn("densities", payload["filters"])
        self.assertNotIn("providers", payload["filters"])

    def test_help_removes_theme_density_and_provider_flags(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CATALOG), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("--theme", result.stdout)
        self.assertNotIn("--density", result.stdout)
        self.assertNotIn("--provider", result.stdout)
        self.assertIn("--renderer-kind", result.stdout)
        self.assertIn("--component-source", result.stdout)


if __name__ == "__main__":
    unittest.main()
