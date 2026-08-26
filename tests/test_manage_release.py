from __future__ import annotations

import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts/manage_release.py"
SPEC = importlib.util.spec_from_file_location("manage_release", MODULE_PATH)
assert SPEC and SPEC.loader
manage_release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manage_release)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def local_links(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    links = re.findall(r"\[[^\]]*\]\(([^)]+)\)", text)
    links += re.findall(r'(?:href|src)=["\']([^"\']+)["\']', text)
    return [
        link.split("#", 1)[0]
        for link in links
        if link
        and not link.startswith(("#", "http://", "https://", "mailto:", "data:"))
    ]


class ManageReleaseTests(unittest.TestCase):
    def test_every_manifest_skill_carries_readme_and_repository_license(self) -> None:
        expected = (REPO_ROOT / "LICENSE").read_bytes()
        for skill in manage_release.manifest_skills():
            readme_path = REPO_ROOT / str(skill["path"]) / "README.md"
            license_path = REPO_ROOT / str(skill["path"]) / "LICENSE"
            self.assertTrue(readme_path.is_file(), str(readme_path))
            self.assertTrue(license_path.is_file(), str(license_path))
            self.assertEqual(license_path.read_bytes(), expected, str(license_path))
            for link in local_links(readme_path):
                self.assertTrue(
                    (readme_path.parent / link).resolve().exists(),
                    f"{readme_path}: {link}",
                )

    def test_release_readme_lists_every_manifest_skill(self) -> None:
        readme = (REPO_ROOT / "docs/release-README.md").read_text(encoding="utf-8")
        for skill in manage_release.manifest_skills():
            self.assertIn("`{}`".format(skill["name"]), readme)

    def test_repository_readme_keeps_repo_only_docs_discoverable(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        for relative in (
            "docs/blue-poster/README.md",
            "docs/ppt-speech-creator/examples/annual-review-example.md",
        ):
            self.assertIn(relative, readme)
            self.assertTrue((REPO_ROOT / relative).is_file())

        for relative in (
            "docs/blue-poster/README.md",
            "docs/blue-poster/README_EN.md",
        ):
            path = REPO_ROOT / relative
            for link in local_links(path):
                self.assertTrue((path.parent / link).resolve().exists(), f"{path}: {link}")

    def test_operational_reference_docs_have_skill_entrypoints(self) -> None:
        expected_links = {
            "optimize-system-performance": {
                "references/deep-forensics-macos.md",
                "references/deep-forensics-windows.md",
                "references/platform-mapping.md",
                "references/report-template.zh.md",
            },
            "ppt-speech-creator": {
                "references/component-library.md",
                "references/page-composition.md",
                "references/swiss-editorial-handoff.md",
                "references/templates/annual-review.md",
                "references/templates/product-launch.md",
                "references/templates/project-review.md",
                "references/templates/述职报告.md",
                "references/timing-strategies.md",
            },
        }
        for skill_name, expected in expected_links.items():
            skill_file = REPO_ROOT / skill_name / "SKILL.md"
            actual = set(local_links(skill_file))
            self.assertTrue(expected.issubset(actual), f"{skill_name}: {sorted(expected - actual)}")
            for link in expected:
                self.assertTrue((skill_file.parent / link).is_file(), f"{skill_name}: {link}")

    def test_check_package_ignores_generated_python_cache_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root / "LICENSE", "demo license\n")
            skill_root = root / "demo-skill"
            write(skill_root / "README.md", "# Demo Skill\n")
            write(
                skill_root / "SKILL.md",
                "---\nname: demo-skill\ndescription: Demo release skill.\n---\n",
            )
            write(skill_root / "LICENSE", "demo license\n")
            write(skill_root / "scripts/__pycache__/demo.cpython-312.pyc", "cache\n")

            with mock.patch.object(manage_release, "REPO_ROOT", root):
                self.assertEqual(
                    manage_release.check_package({"name": "demo-skill", "path": "demo-skill"}),
                    [],
                )
                write(skill_root / "tests/test_demo.py", "def test_demo():\n    assert True\n")
                errors = manage_release.check_package(
                    {"name": "demo-skill", "path": "demo-skill"}
                )

            self.assertTrue(any("包含开发目录" in error for error in errors))

    def test_check_package_requires_matching_license(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root / "LICENSE", "repository license\n")
            skill_root = root / "demo-skill"
            write(skill_root / "README.md", "# Demo Skill\n")
            write(
                skill_root / "SKILL.md",
                "---\nname: demo-skill\ndescription: Demo release skill.\n---\n",
            )

            with mock.patch.object(manage_release, "REPO_ROOT", root):
                missing_errors = manage_release.check_package(
                    {"name": "demo-skill", "path": "demo-skill"}
                )
                write(skill_root / "LICENSE", "different license\n")
                mismatch_errors = manage_release.check_package(
                    {"name": "demo-skill", "path": "demo-skill"}
                )

            self.assertTrue(any("缺少 LICENSE" in error for error in missing_errors))
            self.assertTrue(any("LICENSE 与仓库根 LICENSE 不一致" in error for error in mismatch_errors))

    def test_check_package_requires_readme(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write(root / "LICENSE", "repository license\n")
            skill_root = root / "demo-skill"
            write(
                skill_root / "SKILL.md",
                "---\nname: demo-skill\ndescription: Demo release skill.\n---\n",
            )
            write(skill_root / "LICENSE", "repository license\n")

            with mock.patch.object(manage_release, "REPO_ROOT", root):
                errors = manage_release.check_package(
                    {"name": "demo-skill", "path": "demo-skill"}
                )

            self.assertTrue(any("缺少 README.md" in error for error in errors))

    def test_build_release_copies_root_metadata_and_skill_license(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "repository"
            output = base / "release"
            write(root / "docs/release-README.md", "# User release\n")
            write(root / "LICENSE", "root license\n")
            write(root / "demo-skill/README.md", "# Demo Skill\n")
            write(
                root / "demo-skill/SKILL.md",
                "---\nname: demo-skill\ndescription: Demo release skill.\n---\n",
            )
            write(root / "demo-skill/LICENSE", "root license\n")
            write(
                root / "skills-release.json",
                json.dumps(
                    {
                        "schema_version": 1,
                        "skills": [
                            {"name": "demo-skill", "path": "demo-skill", "source": "repository"}
                        ],
                    }
                ),
            )

            with mock.patch.object(manage_release, "REPO_ROOT", root), mock.patch.object(
                manage_release, "MANIFEST_PATH", root / "skills-release.json"
            ):
                manage_release.build_release(output)

            self.assertEqual((output / "README.md").read_text(encoding="utf-8"), "# User release\n")
            self.assertEqual((output / "LICENSE").read_text(encoding="utf-8"), "root license\n")
            self.assertEqual(
                (output / "demo-skill/LICENSE").read_text(encoding="utf-8"),
                "root license\n",
            )
            manifest = json.loads((output / "_release-manifest.json").read_text(encoding="utf-8"))
            for relative in (
                "README.md",
                "LICENSE",
                "demo-skill/README.md",
                "demo-skill/LICENSE",
            ):
                self.assertIn(relative, manifest["sha256"])


if __name__ == "__main__":
    unittest.main()
