from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "build-landmark-model-lighting"
INIT_SCRIPT = SKILL_ROOT / "scripts/init_case.py"
VALIDATE_SCRIPT = SKILL_ROOT / "scripts/validate_case.py"

CONTRACT_FILES = (
    "brief/model-brief.json",
    "case-manifest.json",
    "direction/direction-set.json",
    "qa/comparison-report.json",
    "references/reference-bundle.json",
    "reports/delivery-manifest.json",
    "runtime/acceptance-contract.js",
)


def run_script(script: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *arguments],
        capture_output=True,
        text=True,
    )


class BuildLandmarkModelLightingTests(unittest.TestCase):
    def test_builtin_self_tests_pass(self) -> None:
        for script in (INIT_SCRIPT, VALIDATE_SCRIPT):
            result = run_script(script, "--self-test")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"passed"', result.stdout)

    def test_init_creates_contract_and_rejects_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            case_root = str(Path(temporary_name) / "case")
            result = run_script(
                INIT_SCRIPT,
                "--root", case_root,
                "--subject", "测试大厦",
                "--slug", "test-tower",
                "--effect", "auto",
                "--review-mode", "user-self-check",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "initialized")
            self.assertEqual(payload["review_mode"], "user-self-check")
            for relative in CONTRACT_FILES:
                self.assertTrue((Path(case_root) / relative).is_file(), relative)

            repeat = run_script(
                INIT_SCRIPT,
                "--root", case_root,
                "--subject", "测试大厦",
                "--slug", "test-tower",
                "--effect", "auto",
                "--review-mode", "user-self-check",
            )
            self.assertNotEqual(repeat.returncode, 0)
            self.assertIn("refusing to overwrite", (repeat.stdout + repeat.stderr).lower())

    def test_strict_validation_rejects_unsealed_case(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            case_root = str(Path(temporary_name) / "case")
            run_script(
                INIT_SCRIPT,
                "--root", case_root,
                "--subject", "测试大厦",
                "--slug", "test-tower",
                "--effect", "auto",
                "--review-mode", "user-self-check",
            )
            result = run_script(VALIDATE_SCRIPT, "--root", case_root, "--strict")
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "failed")
            self.assertTrue(payload["errors"])
            self.assertIn("brief: status must be frozen", payload["errors"])


if __name__ == "__main__":
    unittest.main()
