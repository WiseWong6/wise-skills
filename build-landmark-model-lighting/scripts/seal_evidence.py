#!/usr/bin/env python3
"""Seal one fresh landmark validation run to the current asset and runtime bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


FIXED_ARTIFACTS = {
    "case-manifest": "case-manifest.json",
    "model-brief": "brief/model-brief.json",
    "reference-bundle": "references/reference-bundle.json",
    "direction-set": "direction/direction-set.json",
    "comparison-report": "qa/comparison-report.json",
}
REPORT_KEYS = ("khronos_report", "loader_report", "browser_report")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"{label}: missing file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{label}: invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label}: root must be an object")
    return value


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def git_context(root: Path) -> tuple[Path | None, str | None, list[str]]:
    probe = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
        check=False,
    )
    if probe.returncode != 0:
        return None, None, []
    repository = Path(probe.stdout.strip()).resolve()
    head_probe = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    head = head_probe.stdout.strip() if head_probe.returncode == 0 else None
    relative_case = root.resolve().relative_to(repository)
    status_probe = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            str(relative_case),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    dirty = []
    if status_probe.returncode == 0:
        dirty = [line[3:] for line in status_probe.stdout.splitlines() if len(line) >= 4]
    return repository, head, dirty


def resolve_declared_path(
    case_root: Path,
    declared: Any,
    label: str,
    repository_root: Path | None,
) -> Path:
    if not isinstance(declared, str) or not declared.strip():
        raise ValueError(f"{label}: path is required")
    candidate = (case_root / declared).resolve()
    allowed_root = repository_root or case_root
    try:
        candidate.relative_to(allowed_root)
    except ValueError as error:
        raise ValueError(f"{label}: path escapes the allowed root: {declared}") from error
    if not candidate.is_file():
        raise ValueError(f"{label}: file does not exist: {declared}")
    return candidate


def entry_path(container: Any, label: str) -> str:
    if not isinstance(container, dict):
        raise ValueError(f"{label}: schema 3 object with path/sha256 is required")
    path = container.get("path")
    if not isinstance(path, str) or not path:
        raise ValueError(f"{label}.path is required")
    return path


def parse_utc_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label}: UTC timestamp is required")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError(f"{label}: invalid ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{label}: timezone is required")
    return parsed.astimezone(timezone.utc)


def report_timestamp(report: dict[str, Any], label: str) -> datetime:
    keys = (
        ("validatedAt",),
        ("checked_at",),
        ("checkedAt",),
        ("completed_at",),
        ("evidence", "completed_at"),
    )
    for key_path in keys:
        value: Any = report
        for key in key_path:
            value = value.get(key) if isinstance(value, dict) else None
        if value:
            return parse_utc_timestamp(value, f"{label}.{'.'.join(key_path)}")
    raise ValueError(f"{label}: validation completion timestamp is required")


def report_asset_hash(report: dict[str, Any]) -> str | None:
    for key in ("asset_sha256", "sha256", "expectedSha", "expected_sha256"):
        value = report.get(key)
        if isinstance(value, str) and len(value) == 64:
            return value.lower()
    evidence = report.get("_evidence")
    if isinstance(evidence, dict):
        value = evidence.get("asset_sha256")
        if isinstance(value, str) and len(value) == 64:
            return value.lower()
    return None


def assert_fresh(timestamp: datetime, now: datetime, max_age_hours: float, label: str) -> None:
    if timestamp > now + timedelta(minutes=5):
        raise ValueError(f"{label}: timestamp is in the future")
    if now - timestamp > timedelta(hours=max_age_hours):
        raise ValueError(f"{label}: report is older than {max_age_hours:g} hours")


def artifact(role: str, declared_path: str, resolved: Path) -> dict[str, Any]:
    return {
        "role": role,
        "path": declared_path,
        "sha256": sha256_file(resolved),
        "bytes": resolved.stat().st_size,
    }


def seal_case(root: Path, max_age_hours: float = 24.0) -> dict[str, Any]:
    if max_age_hours <= 0:
        raise ValueError("max_age_hours must be positive")
    root = root.resolve()
    delivery_path = root / "reports" / "delivery-manifest.json"
    delivery = read_json(delivery_path, "delivery")
    if delivery.get("schema_version") != 3:
        raise ValueError("delivery: schema_version 3 is required; migrate the case first")

    repository_root, git_head, dirty_paths = git_context(root)
    asset = delivery.get("asset")
    if not isinstance(asset, dict):
        raise ValueError("delivery.asset must be an object")
    asset_declared = asset.get("path")
    asset_path = resolve_declared_path(root, asset_declared, "delivery.asset", repository_root)
    asset_hash = sha256_file(asset_path)

    source_declared = entry_path(delivery.get("source_entry"), "delivery.source_entry")
    source_path = resolve_declared_path(root, source_declared, "delivery.source_entry", repository_root)
    runtime = delivery.get("runtime")
    if not isinstance(runtime, dict):
        raise ValueError("delivery.runtime must be an object")
    runtime_declared = entry_path(runtime.get("entry"), "delivery.runtime.entry")
    runtime_path = resolve_declared_path(root, runtime_declared, "delivery.runtime.entry", repository_root)

    validation = delivery.get("validation")
    if not isinstance(validation, dict):
        raise ValueError("delivery.validation must be an object")
    report_records: dict[str, tuple[str, Path, dict[str, Any]]] = {}
    now = datetime.now(timezone.utc)
    run_id = str(uuid.uuid4())
    sealed_at = now.isoformat().replace("+00:00", "Z")

    for key in REPORT_KEYS:
        declared = entry_path(validation.get(key), f"delivery.validation.{key}")
        path = resolve_declared_path(root, declared, f"delivery.validation.{key}", repository_root)
        report = read_json(path, key)
        if report.get("status") not in (None, "passed"):
            raise ValueError(f"{key}: status must be passed")
        timestamp = report_timestamp(report, key)
        assert_fresh(timestamp, now, max_age_hours, key)
        if key == "khronos_report":
            issues = report.get("issues")
            if not isinstance(issues, dict) or issues.get("numErrors") != 0:
                raise ValueError("khronos_report: issues.numErrors must be zero")
            if report.get("mimeType") != "model/gltf-binary":
                raise ValueError("khronos_report: mimeType must be model/gltf-binary")
            if Path(str(report.get("uri", ""))).name != asset_path.name:
                raise ValueError("khronos_report: uri must name the current GLB")
            if not isinstance(report.get("validatorVersion"), str):
                raise ValueError("khronos_report: validatorVersion is required")
        else:
            if report.get("status") != "passed":
                raise ValueError(f"{key}: status must be passed")
            if report_asset_hash(report) != asset_hash:
                raise ValueError(f"{key}: asset SHA-256 must match the current GLB")
        if key == "browser_report":
            http_hash = report.get("http_asset_sha256")
            if not isinstance(http_hash, str) or http_hash.lower() != asset_hash:
                raise ValueError("browser_report: http_asset_sha256 must match the current GLB")
        report_records[key] = (declared, path, report)

    drivers = validation.get("drivers")
    if not isinstance(drivers, list) or not drivers:
        raise ValueError("delivery.validation.drivers: at least one validation driver is required")
    driver_records: list[tuple[str, Path]] = []
    for index, driver in enumerate(drivers):
        declared = entry_path(driver, f"delivery.validation.drivers[{index}]")
        path = resolve_declared_path(
            root,
            declared,
            f"delivery.validation.drivers[{index}]",
            repository_root,
        )
        driver_records.append((declared, path))

    for key, (declared, path, report) in report_records.items():
        report["_evidence"] = {
            "run_id": run_id,
            "sealed_at": sealed_at,
            "asset_sha256": asset_hash,
        }
        write_json_atomic(path, report)
        validation[key] = {
            "path": declared,
            "sha256": sha256_file(path),
        }

    comparison_path = root / FIXED_ARTIFACTS["comparison-report"]
    comparison = read_json(comparison_path, "comparison-report")
    comparison["asset_sha256"] = asset_hash
    comparison["_evidence"] = {
        "run_id": run_id,
        "sealed_at": sealed_at,
        "asset_sha256": asset_hash,
    }
    write_json_atomic(comparison_path, comparison)

    delivery["asset"]["sha256"] = asset_hash
    delivery["asset"]["bytes"] = asset_path.stat().st_size
    delivery["source_entry"] = {"path": source_declared, "sha256": sha256_file(source_path)}
    runtime["entry"] = {"path": runtime_declared, "sha256": sha256_file(runtime_path)}
    validation["drivers"] = [
        {"path": declared, "sha256": sha256_file(path)} for declared, path in driver_records
    ]

    artifacts = [artifact("glb", str(asset_declared), asset_path)]
    artifacts.append(artifact("model-source", source_declared, source_path))
    artifacts.append(artifact("runtime-entry", runtime_declared, runtime_path))
    for role, declared in FIXED_ARTIFACTS.items():
        path = resolve_declared_path(root, declared, role, repository_root)
        artifacts.append(artifact(role, declared, path))
    for key, (declared, path, _) in report_records.items():
        artifacts.append(artifact(key.replace("_report", "-report"), declared, path))
    for index, (declared, path) in enumerate(driver_records):
        artifacts.append(artifact(f"validation-driver:{index}", declared, path))

    seal = {
        "schema_version": 1,
        "run_id": run_id,
        "sealed_at": sealed_at,
        "max_report_age_hours": max_age_hours,
        "asset": {
            "path": str(asset_declared),
            "sha256": asset_hash,
            "bytes": asset_path.stat().st_size,
        },
        "artifacts": artifacts,
        "git": {
            "repository_root": str(repository_root) if repository_root else None,
            "head": git_head,
            "case_dirty_paths": dirty_paths,
        },
    }
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    seal_relative = f"reports/evidence-seals/{stamp}-{run_id}.json"
    seal_path = root / seal_relative
    write_json_atomic(seal_path, seal)
    delivery["evidence_seal"] = {
        "path": seal_relative,
        "sha256": sha256_file(seal_path),
    }
    write_json_atomic(delivery_path, delivery)
    return {
        "status": "sealed",
        "root": str(root),
        "run_id": run_id,
        "asset_sha256": asset_hash,
        "seal_path": str(seal_path),
        "seal_sha256": sha256_file(seal_path),
        "git_head": git_head,
        "case_dirty_paths": dirty_paths,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Landmark case root")
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=24.0,
        help="Maximum age of validation reports before sealing (default: 24)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = seal_case(args.root, args.max_age_hours)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
