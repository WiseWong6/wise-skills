import json
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional, Set, Union


SKILL_ROOT = Path(__file__).resolve().parents[2] / "skill-optimizer"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from audit_skill import MAX_TEXT_BYTES, audit_skill, estimate_tokens  # noqa: E402


DESCRIPTION = "用于审计和优化一个现有 Skill，并先用通俗中文解释问题后等待用户确认。"
SHORT_DESCRIPTION = "用通俗中文诊断现有 Skill 并降低上下文与执行成本"


def write(path: Path, content: Union[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def make_valid_skill(root: Path, body: str = "# Demo\n\n完成一项明确任务。\n") -> None:
    write(
        root / "SKILL.md",
        "---\nname: {}\ndescription: {}\n---\n\n{}".format(root.name, DESCRIPTION, body),
    )
    write(
        root / "agents/openai.yaml",
        "interface:\n"
        '  display_name: "Demo Skill"\n'
        '  short_description: "{}"\n'.format(SHORT_DESCRIPTION)
        + '  default_prompt: "使用 ${} 完成这项任务。"\n'.format(root.name),
    )


def add_release_envelope(root: Path, readme: str = "# Demo Skill\n\n安装与使用说明。\n") -> None:
    write(root / "README.md", readme)
    write(root / "LICENSE", "MIT License\n\nCopyright 2026 Demo\n")


def codes(result: dict, severity: Optional[str] = None) -> Set[str]:
    return {
        item["code"]
        for item in result["findings"]
        if severity is None or item["severity"] == severity
    }


class AuditSkillTests(unittest.TestCase):
    def test_optimizer_contract_separates_roles_surfaces_and_supported_platforms(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        metadata = (SKILL_ROOT / "agents/openai.yaml").read_text(encoding="utf-8")

        for requirement in (
            "权威源码 → 发行载荷 → Agent 安装入口/软链 → Agent 实际加载 → 真实任务",
            "生命周期审计判据",
            "平台 Schema Profile",
            "不通过目录名猜开发仓或发行仓",
            "--profile <auto|general|review>",
            "--schema-profile <auto|codex|redskill>",
            "--release-manifest <发行 manifest 路径>",
            "--agent-entry codex=<Codex 安装入口>",
            "--supported-node-majors 22,24",
            "未知 Skill 的 doctor/build/install 不自动执行",
            "version_coordinates",
            "runtime_verification",
            "deadweight-candidate",
            "被 manifest 列出，不等于有功能用途",
            "Git SHA、frontmatter 语义版本和平台线上版本不是同一个版本数字",
            "系统原生能力 → 已有依赖 → 新增依赖",
            "不得称为系统性修复",
            "先给人话方案",
            "用户确认后实施",
            "真实运行验收",
            "macOS/Windows × Agent × 入口",
            "平台/Agent 未实测",
            "用户确认前不修改权威源码",
            "逐条执行、逐条复核",
        ):
            self.assertIn(requirement, skill)
        self.assertNotIn("Linux", skill)
        for requirement in (
            "开发者",
            "使用者",
            "macOS/Windows",
            "公共根因",
            "影响面",
            "防复发",
            "README",
            "License/NOTICE",
            "生命周期证据图",
            "死重候选",
            "不自动删除或修复软链",
        ):
            self.assertIn(requirement, metadata)

    def test_valid_skill_has_no_blocking_issue(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "demo-skill"
            root.mkdir()
            make_valid_skill(root)

            result, exit_code = audit_skill(root)

            self.assertEqual(exit_code, 0)
            self.assertEqual(result["summary"]["error"], 0)
            self.assertGreater(result["metrics"]["triggered_body_estimated_tokens"], 0)
            self.assertGreater(result["metrics"]["declared_context_estimated_tokens"], 0)
            self.assertGreater(result["metrics"]["target_total_bytes"], 0)
            self.assertNotIn("total_text_estimated_tokens", result["metrics"])
            self.assertEqual(
                result["surfaces"]["release_artifact"]["status"], "not-provided"
            )

    def test_release_surface_does_not_require_readme_or_license(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source" / "private-skill"
            release = Path(temp) / "release" / "private-skill"
            source.mkdir(parents=True)
            release.mkdir(parents=True)
            make_valid_skill(source)
            make_valid_skill(release)

            result, exit_code = audit_skill(
                release,
                source=source,
                surface="release",
            )

            self.assertEqual(exit_code, 0)
            self.assertNotIn("release-readme-removed", codes(result))
            self.assertNotIn("release-license-removed", codes(result))
            envelope = result["surfaces"]["release_envelope"]
            self.assertEqual(envelope["status"], "preserved")
            self.assertFalse(envelope["readme"]["required"])
            self.assertFalse(envelope["readme"]["source_present"])
            self.assertFalse(envelope["license"]["required"])
            self.assertFalse(envelope["license"]["source_present"])
            self.assertEqual(result["surfaces"]["release_artifact"]["status"], "provided")
            self.assertEqual(result["surfaces"]["effective_profile"], "review")

    def test_release_surface_rejects_removing_existing_readme_and_legal_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source" / "preserved-skill"
            release = Path(temp) / "release" / "preserved-skill"
            source.mkdir(parents=True)
            release.mkdir(parents=True)
            make_valid_skill(source)
            make_valid_skill(release)
            add_release_envelope(source)
            write(source / "NOTICE", "Third-party notices.\n")

            result, exit_code = audit_skill(
                release,
                source=source,
                surface="release",
            )

            self.assertEqual(exit_code, 1)
            self.assertIn("release-readme-removed", codes(result, "error"))
            self.assertIn("release-license-removed", codes(result, "error"))
            self.assertIn("release-legal-notice-removed", codes(result, "error"))
            envelope = result["surfaces"]["release_envelope"]
            self.assertEqual(envelope["status"], "regressed")
            self.assertTrue(envelope["readme"]["source_present"])
            self.assertTrue(envelope["readme"]["removed"])
            self.assertTrue(envelope["license"]["source_present"])
            self.assertTrue(envelope["license"]["removed"])

    def test_complete_release_envelope_passes_without_entering_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "complete-release"
            root.mkdir()
            make_valid_skill(root)
            baseline, _ = audit_skill(root)
            add_release_envelope(root, "# Complete\n\n" + "人类安装说明。" * 80 + "\n")
            write(root / "NOTICE", "Third-party notices.\n")

            result, exit_code = audit_skill(root, surface="release")

            self.assertEqual(exit_code, 0)
            self.assertNotIn("release-readme-removed", codes(result))
            self.assertNotIn("release-license-removed", codes(result))
            self.assertNotIn("extra-doc", codes(result))
            self.assertEqual(result["surfaces"]["release_envelope"]["status"], "observed")
            self.assertEqual(
                result["metrics"]["declared_context_estimated_tokens"],
                baseline["metrics"]["declared_context_estimated_tokens"],
            )
            self.assertGreater(
                result["metrics"]["target_text_estimated_tokens"],
                baseline["metrics"]["target_text_estimated_tokens"],
            )

    def test_release_readme_relative_links_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "broken-release"
            root.mkdir()
            make_valid_skill(root)
            add_release_envelope(
                root,
                "# Broken\n\n<a href=\"references/style-catalog.html\">本地风格图册</a>\n",
            )

            result, exit_code = audit_skill(root, surface="release")

            self.assertEqual(exit_code, 1)
            self.assertIn("link-broken", codes(result, "error"))
            self.assertNotIn("release-readme-removed", codes(result))
            self.assertNotIn("release-license-removed", codes(result))

    def test_showcase_examples_are_visible_but_not_called_developer_junk(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "showcase-release"
            root.mkdir()
            make_valid_skill(root)
            add_release_envelope(root)
            write(root / "assets/examples/demo.webp", b"RIFF-demo")

            result, exit_code = audit_skill(root, surface="release")

            self.assertEqual(exit_code, 0)
            self.assertIn(
                "assets/examples/demo.webp",
                result["surfaces"]["release_envelope"]["showcase_examples"],
            )
            self.assertFalse(result["surfaces"]["developer_assets"]["counts"])

    def test_developer_assets_are_classified_without_being_called_removable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "developer-skill"
            root.mkdir()
            make_valid_skill(root)
            write(root / "tests/test_demo.py", "def test_demo():\n    assert True\n")
            write(root / "requirements-dev.txt", "pytest>=8\n")
            write(root / "scripts/build_catalog.py", "print('build')\n")

            result, exit_code = audit_skill(root)

            self.assertEqual(exit_code, 0)
            assets = result["surfaces"]["developer_assets"]
            self.assertEqual(assets["counts"]["tests"], 1)
            self.assertEqual(assets["counts"]["development-dependencies"], 1)
            self.assertEqual(assets["counts"]["development-scripts"], 1)
            self.assertIn("可留在源码", assets["classification"])
            self.assertIn("developer-assets-present", codes(result, "info"))

    def test_runtime_commands_and_windows_shell_gap_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "portable-skill"
            root.mkdir()
            make_valid_skill(
                root,
                "# Portable\n\n支持 macOS、Windows，由 Codex 和 Claude 调用。\n",
            )
            write(
                root / "scripts/run",
                "#!/bin/sh\ncommand -v pdfinfo >/dev/null || exit 1\npdfinfo output.pdf\n",
            )

            result, exit_code = audit_skill(root)

            self.assertEqual(exit_code, 0)
            commands = {
                item["command"] for item in result["surfaces"]["runtime_command_candidates"]
            }
            self.assertIn("pdfinfo", commands)
            self.assertEqual(
                result["surfaces"]["declared_support"]["platforms"],
                ["macOS", "Windows"],
            )
            self.assertEqual(
                result["surfaces"]["declared_support"]["agents"],
                ["codex", "claude"],
            )
            self.assertIn("runtime-command-candidates", codes(result, "info"))
            self.assertIn("windows-entrypoint-unverified", codes(result, "warning"))

    def test_source_and_installed_copy_drift_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source" / "demo-skill"
            installed = base / "installed" / "demo-skill"
            source.mkdir(parents=True)
            installed.mkdir(parents=True)
            make_valid_skill(source)
            make_valid_skill(installed)
            write(source / "references/source-only.md", "只在源码中。\n")

            result, exit_code = audit_skill(installed, source=source)

            self.assertEqual(exit_code, 0)
            comparison = result["surfaces"]["authoritative_source"]["comparison"]
            self.assertEqual(comparison["status"], "drift")
            self.assertEqual(comparison["source_only_count"], 1)
            self.assertIn("source-install-drift", codes(result, "warning"))

    def test_codex_and_redskill_schema_profiles_do_not_share_one_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Demo-Skill"
            root.mkdir()
            write(
                root / "SKILL.md",
                "---\n"
                "name: Demo-Skill\n"
                "description: Demo platform-specific schema.\n"
                'version: "1.2.3"\n'
                "metadata:\n"
                "  author: Demo\n"
                "---\n",
            )

            codex, codex_exit = audit_skill(root, schema_profile="codex")
            redskill, redskill_exit = audit_skill(root, schema_profile="redskill")

            self.assertEqual(codex_exit, 1)
            self.assertIn("skill-name-invalid", codes(codex, "error"))
            self.assertIn("frontmatter-extra-keys", codes(codex, "warning"))
            self.assertEqual(redskill_exit, 0)
            self.assertNotIn("skill-name-invalid", codes(redskill))
            self.assertNotIn("frontmatter-extra-keys", codes(redskill))
            self.assertNotIn("redskill-version-policy", codes(redskill))
            self.assertEqual(
                redskill["surfaces"]["schema_profile"]["effective"], "redskill"
            )

    def test_redskill_missing_version_is_policy_warning_not_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "redskill-demo"
            root.mkdir()
            make_valid_skill(root)

            result, exit_code = audit_skill(root, schema_profile="redskill")

            self.assertEqual(exit_code, 0)
            self.assertIn("redskill-version-policy", codes(result, "warning"))
            finding = next(
                item for item in result["findings"] if item["code"] == "redskill-version-policy"
            )
            self.assertEqual(finding["kind"], "policy")

    @unittest.skipUnless(hasattr(os, "symlink"), "requires symlinks")
    def test_agent_entry_chain_reports_multi_hop_and_cross_agent_upstream(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source" / "demo-skill"
            codex_entry = base / ".codex/skills/demo-skill"
            agents_entry = base / ".agents/skills/demo-skill"
            source.mkdir(parents=True)
            codex_entry.parent.mkdir(parents=True)
            agents_entry.parent.mkdir(parents=True)
            make_valid_skill(source)
            os.symlink(str(source), str(codex_entry), target_is_directory=True)
            os.symlink(str(codex_entry), str(agents_entry), target_is_directory=True)

            result, exit_code = audit_skill(
                source,
                agent_entries=(("codex", codex_entry), ("agents", agents_entry)),
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("agent-entry-multi-hop", codes(result, "warning"))
            self.assertIn("agent-entry-cross-agent-upstream", codes(result, "warning"))
            agents = next(
                item
                for item in result["lifecycle"]["agent_entries"]
                if item["agent"] == "agents"
            )
            self.assertEqual(agents["hop_count"], 2)
            self.assertEqual(agents["cross_agent_targets"], ["codex"])
            self.assertEqual(result["runtime_verification"]["status"], "not-run")

    @unittest.skipUnless(hasattr(os, "symlink"), "requires symlinks")
    def test_broken_and_cyclic_agent_entries_are_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "demo-skill"
            root.mkdir()
            make_valid_skill(root)
            broken = base / "broken"
            os.symlink("missing", str(broken))

            broken_result, broken_exit = audit_skill(
                root, agent_entries=(("codex", broken),)
            )
            self.assertEqual(broken_exit, 1)
            self.assertIn("agent-entry-broken", codes(broken_result, "error"))

            missing = base / "not-created"
            missing_result, missing_exit = audit_skill(
                root, agent_entries=(("codex", missing),)
            )
            self.assertEqual(missing_exit, 1)
            self.assertIn("agent-entry-missing", codes(missing_result, "error"))

            first = base / "cycle-a"
            second = base / "cycle-b"
            os.symlink(second.name, str(first))
            os.symlink(first.name, str(second))
            cycle_result, cycle_exit = audit_skill(
                root, agent_entries=(("codex", first),)
            )
            self.assertEqual(cycle_exit, 1)
            self.assertIn("agent-entry-cycle", codes(cycle_result, "error"))

    @unittest.skipUnless(hasattr(os, "symlink"), "requires symlinks")
    def test_wrong_relative_agent_entry_to_another_skill_is_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "demo-skill"
            wrong = base / "other-skill"
            entry = base / ".agents/skills/demo-skill"
            root.mkdir()
            wrong.mkdir()
            entry.parent.mkdir(parents=True)
            make_valid_skill(root)
            make_valid_skill(wrong)
            os.symlink("../../other-skill", str(entry), target_is_directory=True)

            result, exit_code = audit_skill(
                root, agent_entries=(("agents", entry),)
            )

            self.assertEqual(exit_code, 1)
            self.assertIn("agent-entry-target-mismatch", codes(result, "error"))
            trace = result["lifecycle"]["agent_entries"][0]
            self.assertTrue(trace["hops"][0]["relative"])
            self.assertEqual(trace["declared_skill_name"], "other-skill")

    def test_independent_agent_copies_report_content_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source" / "demo-skill"
            installed = base / "installed" / "demo-skill"
            source.mkdir(parents=True)
            installed.mkdir(parents=True)
            make_valid_skill(source)
            make_valid_skill(installed, "# Drift\n\n另一份可独立变化的内容。\n")

            result, exit_code = audit_skill(
                source,
                agent_entries=(("codex", source), ("agents", installed)),
            )

            self.assertEqual(exit_code, 0)
            self.assertIn("agent-entry-content-drift", codes(result, "warning"))

    def test_release_manifest_hash_damage_is_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "manifest-skill"
            root.mkdir()
            make_valid_skill(root)
            actual = hashlib.sha256((root / "SKILL.md").read_bytes()).hexdigest()
            manifest = Path(temp) / "_release-manifest.json"
            write(
                manifest,
                json.dumps(
                    {
                        "skills": ["manifest-skill"],
                        "sha256": {
                            "manifest-skill/SKILL.md": "0" * 64,
                            "unrelated/README.md": actual,
                        },
                    }
                ),
            )
            result, exit_code = audit_skill(
                root, surface="release", release_manifest=manifest
            )

            self.assertEqual(exit_code, 1)
            self.assertIn("release-manifest-hash-mismatch", codes(result, "error"))
            self.assertTrue(
                result["lifecycle"]["release_manifest"]["skill_declared"]
            )

    def test_repository_manifest_does_not_apply_root_file_to_same_named_skill_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "manifest-skill"
            root.mkdir()
            make_valid_skill(root)
            add_release_envelope(root)
            manifest = Path(temp) / "_release-manifest.json"
            skill_readme = hashlib.sha256((root / "README.md").read_bytes()).hexdigest()
            skill_contract = hashlib.sha256((root / "SKILL.md").read_bytes()).hexdigest()
            write(
                manifest,
                json.dumps(
                    {
                        "skills": ["manifest-skill"],
                        "sha256": {
                            "README.md": "0" * 64,
                            "manifest-skill/README.md": skill_readme,
                            "manifest-skill/SKILL.md": skill_contract,
                        },
                    }
                ),
            )
            result, exit_code = audit_skill(
                root, surface="release", release_manifest=manifest
            )

            self.assertEqual(exit_code, 0)
            self.assertNotIn("release-manifest-hash-mismatch", codes(result))
            checked = result["lifecycle"]["release_manifest"]["checked"]
            self.assertEqual(
                {item["file"] for item in checked}, {"README.md", "SKILL.md"}
            )

    @unittest.skipUnless(shutil.which("git"), "requires git")
    def test_release_source_commit_is_separate_from_git_and_dirty_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repository = Path(temp) / "repository"
            root = repository / "coordinate-skill"
            root.mkdir(parents=True)
            make_valid_skill(root)
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            subprocess.run(["git", "add", "."], cwd=repository, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Skill Test",
                    "-c",
                    "user.email=skill-test@example.invalid",
                    "commit",
                    "-qm",
                    "fixture",
                ],
                cwd=repository,
                check=True,
            )
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repository,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            manifest = repository / "_release-manifest.json"
            write(
                manifest,
                json.dumps(
                    {
                        "skills": ["coordinate-skill"],
                        "source_commit": "deadbeef",
                        "sha256": {
                            "coordinate-skill/SKILL.md": hashlib.sha256(
                                (root / "SKILL.md").read_bytes()
                            ).hexdigest(),
                            "coordinate-skill/agents/openai.yaml": hashlib.sha256(
                                (root / "agents/openai.yaml").read_bytes()
                            ).hexdigest(),
                        },
                    }
                ),
            )
            write(root / "runtime-note.tmp", "untracked coordinate evidence\n")

            result, exit_code = audit_skill(
                root, source=root, surface="release", release_manifest=manifest
            )

            self.assertEqual(exit_code, 0)
            coordinates = result["version_coordinates"]
            self.assertEqual(coordinates["source"]["git_head"], head)
            self.assertTrue(coordinates["source"]["git_dirty"])
            self.assertEqual(coordinates["release"]["source_commit"], "deadbeef")
            self.assertIn("release-source-commit-divergence", codes(result, "warning"))

    def test_deadweight_uses_functional_edges_not_manifest_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "deadweight-skill"
            root.mkdir()
            make_valid_skill(
                root,
                "# Runtime\n\n运行 `scripts/run.py`，并由 `scripts/loader.py` 动态读取数据。\n",
            )
            add_release_envelope(root)
            write(root / "scripts/run.py", "print('run')\n")
            write(
                root / "scripts/loader.py",
                'from pathlib import Path\nlist(Path("assets/dynamic").glob("*.json"))\n',
            )
            write(root / "assets/dynamic/live.json", "{}\n")
            write(root / "assets/unused.json", "{}\n")
            write(root / "tests/test_demo.py", "def test_demo():\n    assert True\n")
            write(root / "archive/old.txt", "archived\n")
            write(
                root / "bundle-manifest.json",
                json.dumps(
                    {
                        "files": {
                            "assets/unused.json": "inventory-only",
                            "assets/dynamic/live.json": "inventory-only",
                        }
                    }
                ),
            )

            result, exit_code = audit_skill(root, surface="release")

            self.assertEqual(exit_code, 0)
            by_path = {
                item["path"]: item for item in result["reachability"]["files"]
            }
            self.assertEqual(
                by_path["assets/unused.json"]["status"], "deadweight-candidate"
            )
            self.assertEqual(
                {edge["kind"] for edge in by_path["assets/unused.json"]["inbound_edges"]},
                {"integrity"},
            )
            self.assertEqual(
                by_path["assets/dynamic/live.json"]["status"], "dynamic-unresolved"
            )
            self.assertEqual(by_path["README.md"]["status"], "user-envelope")
            self.assertEqual(by_path["LICENSE"]["status"], "user-envelope")
            self.assertEqual(
                by_path["tests/test_demo.py"]["status"], "development-only"
            )
            self.assertEqual(by_path["archive/old.txt"]["status"], "archive-only")
            self.assertEqual(by_path["bundle-manifest.json"]["status"], "required")
            self.assertNotIn("confirmed-deadweight", codes(result))

    def test_unused_dependency_requires_build_evidence_and_stays_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "dependency-candidate-skill"
            root.mkdir()
            make_valid_skill(root, "# Runtime\n\n运行 `scripts/main.mjs`。\n")
            write(
                root / "package.json",
                json.dumps(
                    {
                        "dependencies": {
                            "used-package": "1.0.0",
                            "unused-package": "1.0.0",
                        },
                        "devDependencies": {"test-package": "1.0.0"},
                    }
                ),
            )
            write(root / "scripts/main.mjs", 'import "used-package";\n')
            metafile = root / "metafile.json"
            write(
                metafile,
                json.dumps(
                    {
                        "inputs": {
                            "scripts/main.mjs": {"bytes": 24},
                            "node_modules/used-package/index.js": {"bytes": 50},
                        },
                        "outputs": {
                            "dist/main.js": {
                                "bytes": 74,
                                "inputs": {
                                    "scripts/main.mjs": {"bytesInOutput": 24},
                                    "node_modules/used-package/index.js": {
                                        "bytesInOutput": 50
                                    },
                                },
                            }
                        },
                    }
                ),
            )

            result, exit_code = audit_skill(
                root, surface="release", metafile=metafile
            )

            self.assertEqual(exit_code, 0)
            roles = {
                item["name"]: item for item in result["reachability"]["dependencies"]
            }
            self.assertEqual(roles["used-package"]["status"], "required")
            self.assertEqual(
                roles["unused-package"]["status"], "deadweight-candidate"
            )
            self.assertEqual(roles["test-package"]["status"], "development-only")
            self.assertIn("unused-dependency-candidate", codes(result, "warning"))

    def test_local_python_package_imports_keep_split_runtime_modules_reachable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "python-module-skill"
            root.mkdir()
            make_valid_skill(root, "# Runtime\n\n运行 `scripts/audit_skill.py`。\n")
            write(
                root / "scripts/audit_skill.py",
                "from skill_audit import core as _core\n_core.run()\n",
            )
            write(root / "scripts/skill_audit/__init__.py", "\n")
            write(
                root / "scripts/skill_audit/core.py",
                "from skill_audit.model import result\ndef run(): return result\n",
            )
            write(root / "scripts/skill_audit/model.py", "result = True\n")

            result, exit_code = audit_skill(root, surface="release")

            self.assertEqual(exit_code, 0)
            by_path = {
                item["path"]: item for item in result["reachability"]["files"]
            }
            for path in (
                "scripts/audit_skill.py",
                "scripts/skill_audit/__init__.py",
                "scripts/skill_audit/core.py",
                "scripts/skill_audit/model.py",
            ):
                self.assertEqual(by_path[path]["status"], "required")

    def test_structure_matrix_explains_policy_without_a_score(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "structured-skill"
            root.mkdir()
            write(
                root / "SKILL.md",
                "---\nname: structured-skill\n"
                "description: Structure matrix test.\n"
                'version: "1.0.0"\n---\n\n'
                "[A](references/a.md)\n",
            )
            write(root / "references/a.md", "[B](b.md)\n")
            write(root / "references/b.md", "[A](a.md)\n")
            write(root / "custom/data.txt", "custom\n")

            result, exit_code = audit_skill(
                root, surface="release", schema_profile="redskill"
            )

            self.assertEqual(exit_code, 0)
            self.assertIsNone(result["structure"]["score"])
            self.assertIn("reference-graph-cycle", codes(result, "warning"))
            self.assertIn("structure-top-level-unclassified", codes(result, "warning"))
            self.assertIn("redskill-top-level-structure-policy", codes(result, "warning"))
            dag = next(
                item
                for item in result["structure"]["checks"]
                if item["id"] == "lifecycle-dag"
            )
            self.assertEqual(dag["status"], "review")

    @unittest.skipUnless(hasattr(os, "symlink") and shutil.which("git"), "requires git and symlinks")
    def test_symlinked_install_is_not_treated_as_independent_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            repository = base / "repository"
            source = repository / "linked-skill"
            installed = base / "installed" / "linked-skill"
            source.mkdir(parents=True)
            installed.parent.mkdir(parents=True)
            make_valid_skill(source)
            subprocess.run(
                ["git", "init", str(repository)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            os.symlink(str(source), str(installed), target_is_directory=True)

            result, exit_code = audit_skill(installed, source=source)

            self.assertEqual(exit_code, 0)
            self.assertTrue(result["surfaces"]["input_is_symlink"])
            self.assertTrue(result["surfaces"]["git"]["managed"])
            self.assertEqual(
                result["surfaces"]["authoritative_source"]["comparison"]["status"],
                "same-tree",
            )
            self.assertIn("installed-source-symlink", codes(result))
            self.assertIn("source-install-same-tree", codes(result, "info"))

    def test_missing_skill_md_is_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "missing-skill"
            root.mkdir()

            result, exit_code = audit_skill(root)

            self.assertEqual(exit_code, 1)
            self.assertIn("skill-md-missing", codes(result, "error"))

    def test_invalid_frontmatter_and_directory_mismatch_are_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "right-name"
            root.mkdir()
            write(root / "SKILL.md", "---\nname: wrong_name\ndescription: TODO\n---\n")

            result, exit_code = audit_skill(root)

            self.assertEqual(exit_code, 1)
            self.assertIn("skill-name-invalid", codes(result, "error"))
            self.assertIn("skill-name-directory-mismatch", codes(result, "error"))
            self.assertIn("frontmatter-required", codes(result, "error"))

    def test_broken_link_deep_reference_and_orphan_doc_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "linked-skill"
            root.mkdir()
            make_valid_skill(
                root,
                "# Linked\n\n[第一层](references/one.md)\n\n[缺失](references/missing.md)\n\n"
                "```markdown\n[代码示例，不是依赖](references/example.md)\n```\n\n"
                "~~~markdown\n[另一种代码围栏](references/example-two.md)\n~~~\n",
            )
            write(root / "references/one.md", "# One\n\n[第二层](two.md)\n")
            write(root / "references/two.md", "# Two\n")
            write(root / "references/orphan.md", "# Orphan\n")

            result, exit_code = audit_skill(root)

            self.assertEqual(exit_code, 1)
            self.assertIn("link-broken", codes(result, "error"))
            self.assertEqual(
                sum(item["code"] == "link-broken" for item in result["findings"]),
                1,
            )
            self.assertIn("reference-depth", codes(result, "warning"))
            self.assertIn("orphan-doc", codes(result, "warning"))
            self.assertEqual(result["metrics"]["max_reference_depth"], 2)

    def test_backticked_root_relative_paths_are_reachable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "backtick-path-skill"
            root.mkdir()
            make_valid_skill(
                root,
                "# Backtick Paths\n\n需要时读取 `references/stage.md`。\n",
            )
            write(
                root / "references/stage.md",
                "# Stage\n\n按布局读取 `references/templates/layout.md`。\n",
            )
            write(root / "references/templates/layout.md", "# Layout\n")

            result, exit_code = audit_skill(root)

            self.assertEqual(exit_code, 0)
            self.assertNotIn("orphan-doc", codes(result, "warning"))
            self.assertEqual(
                result["files"]["reachable_references"],
                ["references/stage.md", "references/templates/layout.md"],
            )

    def test_duplicate_paragraph_and_human_docs_are_separate(self) -> None:
        paragraph = "这是一段足够长的重复规则，用来确认审计器能够发现跨文件的完全重复内容，并提醒维护者只保留一个权威位置。"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "duplicate-skill"
            root.mkdir()
            make_valid_skill(root, "# Duplicate\n\n{}\n\n[细节](references/detail.md)\n".format(paragraph))
            write(root / "references/detail.md", paragraph + "\n")
            write(root / "README.md", "辅助说明\n")

            result, exit_code = audit_skill(root)

            self.assertEqual(exit_code, 0)
            self.assertIn("duplicate-paragraph", codes(result, "warning"))
            self.assertNotIn("extra-doc", codes(result))
            self.assertIn(
                "README.md",
                result["surfaces"]["release_envelope"]["human_documents"],
            )

    def test_legacy_words_are_information_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "legacy-skill"
            root.mkdir()
            make_valid_skill(root, "# Legacy\n\n保留旧逻辑作为 fallback。\n")

            result, exit_code = audit_skill(root)

            self.assertEqual(exit_code, 0)
            self.assertIn("legacy-signal", codes(result, "info"))

    def test_openai_metadata_mismatch_is_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "metadata-skill"
            root.mkdir()
            make_valid_skill(root)
            write(
                root / "agents/openai.yaml",
                "interface:\n"
                '  display_name: "Metadata"\n'
                '  short_description: "太短"\n'
                '  default_prompt: "使用别的 Skill。"\n',
            )

            result, exit_code = audit_skill(root)

            self.assertEqual(exit_code, 0)
            self.assertIn("openai-yaml-description-length", codes(result, "warning"))
            self.assertIn("openai-yaml-prompt-name", codes(result, "warning"))

    def test_binary_is_skipped_but_oversized_text_is_streamed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "bounded-skill"
            root.mkdir()
            make_valid_skill(root)
            write(root / "assets/image.bin", b"\x00\x01\x02")
            write(root / "references/huge.txt", b"x" * (MAX_TEXT_BYTES + 1))

            result, exit_code = audit_skill(root)

            self.assertEqual(exit_code, 0)
            reasons = {item["reason"] for item in result["files"]["skipped"]}
            self.assertIn("二进制文件", reasons)
            self.assertFalse(any("超过" in reason for reason in reasons))
            self.assertEqual(
                [item["file"] for item in result["files"]["streamed"]],
                ["references/huge.txt"],
            )
            self.assertEqual(result["metrics"]["streamed_text_file_count"], 1)

    def test_node_24_doctor_gate_conflicts_with_node_22_contract_and_host(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "node-gate-skill"
            root.mkdir()
            make_valid_skill(root, "# Runtime\n\n要求 Node >= 22+。\n")
            write(
                root / "package.json",
                json.dumps({"engines": {"node": ">=22"}}),
            )
            write(
                root / "scripts/doctor.mjs",
                "const MIN_NODE_MAJOR = 24;\n"
                "if (Number(process.versions.node.split('.')[0]) < MIN_NODE_MAJOR) process.exit(1);\n",
            )
            write(
                root / ".github/workflows/test.yml",
                "strategy:\n  matrix:\n    node-version: [22, 24]\n",
            )

            result, exit_code = audit_skill(
                root,
                supported_node_majors=(22, 24),
                host_node_major=22,
            )

            self.assertEqual(exit_code, 1)
            self.assertIn("runtime-node-constraint-conflict", codes(result, "error"))
            self.assertIn("runtime-node-host-incompatible", codes(result, "error"))
            self.assertIn("runtime-node-test-matrix-conflict", codes(result, "error"))
            self.assertIn("runtime-supported-lts-excluded", codes(result, "warning"))

    def test_large_generated_bundle_blocks_review_without_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "opaque-bundle-skill"
            root.mkdir()
            make_valid_skill(root)
            add_release_envelope(root)
            prefix = b"// generated by esbuild\n// node_modules/undici/index.js\n"
            write(root / "bin/wise-ppt.js", prefix + b"x" * (3400 * 1024))

            result, exit_code = audit_skill(root, surface="release")

            self.assertEqual(exit_code, 1)
            self.assertIn("artifact-large-executable", codes(result, "warning"))
            self.assertIn("artifact-generated-provenance-missing", codes(result, "error"))
            item = result["surfaces"]["artifact_analysis"]["executables"][0]
            self.assertEqual(item["classification"], "generated-minified")
            self.assertGreater(item["line_count"], 1)
            self.assertNotEqual(item["classification"], "suspected-obfuscated")

    def test_metafile_and_notice_reduce_bundle_block_to_size_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "traceable-bundle-skill"
            root.mkdir()
            make_valid_skill(root)
            add_release_envelope(root)
            write(root / "NOTICE", "Third-party components are declared here.\n")
            prefix = b"// generated by esbuild\n// node_modules/undici/index.js\n"
            write(root / "bin/wise-ppt.js", prefix + b"x" * (1200 * 1024))
            write(
                root / "metafile.json",
                json.dumps(
                    {
                        "inputs": {
                            "src/main.js": {"bytes": 100},
                            "node_modules/undici/index.js": {"bytes": 900},
                        },
                        "outputs": {
                            "bin/wise-ppt.js": {
                                "bytes": 1000,
                                "inputs": {
                                    "src/main.js": {"bytesInOutput": 100},
                                    "node_modules/undici/index.js": {"bytesInOutput": 900},
                                },
                            }
                        },
                    }
                ),
            )

            result, exit_code = audit_skill(
                root,
                surface="release",
                supported_node_majors=(22, 24),
                host_node_major=22,
            )

            self.assertEqual(exit_code, 0)
            self.assertNotIn("artifact-generated-provenance-missing", codes(result))
            self.assertIn("artifact-large-executable", codes(result, "warning"))
            self.assertIn("artifact-third-party-dominant", codes(result, "warning"))
            self.assertEqual(
                result["surfaces"]["metafile"]["measurement"], "bytes-in-output"
            )
            undici = next(
                item
                for item in result["surfaces"]["dependency_analysis"]["dependencies"]
                if item["name"] == "undici"
            )
            self.assertTrue(undici["bundled"])
            self.assertEqual(undici["bytes"], 900)

    def test_large_release_reports_category_shares_without_calling_assets_junk(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "asset-heavy-skill"
            root.mkdir()
            make_valid_skill(root)
            add_release_envelope(root)
            for index in range(233):
                write(root / "catalog" / "items" / ("item-{}.json".format(index)), b"x" * 18010)
            write(root / "assets/fonts/display.woff2", b"font-data" * 2000)
            write(root / "assets/examples/demo.png", b"image-data" * 2000)

            result, exit_code = audit_skill(root, surface="release")

            self.assertEqual(exit_code, 0)
            self.assertIn("artifact-release-budget", codes(result, "warning"))
            categories = {
                item["category"]: item
                for item in result["surfaces"]["artifact_analysis"]["categories"]
            }
            self.assertGreater(categories["data"]["bytes"], 4 * 1024 * 1024)
            self.assertGreater(categories["fonts"]["bytes"], 0)
            self.assertGreater(categories["examples"]["bytes"], 0)
            self.assertFalse(any("junk" in item["code"] for item in result["findings"]))

    def test_undici_candidate_requires_plain_fetch_not_agent_api(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            plain = base / "plain-undici"
            advanced = base / "agent-undici"
            plain.mkdir()
            advanced.mkdir()
            for root in (plain, advanced):
                make_valid_skill(root, "# Runtime\n\n要求 Node >= 22+。\n")
                write(
                    root / "package.json",
                    json.dumps(
                        {
                            "engines": {"node": ">=22"},
                            "dependencies": {"undici": "^7.0.0"},
                        }
                    ),
                )
            write(plain / "bin/cli.mjs", 'import { fetch } from "undici";\nfetch("https://example.invalid");\n')
            write(advanced / "bin/cli.mjs", 'import { Agent, fetch } from "undici";\nconst dispatcher = new Agent({});\n')

            plain_result, _ = audit_skill(plain, host_node_major=22)
            advanced_result, _ = audit_skill(advanced, host_node_major=22)

            self.assertIn(
                "dependency-undici-native-candidate", codes(plain_result, "warning")
            )
            self.assertNotIn(
                "dependency-undici-native-candidate", codes(advanced_result)
            )
            advanced_candidate = next(
                item
                for item in advanced_result["surfaces"]["dependency_analysis"]["candidates"]
                if item["dependency"] == "undici"
            )
            self.assertFalse(advanced_candidate["candidate"])
            self.assertIn("agent", advanced_candidate["evidence"]["advanced_apis"])

    def test_pako_candidate_is_node_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            node_root = base / "node-pako"
            browser_root = base / "browser-pako"
            for root in (node_root, browser_root):
                root.mkdir()
                make_valid_skill(root)
                write(
                    root / "package.json",
                    json.dumps({"dependencies": {"pako": "^2.1.0"}}),
                )
            write(node_root / "bin/compress.mjs", 'import pako from "pako";\nexport { pako };\n')
            write(browser_root / "browser/compress.mjs", 'import pako from "pako";\nwindow.pako = pako;\n')

            node_result, _ = audit_skill(node_root)
            browser_result, _ = audit_skill(browser_root)

            self.assertIn("dependency-pako-native-candidate", codes(node_result, "warning"))
            self.assertNotIn("dependency-pako-native-candidate", codes(browser_result))

    def test_iconv_candidate_requires_transitive_utf8_only_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            utf8 = base / "utf8-skill"
            multi = base / "multi-encoding-skill"
            for root in (utf8, multi):
                root.mkdir()
                make_valid_skill(root, "# Input\n\n输入合同仅支持 UTF-8。\n")
                write(root / "package.json", json.dumps({"dependencies": {"wrapper": "1.0.0"}}))
                write(
                    root / "package-lock.json",
                    json.dumps(
                        {
                            "lockfileVersion": 3,
                            "packages": {
                                "": {"dependencies": {"wrapper": "1.0.0"}},
                                "node_modules/wrapper": {"version": "1.0.0"},
                                "node_modules/iconv-lite": {"version": "0.6.3"},
                            },
                        }
                    ),
                )
            write(multi / "scripts/decode.mjs", "const supported = ['gbk', 'utf-8'];\n")

            utf8_result, _ = audit_skill(utf8)
            multi_result, _ = audit_skill(multi)

            self.assertIn(
                "dependency-iconv-transitive-candidate", codes(utf8_result, "warning")
            )
            self.assertNotIn("dependency-iconv-transitive-candidate", codes(multi_result))

    def test_html_parser_overlap_requires_same_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            same = base / "same-parser-entry"
            separate = base / "separate-parser-entry"
            for root in (same, separate):
                root.mkdir()
                make_valid_skill(root)
                write(
                    root / "package.json",
                    json.dumps(
                        {"dependencies": {"parse5": "^7", "cheerio": "^1"}}
                    ),
                )
            write(same / "bin/parse.mjs", 'import parse5 from "parse5";\nimport * as cheerio from "cheerio";\n')
            write(separate / "bin/one.mjs", 'import parse5 from "parse5";\n')
            write(separate / "bin/two.mjs", 'import * as cheerio from "cheerio";\n')

            same_result, _ = audit_skill(same)
            separate_result, _ = audit_skill(separate)

            self.assertIn(
                "dependency-html-parser-overlap-candidate", codes(same_result, "warning")
            )
            self.assertNotIn(
                "dependency-html-parser-overlap-candidate", codes(separate_result)
            )

    def test_offline_contract_conflicts_with_font_download_in_build(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "offline-font-skill"
            root.mkdir()
            make_valid_skill(root, "# Offline\n\n本 Skill 完全离线运行和构建。\n")
            write(
                root / "scripts/build_fonts.mjs",
                'const font = await fetch("https://fonts.example.invalid/display.woff2");\n',
            )

            result, exit_code = audit_skill(root)

            self.assertEqual(exit_code, 1)
            self.assertIn("network-offline-contract-conflict", codes(result, "error"))
            event = result["surfaces"]["network_analysis"]["events"][0]
            self.assertEqual(event["phase"], "build-release")
            self.assertFalse(result["surfaces"]["network_analysis"]["executed_target_code"])

    def test_optional_verified_download_is_warning_not_offline_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "optional-download-skill"
            root.mkdir()
            make_valid_skill(root)
            write(
                root / "README.md",
                "# Optional\n\n首次可选下载字体；下载后校验 SHA256，失败时继续使用系统字体。\n",
            )
            write(
                root / "scripts/build_fonts.mjs",
                'import { createHash } from "node:crypto";\n'
                'const font = await fetch("https://fonts.example.invalid/display.woff2");\n'
                'createHash("sha256");\n',
            )

            result, exit_code = audit_skill(root)

            self.assertEqual(exit_code, 0)
            self.assertIn("network-optional-download", codes(result, "warning"))
            self.assertNotIn("network-offline-contract-conflict", codes(result))

    def test_pdf_lib_is_cost_fact_not_automatic_removal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "pdf-export-skill"
            root.mkdir()
            make_valid_skill(root)
            write(
                root / "package.json",
                json.dumps({"dependencies": {"pdf-lib": "^1.17.1"}}),
            )
            write(
                root / "bin/export.mjs",
                'import { PDFDocument } from "pdf-lib";\nexport async function merge() { return PDFDocument.create(); }\n',
            )

            result, exit_code = audit_skill(root)

            self.assertEqual(exit_code, 0)
            self.assertIn("dependency-pdf-lib-cost", codes(result, "info"))
            self.assertFalse(
                any(
                    item.get("dependency") == "pdf-lib" and item.get("candidate")
                    for item in result["surfaces"]["dependency_analysis"]["candidates"]
                )
            )

    def test_vendor_legacy_signals_are_aggregated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "vendor-noise-skill"
            root.mkdir()
            make_valid_skill(root)
            write(root / "bin/vendor-bundle.js", ("fallback legacy deprecated\n" * 120))

            result, _ = audit_skill(root)

            self.assertIn("legacy-generated-signals-suppressed", codes(result, "info"))
            self.assertNotIn("legacy-signal", codes(result, "info"))

    def test_release_source_only_development_files_are_expected_pruning(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source" / "trimmed-skill"
            release = Path(temp) / "release" / "trimmed-skill"
            source.mkdir(parents=True)
            release.mkdir(parents=True)
            for root in (source, release):
                make_valid_skill(root)
                add_release_envelope(root)
            write(source / "tests/test_internal.py", "def test_internal():\n    assert True\n")

            result, exit_code = audit_skill(release, source=source, surface="release")

            self.assertEqual(exit_code, 0)
            comparison = result["surfaces"]["authoritative_source"]["comparison"]
            self.assertEqual(comparison["status"], "expected-release-pruning")
            self.assertNotIn("source-install-drift", codes(result))
            self.assertIn("source-release-pruning-expected", codes(result, "info"))

    @unittest.skipUnless(hasattr(os, "symlink"), "platform does not support symlinks")
    def test_symlink_outside_root_is_blocking_and_not_read(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "safe-skill"
            root.mkdir()
            make_valid_skill(root)
            outside = base / "outside.md"
            write(outside, "外部秘密内容")
            os.symlink(str(outside), str(root / "outside-link.md"))

            result, exit_code = audit_skill(root)

            self.assertEqual(exit_code, 1)
            self.assertIn("symlink-outside", codes(result, "error"))
            self.assertNotIn("outside-link.md", result["files"]["text"])

    def test_token_estimation_is_stable_for_chinese_and_ascii(self) -> None:
        self.assertEqual(estimate_tokens("中文ab12"), 3)
        self.assertEqual(estimate_tokens("abcdefgh"), 2)

    def test_cli_exit_codes_and_json_output(self) -> None:
        script = SKILL_ROOT / "scripts/audit_skill.py"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "cli-skill"
            root.mkdir()
            make_valid_skill(root)
            ok = subprocess.run(
                [sys.executable, str(script), str(root), "--format", "json"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            release = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    str(root),
                    "--surface",
                    "release",
                    "--format",
                    "json",
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            missing = subprocess.run(
                [sys.executable, str(script), str(root / "does-not-exist")],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

            self.assertEqual(ok.returncode, 0)
            self.assertEqual(json.loads(ok.stdout)["summary"]["exit_code"], 0)
            self.assertEqual(release.returncode, 0)
            self.assertFalse(json.loads(release.stdout)["surfaces"]["release_envelope"]["readme"]["required"])
            self.assertEqual(missing.returncode, 2)


if __name__ == "__main__":
    unittest.main()
