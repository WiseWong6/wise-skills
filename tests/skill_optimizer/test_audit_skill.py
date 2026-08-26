import json
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
            "系统性诊断与反补丁门禁",
            "问题合同",
            "公共根因与影响面",
            "不得称为“系统性修复”",
            "修改前失败、修改后通过",
            "临时缓解不能作为完整修复关闭",
            "先拆角色、载体和成本",
            "在 Git 中保留",
            "进入发行包",
            "用户必须安装",
            "macOS/Windows × Agent × 入口",
            "平台/Agent 未实测",
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

    def test_duplicate_paragraph_and_extra_doc_are_reported(self) -> None:
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
            self.assertIn("extra-doc", codes(result, "warning"))

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

    def test_binary_and_oversized_files_are_skipped(self) -> None:
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
            self.assertTrue(any("超过" in reason for reason in reasons))

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
            missing = subprocess.run(
                [sys.executable, str(script), str(root / "does-not-exist")],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

            self.assertEqual(ok.returncode, 0)
            self.assertEqual(json.loads(ok.stdout)["summary"]["exit_code"], 0)
            self.assertEqual(missing.returncode, 2)


if __name__ == "__main__":
    unittest.main()
