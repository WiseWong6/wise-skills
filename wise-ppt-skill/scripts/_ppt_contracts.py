#!/usr/bin/env python3
"""Shared, dependency-free contracts for wise-ppt command-line tools.

This module deliberately contains no content-planning heuristics.  It loads the
machine-readable Core schemas and theme manifests, performs deterministic
validation, and exposes normalized catalog records for filtering.
"""

from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence
from urllib.parse import urlparse


SCHEMA_FILES = {
    "content": ("content.schema.json", "content-model.schema.json", "content-map.schema.json"),
    "plan": ("deck-plan.schema.json", "plan.schema.json", "narrative-plan.schema.json"),
    "render": ("render-plan.schema.json", "render.schema.json", "rendering-plan.schema.json"),
}

DOCUMENT_FILES = {
    "content": ("content.json", "content-model.json", "content-map.json"),
    "plan": ("deck-plan.json", "plan.json", "narrative-plan.json"),
    "render": ("render-plan.json", "render.json", "rendering-plan.json"),
}

STRUCTURAL_ROLES = {"hook", "orient", "close", "cover", "divider", "outro"}
PRIORITIES = {"must", "should", "could"}
PROVIDERS = {"typography", "table", "image", "native-html", "echarts", "atlas", "svg"}
CORE_PRIMITIVES = {
    "focus-field",
    "bilateral-split",
    "peer-array",
    "linear-sequence",
    "parallel-tracks",
    "radial-burst",
    "nested-regions",
    "layered-stack",
    "matrix-field",
    "network-field",
    "converging-path",
    "evidence-annotation",
}


class ContractError(RuntimeError):
    """Raised when a required contract file cannot be loaded."""


@dataclass(frozen=True)
class Issue:
    code: str
    path: str
    message: str
    severity: str = "error"

    def format(self) -> str:
        return f"{self.severity.upper()} {self.code} {self.path}: {self.message}"


