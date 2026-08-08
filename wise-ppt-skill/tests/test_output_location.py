from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _ppt_contracts import run_validation, validate_output_location  # noqa: E402


class OutputLocationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.skill_root = self.base / "wise-ppt-skill"
        self.workspace = self.base / "user-project"
        self.skill_root.mkdir()
        self.workspace.mkdir()

    def assert_has_code(self, result, code: str) -> None:
        self.assertIn(code, {issue.code for issue in result.errors})

    def test_accepts_nonexistent_deck_directory_inside_workspace(self) -> None:
        deck = self.workspace / "output" / "quarterly-review"
        result = validate_output_location(
            deck,
            self.skill_root,
            self.workspace,
            require_workspace=True,
        )
        self.assertTrue(result.ok, [issue.format() for issue in result.issues])

    def test_rejects_deck_outside_workspace(self) -> None:
        result = validate_output_location(
            self.base / "elsewhere" / "deck",
            self.skill_root,
            self.workspace,
            require_workspace=True,
        )
        self.assert_has_code(result, "output.outside_workspace")

    def test_rejects_skill_output_even_when_skill_is_workspace(self) -> None:
        result = validate_output_location(
            self.skill_root / "output" / "deck",
            self.skill_root,
            self.skill_root,
            require_workspace=True,
        )
        self.assert_has_code(result, "output.inside_skill")

    def test_internal_contract_paths_are_only_allowed_for_normal_validation(self) -> None:
        internal = self.skill_root / "themes" / "paper-ink" / "gallery" / "fixture"
        normal_validation = validate_output_location(internal, self.skill_root, allow_internal=True)
        delivery_preflight = validate_output_location(
            internal,
            self.skill_root,
            self.skill_root,
            require_workspace=True,
        )
        self.assertTrue(normal_validation.ok)
        self.assert_has_code(delivery_preflight, "output.inside_skill")

        examples = self.skill_root / "themes" / "paper-ink" / "examples" / "fixture"
        examples_result = validate_output_location(examples, self.skill_root, allow_internal=True)
        examples_delivery = validate_output_location(
            examples,
            self.skill_root,
            self.skill_root,
            require_workspace=True,
        )
        self.assertTrue(examples_result.ok)
        self.assert_has_code(examples_delivery, "output.inside_skill")

    def test_normal_validation_rejects_skill_output(self) -> None:
        result = run_validation(
            "content",
            self.skill_root / "output" / "deck" / "content.json",
            self.skill_root,
        )
        self.assert_has_code(result, "output.inside_skill")

    def test_cli_location_preflight(self) -> None:
        deck = self.workspace / "output" / "launch"
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "validate.py"),
                "location",
                str(deck),
                "--workspace",
                str(self.workspace),
                "--root",
                str(self.skill_root),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("PASS location", completed.stdout)


if __name__ == "__main__":
    unittest.main()
