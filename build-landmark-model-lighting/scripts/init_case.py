#!/usr/bin/env python3
"""Create a non-destructive landmark modeling case from the bundled contract."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = SKILL_DIR / "assets" / "case-template"
SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
ALLOWED_EFFECTS = ("auto", "color", "build", "edge-color")
ALLOWED_REVIEW_MODES = ("user-self-check", "agent-visual-review", "independent-review")


def parse_effects(value: str) -> list[str]:
    effects = [item.strip() for item in value.split(",") if item.strip()]
    if not effects:
        raise ValueError("At least one effect is required")
    unknown = sorted(set(effects) - set(ALLOWED_EFFECTS))
    if unknown:
        raise ValueError(f"Unknown effect(s): {', '.join(unknown)}")
    if "auto" in effects and len(effects) > 1:
        raise ValueError("auto cannot be combined with explicit effects")
    if len(effects) != len(set(effects)):
        raise ValueError("Duplicate effects are not allowed")
    return effects


def substitute(value: Any, replacements: dict[str, str], effects: list[str]) -> Any:
    if isinstance(value, dict):
        return {key: substitute(item, replacements, effects) for key, item in value.items()}
    if isinstance(value, list):
        if value == ["__EFFECT__"]:
            return effects
        return [substitute(item, replacements, effects) for item in value]
    if isinstance(value, str):
        if value == "__EFFECT__":
            return effects[0]
        for token, replacement in replacements.items():
            value = value.replace(token, replacement)
    return value


def initialize_case(
    root: Path,
    subject: str,
    slug: str,
    effects: list[str],
    review_mode: str = "user-self-check",
) -> list[Path]:
    root = root.resolve()
    if not subject.strip():
        raise ValueError("subject cannot be empty")
    if not SLUG_RE.fullmatch(slug):
        raise ValueError("slug must contain lowercase ASCII letters, digits, and interior hyphens")
    if review_mode not in ALLOWED_REVIEW_MODES:
        raise ValueError(f"Unknown review mode: {review_mode}")
    if not TEMPLATE_DIR.is_dir():
        raise FileNotFoundError(f"Template directory is missing: {TEMPLATE_DIR}")

    template_files = sorted(path for path in TEMPLATE_DIR.rglob("*") if path.is_file())
    destinations = [(path, root / path.relative_to(TEMPLATE_DIR)) for path in template_files]
    existing = [destination for _, destination in destinations if destination.exists()]
    if existing:
        joined = "\n".join(f"- {path}" for path in existing)
        raise FileExistsError(f"Refusing to overwrite managed case files:\n{joined}")

    replacements = {
        "__SUBJECT__": subject.strip(),
        "__SLUG__": slug,
        "__CREATED_AT__": datetime.now(timezone.utc).isoformat(),
        "__REVIEW_MODE__": review_mode,
    }
    created_files: list[Path] = []
    created_dirs: list[Path] = []

    try:
        root.mkdir(parents=True, exist_ok=True)
        for template, destination in destinations:
            if not destination.parent.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                created_dirs.append(destination.parent)
            if template.suffix == ".json":
                payload = json.loads(template.read_text(encoding="utf-8"))
                payload = substitute(payload, replacements, effects)
                destination.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            else:
                text = template.read_text(encoding="utf-8")
                for token, replacement in replacements.items():
                    text = text.replace(token, replacement)
                destination.write_text(text, encoding="utf-8")
            created_files.append(destination)

        for directory in (root / "model", root / "qa" / "captures"):
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                created_dirs.append(directory)
    except Exception:
        for path in reversed(created_files):
            path.unlink(missing_ok=True)
        for directory in sorted(set(created_dirs), key=lambda path: len(path.parts), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise

    return created_files


def run_self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="landmark-case-init-") as temp_dir:
        root = Path(temp_dir) / "museum-case"
        created = initialize_case(
            root,
            "测试美术馆",
            "test-museum",
            ["color", "build"],
            "user-self-check",
        )
        manifest = json.loads((root / "case-manifest.json").read_text(encoding="utf-8"))
        assert manifest["subject"] == "测试美术馆"
        assert manifest["selected_effects"] == ["color", "build"]
        assert manifest["review_policy"]["mode"] == "user-self-check"
        assert (root / "runtime" / "acceptance-contract.js").is_file()
        assert (root / "qa" / "captures").is_dir()
        assert len(created) >= 7
        try:
            initialize_case(root, "测试美术馆", "test-museum", ["color"])
        except FileExistsError:
            pass
        else:
            raise AssertionError("Second initialization should refuse to overwrite files")
    print(json.dumps({"status": "passed", "test": "init_case"}, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="Case root to create")
    parser.add_argument("--subject", help="Human-readable building or landmark name")
    parser.add_argument("--slug", help="Lowercase ASCII case slug")
    parser.add_argument(
        "--effect",
        default="auto",
        help="auto or a comma-separated subset of color,build,edge-color",
    )
    parser.add_argument(
        "--review-mode",
        choices=ALLOWED_REVIEW_MODES,
        default="user-self-check",
        help="user-self-check (default), agent-visual-review, or independent-review",
    )
    parser.add_argument("--self-test", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.self_test:
        run_self_test()
        return 0
    if args.root is None or args.subject is None or args.slug is None:
        print("--root, --subject, and --slug are required", file=sys.stderr)
        return 2
    try:
        effects = parse_effects(args.effect)
        created = initialize_case(args.root, args.subject, args.slug, effects, args.review_mode)
    except (ValueError, FileExistsError, FileNotFoundError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": "initialized",
                "root": str(args.root.resolve()),
                "subject": args.subject.strip(),
                "effects": effects,
                "review_mode": args.review_mode,
                "created_files": [str(path) for path in created],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