@dataclass
class ValidationResult:
    issues: list[Issue] = field(default_factory=list)

    def error(self, code: str, path: str, message: str) -> None:
        self.issues.append(Issue(code=code, path=path, message=message))

    def warn(self, code: str, path: str, message: str) -> None:
        self.issues.append(Issue(code=code, path=path, message=message, severity="warning"))

    def extend(self, other: "ValidationResult") -> None:
        self.issues.extend(other.issues)

    @property
    def errors(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def has_config_error(self) -> bool:
        return any(issue.code.startswith("config.") for issue in self.errors)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"缺少文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"JSON 无法解析：{path}:{exc.lineno}:{exc.colno} {exc.msg}") from exc


def resolve_root(explicit: str | os.PathLike[str] | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    configured = os.environ.get("WISE_PPT_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def _deck_directory(target: Path) -> Path:
    resolved = target.expanduser().resolve()
    if resolved.is_file() or (not resolved.exists() and resolved.suffix.casefold() == ".json"):
        return resolved.parent
    return resolved


def _relative_to(path: Path, parent: Path) -> Path | None:
    try:
        return path.relative_to(parent)
    except ValueError:
        return None


def _is_internal_contract_path(relative: Path) -> bool:
    parts = relative.parts
    if len(parts) >= 2 and parts[:2] == ("core", "examples"):
        return True
    if len(parts) >= 3 and parts[0] == "themes" and parts[2] in {"examples", "gallery"}:
        return True
    return bool(parts and parts[0] == "tests")


def validate_output_location(
    target: Path,
    root: Path,
    workspace: Path | None = None,
    *,
    allow_internal: bool = False,
    require_workspace: bool = False,
) -> ValidationResult:
    """Validate that a deliverable deck belongs to the user's workspace.

    Contract examples, galleries and test fixtures may be validated in-place by
    normal validation commands. The explicit ``location`` preflight never
    treats repository-internal paths as user deliverables.
    """

    result = ValidationResult()
    deck = _deck_directory(target)
    skill_root = root.expanduser().resolve()

    if require_workspace and workspace is None:
        result.error(
            "config.workspace",
            str(deck),
            "location 预检必须通过 --workspace 指定用户当前工作区根目录",
        )
        return result

    relative_to_skill = _relative_to(deck, skill_root)
    if relative_to_skill is not None:
        if not (allow_internal and _is_internal_contract_path(relative_to_skill)):
            result.error(
                "output.inside_skill",
                str(deck),
                "正式 PPT 产物必须位于用户工作区，不能写入 wise-ppt-skill 根目录或其 output/outputs 子目录",
            )

    if workspace is not None:
        workspace_root = workspace.expanduser().resolve()
        if not workspace_root.is_dir():
            result.error(
                "config.workspace",
                str(workspace_root),
                "用户工作区根目录不存在或不是目录",
            )
        elif _relative_to(deck, workspace_root) is None:
            result.error(
                "output.outside_workspace",
                str(deck),
                f"正式 PPT 产物必须位于用户工作区内：{workspace_root}",
            )
    return result


def _json_pointer_get(document: Any, pointer: str) -> Any:
    if pointer in ("", "#"):
        return document
    if pointer.startswith("#"):
        pointer = pointer[1:]
    if not pointer.startswith("/"):
        raise ContractError(f"不支持的 JSON Pointer：{pointer}")
    current = document
    for raw_part in pointer[1:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise ContractError(f"JSON Pointer 不存在：#{pointer}")
    return current


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return True


def _json_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class JsonSchemaValidator:
    """A practical JSON Schema subset sufficient for the repository contracts.

    Supported keywords include local/relative ``$ref``, type, required,
    properties, additionalProperties, patternProperties, array cardinality,
    enum/const, string and numeric bounds, allOf/anyOf/oneOf/not and
    if/then/else. Unknown annotation keywords are intentionally ignored.
    """

    def __init__(self, schema_path: Path):
        self.schema_path = schema_path.resolve()
        self._documents: dict[Path, Any] = {self.schema_path: load_json(self.schema_path)}

    def validate(self, instance: Any, instance_name: str = "$") -> ValidationResult:
        result = ValidationResult()
        self._walk(instance, self._documents[self.schema_path], instance_name, self.schema_path, result)
        return result

    def _branch_valid(self, value: Any, schema: Any, path: str, schema_file: Path) -> bool:
        branch = ValidationResult()
        self._walk(value, schema, path, schema_file, branch)
        return branch.ok

    def _resolve_ref(self, ref: str, schema_file: Path) -> tuple[Any, Path]:
        file_part, marker, pointer = ref.partition("#")
        target_file = schema_file if not file_part else (schema_file.parent / file_part).resolve()
        if target_file not in self._documents:
            self._documents[target_file] = load_json(target_file)
        target = self._documents[target_file]
        if marker:
            target = _json_pointer_get(target, f"#{pointer}")
        return target, target_file

    def _walk(
        self,
        value: Any,
        schema: Any,
        path: str,
        schema_file: Path,
        result: ValidationResult,
    ) -> None:
        if schema is True:
            return
        if schema is False:
            result.error("schema.false", path, "该值被 schema 明确禁止")
            return
        if not isinstance(schema, dict):
            result.error("schema.invalid", path, "schema 节点必须是对象或布尔值")
            return

        if "$ref" in schema:
            try:
                target, target_file = self._resolve_ref(str(schema["$ref"]), schema_file)
                self._walk(value, target, path, target_file, result)
            except (ContractError, ValueError, IndexError) as exc:
                result.error("config.schema_ref", path, str(exc))
            sibling = {key: item for key, item in schema.items() if key != "$ref"}
            if sibling:
                self._walk(value, sibling, path, schema_file, result)
            return

        for branch_schema in schema.get("allOf", []):
            self._walk(value, branch_schema, path, schema_file, result)

        if "anyOf" in schema:
            if not any(self._branch_valid(value, branch, path, schema_file) for branch in schema["anyOf"]):
                result.error("schema.anyOf", path, "不符合 anyOf 中任何一种结构")
                return

        if "oneOf" in schema:
            matches = sum(self._branch_valid(value, branch, path, schema_file) for branch in schema["oneOf"])
            if matches != 1:
                result.error("schema.oneOf", path, f"必须且只能符合一种结构，当前符合 {matches} 种")
                return

        if "not" in schema and self._branch_valid(value, schema["not"], path, schema_file):
            result.error("schema.not", path, "命中了禁止结构")

        if "if" in schema:
            selected = "then" if self._branch_valid(value, schema["if"], path, schema_file) else "else"
            if selected in schema:
                self._walk(value, schema[selected], path, schema_file, result)

        expected = schema.get("type")
        if expected is not None:
            expected_types = [expected] if isinstance(expected, str) else list(expected)
            if not any(_type_matches(value, item) for item in expected_types):
                result.error(
                    "schema.type",
                    path,
                    f"类型应为 {'/'.join(expected_types)}，实际为 {type(value).__name__}",
                )
                return

        if "const" in schema and value != schema["const"]:
            result.error("schema.const", path, f"值必须为 {schema['const']!r}")
        if "enum" in schema and value not in schema["enum"]:
            result.error("schema.enum", path, f"值 {value!r} 不在允许集合中")

        if isinstance(value, dict):
            self._validate_object(value, schema, path, schema_file, result)
        elif isinstance(value, list):
            self._validate_array(value, schema, path, schema_file, result)
        elif isinstance(value, str):
            self._validate_string(value, schema, path, result)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            self._validate_number(value, schema, path, result)

    def _validate_object(
        self,
        value: dict[str, Any],
        schema: dict[str, Any],
        path: str,
        schema_file: Path,
        result: ValidationResult,
    ) -> None:
        for key in schema.get("required", []):
            if key not in value:
                result.error("schema.required", f"{path}.{key}", "缺少必填字段")
        if len(value) < schema.get("minProperties", 0):
            result.error("schema.minProperties", path, "对象字段数不足")
        if "maxProperties" in schema and len(value) > schema["maxProperties"]:
            result.error("schema.maxProperties", path, "对象字段数超限")

        properties = schema.get("properties", {})
        pattern_properties = schema.get("patternProperties", {})
        matched: set[str] = set()
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if key in properties:
                matched.add(key)
                self._walk(item, properties[key], child_path, schema_file, result)
            for pattern, child_schema in pattern_properties.items():
                try:
                    if re.search(pattern, key):
                        matched.add(key)
                        self._walk(item, child_schema, child_path, schema_file, result)
                except re.error as exc:
                    result.error("config.schema_pattern", child_path, f"无效正则：{exc}")
            if "propertyNames" in schema:
                self._walk(key, schema["propertyNames"], f"{child_path}<name>", schema_file, result)

        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in matched:
                continue
            if additional is False:
                result.error("schema.additionalProperties", f"{path}.{key}", "不允许额外字段")
            elif isinstance(additional, dict):
                self._walk(item, additional, f"{path}.{key}", schema_file, result)

        for key, dependencies in schema.get("dependentRequired", {}).items():
            if key in value:
                for dependency in dependencies:
                    if dependency not in value:
                        result.error(
                            "schema.dependentRequired",
                            f"{path}.{dependency}",
                            f"字段 {key!r} 出现时必须同时提供 {dependency!r}",
                        )

    def _validate_array(
        self,
        value: list[Any],
        schema: dict[str, Any],
        path: str,
        schema_file: Path,
        result: ValidationResult,
    ) -> None:
        if len(value) < schema.get("minItems", 0):
            result.error("schema.minItems", path, f"数组至少需要 {schema['minItems']} 项")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            result.error("schema.maxItems", path, f"数组最多允许 {schema['maxItems']} 项")
        if schema.get("uniqueItems"):
            seen: set[str] = set()
            for index, item in enumerate(value):
                key = _json_key(item)
                if key in seen:
                    result.error("schema.uniqueItems", f"{path}[{index}]", "数组项必须唯一")
                seen.add(key)

        prefix_items = schema.get("prefixItems", [])
        for index, child_schema in enumerate(prefix_items):
            if index < len(value):
                self._walk(value[index], child_schema, f"{path}[{index}]", schema_file, result)
        items = schema.get("items")
        if items is not None:
            start = len(prefix_items) if prefix_items else 0
            for index in range(start, len(value)):
                self._walk(value[index], items, f"{path}[{index}]", schema_file, result)
        if "contains" in schema:
            matches = sum(self._branch_valid(item, schema["contains"], path, schema_file) for item in value)
            minimum = schema.get("minContains", 1)
            maximum = schema.get("maxContains")
            if matches < minimum or (maximum is not None and matches > maximum):
                result.error("schema.contains", path, f"contains 匹配数 {matches} 不在允许范围")

    @staticmethod
    def _validate_string(value: str, schema: dict[str, Any], path: str, result: ValidationResult) -> None:
        if len(value) < schema.get("minLength", 0):
            result.error("schema.minLength", path, f"字符串长度至少为 {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            result.error("schema.maxLength", path, f"字符串长度最多为 {schema['maxLength']}")
        if "pattern" in schema:
            try:
                if re.search(schema["pattern"], value) is None:
                    result.error("schema.pattern", path, f"字符串不符合正则 {schema['pattern']!r}")
            except re.error as exc:
                result.error("config.schema_pattern", path, f"无效正则：{exc}")
        fmt = schema.get("format")
        if fmt in {"uri", "uri-reference"} and value:
            parsed = urlparse(value)
            if fmt == "uri" and not parsed.scheme:
                result.error("schema.format", path, "不是绝对 URI")

    @staticmethod
    def _validate_number(value: float, schema: dict[str, Any], path: str, result: ValidationResult) -> None:
        if "minimum" in schema and value < schema["minimum"]:
            result.error("schema.minimum", path, f"数值不得小于 {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            result.error("schema.maximum", path, f"数值不得大于 {schema['maximum']}")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            result.error("schema.exclusiveMinimum", path, f"数值必须大于 {schema['exclusiveMinimum']}")
        if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
            result.error("schema.exclusiveMaximum", path, f"数值必须小于 {schema['exclusiveMaximum']}")
        if "multipleOf" in schema:
            quotient = value / schema["multipleOf"]
            if not math.isclose(quotient, round(quotient)):
                result.error("schema.multipleOf", path, f"数值必须是 {schema['multipleOf']} 的倍数")


def find_schema(root: Path, kind: str) -> Path:
    if kind not in SCHEMA_FILES:
        raise ContractError(f"未知 schema 类型：{kind}")
    for filename in SCHEMA_FILES[kind]:
        for directory in (root / "core" / "schemas", root / "core" / "schema", root / "core"):
            candidate = directory / filename
            if candidate.is_file():
                return candidate
    expected = root / "core" / "schemas" / SCHEMA_FILES[kind][0]
    raise ContractError(f"缺少 {kind} schema：期望 {expected}")


def validate_against_schema(root: Path, kind: str, document: Any, label: str) -> ValidationResult:
    try:
        validator = JsonSchemaValidator(find_schema(root, kind))
        return validator.validate(document, label)
    except ContractError as exc:
        result = ValidationResult()
        result.error("config.schema", label, str(exc))
        return result


def find_document(target: Path, kind: str, required: bool = True) -> Path | None:
    target = target.expanduser().resolve()
    if target.is_file():
        return target
    if target.is_dir():
        for filename in DOCUMENT_FILES[kind]:
            candidate = target / filename
            if candidate.is_file():
                return candidate
        for subdir in ("contracts", "planning", "data"):
            for filename in DOCUMENT_FILES[kind]:
                candidate = target / subdir / filename
                if candidate.is_file():
                    return candidate
    if required:
        names = ", ".join(DOCUMENT_FILES[kind])
        raise ContractError(f"在 {target} 下找不到 {kind} 文档（候选：{names}）")
    return None


def resolve_link(base_file: Path, link: str | None, root: Path, kind: str) -> Path:
    if link:
        raw = Path(link).expanduser()
        candidates = [raw] if raw.is_absolute() else [base_file.parent / raw, root / raw]
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
        raise ContractError(f"{kind} 引用文件不存在：{link}（来自 {base_file}）")
    fallback = find_document(base_file.parent, kind, required=False)
    if fallback:
        return fallback
    raise ContractError(f"{base_file} 未声明 {kind}_file，且同目录没有默认 {kind} 文档")


@dataclass(frozen=True)
class ThemeRecord:
    theme_id: str
    registry_entry: Mapping[str, Any]
    theme_document: Mapping[str, Any]
    theme_path: Path
    layout_manifest_path: Path


def _resolve_registry_path(root: Path, registry_path: Path, value: str) -> Path:
    raw = Path(value).expanduser()
    candidates = [raw] if raw.is_absolute() else [root / raw, registry_path.parent / raw]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return candidates[0].resolve()


def load_theme_registry(root: Path) -> tuple[Mapping[str, Any], Path]:
    path = root / "themes" / "registry.json"
    if not path.is_file():
        raise ContractError(f"缺少主题注册表：{path}")
    document = load_json(path)
    if not isinstance(document, dict) or not isinstance(document.get("themes"), list):
        raise ContractError(f"主题注册表结构错误：{path} 必须包含 themes[]")
    return document, path


def resolve_theme(root: Path, requested: str | None = None) -> ThemeRecord:
    registry, registry_path = load_theme_registry(root)
    theme_id = requested or registry.get("default_theme_id") or registry.get("default_theme")
    if not theme_id:
        raise ContractError(f"主题未指定，且 {registry_path} 没有 default_theme_id")
    entries = [entry for entry in registry["themes"] if isinstance(entry, dict)]
    entry = next(
        (
            item
            for item in entries
            if (item.get("theme_id") or item.get("id")) == theme_id and item.get("enabled", True)
        ),
        None,
    )
    if entry is None:
        available = sorted(str(item.get("theme_id") or item.get("id")) for item in entries)
        raise ContractError(f"未知或未启用的主题 {theme_id!r}；可用主题：{', '.join(available)}")

    theme_ref = entry.get("path") or entry.get("manifest") or f"themes/{theme_id}/theme.json"
    theme_path = _resolve_registry_path(root, registry_path, str(theme_ref))
    if not theme_path.is_file():
        raise ContractError(f"主题清单不存在：{theme_path}")
    theme_doc = load_json(theme_path)
    if not isinstance(theme_doc, dict):
        raise ContractError(f"主题清单必须是对象：{theme_path}")
    declared_id = theme_doc.get("theme_id") or theme_doc.get("id")
    if declared_id and declared_id != theme_id:
        raise ContractError(f"主题 ID 不一致：registry={theme_id!r}, theme={declared_id!r}")

    layout_ref = entry.get("layout_manifest") or theme_doc.get("layout_manifest")
    if not layout_ref:
        raise ContractError(f"主题 {theme_id!r} 未声明 layout_manifest")
    layout_path = _resolve_registry_path(root, registry_path, str(layout_ref))
    if not layout_path.is_file():
        layout_path = _resolve_registry_path(root, theme_path, str(layout_ref))
    if not layout_path.is_file():
        raise ContractError(f"布局 manifest 不存在：{layout_path}")
    return ThemeRecord(
        theme_id=str(theme_id),
        registry_entry=entry,
        theme_document=theme_doc,
        theme_path=theme_path,
        layout_manifest_path=layout_path,
    )


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        output: list[str] = []
        for item in value:
            if isinstance(item, str):
                output.append(item)
            elif isinstance(item, dict):
                identifier = item.get("id") or item.get("name") or item.get("value")
                if identifier:
                    output.append(str(identifier))
        return output
    return []


def normalize_layout(raw: Mapping[str, Any], source: Path) -> dict[str, Any]:
    supports = raw.get("supports") if isinstance(raw.get("supports"), dict) else {}
    layout_id = raw.get("layout_id") or raw.get("id") or raw.get("stable_id")
    if not layout_id:
        raise ContractError(f"布局缺少 layout_id：{source}")
    slots = raw.get("slots") if isinstance(raw.get("slots"), list) else []
    providers = _strings(
        raw.get("renderers") or raw.get("providers") or raw.get("provider_ids") or supports.get("providers")
    )
    for slot in slots:
        if isinstance(slot, dict):
            providers.extend(_strings(slot.get("allowed_providers")))
    providers = list(dict.fromkeys(providers))
    return {
        "id": str(layout_id),
        "name": str(raw.get("name") or layout_id),
        "display_code": raw.get("display_code") or raw.get("code"),
        "family": raw.get("family"),
        "description": raw.get("description", ""),
        "roles": _strings(raw.get("roles") or raw.get("role") or supports.get("roles")),
        "relations": _strings(
            raw.get("relations") or raw.get("relation_shapes") or raw.get("relation") or supports.get("relations")
        ),
        "core_primitives": _strings(raw.get("core_primitives") or supports.get("core_primitives")),
        "densities": _strings(raw.get("densities") or raw.get("density") or supports.get("densities")),
        "providers": providers,
        "primitives": _strings(raw.get("primitives")),
        "capacity": raw.get("capacity") if isinstance(raw.get("capacity"), dict) else {},
        "slots": slots,
        "examples": raw.get("examples") if isinstance(raw.get("examples"), dict) else {},
        "selection_notes": raw.get("selection_notes") or raw.get("rationale_hint") or "",
        "anti_patterns": raw.get("anti_patterns") if isinstance(raw.get("anti_patterns"), list) else [],
        "source": str(source),
        "raw": dict(raw),
    }


def load_layout_catalog(root: Path, theme_id: str | None = None) -> tuple[ThemeRecord, list[dict[str, Any]], Mapping[str, Any]]:
    theme = resolve_theme(root, theme_id)
    manifest = load_json(theme.layout_manifest_path)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("layouts"), list):
        raise ContractError(f"布局 manifest 必须包含 layouts[]：{theme.layout_manifest_path}")
    manifest_theme = manifest.get("theme_id")
    if manifest_theme and manifest_theme != theme.theme_id:
        raise ContractError(
            f"布局 manifest 主题不一致：theme={theme.theme_id!r}, manifest={manifest_theme!r}"
        )
    records: list[dict[str, Any]] = []
    for index, item in enumerate(manifest["layouts"]):
        if not isinstance(item, dict):
            raise ContractError(f"布局 manifest layouts[{index}] 必须是对象：{theme.layout_manifest_path}")
        records.append(normalize_layout(item, theme.layout_manifest_path))
    return theme, records, manifest


def _slug(value: Any) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return normalized or "component"


def _parse_atlas_js(path: Path) -> list[Mapping[str, Any]]:
    source = path.read_text(encoding="utf-8")
    marker = "window.SWISS_CATALOG_DATA"
    start_marker = source.find(marker)
    if start_marker < 0:
        raise ContractError(f"atlas catalog 缺少 {marker}：{path}")
    start = source.find("{", start_marker)
    if start < 0:
        raise ContractError(f"atlas catalog 没有 JSON 对象：{path}")
    try:
        document, _ = json.JSONDecoder().raw_decode(source[start:])
    except json.JSONDecodeError as exc:
        raise ContractError(f"atlas catalog 无法解析：{path}: {exc}") from exc
    entries = document.get("entries") if isinstance(document, dict) else None
    if not isinstance(entries, list):
        raise ContractError(f"atlas catalog 缺少 entries[]：{path}")
    return [entry for entry in entries if isinstance(entry, dict)]


def _normalize_component(raw: Mapping[str, Any], source: Path, default_provider: str = "atlas") -> dict[str, Any]:
    number = raw.get("num")
    name = raw.get("name") or raw.get("component_id") or raw.get("id")
    variant = raw.get("variant")
    component_id = raw.get("component_id") or raw.get("id")
    if not component_id:
        number_part = f"{int(number):03d}." if isinstance(number, int) else ""
        component_id = f"atlas.{number_part}{_slug(name)}"
        if variant:
            component_id += f".{_slug(variant)}"
    label = raw.get("label") or raw.get("display_name") or name or component_id
    aliases = list(
        dict.fromkeys(
            item
            for item in (
                name,
                label,
                variant,
                str(number) if number is not None else None,
                *_strings(raw.get("aliases")),
            )
            if item
        )
    )
    return {
        "id": str(component_id),
        "name": str(label),
        "canonical_name": str(name or component_id),
        "variant": variant,
        "group": raw.get("group"),
        "group_label": raw.get("groupLabel") or raw.get("group_label"),
        "description": raw.get("description", ""),
        "tasks": _strings(raw.get("tasks") or raw.get("task")),
        "roles": _strings(raw.get("roles")),
        "relations": _strings(raw.get("relations") or raw.get("relation_shapes")),
        "densities": _strings(raw.get("densities") or raw.get("density")),
        "providers": _strings(raw.get("providers") or raw.get("provider")) or [default_provider],
        "capacity": raw.get("capacity") if isinstance(raw.get("capacity"), dict) else {},
        "slots": raw.get("slots") if isinstance(raw.get("slots"), list) else [],
        "aliases": aliases,
        "selection_notes": raw.get("selection_notes") or raw.get("description") or "",
        "requires": _strings(raw.get("requires")),
        "source": str(source),
        "raw": dict(raw),
    }


def find_component_catalog(root: Path, theme: ThemeRecord | None = None) -> Path:
    candidates: list[Path] = []
    if theme:
        for key in ("component_manifest", "component_catalog"):
            ref = theme.registry_entry.get(key) or theme.theme_document.get(key)
            if ref:
                candidates.extend([root / str(ref), theme.theme_path.parent / str(ref)])
        candidates.extend(
            [
                theme.theme_path.parent / "component-manifest.json",
                theme.theme_path.parent / "components.json",
            ]
        )
    candidates.extend(
        [
            root / "core" / "catalogs" / "component-manifest.json",
            root / "core" / "catalogs" / "components.json",
            root / "core" / "component-manifest.json",
        ]
    )
    configured = os.environ.get("PPT_COMPONENT_ATLAS_CATALOG")
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend(
        [
            Path.home() / ".codex" / "skills" / "ppt-component-atlas" / "public" / "catalog-data.js",
            Path.home() / ".agents" / "skills" / "ppt-component-atlas" / "public" / "catalog-data.js",
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise ContractError(
        "缺少组件 catalog：可提供 core/catalogs/component-manifest.json，"
        "或安装 ppt-component-atlas，或设置 PPT_COMPONENT_ATLAS_CATALOG"
    )


def load_component_catalog(root: Path, theme_id: str | None = None) -> tuple[ThemeRecord, list[dict[str, Any]], Path]:
    theme = resolve_theme(root, theme_id)
    path = find_component_catalog(root, theme)
    if path.suffix == ".js":
        entries = _parse_atlas_js(path)
        records = [_normalize_component(item, path, "atlas") for item in entries]
    else:
        document = load_json(path)
        if isinstance(document, list):
            entries = document
        elif isinstance(document, dict):
            entries = document.get("components") or document.get("entries") or document.get("items")
        else:
            entries = None
        if not isinstance(entries, list):
            raise ContractError(f"组件 catalog 必须包含 components[]/entries[]：{path}")
        records = [_normalize_component(item, path) for item in entries if isinstance(item, dict)]

    # The built-in provider catalog and the independently installed Atlas are
    # complementary sources.  Merge them mechanically and let callers filter;
    # never score or auto-select a record here.
    built_in = root / "core" / "catalogs" / "component-manifest.json"
    extra_paths: list[Path] = []
    if built_in.is_file() and built_in.resolve() != path:
        extra_paths.append(built_in.resolve())
    for atlas_path in (
        Path.home() / ".codex" / "skills" / "ppt-component-atlas" / "public" / "catalog-data.js",
        Path.home() / ".agents" / "skills" / "ppt-component-atlas" / "public" / "catalog-data.js",
    ):
        if atlas_path.is_file() and atlas_path.resolve() != path:
            extra_paths.append(atlas_path.resolve())
            break
    for extra_path in extra_paths:
        if extra_path.suffix == ".js":
            extra_entries = _parse_atlas_js(extra_path)
            records.extend(_normalize_component(item, extra_path, "atlas") for item in extra_entries)
        else:
            extra_document = load_json(extra_path)
            extra_entries = (
                extra_document.get("components") or extra_document.get("entries") or extra_document.get("items")
                if isinstance(extra_document, dict)
                else extra_document
            )
            if not isinstance(extra_entries, list):
                raise ContractError(f"组件 catalog 必须包含 components[]/entries[]：{extra_path}")
            records.extend(
                _normalize_component(item, extra_path)
                for item in extra_entries
                if isinstance(item, dict)
            )
    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        by_id.setdefault(record["id"], record)
    records = list(by_id.values())
    return theme, records, path


def _matches(record: Mapping[str, Any], field: str, requested: Sequence[str]) -> bool:
    if not requested:
        return True
    values = {str(value).casefold() for value in record.get(field, [])}
    return all(value.casefold() in values for value in requested)


def filter_catalog(
    records: Iterable[Mapping[str, Any]],
    *,
    roles: Sequence[str] = (),
    relations: Sequence[str] = (),
    densities: Sequence[str] = (),
    providers: Sequence[str] = (),
    primitives: Sequence[str] = (),
    tasks: Sequence[str] = (),
    name: str | None = None,
) -> list[dict[str, Any]]:
    query = (name or "").casefold().strip()
    output: list[dict[str, Any]] = []
    for raw in records:
        record = dict(raw)
        if not _matches(record, "roles", roles):
            continue
        if not _matches(record, "relations", relations):
            continue
        if not _matches(record, "densities", densities):
            continue
        if not _matches(record, "providers", providers):
            continue
        if not _matches(record, "core_primitives", primitives):
            continue
        if not _matches(record, "tasks", tasks):
            continue
        haystack = " ".join(
            str(item)
            for item in (
                record.get("id"),
                record.get("name"),
                record.get("canonical_name"),
                record.get("display_code"),
                record.get("description"),
                *(record.get("aliases") or []),
            )
            if item
        ).casefold()
        if query and query not in haystack:
            continue
        output.append(record)
    return sorted(output, key=lambda item: str(item.get("id", "")))


def public_catalog_record(record: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "name",
        "canonical_name",
        "display_code",
        "variant",
        "family",
        "group",
        "group_label",
        "description",
        "tasks",
        "roles",
        "relations",
        "densities",
        "providers",
        "core_primitives",
        "primitives",
        "capacity",
        "slots",
        "examples",
        "aliases",
        "selection_notes",
        "requires",
        "anti_patterns",
        "source",
    )
    return {key: record[key] for key in keys if key in record and record[key] not in (None, "", [], {})}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _identifier(item: Any, *keys: str) -> str | None:
    if not isinstance(item, dict):
        return None
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def content_items(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    value = document.get("content_items") or document.get("items") or document.get("claims")
    return [item for item in _as_list(value) if isinstance(item, dict)]


def content_ref_ids(document: Mapping[str, Any]) -> set[str]:
    """Return every addressable item/atom ID in a content contract."""
    output: set[str] = set()
    for item in content_items(document):
        item_id = _identifier(item, "id", "content_id")
        if item_id:
            output.add(item_id)
        for atomic in _as_list(item.get("atomic_values")):
            atomic_id = _identifier(atomic, "id", "value_id")
            if atomic_id:
                output.add(atomic_id)
    return output


def must_content_refs(document: Mapping[str, Any]) -> set[str]:
    """A must item and each of its atomic values must remain traceable."""
    output: set[str] = set()
    for item in content_items(document):
        if item.get("priority") != "must":
            continue
        item_id = _identifier(item, "id", "content_id")
        if item_id:
            output.add(item_id)
        for atomic in _as_list(item.get("atomic_values")):
            atomic_id = _identifier(atomic, "id", "value_id")
            if atomic_id:
                output.add(atomic_id)
    return output


def plan_pages(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    value = document.get("pages") or document.get("slides")
    return [item for item in _as_list(value) if isinstance(item, dict)]


def render_pages(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    value = document.get("pages") or document.get("slides")
    return [item for item in _as_list(value) if isinstance(item, dict)]


def _ref_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        if isinstance(item, str):
            output.append(item)
        elif isinstance(item, dict):
            ref = item.get("content_ref") or item.get("content_id") or item.get("id")
            if isinstance(ref, str):
                output.append(ref)
    return output


def page_content_refs(page: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("content_refs", "evidence_refs", "content_ids"):
        refs.extend(_ref_list(page.get(key)))
    for block in _as_list(page.get("blocks")):
        if isinstance(block, dict):
            refs.extend(_ref_list(block.get("content_refs") or block.get("content_ids")))
    return list(dict.fromkeys(refs))


def slot_content_refs(slot: Mapping[str, Any]) -> list[str]:
    renderer = slot.get("renderer") if isinstance(slot.get("renderer"), dict) else {}
    return _ref_list(renderer.get("content_refs") or slot.get("content_refs"))


def render_page_content_refs(page: Mapping[str, Any]) -> list[str]:
    refs = _ref_list(page.get("content_refs"))
    for slot in _as_list(page.get("slots")):
        if isinstance(slot, dict):
            refs.extend(slot_content_refs(slot))
    return list(dict.fromkeys(refs))


def _load_document(path: Path, result: ValidationResult, label: str) -> Mapping[str, Any] | None:
    try:
        value = load_json(path)
    except ContractError as exc:
        result.error("config.document", label, str(exc))
        return None
    if not isinstance(value, dict):
        result.error("document.type", label, "顶层必须是 JSON 对象")
        return None
    return value


def validate_content_document(document: Mapping[str, Any], path: Path, root: Path) -> ValidationResult:
    label = str(path)
    result = validate_against_schema(root, "content", document, label)
    sources = [item for item in _as_list(document.get("sources")) if isinstance(item, dict)]
    source_ids: set[str] = set()
    source_synthetic: dict[str, bool] = {}
    for index, source in enumerate(sources):
        item_path = f"{label}#.sources[{index}]"
        source_id = _identifier(source, "source_id", "id")
        if not source_id:
            result.error("content.source_id", item_path, "来源缺少稳定 ID")
        elif source_id in source_ids:
            result.error("content.duplicate_source", item_path, f"来源 ID 重复：{source_id}")
        else:
            source_ids.add(source_id)
            source_synthetic[source_id] = source.get("synthetic") is True

    item_ids: set[str] = set()
    atomic_ids: set[str] = set()
    for index, item in enumerate(content_items(document)):
        item_path = f"{label}#.content_items[{index}]"
        item_id = _identifier(item, "id", "content_id")
        if not item_id:
            result.error("content.item_id", item_path, "内容单元缺少稳定 ID")
        elif item_id in item_ids:
            result.error("content.duplicate_item", item_path, f"内容 ID 重复：{item_id}")
        else:
            item_ids.add(item_id)
        priority = item.get("priority")
        if priority not in PRIORITIES:
            result.error("content.priority", item_path, f"priority 必须是 {sorted(PRIORITIES)}")
        status = item.get("status")
        if not isinstance(status, str) or not status:
            result.error("content.status", item_path, "内容单元必须声明 status")
        refs = _ref_list(item.get("source_refs"))
        if status == "sourced" and not refs:
            result.error("content.source_refs", item_path, "status=sourced 的内容必须至少引用一个来源")
        for ref in refs:
            if ref not in source_ids:
                result.error("content.unknown_source", item_path, f"引用了未知来源：{ref}")
            elif status == "sourced" and source_synthetic.get(ref):
                note = str(item.get("status_note") or "").casefold()
                if "synthetic" not in note and "合成" not in note:
                    result.error(
                        "content.synthetic_disclosure",
                        item_path,
                        f"引用 synthetic 来源 {ref} 时，status_note 必须显式说明其合成属性",
                    )
        for atomic_index, atomic in enumerate(_as_list(item.get("atomic_values"))):
            atomic_path = f"{item_path}.atomic_values[{atomic_index}]"
            atomic_id = _identifier(atomic, "id", "value_id")
            if not atomic_id:
                result.error("content.atomic_id", atomic_path, "原子值缺少稳定 ID")
            elif atomic_id in atomic_ids:
                result.error("content.duplicate_atomic", atomic_path, f"原子值 ID 重复：{atomic_id}")
            else:
                atomic_ids.add(atomic_id)
    if not content_items(document):
        result.error("content.empty", label, "content_items[] 不能为空")
    known_relation_targets = item_ids | atomic_ids
    for item_index, item in enumerate(content_items(document)):
        item_id = _identifier(item, "id", "content_id")
        for relation_index, relation in enumerate(_as_list(item.get("relations"))):
            if not isinstance(relation, dict):
                continue
            relation_path = f"{label}#.content_items[{item_index}].relations[{relation_index}]"
            target_ref = relation.get("target_ref")
            if not isinstance(target_ref, str):
                result.error("content.invalid_relation_target", relation_path, "target_ref 必须是字符串 ID")
                continue
            if target_ref not in known_relation_targets:
                result.error("content.unknown_relation_target", relation_path, f"关系指向了未知内容：{target_ref}")
            if target_ref == item_id:
                result.error("content.self_relation", relation_path, f"内容关系不可指向自身：{item_id}")
    brief = document.get("brief") if isinstance(document.get("brief"), dict) else {}
    limits = brief.get("page_limits") if isinstance(brief.get("page_limits"), dict) else {}
    minimum = limits.get("min")
    maximum = limits.get("max")
    requested = limits.get("requested")
    if isinstance(minimum, int) and isinstance(maximum, int) and minimum > maximum:
        result.error("content.page_limits", f"{label}#.brief.page_limits", "min 不能大于 max")
    if (
        isinstance(requested, int)
        and isinstance(minimum, int)
        and isinstance(maximum, int)
        and not minimum <= requested <= maximum
    ):
        result.error("content.page_limits", f"{label}#.brief.page_limits.requested", "requested 必须落在 min/max 内")
    return result


def validate_content_target(target: Path, root: Path) -> ValidationResult:
    result = ValidationResult()
    try:
        path = find_document(target, "content")
    except ContractError as exc:
        result.error("config.content", str(target), str(exc))
        return result
    document = _load_document(path, result, str(path))
    if document is not None:
        result.extend(validate_content_document(document, path, root))
    return result


def validate_plan_document(document: Mapping[str, Any], path: Path, root: Path) -> ValidationResult:
    label = str(path)
    result = validate_against_schema(root, "plan", document, label)
    try:
        content_path = resolve_link(path, document.get("content_file"), root, "content")
    except ContractError as exc:
        result.error("config.content_link", label, str(exc))
        return result
    content_doc = _load_document(content_path, result, str(content_path))
    if content_doc is None:
        return result
    known_content = content_ref_ids(content_doc)
    must_refs = must_content_refs(content_doc)

    pages = plan_pages(document)
    page_ids: set[str] = set()
    block_ids: set[str] = set()
    assertion_titles: dict[str, str] = {}
    takeaways: dict[str, str] = {}
    total_refs: set[str] = set()
    page_ref_map: dict[str, set[str]] = {}
    section_ids: set[str] = set()
    for section_index, section in enumerate(_as_list(document.get("sections"))):
        if not isinstance(section, dict):
            continue
        section_id = _identifier(section, "section_id", "id")
        if section_id in section_ids:
            result.error(
                "plan.duplicate_section",
                f"{label}#.sections[{section_index}]",
                f"section_id 重复：{section_id}",
            )
        elif section_id:
            section_ids.add(section_id)
    orders: list[int] = []
    for index, page in enumerate(pages):
        item_path = f"{label}#.pages[{index}]"
        page_id = _identifier(page, "page_id", "id", "slide_id")
        if not page_id:
            result.error("plan.page_id", item_path, "页面缺少 page_id")
        elif page_id in page_ids:
            result.error("plan.duplicate_page", item_path, f"page_id 重复：{page_id}")
        else:
            page_ids.add(page_id)
        order = page.get("order")
        if isinstance(order, int):
            orders.append(order)
        section_id = page.get("section_id")
        if section_id not in section_ids:
            result.error("plan.unknown_section", item_path, f"页面引用了未知 section_id：{section_id}")
        refs = page_content_refs(page)
        total_refs.update(refs)
        if page_id:
            page_ref_map[page_id] = set(refs)
        role = page.get("role")
        for field_name, seen_values, duplicate_code, blank_code in (
            ("assertion_title", assertion_titles, "plan.duplicate_assertion", "plan.blank_assertion"),
            ("takeaway", takeaways, "plan.duplicate_takeaway", "plan.blank_takeaway"),
        ):
            raw_value = page.get(field_name)
            if not isinstance(raw_value, str) or not raw_value.strip():
                result.error(blank_code, item_path, f"{field_name} 不能为空或纯空白")
                continue
            normalized_value = "".join(
                character
                for character in unicodedata.normalize("NFKC", raw_value).casefold()
                if character.isalnum()
            )
            previous_page = seen_values.get(normalized_value)
            if previous_page:
                result.error(duplicate_code, item_path, f"{field_name} 与 {previous_page} 重复：{raw_value!r}")
            elif normalized_value:
                seen_values[normalized_value] = page_id or f"pages[{index}]"
        if role not in STRUCTURAL_ROLES and not refs:
            result.error("plan.ghost_page", item_path, "非结构页没有引用任何 content_items，属于空壳页")
        for ref in refs:
            if ref not in known_content:
                result.error("plan.unknown_content", item_path, f"引用了未知 content_ref：{ref}")
        declared_refs = set(_ref_list(page.get("content_refs")) + _ref_list(page.get("evidence_refs")))
        block_refs: set[str] = set()
        primary_blocks = 0
        for block_index, block in enumerate(_as_list(page.get("blocks"))):
            if not isinstance(block, dict):
                continue
            block_path = f"{item_path}.blocks[{block_index}]"
            block_id = _identifier(block, "block_id", "id")
            if not block_id:
                result.error("plan.block_id", block_path, "block 缺少 block_id")
            elif block_id in block_ids:
                result.error("plan.duplicate_block", block_path, f"block_id 重复：{block_id}")
            else:
                block_ids.add(block_id)
            if block.get("importance") == "primary":
                primary_blocks += 1
            current_refs = set(_ref_list(block.get("content_refs")))
            block_refs.update(current_refs)
            for ref in current_refs - declared_refs:
                result.error(
                    "plan.block_content_mismatch",
                    block_path,
                    f"block 引用 {ref}，但 page.content_refs/evidence_refs 未声明",
                )
        if primary_blocks != 1:
            result.error("plan.primary_block", item_path, f"每页必须恰好一个 primary block，实际 {primary_blocks}")
        for ref in sorted(declared_refs - block_refs):
            result.error("plan.unmapped_content", item_path, f"页面内容 {ref} 未进入任何 semantic block")
    if not pages:
        result.error("plan.empty", label, "pages[] 不能为空")
    elif not total_refs:
        result.error("plan.ghost_deck", label, "整份 deck 没有引用任何 content_items")
    if orders:
        expected_orders = list(range(1, len(pages) + 1))
        if sorted(orders) != expected_orders:
            result.error("plan.page_order", label, f"page order 必须连续且唯一：期望 {expected_orders}，实际 {sorted(orders)}")

    budget = document.get("page_budget") if isinstance(document.get("page_budget"), dict) else {}
    minimum = budget.get("min")
    maximum = budget.get("max")
    target = budget.get("target")
    if isinstance(minimum, int) and isinstance(maximum, int) and minimum > maximum:
        result.error("plan.page_budget", f"{label}#.page_budget", "min 不能大于 max")
    if isinstance(target, int) and isinstance(minimum, int) and isinstance(maximum, int):
        if not minimum <= target <= maximum:
            result.error("plan.page_budget", f"{label}#.page_budget.target", "target 必须落在 min/max 内")
        if target != len(pages):
            result.error("plan.page_budget", f"{label}#.page_budget.target", f"target={target}，实际 pages={len(pages)}")

    brief = content_doc.get("brief") if isinstance(content_doc.get("brief"), dict) else {}

    for section_index, section in enumerate(_as_list(document.get("sections"))):
        if not isinstance(section, dict):
            continue
        for ref in _ref_list(section.get("page_refs")):
            if ref not in page_ids:
                result.error(
                    "plan.unknown_page",
                    f"{label}#.sections[{section_index}]",
                    f"section 引用了未知 page_ref：{ref}",
                )
        section_id = _identifier(section, "section_id", "id")
        actual = {
            _identifier(page, "page_id", "id")
            for page in pages
            if page.get("section_id") == section_id
        }
        declared = set(_ref_list(section.get("page_refs")))
        if actual != declared:
            result.error(
                "plan.section_membership",
                f"{label}#.sections[{section_index}]",
                f"section.page_refs 与 pages[].section_id 不一致：声明 {sorted(declared)}，实际 {sorted(actual)}",
            )

    decisions_by_ref: dict[str, Mapping[str, Any]] = {}
    for decision_index, decision in enumerate(_as_list(document.get("coverage_decisions"))):
        if not isinstance(decision, dict):
            continue
        decision_path = f"{label}#.coverage_decisions[{decision_index}]"
        content_ref = decision.get("content_ref")
        if isinstance(content_ref, str):
            if content_ref in decisions_by_ref:
                result.error("plan.duplicate_coverage", decision_path, f"coverage_decision 重复：{content_ref}")
            decisions_by_ref[content_ref] = decision
        disposition = decision.get("disposition")
        page_refs = _ref_list(decision.get("page_refs"))
        if content_ref not in known_content:
            result.error("plan.coverage_unknown_content", decision_path, f"未知 content_ref：{content_ref}")
        if disposition == "include" and not page_refs:
            result.error("plan.coverage_page_refs", decision_path, "disposition=include 必须声明 page_refs")
        for page_ref in page_refs:
            if page_ref not in page_ids:
                result.error("plan.coverage_unknown_page", decision_path, f"未知 page_ref：{page_ref}")
            else:
                referenced = page_ref_map.get(page_ref, set())
                if content_ref not in referenced:
                    result.error(
                        "plan.coverage_mismatch",
                        decision_path,
                        f"page_refs 包含 {page_ref}，但该页未实际引用 {content_ref}",
                    )
    for ref in sorted(must_refs):
        decision = decisions_by_ref.get(ref)
        if decision is None:
            result.error("plan.must_decision", label, f"must 内容缺少 coverage_decision：{ref}")
        elif decision.get("disposition") != "include":
            result.error("plan.must_decision", label, f"must 内容必须 include：{ref}")
        if ref not in total_refs:
            result.error("plan.must_coverage", label, f"must 内容未进入任何页面：{ref}")

    # Adaptive confirmation is a deterministic gate, not a conversational
    # suggestion.  Derive every machine-observable trigger from the contracts
    # and require the plan to acknowledge it before rendering.
    required_triggers: set[str] = set()
    objective = brief.get("objective")
    audience = brief.get("audience")
    if (
        not isinstance(objective, str)
        or not objective.strip()
        or not isinstance(audience, str)
        or not audience.strip()
    ):
        required_triggers.add("missing_objective_or_audience")
    if any(
        relation.get("type") == "contradicts"
        for item in content_items(content_doc)
        for relation in _as_list(item.get("relations"))
        if isinstance(relation, dict)
    ):
        required_triggers.add("source_conflict")

    uncertain_must = {
        _identifier(item, "id", "content_id")
        for item in content_items(content_doc)
        if item.get("priority") == "must" and item.get("status") in {"inferred", "placeholder"}
    }
    removed_must = {
        ref
        for ref in must_refs
        if isinstance(decisions_by_ref.get(ref), dict)
        and decisions_by_ref[ref].get("disposition") in {"defer", "omit"}
    }
    if uncertain_must or removed_must:
        required_triggers.add("must_infer_or_placeholder_or_remove")

    content_limits = brief.get("page_limits") if isinstance(brief.get("page_limits"), dict) else {}
    content_max = content_limits.get("max")
    drivers = [driver for driver in _as_list(budget.get("drivers")) if isinstance(driver, dict)]
    page_limit_overflow = any(
        driver.get("type") == "page_limit"
        and isinstance(driver.get("count"), int)
        and isinstance(content_max, int)
        and driver["count"] > content_max
        for driver in drivers
    )
    must_missing_at_capacity = (
        isinstance(maximum, int)
        and len(pages) >= maximum
        and bool(must_refs - total_refs)
    )
    if page_limit_overflow or must_missing_at_capacity:
        required_triggers.add("must_content_overflow")

    requested_pages = content_limits.get("requested")
    has_raw_prose = any(
        source.get("kind") == "raw_text"
        for source in _as_list(content_doc.get("sources"))
        if isinstance(source, dict)
    )
    if isinstance(target, int) and target >= 16 and requested_pages is None and has_raw_prose:
        required_triggers.add("raw_prose_16_plus")

    confirmation = document.get("confirmation") if isinstance(document.get("confirmation"), dict) else {}
    confirmation_decision = confirmation.get("decision")
    declared_triggers = set(_strings(confirmation.get("triggers")))
    for trigger in sorted(required_triggers - declared_triggers):
        result.error(
            "plan.confirmation_trigger",
            f"{label}#.confirmation",
            f"检测到 {trigger}，必须声明该 trigger",
        )
    for trigger in sorted(declared_triggers - required_triggers):
        result.error(
            "plan.confirmation_spurious_trigger",
            f"{label}#.confirmation",
            f"未检测到 {trigger}，不得机械暂停制作",
        )
    expected_confirmation_decision = "needs_confirmation" if required_triggers else "proceed"
    if confirmation_decision != expected_confirmation_decision:
        result.error(
            "plan.confirmation_decision",
            f"{label}#.confirmation.decision",
            f"根据派生 triggers，decision 必须为 {expected_confirmation_decision!r}",
        )
    if required_triggers and not _strings(confirmation.get("questions")):
        result.error(
            "plan.confirmation_questions",
            f"{label}#.confirmation.questions",
            "needs_confirmation 必须给出至少一个可回答的问题",
        )
    return result


def validate_plan_target(target: Path, root: Path) -> ValidationResult:
    result = ValidationResult()
    try:
        path = find_document(target, "plan")
    except ContractError as exc:
        result.error("config.plan", str(target), str(exc))
        return result
    document = _load_document(path, result, str(path))
    if document is not None:
        result.extend(validate_plan_document(document, path, root))
    return result


def _relation_primary(page: Mapping[str, Any]) -> str | None:
    value = page.get("relation_shape") or page.get("relation")
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        primary = value.get("primary") or value.get("type")
        return str(primary) if primary else None
    return None


def _meaningful_rationale(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = re.sub(r"\s+", "", value).casefold()
    if len(normalized) < 10:
        return False
    copy_words = ("照抄", "抄模板", "套模板", "复制模板", "直接copy", "copytemplate", "sameastemplate")
    if any(word in normalized for word in copy_words) and len(normalized) < 32:
        return False
    return True


def _capacity_bound(capacity: Mapping[str, Any], name: str, bound: str) -> int | None:
    value = capacity.get(name)
    if isinstance(value, dict) and isinstance(value.get(bound), int):
        return value[bound]
    aliases = {
        ("semantic_units", "max"): ("max_items", "max_units", "max_content_items"),
        ("semantic_units", "min"): ("min_items", "min_units", "min_content_items"),
        ("primary_items", "max"): ("max_primary_items",),
        ("primary_items", "min"): ("min_primary_items",),
    }
    for key in aliases.get((name, bound), ()):
        if isinstance(capacity.get(key), int):
            return capacity[key]
    return None


class AttributeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs if name.startswith("data-")}
        if values:
            values["__tag__"] = tag
            self.elements.append(values)


def parse_html_attributes(path: Path) -> list[dict[str, str]]:
    parser = AttributeParser()
    try:
        parser.feed(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise ContractError(f"HTML 无法读取：{path}: {exc}") from exc
    return parser.elements


def _html_path_for_page(
    page: Mapping[str, Any],
    page_id: str,
    render_path: Path,
    html_index: Mapping[str, Path],
) -> Path | None:
    for key in ("html_file", "html_path", "output_file", "file"):
        value = page.get(key)
        if isinstance(value, str) and value:
            candidate = Path(value)
            if not candidate.is_absolute():
                candidate = render_path.parent / candidate
            return candidate.resolve()
    attrs = page.get("html_attributes") if isinstance(page.get("html_attributes"), dict) else {}
    declared = attrs.get("data-html-path")
    if isinstance(declared, str) and declared:
        candidate = Path(declared)
        if not candidate.is_absolute():
            candidate = render_path.parent / candidate
        return candidate.resolve()
    if page_id in html_index:
        return html_index[page_id]
    for candidate in (
        render_path.parent / "frames" / f"{page_id}.html",
        render_path.parent / "pages" / f"{page_id}.html",
        render_path.parent / f"{page_id}.html",
    ):
        if candidate.is_file():
            return candidate.resolve()
    return None


def _build_html_index(directory: Path) -> dict[str, Path]:
    output: dict[str, Path] = {}
    if not directory.is_dir():
        return output
    for path in sorted(directory.rglob("*.html")):
        try:
            elements = parse_html_attributes(path)
        except ContractError:
            continue
        for attrs in elements:
            page_id = attrs.get("data-page-id") or attrs.get("data-slide-id")
            if page_id and page_id not in output:
                output[page_id] = path.resolve()
    return output


def _layout_slot_map(layout: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    output: dict[str, Mapping[str, Any]] = {}
    for slot in layout.get("slots", []):
        if isinstance(slot, dict):
            slot_id = _identifier(slot, "slot_id", "id")
            if slot_id:
                output[slot_id] = slot
    return output


def _validate_html_page(
    page: Mapping[str, Any],
    page_id: str,
    layout_id: str,
    theme_id: str,
    render_path: Path,
    html_index: Mapping[str, Path],
    result: ValidationResult,
    item_path: str,
) -> None:
    html_path = _html_path_for_page(page, page_id, render_path, html_index)
    if html_path is None or not html_path.is_file():
        result.error("render.html_missing", item_path, f"找不到 page_id={page_id} 对应的 HTML 文件")
        return
    try:
        elements = parse_html_attributes(html_path)
    except ContractError as exc:
        result.error("config.html", item_path, str(exc))
        return
    declared = page.get("html_attributes") if isinstance(page.get("html_attributes"), dict) else {}
    expected = {str(key): str(value) for key, value in declared.items() if str(key).startswith("data-")}
    page_element = next(
        (
            attrs
            for attrs in elements
            if attrs.get("data-page-id", attrs.get("data-slide-id")) == page_id
        ),
        None,
    )
    if page_element is None:
        result.error("render.html_page_data", str(html_path), f"缺少 data-page-id={page_id!r} 的页面声明")
    else:
        for key, expected_value in expected.items():
            if page_element.get(key) != str(expected_value):
                result.error(
                    "render.html_page_data",
                    str(html_path),
                    f"页面声明 {key} 应为 {expected_value!r}，实际为 {page_element.get(key)!r}",
                )

    for slot in _as_list(page.get("slots")):
        if not isinstance(slot, dict):
            continue
        block_id = _identifier(slot, "block_id")
        renderer = slot.get("renderer") if isinstance(slot.get("renderer"), dict) else {}
        provider = renderer.get("provider")
        component = renderer.get("component") or renderer.get("component_id")
        refs = set(slot_content_refs(slot))
        matching = [attrs for attrs in elements if attrs.get("data-block-id") == block_id]
        if not matching:
            result.error("render.html_component_data", str(html_path), f"block {block_id!r} 缺少组件 data-* 声明")
            continue
        attrs = matching[0]
        checks = {
            "data-provider": provider,
            "data-component": component,
        }
        for key, expected_value in checks.items():
            if expected_value is not None and attrs.get(key) != str(expected_value):
                result.error(
                    "render.html_component_data",
                    str(html_path),
                    f"block {block_id!r} 的 {key} 应为 {expected_value!r}，实际为 {attrs.get(key)!r}",
                )
        actual_refs = set((attrs.get("data-content-ref") or "").split())
        if actual_refs != refs:
            result.error(
                "render.html_content_refs",
                str(html_path),
                f"block {block_id!r} 的 data-content-ref 应为 {sorted(refs)}，实际为 {sorted(actual_refs)}",
            )


def validate_render_document(document: Mapping[str, Any], path: Path, root: Path) -> ValidationResult:
    label = str(path)
    result = validate_against_schema(root, "render", document, label)
    try:
        content_path = resolve_link(path, document.get("content_file"), root, "content")
        plan_path = resolve_link(path, document.get("deck_plan_file") or document.get("plan_file"), root, "plan")
    except ContractError as exc:
        result.error("config.render_link", label, str(exc))
        return result
    content_doc = _load_document(content_path, result, str(content_path))
    plan_doc = _load_document(plan_path, result, str(plan_path))
    if content_doc is None or plan_doc is None:
        return result

    confirmation = plan_doc.get("confirmation") if isinstance(plan_doc.get("confirmation"), dict) else {}
    if confirmation.get("decision") != "proceed":
        result.error(
            "render.confirmation_required",
            str(plan_path),
            "deck plan 尚未获得 proceed 决策，必须停止进入 render",
        )
        return result

    requested_theme = document.get("theme_id") or document.get("theme")
    try:
        theme, layouts, _ = load_layout_catalog(root, str(requested_theme) if requested_theme else None)
    except ContractError as exc:
        code = "render.unknown_theme" if "未知" in str(exc) else "config.theme"
        result.error(code, label, str(exc))
        return result
    layout_by_id = {record["id"]: record for record in layouts}
    known_content = content_ref_ids(content_doc)
    plan_by_id = {
        _identifier(page, "page_id", "id", "slide_id"): page
        for page in plan_pages(plan_doc)
        if _identifier(page, "page_id", "id", "slide_id")
    }
    html_index = _build_html_index(path.parent)
    seen_pages: set[str] = set()
    atlas_records: list[dict[str, Any]] | None = None

    for index, page in enumerate(render_pages(document)):
        item_path = f"{label}#.pages[{index}]"
        page_id = _identifier(page, "page_id", "id", "slide_id")
        if not page_id:
            result.error("render.page_id", item_path, "页面缺少 page_id")
            continue
        if page_id in seen_pages:
            result.error("render.duplicate_page", item_path, f"page_id 重复：{page_id}")
        seen_pages.add(page_id)
        plan_page = plan_by_id.get(page_id)
        if plan_page is None:
            result.error("render.unknown_page", item_path, f"找不到对应的 deck page：{page_id}")
            continue

        layout_id = _identifier(page, "layout_id", "layout")
        if not layout_id:
            result.error("render.layout_id", item_path, "页面缺少 layout_id")
            continue
        layout = layout_by_id.get(layout_id)
        reuse_mode = page.get("reuse_mode")
        if layout is None:
            result.error("render.unsupported_layout", item_path, f"主题未登记 layout_id：{layout_id}")

        plan_primitive = plan_page.get("spatial_primitive")
        core_primitive = page.get("core_primitive")
        if core_primitive != plan_primitive:
            result.error(
                "render.core_primitive_mismatch",
                item_path,
                f"core_primitive 必须等于 deck spatial_primitive：期望 {plan_primitive!r}，实际 {core_primitive!r}",
            )
        theme_primitives = _strings(page.get("theme_primitives"))
        if not theme_primitives:
            result.error("render.theme_primitives", item_path, "theme_primitives 必须至少声明一个主题实现原语")
        if layout is not None:
            supported_core_primitives = set(layout.get("core_primitives", []))
            if core_primitive not in supported_core_primitives:
                result.error(
                    "render.unsupported_core_primitive",
                    item_path,
                    f"布局 {layout_id} 不支持 core_primitive={core_primitive!r}；"
                    f"允许 {sorted(supported_core_primitives)}",
                )
            if theme_primitives:
                declared_primitives = set(layout.get("primitives", []))
                unsupported_primitives = set(theme_primitives) - declared_primitives
                if unsupported_primitives:
                    result.error(
                        "render.unknown_theme_primitive",
                        item_path,
                        f"reuse_mode={reuse_mode!r} 使用了 layout manifest 未声明的原语 "
                        f"{sorted(unsupported_primitives)}；novel 也必须先登记新 layout/primitives "
                        "再生成 Render Plan",
                    )

        rationale = page.get("rationale")
        if not _meaningful_rationale(rationale):
            result.error("render.copy_rationale", item_path, "rationale 必须解释内容关系、容量或表达选择，不能只写照抄模板")
        if reuse_mode == "copy" and not page.get("reuse_source"):
            result.error("render.copy_source", item_path, "reuse_mode=copy 必须声明 reuse_source")

        status = page.get("capacity_status")
        if status != "fit":
            result.error("render.capacity_status", item_path, f"capacity_status 必须为 'fit'，实际为 {status!r}")

        role = plan_page.get("role")
        relation = _relation_primary(plan_page)
        density = page.get("density") or plan_page.get("density_intent")
        if layout is not None:
            if layout["roles"] and role not in layout["roles"]:
                result.error("render.unsupported_role", item_path, f"布局 {layout_id} 不支持 role={role!r}")
            if layout["relations"] and relation not in layout["relations"]:
                result.error("render.unsupported_relation", item_path, f"布局 {layout_id} 不支持 relation={relation!r}")
            if layout["densities"] and density not in layout["densities"]:
                result.error("render.unsupported_density", item_path, f"布局 {layout_id} 不支持 density={density!r}")

        plan_refs = set(page_content_refs(plan_page))
        rendered_refs = set(render_page_content_refs(page))
        for ref in sorted(rendered_refs):
            if ref not in known_content:
                result.error("render.unknown_content", item_path, f"渲染引用了未知 content_ref：{ref}")
            elif ref not in plan_refs:
                result.error("render.unplanned_content", item_path, f"渲染引用 {ref}，但 deck page 未规划该内容")
        for ref in sorted(plan_refs - rendered_refs):
            result.error("render.missing_content", item_path, f"deck page 规划的 {ref} 没有进入任何渲染槽位")

        plan_blocks = {
            _identifier(block, "block_id", "id")
            for block in _as_list(plan_page.get("blocks"))
            if isinstance(block, dict) and _identifier(block, "block_id", "id")
        }
        slots = [slot for slot in _as_list(page.get("slots")) if isinstance(slot, dict)]
        slot_ids: set[str] = set()
        mapped_blocks: set[str] = set()
        primary_visuals = 0
        layout_slots = _layout_slot_map(layout) if layout else {}
        primary_items = 0
        for slot_index, slot in enumerate(slots):
            slot_path = f"{item_path}.slots[{slot_index}]"
            slot_id = _identifier(slot, "slot_id", "id")
            block_id = _identifier(slot, "block_id")
            if not slot_id:
                result.error("render.slot_id", slot_path, "槽位缺少 slot_id")
                continue
            if slot_id in slot_ids:
                result.error("render.duplicate_slot", slot_path, f"slot_id 重复：{slot_id}")
            slot_ids.add(slot_id)
            if block_id not in plan_blocks:
                result.error("render.unknown_block", slot_path, f"block_id 未在 deck page 声明：{block_id}")
            elif block_id in mapped_blocks:
                result.error("render.duplicate_block_mapping", slot_path, f"block_id 被多个 slot 使用：{block_id}")
            else:
                mapped_blocks.add(block_id)
            if slot.get("visual_role") == "primary":
                primary_visuals += 1
            slot_spec = layout_slots.get(slot_id) if layout else None
            if layout and slot_spec is None:
                result.error("render.unsupported_slot", slot_path, f"布局 {layout_id} 不支持 slot_id={slot_id!r}")
            renderer = slot.get("renderer") if isinstance(slot.get("renderer"), dict) else {}
            provider = renderer.get("provider")
            if provider not in PROVIDERS:
                result.error("render.provider", slot_path, f"未知 provider：{provider!r}")
            if slot_spec:
                allowed = _strings(slot_spec.get("allowed_providers"))
                if allowed and provider not in allowed:
                    result.error(
                        "render.unsupported_provider",
                        slot_path,
                        f"slot {slot_id} 不支持 provider={provider!r}；允许 {allowed}",
                    )
            refs = slot_content_refs(slot)
            item_count = len(refs)
            if renderer.get("data_ref") and not refs:
                item_count += 1
            if slot_spec:
                minimum = slot_spec.get("min_items")
                maximum = slot_spec.get("max_items")
                if isinstance(minimum, int) and item_count < minimum:
                    result.error("render.slot_underfill", slot_path, f"槽位至少需要 {minimum} 项，实际 {item_count}")
                if isinstance(maximum, int) and item_count > maximum:
                    result.error("render.slot_overflow", slot_path, f"槽位最多允许 {maximum} 项，实际 {item_count}")
                if slot_spec.get("required") and item_count == 0 and minimum != 0:
                    result.error("render.required_slot_empty", slot_path, "必填槽位不能为空")
            if slot.get("visual_role") == "primary":
                primary_items += item_count

            component = renderer.get("component") or renderer.get("component_id")
            if provider == "echarts":
                if not renderer.get("data_ref"):
                    result.error("render.echarts_data_ref", slot_path, "ECharts renderer 必须声明 data_ref")
                if not isinstance(renderer.get("encode"), dict) or not renderer.get("encode"):
                    result.error("render.echarts_encode", slot_path, "ECharts renderer 必须声明非空 encode")
            if provider == "atlas":
                if not component:
                    result.error("render.atlas_component", slot_path, "provider=atlas 必须声明 component")
                else:
                    if atlas_records is None:
                        try:
                            _, atlas_records, _ = load_component_catalog(root, theme.theme_id)
                        except ContractError as exc:
                            result.error("config.component_catalog", slot_path, str(exc))
                            atlas_records = []
                    aliases = {
                        str(alias).casefold()
                        for record in atlas_records
                        for alias in (record.get("id"), record.get("canonical_name"), record.get("name"), *(record.get("aliases") or []))
                        if alias
                    }
                    if str(component).casefold() not in aliases:
                        result.error("render.unknown_component", slot_path, f"atlas catalog 中不存在组件 {component!r}")

            block = next(
                (
                    candidate
                    for candidate in _as_list(plan_page.get("blocks"))
                    if isinstance(candidate, dict) and _identifier(candidate, "block_id", "id") == block_id
                ),
                None,
            )
            if block is not None:
                expected_refs = set(_ref_list(block.get("content_refs")))
                if set(refs) != expected_refs:
                    result.error(
                        "render.block_content_mismatch",
                        slot_path,
                        f"renderer.content_refs 应与 block 一致：期望 {sorted(expected_refs)}，实际 {sorted(set(refs))}",
                    )

        for missing_block in sorted(plan_blocks - mapped_blocks):
            result.error("render.missing_block", item_path, f"deck block 未映射到 render slot：{missing_block}")
        if primary_visuals != 1:
            result.error("render.primary_visual", item_path, f"每页必须恰好一个 primary visual_role，实际 {primary_visuals}")

        if layout is not None:
            for required_id, spec in layout_slots.items():
                if spec.get("required") and required_id not in slot_ids:
                    result.error("render.required_slot", item_path, f"缺少布局必填槽位：{required_id}")
            semantic_count = len(plan_refs)
            capacity = layout.get("capacity", {})
            semantic_min = _capacity_bound(capacity, "semantic_units", "min")
            semantic_max = _capacity_bound(capacity, "semantic_units", "max")
            primary_min = _capacity_bound(capacity, "primary_items", "min")
            primary_max = _capacity_bound(capacity, "primary_items", "max")
            if semantic_min is not None and semantic_count < semantic_min:
                result.error("render.capacity_underfill", item_path, f"语义单元至少 {semantic_min} 个，实际 {semantic_count}")
            if semantic_max is not None and semantic_count > semantic_max:
                result.error("render.capacity_overflow", item_path, f"语义单元最多 {semantic_max} 个，实际 {semantic_count}")
            if primary_min is not None and primary_items < primary_min:
                result.error("render.primary_underfill", item_path, f"主项至少 {primary_min} 个，实际 {primary_items}")
            if primary_max is not None and primary_items > primary_max:
                result.error("render.primary_overflow", item_path, f"主项最多 {primary_max} 个，实际 {primary_items}")

        attrs = page.get("html_attributes")
        if not isinstance(attrs, dict):
            result.error("render.html_attributes", item_path, "必须声明 html_attributes 对象")
        else:
            expected_attrs = {
                "data-page-id": page_id,
                "data-page-role": role,
                "data-theme": theme.theme_id,
                "data-layout": layout_id,
                "data-density": density,
                "data-reuse-mode": reuse_mode,
            }
            for key, expected_value in expected_attrs.items():
                if attrs.get(key) != expected_value:
                    result.error("render.html_attributes", item_path, f"{key} 必须为 {expected_value!r}")
        _validate_html_page(page, page_id, layout_id, theme.theme_id, path, html_index, result, item_path)

    missing_pages = sorted(set(plan_by_id) - seen_pages)
    for page_id in missing_pages:
        result.error("render.missing_page", label, f"deck page 未进入 render plan：{page_id}")
    return result


def validate_render_target(target: Path, root: Path) -> ValidationResult:
    result = ValidationResult()
    try:
        path = find_document(target, "render")
    except ContractError as exc:
        result.error("config.render", str(target), str(exc))
        return result
    document = _load_document(path, result, str(path))
    if document is not None:
        result.extend(validate_render_document(document, path, root))
    return result


def validate_coverage_target(target: Path, root: Path) -> ValidationResult:
    result = ValidationResult()
    try:
        plan_path = find_document(target, "plan")
        plan_doc = load_json(plan_path)
        content_path = resolve_link(plan_path, plan_doc.get("content_file"), root, "content")
        content_doc = load_json(content_path)
    except ContractError as exc:
        result.error("config.coverage", str(target), str(exc))
        return result
    if not isinstance(plan_doc, dict) or not isinstance(content_doc, dict):
        result.error("coverage.document", str(target), "coverage 输入必须是 JSON 对象")
        return result
    must_ids = must_content_refs(content_doc)
    planned = {ref for page in plan_pages(plan_doc) for ref in page_content_refs(page)}
    blocked = {
        ref
        for page in plan_pages(plan_doc)
        for block in _as_list(page.get("blocks"))
        if isinstance(block, dict)
        for ref in _ref_list(block.get("content_refs"))
    }
    for ref in sorted(must_ids - planned):
        result.error("coverage.must_missing_plan", str(plan_path), f"must 内容未进入 deck plan：{ref}")
    for ref in sorted(must_ids - blocked):
        result.error("coverage.must_missing_block", str(plan_path), f"must 内容未进入 semantic block：{ref}")

    decisions = {
        decision.get("content_ref"): decision
        for decision in _as_list(plan_doc.get("coverage_decisions"))
        if isinstance(decision, dict) and decision.get("content_ref")
    }
    for ref in sorted(must_ids):
        decision = decisions.get(ref)
        if decision is None:
            result.error("coverage.must_decision", str(plan_path), f"must 内容缺少 coverage_decision：{ref}")
        elif decision.get("disposition") != "include":
            result.error(
                "coverage.must_disposition",
                str(plan_path),
                f"must 内容 {ref} 的 disposition 不能是 {decision.get('disposition')!r}",
            )

    render_path = find_document(target, "render", required=False)
    if render_path:
        try:
            render_doc = load_json(render_path)
        except ContractError as exc:
            result.error("config.coverage_render", str(render_path), str(exc))
            return result
        if isinstance(render_doc, dict):
            rendered = {ref for page in render_pages(render_doc) for ref in render_page_content_refs(page)}
            for ref in sorted(must_ids - rendered):
                result.error("coverage.must_missing_render", str(render_path), f"must 内容未进入 render plan：{ref}")
            html_refs: set[str] = set()
            html_text_by_ref: dict[str, list[str]] = {}
            for page in render_pages(render_doc):
                page_id = _identifier(page, "page_id", "id") or "<unknown>"
                output_file = page.get("output_file")
                if not isinstance(output_file, str):
                    continue
                html_path = (render_path.parent / output_file).resolve()
                if not html_path.is_file():
                    result.error("coverage.html_missing", page_id, f"output_file 不存在：{html_path}")
                    continue
                try:
                    source = html_path.read_text(encoding="utf-8")
                    elements = parse_html_attributes(html_path)
                except (OSError, UnicodeDecodeError, ContractError) as exc:
                    result.error("config.coverage_html", str(html_path), str(exc))
                    continue
                for attrs in elements:
                    refs = (attrs.get("data-content-ref") or "").split()
                    html_refs.update(refs)
                    for ref in refs:
                        html_text_by_ref.setdefault(ref, []).append(source)
            for ref in sorted(must_ids - html_refs):
                result.error("coverage.must_missing_html", str(render_path), f"must 内容未进入 HTML data-content-ref：{ref}")

            atomic_values: dict[str, Any] = {}
            for item in content_items(content_doc):
                for atomic in _as_list(item.get("atomic_values")):
                    if isinstance(atomic, dict):
                        atomic_id = _identifier(atomic, "id", "value_id")
                        if atomic_id:
                            atomic_values[atomic_id] = atomic.get("value")
            for ref in sorted(must_ids & set(atomic_values)):
                expected = atomic_values[ref]
                if expected is None:
                    continue
                sources = html_text_by_ref.get(ref, [])
                if sources and not any(str(expected) in source for source in sources):
                    result.error(
                        "coverage.atomic_value_missing",
                        ref,
                        f"HTML 声明了 {ref}，但未找到原子值 {expected!r}",
                    )
    for item in content_items(content_doc):
        if item.get("status") in {"inferred", "placeholder"}:
            result.warn(
                "coverage.unverified_content",
                _identifier(item, "id", "content_id") or str(content_path),
                f"{item.get('status')} 内容必须在人工复核时显式确认：{item.get('status_note', '')}",
            )
    return result


def _resolve_example(root: Path, manifest_path: Path, value: str) -> Path:
    raw = Path(value)
    candidates = [raw] if raw.is_absolute() else [root / raw, manifest_path.parent / raw]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return candidates[0].resolve()


def validate_gallery(root: Path, theme_id: str | None = None) -> ValidationResult:
    result = ValidationResult()
    try:
        theme, layouts, manifest = load_layout_catalog(root, theme_id)
    except ContractError as exc:
        result.error("config.gallery", str(root), str(exc))
        return result
    manifest_path = theme.layout_manifest_path
    declared_count = manifest.get("layout_count")
    valid_declared_count = (
        isinstance(declared_count, int)
        and not isinstance(declared_count, bool)
        and declared_count > 0
    )
    if not valid_declared_count:
        result.error("gallery.layout_count", str(manifest_path), "layout_count 必须是正整数")
    elif declared_count != len(layouts):
        result.error(
            "gallery.layout_count",
            str(manifest_path),
            f"layout_count={declared_count!r}，实际 layouts[]={len(layouts)}",
        )
    if not layouts:
        result.error("gallery.empty", str(manifest_path), "layouts[] 不能为空")
    expected_count = declared_count if valid_declared_count else len(layouts)
    ids = [record["id"] for record in layouts]
    if len(ids) != len(set(ids)):
        result.error("gallery.duplicate_id", str(manifest_path), "layout_id 必须唯一")
    codes = [record.get("display_code") for record in layouts if record.get("display_code")]
    if len(codes) != len(set(codes)):
        result.error("gallery.duplicate_code", str(manifest_path), "display_code 必须唯一")

    declared_densities = set(_strings(manifest.get("density_levels")))
    declared_providers = set(_strings(manifest.get("provider_ids")))
    declared_core_primitive_list = _strings(manifest.get("core_primitive_ids"))
    declared_core_primitives = set(declared_core_primitive_list)
    if (
        declared_core_primitives != CORE_PRIMITIVES
        or len(declared_core_primitive_list) != len(CORE_PRIMITIVES)
    ):
        result.error(
            "gallery.core_primitive_ids",
            str(manifest_path),
            "core_primitive_ids 必须精确登记 Core 12 个空间原语；"
            f"实际条目数 {len(declared_core_primitive_list)}，"
            f"缺少 {sorted(CORE_PRIMITIVES - declared_core_primitives)}，"
            f"多出 {sorted(declared_core_primitives - CORE_PRIMITIVES)}",
        )
    for record in layouts:
        record_path = f"{manifest_path}#{record['id']}"
        display_code = record.get("display_code")
        if display_code and str(display_code).casefold() in record["id"].casefold().split("."):
            result.error("gallery.display_code_as_id", record_path, "display_code 只能展示，不能成为稳定 layout_id")
        unknown_densities = set(record.get("densities", [])) - declared_densities
        if declared_densities and unknown_densities:
            result.error("gallery.unknown_density", record_path, f"未登记 density：{sorted(unknown_densities)}")
        primitives = record.get("primitives", [])
        core_primitives = record.get("core_primitives", [])
        if not core_primitives:
            result.error("gallery.core_primitives", record_path, "layout 必须声明至少一个 Core 空间原语")
        else:
            if len(core_primitives) > 3:
                result.error("gallery.core_primitives", record_path, "layout core_primitives 最多声明 3 个")
            unknown_core_primitives = set(core_primitives) - declared_core_primitives
            if unknown_core_primitives:
                result.error(
                    "gallery.unknown_core_primitive",
                    record_path,
                    f"未知 Core 空间原语：{sorted(unknown_core_primitives)}",
                )
            if len(core_primitives) != len(set(core_primitives)):
                result.error("gallery.duplicate_core_primitive", record_path, "layout core_primitives 不可重复")
        if not primitives:
            result.error("gallery.primitives", record_path, "layout 必须声明至少一个主题实现原语")
        elif len(primitives) != len(set(primitives)):
            result.error("gallery.duplicate_primitive", record_path, "layout primitives 不可重复")
        capacity = record.get("capacity", {})
        for capacity_key in ("semantic_units", "primary_items"):
            bounds = capacity.get(capacity_key) if isinstance(capacity, dict) else None
            if isinstance(bounds, dict):
                minimum = bounds.get("min")
                maximum = bounds.get("max")
                if isinstance(minimum, int) and isinstance(maximum, int) and minimum > maximum:
                    result.error("gallery.capacity", record_path, f"{capacity_key}.min 不能大于 max")
        slot_ids: set[str] = set()
        for slot in record.get("slots", []):
            if not isinstance(slot, dict):
                continue
            slot_id = _identifier(slot, "slot_id", "id")
            if not slot_id:
                result.error("gallery.slot_id", record_path, "layout slot 缺少 slot_id")
            elif slot_id in slot_ids:
                result.error("gallery.duplicate_slot", record_path, f"slot_id 重复：{slot_id}")
            else:
                slot_ids.add(slot_id)
            minimum = slot.get("min_items")
            maximum = slot.get("max_items")
            if isinstance(minimum, int) and isinstance(maximum, int) and minimum > maximum:
                result.error("gallery.slot_capacity", record_path, f"slot {slot_id} 的 min_items 不能大于 max_items")
            unknown_providers = set(_strings(slot.get("allowed_providers"))) - declared_providers
            if declared_providers and unknown_providers:
                result.error(
                    "gallery.unknown_provider",
                    record_path,
                    f"slot {slot_id} 使用未登记 provider：{sorted(unknown_providers)}",
                )

    galleries = theme.theme_document.get("galleries")
    if not isinstance(galleries, dict) or not galleries:
        result.error("gallery.index_paths", str(theme.theme_path), "主题必须声明非空 galleries 映射")
        galleries = {}
    manifest_variants = _strings(manifest.get("gallery_variants"))
    variants = manifest_variants or [str(name) for name in galleries]
    if manifest_variants and set(manifest_variants) != set(galleries):
        result.error(
            "gallery.variant_declaration",
            str(manifest_path),
            f"manifest gallery_variants 与 theme.galleries 不一致："
            f"{sorted(manifest_variants)} != {sorted(galleries)}",
        )
    if not variants:
        return result

    example_sets: dict[str, set[Path]] = {variant: set() for variant in variants}
    for record in layouts:
        examples = record.get("examples", {})
        undeclared_variants = set(examples) - set(variants) if isinstance(examples, dict) else set()
        if undeclared_variants:
            result.error(
                "gallery.undeclared_variant",
                record["id"],
                f"examples 包含 theme/manifest 未声明的变体：{sorted(undeclared_variants)}",
            )
        for variant in variants:
            value = examples.get(variant) if isinstance(examples, dict) else None
            if not isinstance(value, str) or not value:
                result.error("gallery.example_path", record["id"], f"缺少 examples.{variant} 路径")
                continue
            path = _resolve_example(root, manifest_path, value)
            example_sets[variant].add(path)
            if not path.is_file():
                result.error("gallery.example_missing", record["id"], f"画册文件不存在：{path}")

    for variant in variants:
        index_ref = galleries.get(variant)
        if not isinstance(index_ref, str):
            result.error("gallery.index_path", str(theme.theme_path), f"缺少 galleries.{variant}")
            continue
        index_path = _resolve_example(root, theme.theme_path, index_ref)
        if not index_path.is_file():
            result.error("gallery.index_missing", str(theme.theme_path), f"画册入口不存在：{index_path}")
            continue
        frame_dir = index_path.parent / "frames"
        actual = {path.resolve() for path in frame_dir.glob("*.html")} if frame_dir.is_dir() else set()
        if len(actual) != expected_count:
            result.error(
                "gallery.variant_count",
                str(frame_dir),
                f"{variant} 画册应有 layout_count={expected_count} 页，实际 {len(actual)}",
            )
        declared = example_sets[variant]
        missing_declared = sorted(str(path) for path in actual - declared)
        missing_files = sorted(str(path) for path in declared - actual)
        if missing_declared:
            result.error("gallery.unregistered_page", str(frame_dir), f"未登记页面：{', '.join(missing_declared)}")
        if missing_files:
            result.error("gallery.path_mismatch", str(frame_dir), f"manifest 路径不在画册目录：{', '.join(missing_files)}")
    total = sum(len(paths) for paths in example_sets.values())
    expected_total = expected_count * len(variants)
    if total != expected_total:
        result.error(
            "gallery.total_count",
            str(manifest_path),
            f"{len(variants)} 套画册应有 {expected_total} 条唯一示例路径，实际 {total}",
        )
    return result


CORE_STYLE_TOKENS = (
    "#dfe0d9",
    "#191917",
    "--paper",
    "--ink",
    "paper-ink",
    "纸墨",
    "线稿",
    "sourcehansans",
    "sourcehanserif",
    "courier prime",
    "lxgw wenkai",
)
LEGACY_CODE_RE = re.compile(r"(?<![A-Za-z0-9])(?:[A-O][1-9][0-9]?)(?![A-Za-z0-9])")


def validate_core_purity(root: Path) -> ValidationResult:
    result = ValidationResult()
    core = root / "core"
    if not core.is_dir():
        result.error("config.core", str(core), "缺少 core/ 目录")
        return result
    suffixes = {".md", ".json", ".py", ".js", ".html", ".css", ".txt", ".yaml", ".yml"}
    for path in sorted(item for item in core.rglob("*") if item.is_file() and item.suffix.lower() in suffixes):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        lowered = text.casefold()
        found_tokens = [token for token in CORE_STYLE_TOKENS if token in lowered]
        if found_tokens:
            result.error("core.theme_token", str(path), f"Core 含主题专属 token：{', '.join(found_tokens)}")
        codes = sorted(set(LEGACY_CODE_RE.findall(text)))
        if codes:
            result.error("core.legacy_code", str(path), f"Core 含画册短码：{', '.join(codes[:12])}")
    return result


def select_theme_for_target(target: Path, root: Path) -> str | None:
    render_path = find_document(target, "render", required=False)
    if render_path:
        try:
            document = load_json(render_path)
            if isinstance(document, dict):
                value = document.get("theme_id") or document.get("theme")
                if isinstance(value, str):
                    return value
        except ContractError:
            pass
    return None


def validate_gallery_target(target: Path, root: Path) -> ValidationResult:
    theme_id: str | None = None
    target_text = str(target)
    if not target.exists() and target_text not in {".", ""}:
        theme_id = target_text
    elif target.is_dir() and (target / "layout-manifest.json").is_file():
        try:
            manifest = load_json(target / "layout-manifest.json")
            if isinstance(manifest, dict):
                theme_id = manifest.get("theme_id")
        except ContractError:
            pass
    else:
        theme_id = select_theme_for_target(target, root)
    return validate_gallery(root, theme_id)


def validate_all(target: Path, root: Path) -> ValidationResult:
    result = ValidationResult()
    location = validate_output_location(target, root, allow_internal=True)
    result.extend(location)
    if not location.ok:
        return result
    result.extend(validate_content_target(target, root))
    result.extend(validate_plan_target(target, root))
    result.extend(validate_render_target(target, root))
    result.extend(validate_coverage_target(target, root))
    result.extend(validate_gallery_target(target, root))
    result.extend(validate_core_purity(root))
    return result


VALIDATORS = {
    "content": validate_content_target,
    "plan": validate_plan_target,
    "render": validate_render_target,
    "coverage": validate_coverage_target,
    "gallery": validate_gallery_target,
    "all": validate_all,
}


def run_validation(kind: str, target: Path, root: Path) -> ValidationResult:
    if kind not in VALIDATORS:
        raise ContractError(f"未知校验类型：{kind}")
    if kind in {"content", "plan", "render", "coverage"}:
        location = validate_output_location(target, root, allow_internal=True)
        if not location.ok:
            return location
    return VALIDATORS[kind](target, root)
