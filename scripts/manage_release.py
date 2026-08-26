#!/usr/bin/env python3
"""Check, sync, and build the Wise Skills user release payload."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "skills-release.json"
SKIP_PARTS = {".git", "__pycache__"}
SKIP_NAMES = {".DS_Store"}
FORBIDDEN_PARTS = {".git", ".github", "test", "tests", "__pycache__"}
FORBIDDEN_NAMES = {
    ".DS_Store",
    ".gitignore",
    ".metadata.json",
    ".openclawmpignore",
    "SKILLHUB-RELEASE.md",
    "skill.json",
}
RELEASE_ROOT_FILES = (
    ("docs/release-README.md", "README.md"),
    ("LICENSE", "LICENSE"),
)


class ReleaseError(RuntimeError):
    pass


def load_manifest() -> Mapping[str, object]:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("skills"), list):
        raise ReleaseError("skills-release.json 格式无效")
    return data


def manifest_skills() -> List[Mapping[str, object]]:
    return list(load_manifest()["skills"])  # type: ignore[index]


def resolve_repo_path(value: str) -> Path:
    return (REPO_ROOT / value).resolve()


def iter_payload_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in SKIP_PARTS for part in relative.parts):
            continue
        if path.name in SKIP_NAMES or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise ReleaseError("发行载荷不允许软链：{}".format(path))
        if path.is_file():
            yield path


def selected_external_files(skill: Mapping[str, object]) -> Dict[str, Path]:
    source = resolve_repo_path(str(skill["external_source"]))
    if not source.is_dir():
        raise ReleaseError("外部权威源码不存在：{}".format(source))

    selected: Dict[str, Path] = {}
    for entry in skill.get("include", []):
        candidate = source / str(entry)
        if not candidate.exists():
            if str(entry) == "SKILL.md":
                raise ReleaseError("外部权威源码缺少 SKILL.md：{}".format(source))
            continue
        paths = [candidate] if candidate.is_file() else iter_payload_files(candidate)
        for path in paths:
            relative = path.relative_to(source).as_posix()
            selected[relative] = path
    return selected


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compare_external_mirror(skill: Mapping[str, object]) -> List[str]:
    mirror = resolve_repo_path(str(skill["path"]))
    expected = selected_external_files(skill)
    actual = {
        path.relative_to(mirror).as_posix(): path
        for path in iter_payload_files(mirror)
    } if mirror.is_dir() else {}

    errors: List[str] = []
    for relative in sorted(set(expected) - set(actual)):
        errors.append("镜像缺少 {}".format(relative))
    for relative in sorted(set(actual) - set(expected)):
        errors.append("镜像多出 {}".format(relative))
    for relative in sorted(set(expected) & set(actual)):
        if file_digest(expected[relative]) != file_digest(actual[relative]):
            errors.append("镜像内容漂移 {}".format(relative))
    return errors


def parse_skill_name(skill_file: Path) -> str:
    text = skill_file.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---", text, flags=re.DOTALL)
    if not match:
        raise ReleaseError("SKILL.md 缺少 frontmatter：{}".format(skill_file))
    name_match = re.search(r"^name:\s*([^\n#]+?)\s*$", match.group(1), flags=re.MULTILINE)
    if not name_match:
        raise ReleaseError("SKILL.md 缺少 name：{}".format(skill_file))
    return name_match.group(1).strip().strip("'\"")


def is_ignored_generated_file(path: Path, relative: Path) -> bool:
    return (
        "__pycache__" in relative.parts
        or path.name == ".DS_Store"
        or path.suffix == ".pyc"
    )


def check_package(skill: Mapping[str, object]) -> List[str]:
    name = str(skill["name"])
    root = resolve_repo_path(str(skill["path"]))
    errors: List[str] = []
    if not root.is_dir():
        return ["{}：发行目录不存在 {}".format(name, root)]
    skill_file = root / "SKILL.md"
    if not skill_file.is_file():
        errors.append("{}：缺少 SKILL.md".format(name))
    else:
        try:
            actual_name = parse_skill_name(skill_file)
            if actual_name != name:
                errors.append("{}：frontmatter name 为 {}".format(name, actual_name))
        except (OSError, UnicodeError, ReleaseError) as exc:
            errors.append(str(exc))

    license_file = root / "LICENSE"
    repository_license = REPO_ROOT / "LICENSE"
    readme_file = root / "README.md"
    if not readme_file.is_file():
        errors.append("{}：缺少 README.md".format(name))
    if not license_file.is_file():
        errors.append("{}：缺少 LICENSE".format(name))
    elif repository_license.is_file() and file_digest(license_file) != file_digest(repository_license):
        errors.append("{}：LICENSE 与仓库根 LICENSE 不一致".format(name))

    files = [path for path in sorted(root.rglob("*")) if path.is_file() or path.is_symlink()]
    for path in files:
        relative = path.relative_to(root)
        if is_ignored_generated_file(path, relative):
            continue
        if path.is_symlink():
            errors.append("{}：发行载荷不允许软链 {}".format(name, relative))
            continue
        if any(part in FORBIDDEN_PARTS for part in relative.parts):
            errors.append("{}：包含开发目录 {}".format(name, relative))
        if path.name in FORBIDDEN_NAMES or path.name.endswith(".bak") or path.suffix == ".pyc":
            errors.append("{}：包含非运行时文件 {}".format(name, relative))
        if path.suffix.lower() in {".md", ".py", ".sh", ".ps1", ".js", ".mjs", ".json", ".yaml", ".yml"}:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeError:
                continue
            if "/Users/wisewong/" in text:
                errors.append("{}：包含本机绝对路径 {}".format(name, relative))
    return errors


def check_all(require_external: bool = False) -> List[str]:
    skills = manifest_skills()
    names = [str(skill.get("name", "")) for skill in skills]
    paths = [str(skill.get("path", "")) for skill in skills]
    errors: List[str] = []
    if len(names) != len(set(names)):
        errors.append("skills-release.json 存在重复 name")
    if len(paths) != len(set(paths)):
        errors.append("skills-release.json 存在重复 path")
    for source_name, destination_name in RELEASE_ROOT_FILES:
        source = resolve_repo_path(source_name)
        if not source.is_file():
            errors.append("发行包根文件缺失：{} -> {}".format(source_name, destination_name))
    for skill in skills:
        errors.extend(check_package(skill))
        if skill.get("source") == "external-mirror":
            external_source = resolve_repo_path(str(skill["external_source"]))
            if not external_source.is_dir():
                if require_external:
                    errors.append("{}：外部权威源码不存在 {}".format(skill["name"], external_source))
                continue
            errors.extend(
                "{}：{}".format(skill["name"], item)
                for item in compare_external_mirror(skill)
            )
    return errors


def remove_empty_directories(root: Path) -> None:
    for path in sorted((item for item in root.rglob("*") if item.is_dir()), reverse=True):
        try:
            path.rmdir()
        except OSError:
            pass


def sync_external_mirrors() -> None:
    for skill in manifest_skills():
        if skill.get("source") != "external-mirror":
            continue
        name = str(skill["name"])
        mirror = resolve_repo_path(str(skill["path"]))
        expected = selected_external_files(skill)
        mirror.mkdir(parents=True, exist_ok=True)
        actual = {
            path.relative_to(mirror).as_posix(): path
            for path in iter_payload_files(mirror)
        }
        for relative, path in actual.items():
            if relative not in expected:
                path.unlink()
        remove_empty_directories(mirror)
        for relative, source in expected.items():
            destination = mirror / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists() or file_digest(source) != file_digest(destination):
                shutil.copy2(str(source), str(destination))
        print("已同步 {}：{} 个运行时文件".format(name, len(expected)))


def git_source_state(path: Path) -> Mapping[str, object]:
    result: Dict[str, object] = {"path": str(path)}
    try:
        commit = subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        dirty = bool(subprocess.check_output(
            ["git", "-C", str(path), "status", "--porcelain"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip())
        result.update({"commit": commit, "dirty": dirty})
    except (OSError, subprocess.CalledProcessError):
        result.update({"commit": None, "dirty": None})
    return result


def build_release(output: Path) -> None:
    output = output.resolve()
    protected = {Path("/").resolve(), Path.home().resolve(), REPO_ROOT.resolve()}
    if output in protected:
        raise ReleaseError("拒绝把发行目录设为系统目录、家目录或源码仓根目录")
    if output.exists() and any(output.iterdir()):
        raise ReleaseError("发行目录必须不存在或为空：{}".format(output))
    output.mkdir(parents=True, exist_ok=True)

    release_files: Dict[str, str] = {}
    source_states: Dict[str, Mapping[str, object]] = {}
    for source_name, destination_name in RELEASE_ROOT_FILES:
        source = resolve_repo_path(source_name)
        destination = output / destination_name
        shutil.copy2(str(source), str(destination))
        release_files[destination_name] = file_digest(destination)
    for skill in manifest_skills():
        name = str(skill["name"])
        source = resolve_repo_path(str(skill["path"]))
        destination = output / name
        shutil.copytree(
            str(source),
            str(destination),
            ignore=shutil.ignore_patterns(".DS_Store", "__pycache__", "*.pyc"),
        )
        for path in iter_payload_files(destination):
            relative = path.relative_to(output).as_posix()
            release_files[relative] = file_digest(path)
        if skill.get("source") == "external-mirror":
            source_states[name] = git_source_state(resolve_repo_path(str(skill["external_source"])))

    release_manifest = {
        "schema_version": 1,
        "skills": [str(skill["name"]) for skill in manifest_skills()],
        "external_sources": source_states,
        "sha256": dict(sorted(release_files.items())),
    }
    (output / "_release-manifest.json").write_text(
        json.dumps(release_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("发行包已生成：{}（{} 个 Skill，{} 个文件）".format(output, len(manifest_skills()), len(release_files)))


def main(argv: Sequence[str] = ()) -> int:
    parser = argparse.ArgumentParser(description="管理 Wise Skills 发行载荷")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser("check", help="检查发行边界和外部镜像漂移")
    check_parser.add_argument("--require-external", action="store_true", help="要求外部权威源码存在并参与比较")
    subparsers.add_parser("sync", help="从外部权威源码更新受管发行镜像")
    build_parser = subparsers.add_parser("build", help="生成干净的用户发行包")
    build_parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(list(argv) if argv else None)

    try:
        if args.command == "sync":
            sync_external_mirrors()
        require_external = args.command == "sync" or getattr(args, "require_external", False)
        errors = check_all(require_external=require_external)
        if errors:
            print("FAIL release contract")
            for error in errors:
                print("- {}".format(error))
            return 1
        print("PASS release contract: {} 个 Skill".format(len(manifest_skills())))
        if args.command == "build":
            build_release(args.output)
        return 0
    except (OSError, ReleaseError, ValueError) as exc:
        print("FAIL release contract: {}".format(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
