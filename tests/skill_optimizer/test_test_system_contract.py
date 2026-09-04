import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Tuple


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPOSITORY_ROOT / "skill-optimizer"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from audit_skill import audit_skill, format_text  # noqa: E402


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_skill(root: Path, name: str = "demo-skill") -> None:
    write(
        root / "SKILL.md",
        "---\nname: {}\ndescription: 用于验证测试体系合同的演示 Skill。\n---\n\n"
        "# Demo\n\n完成一项明确任务。\n".format(name),
    )
    write(
        root / "agents/openai.yaml",
        "interface:\n"
        '  display_name: "Demo Skill"\n'
        '  short_description: "验证源仓测试体系声明和执行边界是否完整"\n'
        '  default_prompt: "使用 $demo-skill 完成这项任务。"\n',
    )


def base_contract(
    skill: str = "demo-skill", target_root: str = ".", test_file: str = "tests/test_demo.py"
) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "skill": skill,
        "target_root": target_root,
        "inventory_patterns": ["tests/test_*.py"],
        "mechanisms": [
            {
                "id": "contract-validation",
                "rule_owner": "SKILL.md",
                "case_model": "none",
                "case_sources": [],
            }
        ],
        "runners": [
            {
                "id": "shared-unit-runner",
                "boundary": "unit",
                "mode": "shared",
                "command": "python3 -m unittest discover -s tests -p 'test_*.py'",
                "files": [test_file],
                "covers": ["contract-validation"],
            }
        ],
        "exclusions": [],
    }


def prepare_non_git(
    base: Path, contract: Dict[str, Any]
) -> Tuple[Path, Path]:
    root = base / "demo-skill"
    root.mkdir()
    make_skill(root)
    write(root / "tests/test_demo.py", "def test_demo():\n    assert True\n")
    contract_path = root / "tests/test-system.json"
    write(contract_path, json.dumps(contract, ensure_ascii=False, indent=2))
    return root, contract_path


def finding_codes(result: Dict[str, Any]) -> set:
    return {item["code"] for item in result["findings"]}


