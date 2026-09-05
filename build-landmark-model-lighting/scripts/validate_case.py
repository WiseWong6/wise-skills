#!/usr/bin/env python3
"""Validate evidence, assets, runtime reports, and double-source comparisons."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import struct
import subprocess
import sys
import tempfile
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VIEWS = {
    "front",
    "back",
    "left",
    "right",
    "roof",
    "ground-contact",
    "three-quarter",
}
EFFECTS = {"color", "build", "edge-color"}
REVIEW_MODES = {"user-self-check", "agent-visual-review", "independent-review"}
PAUSE_FREEZES = {
    "effect-progress",
    "auto-rotate",
    "damping",
    "shader-time",
    "pulse",
    "local-lights",
}
AUTHORITATIVE_TYPES = {
    "owner",
    "architect",
    "engineer",
    "government",
    "official",
    "archive",
    "drawing",
}
REQUIRED_DOCUMENTS = {
    "manifest": "case-manifest.json",
    "brief": "brief/model-brief.json",
    "references": "references/reference-bundle.json",
    "directions": "direction/direction-set.json",
    "comparisons": "qa/comparison-report.json",
    "delivery": "reports/delivery-manifest.json",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path, errors: list[str], label: str) -> dict[str, Any]:
    if not path.is_file():
        errors.append(f"{label}: missing {path}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"{label}: invalid JSON: {error}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label}: root must be a JSON object")
        return {}
    return payload


def repository_root(root: Path) -> Path | None:
    probe = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
        check=False,
    )
    if probe.returncode != 0:
        return None
    return Path(probe.stdout.strip()).resolve()


def resolve_case_path(
    root: Path,
    relative: Any,
    errors: list[str],
    label: str,
    allowed_root: Path | None = None,
) -> Path | None:
    if not isinstance(relative, str) or not relative.strip():
        errors.append(f"{label}: path is required")
        return None
    root = root.resolve()
    candidate = (root / relative).resolve()
    boundary = (allowed_root or root).resolve()
    try:
        candidate.relative_to(boundary)
    except ValueError:
        errors.append(f"{label}: path escapes case root: {relative}")
        return None
    if not candidate.is_file():
        errors.append(f"{label}: file does not exist: {relative}")
        return None
    return candidate


def check_hash(path: Path | None, expected: Any, errors: list[str], label: str) -> None:
    if path is None:
        return
    if not isinstance(expected, str) or len(expected) != 64:
        errors.append(f"{label}: a SHA-256 digest is required")
        return
    actual = sha256_file(path)
    if actual.lower() != expected.lower():
        errors.append(f"{label}: SHA-256 mismatch")


def resolve_bound_entry(
    root: Path,
    value: Any,
    errors: list[str],
    label: str,
    *,
    strict: bool,
    allow_legacy: bool,
    allowed_root: Path | None = None,
) -> tuple[str | None, Path | None]:
    if isinstance(value, dict):
        declared = value.get("path")
        path = resolve_case_path(root, declared, errors, f"{label}.path", allowed_root)
        check_hash(path, value.get("sha256"), errors, f"{label}.sha256")
        return declared if isinstance(declared, str) else None, path
    if isinstance(value, str):
        path = resolve_case_path(root, value, errors, label, allowed_root)
        if strict and not allow_legacy:
            errors.append(f"{label}: schema 3 path/sha256 object is required")
        return value, path
    errors.append(f"{label}: path binding is required")
    return None, None


def validate_glb(path: Path | None, errors: list[str], label: str) -> None:
    if path is None:
        return
    try:
        data = path.read_bytes()
    except OSError as error:
        errors.append(f"{label}: cannot read GLB: {error}")
        return
    if len(data) < 20:
        errors.append(f"{label}: GLB is shorter than the header and first chunk")
        return
    magic, version, declared_length = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67:
        errors.append(f"{label}: invalid GLB magic; expected glTF")
    if version != 2:
        errors.append(f"{label}: GLB container version must be 2")
    if declared_length != len(data):
        errors.append(f"{label}: declared GLB length does not match file bytes")
    chunk_length, chunk_type = struct.unpack_from("<II", data, 12)
    if chunk_type != 0x4E4F534A:
        errors.append(f"{label}: first GLB chunk must be JSON")
        return
    chunk_end = 20 + chunk_length
    if chunk_end > len(data):
        errors.append(f"{label}: JSON chunk exceeds GLB length")
        return
    try:
        document = json.loads(data[20:chunk_end].decode("utf-8").rstrip(" \t\r\n\x00"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        errors.append(f"{label}: invalid GLB JSON chunk: {error}")
        return
    asset = document.get("asset") if isinstance(document, dict) else None
    if not isinstance(asset, dict) or asset.get("version") != "2.0":
        errors.append(f"{label}: GLB JSON asset.version must be 2.0")


def image_dimensions(path: Path) -> tuple[str, int, int] | None:
    data = path.read_bytes()
    if len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n"):
        width, height = struct.unpack(">II", data[16:24])
        return "png", width, height
    if len(data) >= 30 and data.startswith((b"RIFF",)) and data[8:12] == b"WEBP":
        kind = data[12:16]
        if kind == b"VP8X" and len(data) >= 30:
            width = 1 + int.from_bytes(data[24:27], "little")
            height = 1 + int.from_bytes(data[27:30], "little")
            return "webp", width, height
    if len(data) >= 4 and data.startswith(b"\xff\xd8"):
        offset = 2
        while offset + 9 <= len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            offset += 2
            if marker in (0xD8, 0xD9):
                continue
            if offset + 2 > len(data):
                break
            segment_length = int.from_bytes(data[offset : offset + 2], "big")
            if segment_length < 2 or offset + segment_length > len(data):
                break
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                height = int.from_bytes(data[offset + 3 : offset + 5], "big")
                width = int.from_bytes(data[offset + 5 : offset + 7], "big")
                return "jpeg", width, height
            offset += segment_length
    return None


def validate_image(path: Path | None, errors: list[str], label: str) -> None:
    if path is None:
        return
    try:
        detected = image_dimensions(path)
    except OSError as error:
        errors.append(f"{label}: cannot read image: {error}")
        return
    if detected is None:
        errors.append(f"{label}: file is not a recognized PNG, JPEG, or WebP image")
        return
    _, width, height = detected
    if width <= 0 or height <= 0:
        errors.append(f"{label}: image dimensions must be positive")


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


def write_test_png(path: Path, width: int = 2, height: int = 2) -> None:
    signature = b"\x89PNG\r\n\x1a\n"

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    rows = b"".join(b"\x00" + b"\xff\xff\xff\xff" * width for _ in range(height))
    path.write_bytes(
        signature
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def write_test_glb(path: Path) -> None:
    document = json.dumps(
        {"asset": {"version": "2.0", "generator": "landmark-validator-self-test"}, "scene": 0, "scenes": [{}]},
        separators=(",", ":"),
    ).encode("utf-8")
    document += b" " * ((4 - len(document) % 4) % 4)
    total_length = 12 + 8 + len(document)
    path.write_bytes(
        struct.pack("<III", 0x46546C67, 2, total_length)
        + struct.pack("<II", len(document), 0x4E4F534A)
        + document
    )


def nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def validator_error_count(report: dict[str, Any]) -> int | None:
    issues = report.get("issues")
    if isinstance(issues, dict) and isinstance(issues.get("numErrors"), int):
        return issues["numErrors"]
    if isinstance(report.get("numErrors"), int):
        return report["numErrors"]
    errors = report.get("errors")
    if isinstance(errors, int):
        return errors
    if isinstance(errors, list):
        return len(errors)
    return None


def validate_case(
    root: Path,
    strict: bool = False,
    allow_legacy_evidence: bool = False,
    require_visual_approval: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    repo_root = repository_root(root)
    errors: list[str] = []
    warnings: list[str] = []
    documents = {
        key: load_json(root / relative, errors, key)
        for key, relative in REQUIRED_DOCUMENTS.items()
    }
    manifest = documents["manifest"]
    brief = documents["brief"]
    refs = documents["references"]
    directions = documents["directions"]
    comparisons = documents["comparisons"]
    delivery = documents["delivery"]

    review_policy = manifest.get("review_policy")
    if strict:
        if manifest.get("schema_version") != 2:
            if allow_legacy_evidence and manifest.get("schema_version") == 1:
                warnings.append("legacy evidence: case manifest schema 1 is not sealed-current proof")
            else:
                errors.append("manifest: schema_version must be 2")
        if not isinstance(review_policy, dict):
            if allow_legacy_evidence:
                warnings.append("legacy evidence: review policy is missing")
                review_policy = {
                    "mode": "user-self-check",
                    "status": "pending",
                    "evidence_paths": [],
                }
            else:
                errors.append("manifest: review_policy is required")
                review_policy = {}
        review_mode = review_policy.get("mode") if isinstance(review_policy, dict) else None
        if review_mode not in REVIEW_MODES:
            errors.append(f"manifest.review_policy: unknown mode {review_mode!r}")
        review_status = review_policy.get("status") if isinstance(review_policy, dict) else None
        if review_status not in {"pending", "passed"}:
            errors.append("manifest.review_policy: status must be pending or passed")
        if require_visual_approval and review_status != "passed":
            errors.append("manifest.review_policy: visual approval is required")
        if require_visual_approval or review_status == "passed":
            for field in ("reviewer", "reviewed_at", "evidence_paths"):
                if review_policy.get(field) in (None, "", []):
                    errors.append(f"manifest.review_policy: {field} is required for visual approval")
        allowed_delivery_states = {"candidate-ready", "visual-approved", "delivered"}
        if manifest.get("status") not in allowed_delivery_states:
            errors.append("manifest: strict status must be candidate-ready, visual-approved, or delivered")
        if manifest.get("current_stage") not in allowed_delivery_states:
            errors.append("manifest: strict current_stage must be candidate-ready, visual-approved, or delivered")
        if (
            manifest.get("status") in {"visual-approved", "delivered"}
            and review_status != "passed"
            and not allow_legacy_evidence
        ):
            errors.append("manifest: visual-approved/delivered requires passed visual review")
        if (
            isinstance(review_policy, dict)
            and review_policy.get("mode") == "user-self-check"
            and review_policy.get("raster_capture") != "explicit-request-only"
            and not allow_legacy_evidence
        ):
            errors.append("manifest.review_policy: user-self-check must use explicit-request-only raster capture")
    else:
        review_policy = review_policy if isinstance(review_policy, dict) else {}

    subjects = {
        value
        for value in (
            manifest.get("subject"),
            brief.get("subject", {}).get("name") if isinstance(brief.get("subject"), dict) else None,
            refs.get("subject"),
            directions.get("subject"),
            comparisons.get("subject"),
            delivery.get("subject"),
        )
        if isinstance(value, str) and value
    }
    if len(subjects) > 1:
        errors.append("contract: subject names disagree across documents")

    selected = manifest.get("selected_effects")
    if not nonempty_list(selected):
        errors.append("manifest: selected_effects must be a non-empty list")
        selected_effects: set[str] = set()
    else:
        selected_effects = set(selected)
        unknown = selected_effects - EFFECTS - {"auto"}
        if unknown:
            errors.append(f"manifest: unknown effects: {sorted(unknown)}")
        if strict and "auto" in selected_effects:
            errors.append("manifest: strict delivery must resolve auto to explicit effects")
        if "auto" in selected_effects and len(selected_effects) > 1:
            errors.append("manifest: auto cannot be combined with explicit effects")

    if strict:
        if brief.get("schema_version") != 3:
            if allow_legacy_evidence and brief.get("schema_version") == 2:
                warnings.append("legacy evidence: ModelBrief schema 2 lacks evidence policy")
            else:
                errors.append("brief: schema_version must be 3")
        if brief.get("status") != "frozen":
            errors.append("brief: status must be frozen")
        for field in ("required_features", "required_parts", "dimensions", "landmarks", "material_regions"):
            if not nonempty_list(brief.get(field)):
                errors.append(f"brief: {field} must be non-empty")
        assumptions = brief.get("forbidden_assumptions", [])
        if not any("Generated direction images" in str(item) for item in assumptions):
            errors.append("brief: generated images must be explicitly excluded as structural truth")
        motion_contract = brief.get("motion_contract")
        if not isinstance(motion_contract, dict):
            errors.append("brief: motion_contract is required")
        else:
            if motion_contract.get("clock") != "raf-timestamp":
                errors.append("brief.motion_contract: clock must be raf-timestamp")
            if motion_contract.get("animation_loop_owners") != 1:
                errors.append("brief.motion_contract: exactly one animation loop owner is required")
            if set(motion_contract.get("pause_freezes", [])) != PAUSE_FREEZES:
                errors.append("brief.motion_contract: pause_freezes must cover every autonomous motion source")
            if motion_contract.get("replay") != "atomic-zero-preserve-user-camera":
                errors.append("brief.motion_contract: replay must be atomic and preserve the user camera")
            if motion_contract.get("visibility_resume") != "reset-frame-baseline":
                errors.append("brief.motion_contract: visibility resume must reset the frame baseline")
            if motion_contract.get("mode_switch") != "prewarmed-atomic-no-blank":
                errors.append("brief.motion_contract: mode switch must be prewarmed, atomic, and blank-free")
        if brief.get("schema_version") == 3:
            if brief.get("accuracy_class") != "visual-reconstruction":
                errors.append("brief: accuracy_class must be visual-reconstruction")
            evidence_policy = brief.get("evidence_policy")
            if not isinstance(evidence_policy, dict):
                errors.append("brief: evidence_policy is required")
            else:
                if evidence_policy.get("require_http_asset_hash") is not True:
                    errors.append("brief.evidence_policy: HTTP asset hash is required")
                if evidence_policy.get("require_same_run_seal") is not True:
                    errors.append("brief.evidence_policy: same-run evidence seal is required")
    if set(brief.get("required_views", [])) != VIEWS:
        errors.append("brief: required_views must contain the seven canonical views")

    sources = refs.get("sources")
    if not isinstance(sources, list):
        errors.append("references: sources must be a list")
        sources = []
    if strict and not sources:
        errors.append("references: at least one real source is required")
    source_ids: set[str] = set()
    covered_views: set[str] = set()
    authoritative = False
    for index, source in enumerate(sources):
        label = f"references.sources[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{label}: must be an object")
            continue
        source_id = source.get("id")
        if not isinstance(source_id, str) or not source_id:
            errors.append(f"{label}: id is required")
        elif source_id in source_ids:
            errors.append(f"{label}: duplicate id {source_id}")
        else:
            source_ids.add(source_id)
        for field in (
            "source_type",
            "authority_type",
            "authority",
            "locator",
            "captured_at",
            "confidence",
            "supports",
            "views",
            "usage_boundary",
        ):
            if field not in source or source[field] in (None, "", []):
                errors.append(f"{label}: {field} is required")
        views = source.get("views", [])
        if isinstance(views, list):
            covered_views.update(item for item in views if isinstance(item, str))
        if source.get("authority_type") in AUTHORITATIVE_TYPES and source.get("confidence") == "high":
            authoritative = True
        local_path = source.get("local_path")
        if local_path:
            path = resolve_case_path(root, local_path, errors, f"{label}.local_path")
            check_hash(path, source.get("sha256"), errors, f"{label}.sha256")
        elif not source.get("locator"):
            errors.append(f"{label}: locator or local_path is required")
    if strict and covered_views != VIEWS:
        errors.append(f"references: missing canonical view coverage: {sorted(VIEWS - covered_views)}")
    if strict and not authoritative:
        errors.append("references: at least one high-confidence authoritative source is required")

    if directions.get("provider") != "image_gen.imagegen":
        errors.append("directions: provider must be image_gen.imagegen")
    if directions.get("no_third_party_fallback") is not True:
        errors.append("directions: no_third_party_fallback must be true")
    if directions.get("structure_truth") is not False:
        errors.append("directions: structure_truth must be false")
    prompts = directions.get("prompts", [])
    prompt_ids = {
        item.get("id") for item in prompts if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    images = directions.get("images")
    if not isinstance(images, list):
        errors.append("directions: images must be a list")
        images = []
    image_roles: set[str] = set()
    for index, item in enumerate(images):
        label = f"directions.images[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label}: must be an object")
            continue
        role = item.get("role")
        if isinstance(role, str):
            image_roles.add(role)
        else:
            errors.append(f"{label}: role is required")
        if item.get("prompt_id") not in prompt_ids:
            errors.append(f"{label}: prompt_id must reference prompts")
        if strict and not isinstance(item.get("created_at"), str):
            errors.append(f"{label}: created_at is required")
        cited_sources = set(item.get("source_ids", []))
        if strict and not cited_sources:
            errors.append(f"{label}: source_ids cannot be empty")
        if not cited_sources.issubset(source_ids):
            errors.append(f"{label}: source_ids contain unknown IDs")
        path = resolve_case_path(root, item.get("path"), errors, f"{label}.path")
        check_hash(path, item.get("sha256"), errors, f"{label}.sha256")
        validate_image(path, errors, f"{label}.path")
    if strict:
        required_roles = {"white-idle", "final-real-material"}
        required_roles.update(f"{effect}-mid" for effect in selected_effects if effect in EFFECTS)
        if not required_roles.issubset(image_roles):
            errors.append(f"directions: missing roles: {sorted(required_roles - image_roles)}")

    if strict and set(brief.get("selected_effects", [])) != selected_effects:
        errors.append("brief: selected_effects must match the manifest")

    asset = delivery.get("asset", {}) if isinstance(delivery.get("asset"), dict) else {}
    asset_path = resolve_case_path(root, asset.get("path"), errors, "delivery.asset.path")
    check_hash(asset_path, asset.get("sha256"), errors, "delivery.asset.sha256")
    validate_glb(asset_path, errors, "delivery.asset.path")
    asset_hash = asset.get("sha256") if isinstance(asset.get("sha256"), str) else ""
    if strict:
        if delivery.get("schema_version") != 3:
            if allow_legacy_evidence and delivery.get("schema_version") == 2:
                warnings.append("legacy evidence: delivery schema 2 has no same-run seal")
            else:
                errors.append("delivery: schema_version must be 3")
        if delivery.get("status") not in {"candidate-ready", "visual-approved", "delivered"}:
            errors.append("delivery: strict status must be candidate-ready, visual-approved, or delivered")
        if require_visual_approval and delivery.get("status") not in {"visual-approved", "delivered"}:
            errors.append("delivery: visual-approved or delivered status is required")
        if asset_path and asset_path.suffix.lower() != ".glb":
            errors.append("delivery.asset: path must reference a GLB")
        for field in ("bytes", "triangles", "vertices"):
            if not isinstance(asset.get(field), int) or asset[field] <= 0:
                errors.append(f"delivery.asset: {field} must be a positive integer")
        if asset_path and asset.get("bytes") != asset_path.stat().st_size:
            errors.append("delivery.asset: bytes must match the current GLB file size")
        for field in ("parts", "materials"):
            if not nonempty_list(asset.get(field)):
                errors.append(f"delivery.asset: {field} must be non-empty")

    _, source_entry_path = resolve_bound_entry(
        root,
        delivery.get("source_entry"),
        errors,
        "delivery.source_entry",
        strict=strict,
        allow_legacy=allow_legacy_evidence,
        allowed_root=repo_root,
    )
    runtime = delivery.get("runtime", {}) if isinstance(delivery.get("runtime"), dict) else {}
    _, runtime_entry_path = resolve_bound_entry(
        root,
        runtime.get("entry"),
        errors,
        "delivery.runtime.entry",
        strict=strict,
        allow_legacy=allow_legacy_evidence,
        allowed_root=repo_root,
    )
    if runtime.get("acceptance_bridge") != "window.__BUILD_WHITE_MODEL_MOTION_ACCEPTANCE__":
        errors.append("delivery.runtime: acceptance_bridge is incorrect")
    if set(runtime.get("viewports", [])) != {"1440x900", "390x844"}:
        errors.append("delivery.runtime: desktop and mobile viewports are required")
    if strict:
        if runtime.get("acceptance_bridge_version") != 4:
            errors.append("delivery.runtime: acceptance_bridge_version must be 4")
        if runtime.get("animation_loop_owners") != 1:
            errors.append("delivery.runtime: exactly one animation loop owner is required")
        if runtime.get("visibility_lifecycle") is not True:
            errors.append("delivery.runtime: visibility lifecycle must be implemented")
        if runtime.get("shader_variants_prewarmed") is not True:
            errors.append("delivery.runtime: selected shader variants must be prewarmed")
    delivery_effects = delivery.get("effects", {}) if isinstance(delivery.get("effects"), dict) else {}
    if set(delivery_effects.get("selected", [])) != selected_effects:
        errors.append("delivery.effects: selected effects disagree with manifest")
    if delivery_effects.get("default") not in selected_effects:
        errors.append("delivery.effects: default must be one of selected effects")

    validation = delivery.get("validation", {}) if isinstance(delivery.get("validation"), dict) else {}
    reports: dict[str, dict[str, Any]] = {}
    report_paths: dict[str, Path | None] = {}
    for key in ("khronos_report", "loader_report", "browser_report"):
        _, report_path = resolve_bound_entry(
            root,
            validation.get(key),
            errors,
            f"delivery.validation.{key}",
            strict=strict,
            allow_legacy=allow_legacy_evidence,
            allowed_root=repo_root,
        )
        report_paths[key] = report_path
        reports[key] = load_json(report_path, errors, key) if report_path else {}
    drivers = validation.get("drivers")
    if strict and delivery.get("schema_version") == 3:
        if not isinstance(drivers, list) or not drivers:
            errors.append("delivery.validation.drivers: at least one bound validation driver is required")
        else:
            for index, driver in enumerate(drivers):
                resolve_bound_entry(
                    root,
                    driver,
                    errors,
                    f"delivery.validation.drivers[{index}]",
                    strict=True,
                    allow_legacy=False,
                    allowed_root=repo_root,
                )
    if reports["khronos_report"]:
        error_count = validator_error_count(reports["khronos_report"])
        if error_count is None:
            errors.append("khronos_report: cannot determine error count")
        elif error_count != 0:
            errors.append(f"khronos_report: expected zero errors, found {error_count}")
        if strict and delivery.get("schema_version") == 3:
            if reports["khronos_report"].get("mimeType") != "model/gltf-binary":
                errors.append("khronos_report: mimeType must be model/gltf-binary")
            if not isinstance(reports["khronos_report"].get("validatorVersion"), str):
                errors.append("khronos_report: validatorVersion is required")
            if not isinstance(reports["khronos_report"].get("validatedAt"), str):
                errors.append("khronos_report: validatedAt is required")
            if asset_path and Path(str(reports["khronos_report"].get("uri", ""))).name != asset_path.name:
                errors.append("khronos_report: uri must name the current GLB")
    for key in ("loader_report", "browser_report"):
        if reports[key] and reports[key].get("status") != "passed":
            errors.append(f"{key}: status must be passed")
    browser_report = reports["browser_report"]
    if strict and browser_report:
        if delivery.get("schema_version") == 3:
            if report_asset_hash(browser_report) != asset_hash.lower():
                errors.append("browser_report: asset SHA-256 must match the current GLB")
            http_hash = browser_report.get("http_asset_sha256")
            if not isinstance(http_hash, str) or http_hash.lower() != asset_hash.lower():
                errors.append("browser_report: http_asset_sha256 must match the current GLB")
        if set(browser_report.get("viewports", [])) != {"1440x900", "390x844"}:
            errors.append("browser_report: both required viewports must pass")
        if set(browser_report.get("canonical_views", [])) != VIEWS:
            errors.append("browser_report: all canonical views must pass")
        tested_effects = browser_report.get("effect_progress", {})
        for effect in selected_effects & EFFECTS:
            values = tested_effects.get(effect, []) if isinstance(tested_effects, dict) else []
            if not {0, 0.5, 1}.issubset(set(values)):
                errors.append(f"browser_report: {effect} must be tested at 0, 0.5, and 1")
        motion = browser_report.get("motion_stability")
        if not isinstance(motion, dict):
            errors.append("browser_report: motion_stability is required")
        else:
            if motion.get("status") != "passed":
                errors.append("browser_report.motion_stability: status must be passed")
            if not isinstance(motion.get("sample_count"), int) or motion["sample_count"] < 3:
                errors.append("browser_report.motion_stability: sample_count must be at least 3")
            for field in (
                "frozen_frame",
                "ui_pause",
                "replay",
                "continuous_playback",
                "mode_switch",
                "visibility_resume",
                "completion",
                "shader_warmup",
                "resource_stability",
            ):
                result = motion.get(field)
                if not isinstance(result, dict) or result.get("passed") is not True:
                    errors.append(f"browser_report.motion_stability.{field}: passed must be true")
            ui_pause = motion.get("ui_pause", {})
            for field in ("progress_stable", "camera_stable", "pixels_stable"):
                if ui_pause.get(field) is not True:
                    errors.append(f"browser_report.motion_stability.ui_pause: {field} must be true")
            replay = motion.get("replay", {})
            for field in ("atomic_first_frame", "camera_preserved"):
                if replay.get(field) is not True:
                    errors.append(f"browser_report.motion_stability.replay: {field} must be true")
            playback = motion.get("continuous_playback", {})
            if playback.get("progress_monotonic") is not True:
                errors.append("browser_report.motion_stability.continuous_playback: progress_monotonic must be true")
            for field in ("unexpected_blank_frames", "unexpected_subject_dropouts"):
                if playback.get(field) != 0:
                    errors.append(f"browser_report.motion_stability.continuous_playback: {field} must be zero")
            mode_switch = motion.get("mode_switch", {})
            for field in ("unexpected_blank_frames", "duplicate_visible_canvases"):
                if mode_switch.get(field) != 0:
                    errors.append(f"browser_report.motion_stability.mode_switch: {field} must be zero")
            visibility = motion.get("visibility_resume", {})
            if visibility.get("baseline_reset") is not True or visibility.get("unexpected_progress_jump") is not False:
                errors.append("browser_report.motion_stability.visibility_resume: baseline reset without a progress jump is required")
            completion = motion.get("completion", {})
            if completion.get("temporary_effects_cleared") is not True or completion.get("abrupt_luminance_spike") is not False:
                errors.append("browser_report.motion_stability.completion: effects must clear without a luminance spike")
            warmup = motion.get("shader_warmup", {})
            if warmup.get("variants_precompiled") is not True:
                errors.append("browser_report.motion_stability.shader_warmup: variants_precompiled must be true")
            resources = motion.get("resource_stability", {})
            if resources.get("renderer_info_plateau") is not True:
                errors.append("browser_report.motion_stability.resource_stability: renderer_info_plateau must be true")
        lifecycle = browser_report.get("runtime_lifecycle")
        if not isinstance(lifecycle, dict):
            errors.append("browser_report: runtime_lifecycle is required")
        else:
            if lifecycle.get("animation_loop_owners") != 1:
                errors.append("browser_report.runtime_lifecycle: animation_loop_owners must be 1")
            if lifecycle.get("visibility_lifecycle") is not True:
                errors.append("browser_report.runtime_lifecycle: visibility_lifecycle must be true")
            if lifecycle.get("dispose_passed") is not True:
                errors.append("browser_report.runtime_lifecycle: dispose_passed must be true")

    loader_report = reports["loader_report"]
    if strict and loader_report and delivery.get("schema_version") == 3:
        if report_asset_hash(loader_report) != asset_hash.lower():
            errors.append("loader_report: asset SHA-256 must match the current GLB")

    evidence_run_id: str | None = None
    if strict and delivery.get("schema_version") == 3:
        _, seal_path = resolve_bound_entry(
            root,
            delivery.get("evidence_seal"),
            errors,
            "delivery.evidence_seal",
            strict=True,
            allow_legacy=False,
            allowed_root=repo_root,
        )
        seal = load_json(seal_path, errors, "evidence_seal") if seal_path else {}
        if seal:
            if seal.get("schema_version") != 1:
                errors.append("evidence_seal: schema_version must be 1")
            evidence_run_id = seal.get("run_id") if isinstance(seal.get("run_id"), str) else None
            if not evidence_run_id:
                errors.append("evidence_seal: run_id is required")
            try:
                sealed_at = seal.get("sealed_at")
                normalized = sealed_at[:-1] + "+00:00" if isinstance(sealed_at, str) and sealed_at.endswith("Z") else sealed_at
                parsed = datetime.fromisoformat(normalized) if isinstance(normalized, str) else None
                if parsed is None or parsed.tzinfo is None:
                    raise ValueError
                if parsed.astimezone(timezone.utc) > datetime.now(timezone.utc):
                    errors.append("evidence_seal: sealed_at cannot be in the future")
            except ValueError:
                errors.append("evidence_seal: sealed_at must be a timezone-aware ISO timestamp")
            sealed_asset = seal.get("asset")
            if not isinstance(sealed_asset, dict):
                errors.append("evidence_seal: asset binding is required")
            else:
                if sealed_asset.get("sha256") != asset_hash:
                    errors.append("evidence_seal: asset SHA-256 must match delivery")
                if asset_path and sealed_asset.get("bytes") != asset_path.stat().st_size:
                    errors.append("evidence_seal: asset bytes must match the current GLB")
            artifacts = seal.get("artifacts")
            required_roles = {
                "glb",
                "model-source",
                "runtime-entry",
                "case-manifest",
                "model-brief",
                "reference-bundle",
                "direction-set",
                "comparison-report",
                "khronos-report",
                "loader-report",
                "browser-report",
            }
            seen_roles: set[str] = set()
            if not isinstance(artifacts, list):
                errors.append("evidence_seal: artifacts must be a list")
                artifacts = []
            for index, item in enumerate(artifacts):
                label = f"evidence_seal.artifacts[{index}]"
                if not isinstance(item, dict):
                    errors.append(f"{label}: must be an object")
                    continue
                role = item.get("role")
                if isinstance(role, str):
                    seen_roles.add(role)
                else:
                    errors.append(f"{label}: role is required")
                artifact_path = resolve_case_path(
                    root,
                    item.get("path"),
                    errors,
                    f"{label}.path",
                    repo_root,
                )
                check_hash(artifact_path, item.get("sha256"), errors, f"{label}.sha256")
                if artifact_path and item.get("bytes") != artifact_path.stat().st_size:
                    errors.append(f"{label}: bytes must match the current file")
            missing_roles = required_roles - seen_roles
            if missing_roles:
                errors.append(f"evidence_seal: missing artifact roles: {sorted(missing_roles)}")
            if not any(role.startswith("validation-driver:") for role in seen_roles):
                errors.append("evidence_seal: at least one validation driver must be sealed")
            for key, report in reports.items():
                evidence = report.get("_evidence") if isinstance(report, dict) else None
                if not isinstance(evidence, dict):
                    errors.append(f"{key}: _evidence binding is required")
                    continue
                if evidence.get("run_id") != evidence_run_id:
                    errors.append(f"{key}: evidence run_id must match the seal")
                if evidence.get("asset_sha256") != asset_hash:
                    errors.append(f"{key}: _evidence asset SHA-256 must match the current GLB")

    visual_required = require_visual_approval or (
        isinstance(review_policy, dict) and review_policy.get("status") == "passed"
    )
    if strict and comparisons.get("schema_version") != 2:
        if allow_legacy_evidence and comparisons.get("schema_version") == 1:
            warnings.append("legacy evidence: comparison report schema 1 lacks reviewer binding")
        else:
            errors.append("comparisons: schema_version must be 2")
    if strict and comparisons.get("schema_version") == 2:
        if comparisons.get("review_mode") != review_policy.get("mode"):
            errors.append("comparisons: review_mode must match manifest review_policy.mode")
    if comparisons.get("asset_sha256") != asset_hash:
        errors.append("comparisons: asset_sha256 must match delivery asset")
    if visual_required and comparisons.get("status") != "passed":
        errors.append("comparisons: status must be passed for visual approval")
    if visual_required:
        if comparisons.get("reviewer") in (None, ""):
            errors.append("comparisons: reviewer is required for visual approval")
        if comparisons.get("reviewed_at") in (None, ""):
            errors.append("comparisons: reviewed_at is required for visual approval")
    comparison_items = comparisons.get("comparisons")
    if not isinstance(comparison_items, list):
        errors.append("comparisons: comparisons must be a list")
        comparison_items = []
    compared_views: set[str] = set()
    for index, item in enumerate(comparison_items):
        label = f"comparisons.comparisons[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label}: must be an object")
            continue
        view = item.get("view")
        if isinstance(view, str):
            compared_views.add(view)
        if visual_required and item.get("status") != "pass":
            errors.append(f"{label}: status must be pass")
        cited_sources = set(item.get("source_ids", []))
        if visual_required and (not cited_sources or not cited_sources.issubset(source_ids)):
            errors.append(f"{label}: valid real source_ids are required")
        direction_roles = set(item.get("direction_roles", []))
        if visual_required and (not direction_roles or not direction_roles.issubset(image_roles)):
            errors.append(f"{label}: valid direction_roles are required")
        capture_path = None
        if visual_required or item.get("runtime_capture"):
            capture_path = resolve_case_path(
                root,
                item.get("runtime_capture"),
                errors,
                f"{label}.runtime_capture",
            )
            validate_image(capture_path, errors, f"{label}.runtime_capture")
            if comparisons.get("schema_version") == 2:
                check_hash(
                    capture_path,
                    item.get("runtime_capture_sha256"),
                    errors,
                    f"{label}.runtime_capture_sha256",
                )
        if visual_required and not nonempty_list(item.get("visible_differences")):
            errors.append(f"{label}: visible_differences must record the visual decision")
    if visual_required and compared_views != VIEWS:
        errors.append(f"comparisons: missing views: {sorted(VIEWS - compared_views)}")

    if visual_required and isinstance(review_policy, dict):
        for index, evidence_path in enumerate(review_policy.get("evidence_paths", [])):
            resolve_case_path(
                root,
                evidence_path,
                errors,
                f"manifest.review_policy.evidence_paths[{index}]",
                repo_root,
            )

    cleanup = delivery.get("cleanup", {}) if isinstance(delivery.get("cleanup"), dict) else {}
    if strict:
        if cleanup.get("servers_stopped") is not True or cleanup.get("browsers_closed") is not True:
            errors.append("delivery.cleanup: temporary servers and browsers must be stopped")
        if cleanup.get("temporary_paths"):
            warnings.append("delivery.cleanup: temporary_paths remain and must be disclosed")

    return {
        "status": "passed" if not errors else "failed",
        "root": str(root),
        "strict": strict,
        "errors": errors,
        "warnings": warnings,
        "evidence_run_id": evidence_run_id,
        "delivery_level": "visual-approved" if visual_required else "candidate-ready",
        "summary": {
            "sources": len(sources),
            "direction_images": len(images),
            "effects": sorted(selected_effects),
            "compared_views": sorted(compared_views),
        },
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_init_module() -> Any:
    script = Path(__file__).with_name("init_case.py")
    spec = importlib.util.spec_from_file_location("landmark_init_case", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load init_case.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_seal_module() -> Any:
    script = Path(__file__).with_name("seal_evidence.py")
    spec = importlib.util.spec_from_file_location("landmark_seal_evidence", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load seal_evidence.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_self_test() -> None:
    init_module = load_init_module()
    seal_module = load_seal_module()
    with tempfile.TemporaryDirectory(prefix="landmark-case-validate-") as temp_dir:
        root = Path(temp_dir) / "stadium"
        init_module.initialize_case(root, "测试网格体育场", "test-lattice-stadium", ["edge-color"])

        source_id = "official-all-views"
        source = {
            "id": source_id,
            "source_type": "visual",
            "authority_type": "official",
            "authority": "Test Official Archive",
            "locator": "https://example.invalid/test-stadium",
            "captured_at": "2026-08-01T00:00:00Z",
            "confidence": "high",
            "supports": ["identity", "geometry", "materials"],
            "views": sorted(VIEWS),
            "usage_boundary": "test-only",
        }
        refs_path = root / REQUIRED_DOCUMENTS["references"]
        refs = json.loads(refs_path.read_text(encoding="utf-8"))
        refs["sources"] = [source]
        write_json(refs_path, refs)

        brief_path = root / REQUIRED_DOCUMENTS["brief"]
        brief = json.loads(brief_path.read_text(encoding="utf-8"))
        brief.update(
            {
                "status": "frozen",
                "required_features": ["lattice shell"],
                "required_parts": ["shell", "bowl"],
                "dimensions": [{"name": "width", "value_m": 100}],
                "landmarks": [{"name": "roof-center", "xyz_m": [0, 20, 0]}],
                "material_regions": [{"name": "shell", "material": "steel"}],
            }
        )
        write_json(brief_path, brief)

        prompt = {"id": "prompt-1", "source_ids": [source_id], "text": "test direction"}
        direction_images = []
        for role in ("white-idle", "edge-color-mid", "final-real-material"):
            image_path = root / "direction" / f"{role}.png"
            write_test_png(image_path)
            direction_images.append(
                {
                    "role": role,
                    "prompt_id": "prompt-1",
                    "source_ids": [source_id],
                    "path": str(image_path.relative_to(root)),
                    "sha256": sha256_file(image_path),
                    "created_at": "2026-08-01T00:00:00Z",
                }
            )
        direction_path = root / REQUIRED_DOCUMENTS["directions"]
        directions = json.loads(direction_path.read_text(encoding="utf-8"))
        directions["prompts"] = [prompt]
        directions["images"] = direction_images
        write_json(direction_path, directions)

        asset_path = root / "model" / "stadium.glb"
        write_test_glb(asset_path)
        asset_hash = sha256_file(asset_path)
        source_entry = root / "model" / "build-model.mjs"
        source_entry.write_text("export const subject = 'test';\n", encoding="utf-8")
        runtime_entry = root / "runtime" / "index.html"
        runtime_entry.write_text("<!doctype html><title>test</title>\n", encoding="utf-8")
        driver_entry = root / "qa" / "browser-test.mjs"
        driver_entry.write_text("export const evidence = true;\n", encoding="utf-8")
        checked_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        write_json(
            root / "reports" / "khronos.json",
            {
                "uri": asset_path.name,
                "mimeType": "model/gltf-binary",
                "validatorVersion": "2.0.0-test",
                "validatedAt": checked_at,
                "issues": {
                    "numErrors": 0,
                    "numWarnings": 0,
                    "numInfos": 0,
                    "numHints": 0,
                    "messages": [],
                    "truncated": False,
                },
                "info": {"version": "2.0"},
            },
        )
        write_json(
            root / "reports" / "loader.json",
            {"status": "passed", "asset_sha256": asset_hash, "checked_at": checked_at},
        )
        write_json(
            root / "reports" / "browser.json",
            {
                "status": "passed",
                "asset_sha256": asset_hash,
                "http_asset_sha256": asset_hash,
                "checked_at": checked_at,
                "viewports": ["1440x900", "390x844"],
                "canonical_views": sorted(VIEWS),
                "effect_progress": {"edge-color": [0, 0.5, 1]},
                "motion_stability": {
                    "status": "passed",
                    "sample_count": 3,
                    "frozen_frame": {"passed": True, "pixel_diff_ratio_max": 0},
                    "ui_pause": {
                        "passed": True,
                        "progress_stable": True,
                        "camera_stable": True,
                        "pixels_stable": True,
                    },
                    "replay": {"passed": True, "atomic_first_frame": True, "camera_preserved": True},
                    "continuous_playback": {
                        "passed": True,
                        "progress_monotonic": True,
                        "unexpected_blank_frames": 0,
                        "unexpected_subject_dropouts": 0,
                    },
                    "mode_switch": {
                        "passed": True,
                        "unexpected_blank_frames": 0,
                        "duplicate_visible_canvases": 0,
                    },
                    "visibility_resume": {
                        "passed": True,
                        "baseline_reset": True,
                        "unexpected_progress_jump": False,
                    },
                    "completion": {
                        "passed": True,
                        "temporary_effects_cleared": True,
                        "abrupt_luminance_spike": False,
                    },
                    "shader_warmup": {"passed": True, "variants_precompiled": True},
                    "resource_stability": {"passed": True, "renderer_info_plateau": True},
                },
                "runtime_lifecycle": {
                    "animation_loop_owners": 1,
                    "visibility_lifecycle": True,
                    "dispose_passed": True,
                },
            },
        )

        comparisons = []
        for view in sorted(VIEWS):
            capture = root / "qa" / "captures" / f"{view}.png"
            write_test_png(capture)
            comparisons.append(
                {
                    "view": view,
                    "status": "pass",
                    "source_ids": [source_id],
                    "direction_roles": ["white-idle", "edge-color-mid"],
                    "runtime_capture": str(capture.relative_to(root)),
                    "runtime_capture_sha256": sha256_file(capture),
                    "visible_differences": ["No blocking discrepancy in test fixture."],
                }
            )
        comparison_path = root / REQUIRED_DOCUMENTS["comparisons"]
        comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
        comparison["asset_sha256"] = asset_hash
        comparison["comparisons"] = comparisons
        write_json(comparison_path, comparison)

        manifest_path = root / REQUIRED_DOCUMENTS["manifest"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["status"] = "candidate-ready"
        manifest["current_stage"] = "candidate-ready"
        write_json(manifest_path, manifest)

        delivery_path = root / REQUIRED_DOCUMENTS["delivery"]
        delivery = json.loads(delivery_path.read_text(encoding="utf-8"))
        delivery.update(
            {
                "status": "candidate-ready",
                "asset": {
                    "path": str(asset_path.relative_to(root)),
                    "sha256": asset_hash,
                    "bytes": asset_path.stat().st_size,
                    "triangles": 12,
                    "vertices": 24,
                    "parts": ["shell", "bowl"],
                    "materials": ["steel", "concrete"],
                },
                "source_entry": {
                    "path": str(source_entry.relative_to(root)),
                    "sha256": sha256_file(source_entry),
                },
            }
        )
        delivery["runtime"]["entry"] = {
            "path": str(runtime_entry.relative_to(root)),
            "sha256": sha256_file(runtime_entry),
        }
        delivery["effects"] = {"selected": ["edge-color"], "default": "edge-color"}
        delivery["validation"] = {
            "khronos_report": {"path": "reports/khronos.json", "sha256": "0" * 64},
            "loader_report": {"path": "reports/loader.json", "sha256": "0" * 64},
            "browser_report": {"path": "reports/browser.json", "sha256": "0" * 64},
            "drivers": [
                {
                    "path": str(driver_entry.relative_to(root)),
                    "sha256": sha256_file(driver_entry),
                }
            ],
        }
        delivery["cleanup"] = {
            "servers_stopped": True,
            "browsers_closed": True,
            "temporary_paths": [],
        }
        write_json(delivery_path, delivery)

        browser_path = root / "reports" / "browser.json"
        browser_report = json.loads(browser_path.read_text(encoding="utf-8"))
        browser_report["checked_at"] = "2020-01-01T00:00:00Z"
        write_json(browser_path, browser_report)
        try:
            seal_module.seal_case(root, max_age_hours=24)
        except ValueError as error:
            assert "older than 24 hours" in str(error)
        else:
            raise AssertionError("Stale browser evidence must not be sealed")
        browser_report["checked_at"] = checked_at
        write_json(browser_path, browser_report)
        seal_module.seal_case(root, max_age_hours=24)

        passed = validate_case(root, strict=True)
        assert passed["status"] == "passed", passed["errors"]
        visual_pending = validate_case(root, strict=True, require_visual_approval=True)
        assert any("visual approval is required" in error for error in visual_pending["errors"])

        directions["provider"] = "third-party-provider"
        write_json(direction_path, directions)
        provider_failure = validate_case(root, strict=True)
        assert any("provider must be image_gen.imagegen" in error for error in provider_failure["errors"])
        directions["provider"] = "image_gen.imagegen"
        write_json(direction_path, directions)

        delivery = json.loads(delivery_path.read_text(encoding="utf-8"))
        delivery["asset"]["sha256"] = "0" * 64
        write_json(delivery_path, delivery)
        hash_failure = validate_case(root, strict=True)
        assert any("SHA-256 mismatch" in error for error in hash_failure["errors"])

        delivery["asset"]["sha256"] = asset_hash
        write_json(delivery_path, delivery)
        browser_report = json.loads(browser_path.read_text(encoding="utf-8"))
        browser_report["motion_stability"]["ui_pause"]["camera_stable"] = False
        write_json(browser_path, browser_report)
        motion_failure = validate_case(root, strict=True)
        assert any("ui_pause: camera_stable must be true" in error for error in motion_failure["errors"])

        original_asset = asset_path.read_bytes()
        invalid_bytes = bytearray(original_asset)
        invalid_bytes[0:4] = b"FAKE"
        asset_path.write_bytes(invalid_bytes)
        invalid_glb = validate_case(root, strict=True)
        assert any("invalid GLB magic" in error for error in invalid_glb["errors"])
        asset_path.write_bytes(original_asset)

        image_path = root / "direction" / "white-idle.png"
        image_path.write_bytes(b"not-an-image")
        invalid_image = validate_case(root, strict=True)
        assert any("not a recognized PNG" in error for error in invalid_image["errors"])

    print(
        json.dumps(
            {
                "status": "passed",
                "test": "validate_case",
                "negative_cases": [
                    "third-party-provider",
                    "asset-hash-mismatch",
                    "paused-camera-motion",
                    "invalid-glb-bytes",
                    "invalid-image-bytes",
                    "stale-browser-report",
                    "sealed-artifact-drift",
                    "visual-approval-pending",
                ],
            },
            ensure_ascii=False,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="Case root to validate")
    parser.add_argument("--strict", action="store_true", help="Require sealed candidate-ready evidence")
    parser.add_argument(
        "--allow-legacy-evidence",
        action="store_true",
        help="Diagnose schema 1/2 cases with warnings; not current sealed proof",
    )
    parser.add_argument(
        "--require-visual-approval",
        action="store_true",
        help="Require reviewer-bound seven-view visual approval",
    )
    parser.add_argument("--output", type=Path, help="Optional path for the JSON validation report")
    parser.add_argument("--self-test", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.self_test:
        run_self_test()
        return 0
    if args.root is None:
        print("--root is required", file=sys.stderr)
        return 2
    if args.require_visual_approval and not args.strict:
        print("--require-visual-approval requires --strict", file=sys.stderr)
        return 2
    result = validate_case(
        args.root,
        strict=args.strict,
        allow_legacy_evidence=args.allow_legacy_evidence,
        require_visual_approval=args.require_visual_approval,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