class TestSystemContractTests(unittest.TestCase):
    def test_source_without_test_assets_is_not_applicable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "demo-skill"
            root.mkdir()
            make_skill(root)

            result, exit_code = audit_skill(root, surface="source")

            self.assertEqual(exit_code, 0)
            self.assertEqual(result["test_system"]["status"], "not-applicable")
            self.assertNotIn("test-system-contract-missing", finding_codes(result))

    def test_missing_contract_reports_review_without_semantic_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "demo-skill"
            root.mkdir()
            make_skill(root)
            write(root / "tests/test_demo.py", "def test_demo():\n    assert True\n")

            result, exit_code = audit_skill(root, surface="source")

            self.assertEqual(exit_code, 0)
            self.assertEqual(result["test_system"]["status"], "review")
            self.assertEqual(result["test_system"]["contract"]["status"], "missing")
            self.assertIn("test-system-contract-missing", finding_codes(result))
            self.assertFalse(result["test_system"]["unregistered_files"])
            self.assertIn("不对文件进行语义聚类", result["test_system"]["limitations"][0])

    def test_valid_contract_passes_and_is_visible_in_structure_and_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, _ = prepare_non_git(Path(temp), base_contract())

            result, exit_code = audit_skill(root, surface="source")

            self.assertEqual(exit_code, 0)
            self.assertEqual(result["test_system"]["status"], "pass")
            self.assertEqual(result["test_system"]["inventory"]["matched_count"], 1)
            check = next(
                item
                for item in result["structure"]["checks"]
                if item["id"] == "test-systemization"
            )
            self.assertEqual(check["status"], "pass")
            self.assertIn("测试体系：pass（合同=valid", format_text(result))

    def test_all_case_models_have_explicit_ownership_rules(self) -> None:
        for case_model in ("none", "inline", "external"):
            with self.subTest(case_model=case_model), tempfile.TemporaryDirectory() as temp:
                contract = base_contract()
                mechanism = contract["mechanisms"][0]
                mechanism["case_model"] = case_model
                if case_model == "inline":
                    mechanism["rationale"] = "各场景验证不同结构合同，不能共享同一数据表。"
                elif case_model == "external":
                    mechanism["case_sources"] = ["tests/cases.json"]
                root, _ = prepare_non_git(Path(temp), contract)
                if case_model == "external":
                    write(root / "tests/cases.json", "[]\n")

                result, exit_code = audit_skill(root, surface="source")

                self.assertEqual(exit_code, 0)
                self.assertEqual(result["test_system"]["status"], "pass")

    def test_contract_violations_are_deterministic_blockers(self) -> None:
        scenarios = (
            ("missing-owner", "test-system-rule-owner-missing"),
            ("unregistered-file", "test-system-unregistered-file"),
            ("duplicate-boundary", "test-system-duplicate-shared-boundary"),
            ("inline-without-rationale", "test-system-inline-rationale"),
            ("executable-external-cases", "test-system-external-case-executable"),
            ("standalone-without-governance", "test-system-standalone-governance"),
            ("path-escape", "test-system-path-escape"),
        )
        for scenario, expected_code in scenarios:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temp:
                contract = base_contract()
                root, contract_path = prepare_non_git(Path(temp), contract)
                if scenario == "missing-owner":
                    contract["mechanisms"][0]["rule_owner"] = "references/missing.md"
                elif scenario == "unregistered-file":
                    write(root / "tests/test_extra.py", "def test_extra():\n    assert True\n")
                elif scenario == "duplicate-boundary":
                    write(root / "tests/test_extra.py", "def test_extra():\n    assert True\n")
                    second = copy.deepcopy(contract["runners"][0])
                    second["id"] = "second-shared-runner"
                    second["files"] = ["tests/test_extra.py"]
                    contract["runners"].append(second)
                elif scenario == "inline-without-rationale":
                    contract["mechanisms"][0]["case_model"] = "inline"
                elif scenario == "executable-external-cases":
                    write(root / "tests/cases.py", "CASES = []\n")
                    contract["mechanisms"][0]["case_model"] = "external"
                    contract["mechanisms"][0]["case_sources"] = ["tests/cases.py"]
                elif scenario == "standalone-without-governance":
                    contract["runners"][0]["mode"] = "standalone"
                elif scenario == "path-escape":
                    write(Path(temp) / "outside.py", "VALUE = True\n")
                    contract["runners"][0]["files"] = ["../outside.py"]
                write(contract_path, json.dumps(contract, ensure_ascii=False, indent=2))

                result, exit_code = audit_skill(root, surface="source")

                self.assertEqual(exit_code, 1)
                self.assertEqual(result["test_system"]["status"], "fail")
                self.assertIn(expected_code, finding_codes(result))

    def test_standalone_runner_with_governance_is_not_duplicate_shared_runner(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            contract = base_contract()
            root, contract_path = prepare_non_git(Path(temp), contract)
            write(root / "tests/test_external.py", "def test_external():\n    assert True\n")
            contract["runners"].append(
                {
                    "id": "external-tool-runner",
                    "boundary": "unit",
                    "mode": "standalone",
                    "command": "external-check --verify",
                    "files": ["tests/test_external.py"],
                    "covers": ["contract-validation"],
                    "owner": "release-maintainer",
                    "reason": "依赖无法嵌入共享进程的外部工具。",
                    "exit_condition": "外部工具提供可导入的标准库接口。",
                }
            )
            write(contract_path, json.dumps(contract, ensure_ascii=False, indent=2))

            result, exit_code = audit_skill(root, surface="source")

            self.assertEqual(exit_code, 0)
            self.assertEqual(result["test_system"]["status"], "pass")
            self.assertEqual(len(result["test_system"]["runners"]), 2)

    def test_declared_exclusion_keeps_non_runner_file_visible(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            contract = base_contract()
            root, contract_path = prepare_non_git(Path(temp), contract)
            write(root / "tests/test_fixture.py", "FIXTURE = True\n")
            contract["exclusions"].append(
                {
                    "file": "tests/test_fixture.py",
                    "reason": "静态 fixture 数据，不是独立测试入口。",
                    "owner": "test-maintainer",
                    "review_when": "fixture 开始执行命令或启动进程时",
                }
            )
            write(contract_path, json.dumps(contract, ensure_ascii=False, indent=2))

            result, exit_code = audit_skill(root, surface="source")

            self.assertEqual(exit_code, 0)
            self.assertEqual(result["test_system"]["status"], "pass")
            self.assertEqual(
                result["test_system"]["exclusions"][0]["file"],
                "tests/test_fixture.py",
            )

    def test_automatic_discovery_rejects_two_rule_owners(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, _ = prepare_non_git(Path(temp), base_contract())
            second = root / "tests/demo-skill/test-system.json"
            write(second, json.dumps(base_contract(), ensure_ascii=False, indent=2))

            result, exit_code = audit_skill(root, surface="source")

            self.assertEqual(exit_code, 1)
            self.assertEqual(result["test_system"]["status"], "fail")
            self.assertIn("test-system-contract-ambiguous", finding_codes(result))

    def test_contract_discovery_cannot_escape_or_use_ignored_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "demo-skill"
            root.mkdir()
            make_skill(root)
            outside = Path(temp) / "outside.json"
            write(outside, json.dumps(base_contract(), ensure_ascii=False, indent=2))

            escaped, escaped_exit = audit_skill(
                root,
                surface="source",
                test_system_contract=Path("../outside.json"),
            )

            self.assertEqual(escaped_exit, 1)
            self.assertIn(
                "test-system-contract-path-escape", finding_codes(escaped)
            )

        with tempfile.TemporaryDirectory() as temp:
            root, contract_path = prepare_non_git(Path(temp), base_contract())
            write(root / ".gitignore", "tests/test-system.json\n")
            subprocess.run(
                ["git", "init", str(root)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["git", "-C", str(root), "add", "SKILL.md", "agents", "tests/test_demo.py"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.assertTrue(contract_path.is_file())

            ignored, ignored_exit = audit_skill(root, surface="source")

            self.assertEqual(ignored_exit, 1)
            self.assertIn("test-system-contract-ignored", finding_codes(ignored))

    def test_release_and_installed_surfaces_skip_source_test_contract(self) -> None:
        for surface in ("release", "installed"):
            with self.subTest(surface=surface), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / "demo-skill"
                root.mkdir()
                make_skill(root)
                write(root / "tests/test_demo.py", "def test_demo():\n    assert True\n")

                result, exit_code = audit_skill(root, surface=surface)

                self.assertEqual(exit_code, 0)
                self.assertEqual(result["test_system"]["status"], "not-applicable")
                self.assertNotIn("test-system-contract-missing", finding_codes(result))

    def test_git_worktree_inventory_includes_nonignored_untracked_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repository = Path(temp) / "repository"
            root = repository / "demo-skill"
            root.mkdir(parents=True)
            make_skill(root)
            write(repository / "tests/demo_skill/test_registered.py", "VALUE = True\n")
            contract = base_contract(
                target_root="demo-skill",
                test_file="tests/demo_skill/test_registered.py",
            )
            contract["mechanisms"][0]["rule_owner"] = "demo-skill/SKILL.md"
            contract["inventory_patterns"] = ["tests/demo_skill/test_*.py"]
            contract_path = repository / "tests/demo_skill/test-system.json"
            write(contract_path, json.dumps(contract, ensure_ascii=False, indent=2))
            subprocess.run(
                ["git", "init", str(repository)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["git", "-C", str(repository), "add", "."],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            write(repository / "tests/demo_skill/test_untracked.py", "VALUE = True\n")

            result, exit_code = audit_skill(root, surface="source")

            self.assertEqual(exit_code, 1)
            self.assertIn("test-system-unregistered-file", finding_codes(result))
            self.assertEqual(
                result["test_system"]["inventory"]["untracked_matched_count"], 1
            )

    def test_cli_accepts_explicit_contract_relative_to_repository_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            contract = base_contract()
            root, auto_path = prepare_non_git(Path(temp), contract)
            explicit = root / "contracts/test-system.json"
            write(explicit, auto_path.read_text(encoding="utf-8"))
            auto_path.unlink()
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SKILL_ROOT / "scripts/audit_skill.py"),
                    str(root),
                    "--surface",
                    "source",
                    "--test-system-contract",
                    "contracts/test-system.json",
                    "--format",
                    "json",
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual(result["test_system"]["contract"]["discovery"], "explicit")
            self.assertEqual(result["test_system"]["status"], "pass")


if __name__ == "__main__":
    unittest.main()
