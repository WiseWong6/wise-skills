#!/usr/bin/env python3
"""Dependency-free v2 contracts for the Wise PPT command-line tools.

The three JSON schemas own document shape.  This module only validates facts
that cross files: references, planning decisions, public capability routing,
HTML bindings, reconstructed media and delivery files.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import unquote, urlparse


CONTRACT_VERSION = 2
SCHEMA_FILES = {
    "content": "content.schema.json",
    "plan": "deck-plan.schema.json",
    "render": "render-plan.schema.json",
}
DOCUMENT_FILES = {
    "content": "content.json",
    "plan": "deck-plan.json",
    "render": "render-plan.json",
}
LEGACY_HTML_ATTRIBUTES = {"data-density", "data-reuse-mode", "data-provider"}
PLAIN_QUESTION_BANNED = (
    "契约",
    "渲染器",
    "语义单元",
    "字段名",
    "错误码",
    "文件路径",
    "contract",
    "schema",
    "renderer",
    "semantic unit",
    "data_ref",
    "layout_id",
    "provider",
)
PLAIN_QUESTION_IMPACT_CUES = (
    "影响",
    "改变",
    "导致",
    "关系到",
    "不同",
    "重点",
    "结论",
    "页序",
    "建议",
    "讲法",
    "取舍",
    "删减",
    "附录",
)
PLAIN_QUESTION_CHOICE_CUES = (
    "还是",
    "或者",
    "或是",
    "请选择",
    "你希望",
    "您希望",
    "你想",
    "您想",
    "请告诉",
    "是否",
    "哪一种",
    "哪个",
    "哪份",
)


class ContractError(RuntimeError):
    """Raised when a required repository contract cannot be loaded."""


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
        self.issues.append(Issue(code, path, message))

    def warn(self, code: str, path: str, message: str) -> None:
        self.issues.append(Issue(code, path, message, "warning"))

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
        raise ContractError(
            f"JSON 无法解析：{path}:{exc.lineno}:{exc.colno} {exc.msg}"
        ) from exc


def resolve_root(explicit: str | os.PathLike[str] | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    configured = os.environ.get("WISE_PPT_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def _deck_directory(target: Path) -> Path:
    resolved = target.expanduser().resolve()
    if resolved.is_file() or (not resolved.exists() and resolved.suffix):
        return resolved.parent
    return resolved


def _relative_to(path: Path, parent: Path) -> Path | None:
    try:
        return path.relative_to(parent)
    except ValueError:
        return None


def _is_internal_contract_path(relative: Path) -> bool:
    parts = relative.parts
    return bool(
        (len(parts) >= 2 and parts[:2] == ("core", "examples"))
        or (len(parts) >= 3 and parts[0] == "themes" and parts[2] == "examples")
        or (parts and parts[0] in {"gallery", "tests"})
    )


def validate_output_location(
    target: Path,
    root: Path,
    workspace: Path | None = None,
    *,
    allow_internal: bool = False,
    require_workspace: bool = False,
) -> ValidationResult:
    """Keep formal deliverables outside the skill package itself."""

    result = ValidationResult()
    deck = _deck_directory(target)
    skill_root = root.expanduser().resolve()
    if require_workspace and workspace is None:
        result.error("config.workspace", str(deck), "请指定用户工作区根目录")
        return result

    inside = _relative_to(deck, skill_root)
    if inside is not None and not (allow_internal and _is_internal_contract_path(inside)):
        result.error(
            "output.inside_skill",
            str(deck),
            "正式 PPT 产物不能写入 wise-ppt-skill 包内",
        )

    if workspace is not None:
        workspace_root = workspace.expanduser().resolve()
        if not workspace_root.is_dir():
            result.error("config.workspace", str(workspace_root), "用户工作区不存在")
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
            try:
                current = current[int(part)]
            except (ValueError, IndexError) as exc:
                raise ContractError(f"JSON Pointer 不存在：#{pointer}") from exc
        elif isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            raise ContractError(f"JSON Pointer 不存在：#{pointer}")
    return current


def _type_matches(value: Any, expected: str) -> bool:
    return {
        "null": value is None,
        "boolean": isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "string": isinstance(value, str),
        "array": isinstance(value, list),
        "object": isinstance(value, dict),
    }.get(expected, True)


def _json_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class JsonSchemaValidator:
    """Small JSON Schema 2020-12 subset used by the bundled schemas."""

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
            result.error("config.schema", path, "schema 节点必须是对象或布尔值")
            return

        if "$ref" in schema:
            try:
                target, target_file = self._resolve_ref(str(schema["$ref"]), schema_file)
                self._walk(value, target, path, target_file, result)
            except ContractError as exc:
                result.error("config.schema_ref", path, str(exc))
            siblings = {key: item for key, item in schema.items() if key != "$ref"}
            if siblings:
                self._walk(value, siblings, path, schema_file, result)
            return

        for branch in schema.get("allOf", []):
            self._walk(value, branch, path, schema_file, result)
        if "anyOf" in schema and not any(
            self._branch_valid(value, branch, path, schema_file) for branch in schema["anyOf"]
        ):
            result.error("schema.anyOf", path, "不符合任何一种允许结构")
            return
        if "oneOf" in schema:
            matches = sum(
                self._branch_valid(value, branch, path, schema_file)
                for branch in schema["oneOf"]
            )
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
            self._object(value, schema, path, schema_file, result)
        elif isinstance(value, list):
            self._array(value, schema, path, schema_file, result)
        elif isinstance(value, str):
            self._string(value, schema, path, result)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            self._number(value, schema, path, result)

    def _object(
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
        patterns = schema.get("patternProperties", {})
        matched: set[str] = set()
        for key, item in value.items():
            child = f"{path}.{key}"
            if key in properties:
                matched.add(key)
                self._walk(item, properties[key], child, schema_file, result)
            for pattern, child_schema in patterns.items():
                try:
                    if re.search(pattern, key):
                        matched.add(key)
                        self._walk(item, child_schema, child, schema_file, result)
                except re.error as exc:
                    result.error("config.schema_pattern", child, f"无效正则：{exc}")
            if "propertyNames" in schema:
                self._walk(key, schema["propertyNames"], f"{child}<name>", schema_file, result)
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
                            f"字段 {key!r} 出现时必须提供 {dependency!r}",
                        )

    def _array(
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
        prefixes = schema.get("prefixItems", [])
        for index, child_schema in enumerate(prefixes):
            if index < len(value):
                self._walk(value[index], child_schema, f"{path}[{index}]", schema_file, result)
        items = schema.get("items")
        if items is not None:
            start = len(prefixes) if prefixes else 0
            for index in range(start, len(value)):
                self._walk(value[index], items, f"{path}[{index}]", schema_file, result)
        if "contains" in schema:
            matches = sum(
                self._branch_valid(item, schema["contains"], f"{path}[{index}]", schema_file)
                for index, item in enumerate(value)
            )
            minimum = schema.get("minContains", 1)
            maximum = schema.get("maxContains")
            if matches < minimum or (maximum is not None and matches > maximum):
                result.error("schema.contains", path, f"contains 匹配数 {matches} 不在允许范围")

    @staticmethod
    def _string(value: str, schema: Mapping[str, Any], path: str, result: ValidationResult) -> None:
        if len(value) < schema.get("minLength", 0):
            result.error("schema.minLength", path, f"字符串长度至少为 {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            result.error("schema.maxLength", path, f"字符串长度最多为 {schema['maxLength']}")
        if "pattern" in schema:
            try:
                if re.search(str(schema["pattern"]), value) is None:
                    result.error("schema.pattern", path, f"字符串不符合正则 {schema['pattern']!r}")
            except re.error as exc:
                result.error("config.schema_pattern", path, f"无效正则：{exc}")
        if schema.get("format") == "uri" and value and not urlparse(value).scheme:
            result.error("schema.format", path, "不是绝对 URI")

    @staticmethod
    def _number(value: float, schema: Mapping[str, Any], path: str, result: ValidationResult) -> None:
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
    path = root / "core" / "schemas" / SCHEMA_FILES[kind]
    if not path.is_file():
        raise ContractError(f"缺少 {kind} schema：{path}")
    return path


def validate_against_schema(root: Path, kind: str, document: Any, label: str) -> ValidationResult:
    try:
        return JsonSchemaValidator(find_schema(root, kind)).validate(document, label)
    except ContractError as exc:
        result = ValidationResult()
        result.error("config.schema", label, str(exc))
        return result


def find_document(target: Path, kind: str, required: bool = True) -> Path | None:
    target = target.expanduser().resolve()
    if target.is_file():
        return target
    candidate = target / DOCUMENT_FILES[kind]
    if candidate.is_file():
        return candidate
    if required:
        raise ContractError(f"在 {target} 下找不到 {DOCUMENT_FILES[kind]}")
    return None


def resolve_link(base_file: Path, link: str | None, root: Path, label: str) -> Path:
    if not link:
        raise ContractError(f"{base_file} 未声明 {label}_file")
    raw = Path(link).expanduser()
    candidates = [raw] if raw.is_absolute() else [base_file.parent / raw, root / raw]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise ContractError(f"{label} 引用文件不存在：{link}（来自 {base_file}）")


def _load_document(path: Path, result: ValidationResult, label: str) -> Mapping[str, Any] | None:
    try:
        value = load_json(path)
    except ContractError as exc:
        result.error("config.document", str(path), str(exc))
        return None
    if not isinstance(value, Mapping):
        result.error("schema.type", label, "文档根节点必须是对象")
        return None
    return value


def _require_v2(document: Mapping[str, Any], path: Path, result: ValidationResult) -> bool:
    if document.get("contract_version") != CONTRACT_VERSION:
        result.error(
            "contract.version",
            str(path),
            "只接受 contract_version: 2；请用 v2 规则重新生成，不提供旧格式兼容",
        )
        return False
    return True


@dataclass(frozen=True)
class ThemeRecord:
    theme_id: str
    registry_entry: Mapping[str, Any]
    theme_document: Mapping[str, Any]
    theme_path: Path


def _resolve_repo_path(root: Path, owner: Path, value: str) -> Path:
    raw = Path(value).expanduser()
    candidates = [raw] if raw.is_absolute() else [root / raw, owner.parent / raw]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def load_theme_registry(root: Path) -> tuple[Mapping[str, Any], Path]:
    path = root / "themes" / "registry.json"
    document = load_json(path)
    if not isinstance(document, Mapping) or not isinstance(document.get("themes"), list):
        raise ContractError(f"主题注册表必须包含 themes[]：{path}")
    return document, path


def resolve_theme(root: Path, requested: str | None = None) -> ThemeRecord:
    registry, registry_path = load_theme_registry(root)
    theme_id = requested or registry.get("default_theme_id")
    entry = next(
        (
            item
            for item in registry.get("themes", [])
            if isinstance(item, Mapping)
            and item.get("theme_id") == theme_id
            and item.get("enabled") is True
        ),
        None,
    )
    if entry is None:
        raise ContractError(f"未知或未启用的主题：{theme_id!r}")
    if not entry.get("path"):
        raise ContractError(f"主题 {theme_id!r} 未声明 path")
    theme_path = _resolve_repo_path(root, registry_path, str(entry["path"]))
    theme = load_json(theme_path)
    if not isinstance(theme, Mapping) or theme.get("theme_id") != theme_id:
        raise ContractError(f"主题清单 ID 不一致：{theme_path}")
    return ThemeRecord(str(theme_id), entry, theme, theme_path)


@dataclass(frozen=True)
class CapabilityCatalog:
    registry: Mapping[str, Any]
    registry_path: Path
    renderer_kinds: frozenset[str]
    component_sources: frozenset[str]
    allowed_pairs: frozenset[tuple[str, str]]
    manifest: Mapping[str, Any]
    manifest_path: Path
    recipes: Mapping[str, Mapping[str, Any]]


def load_capability_catalog(root: Path) -> CapabilityCatalog:
    registry_path = root / "capabilities" / "registry.json"
    registry = load_json(registry_path)
    if not isinstance(registry, Mapping):
        raise ContractError(f"公共能力注册表必须是对象：{registry_path}")
    if registry.get("contract_version") != CONTRACT_VERSION:
        raise ContractError(f"公共能力注册表 contract_version 必须为 2：{registry_path}")
    renderers = {
        str(item.get("renderer_kind"))
        for item in registry.get("renderer_kinds", [])
        if isinstance(item, Mapping) and item.get("renderer_kind")
    }
    sources = {
        str(item.get("component_source"))
        for item in registry.get("component_sources", [])
        if isinstance(item, Mapping) and item.get("component_source")
    }
    pairs: set[tuple[str, str]] = set()
    for item in registry.get("component_sources", []):
        if not isinstance(item, Mapping) or not item.get("component_source"):
            continue
        source = str(item["component_source"])
        for renderer in item.get("allowed_renderer_kinds", []):
            pairs.add((str(renderer), source))
    entry = next(
        (
            item
            for item in registry.get("capabilities", [])
            if isinstance(item, Mapping) and item.get("capability_id") == "layout-gallery"
        ),
        None,
    )
    if not entry or not entry.get("manifest"):
        raise ContractError("公共能力注册表缺少 layout-gallery manifest")
    manifest_path = _resolve_repo_path(root, registry_path, str(entry["manifest"]))
    manifest = load_json(manifest_path)
    if not isinstance(manifest, Mapping) or manifest.get("contract_version") != CONTRACT_VERSION:
        raise ContractError(f"Gallery manifest contract_version 必须为 2：{manifest_path}")
    raw_recipes = manifest.get("recipes")
    if not isinstance(raw_recipes, list):
        raise ContractError(f"Gallery manifest 缺少 recipes[]：{manifest_path}")
    recipes: dict[str, Mapping[str, Any]] = {}
    for item in raw_recipes:
        if not isinstance(item, Mapping) or not item.get("recipe_id"):
            raise ContractError(f"Gallery recipe 缺少 recipe_id：{manifest_path}")
        recipe_id = str(item["recipe_id"])
        if recipe_id in recipes:
            raise ContractError(f"Gallery recipe_id 重复：{recipe_id}")
        recipes[recipe_id] = item
    return CapabilityCatalog(
        registry,
        registry_path,
        frozenset(renderers),
        frozenset(sources),
        frozenset(pairs),
        manifest,
        manifest_path,
        recipes,
    )


def content_items(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [item for item in document.get("content_items", []) if isinstance(item, Mapping)]


def content_ref_ids(document: Mapping[str, Any]) -> set[str]:
    refs: set[str] = set()
    for item in content_items(document):
        if item.get("id"):
            refs.add(str(item["id"]))
        for atom in item.get("atomic_values", []):
            if isinstance(atom, Mapping) and atom.get("id"):
                refs.add(str(atom["id"]))
    return refs


def must_content_refs(document: Mapping[str, Any]) -> set[str]:
    refs: set[str] = set()
    for item in content_items(document):
        if item.get("priority") == "must" and item.get("id"):
            refs.add(str(item["id"]))
            refs.update(
                str(atom["id"])
                for atom in item.get("atomic_values", [])
                if isinstance(atom, Mapping) and atom.get("id")
            )
    return refs


def coverage_required_refs(document: Mapping[str, Any]) -> set[str]:
    """Items always need a decision; atoms only do when their parent is must."""

    refs: set[str] = set()
    for item in content_items(document):
        if item.get("id"):
            refs.add(str(item["id"]))
        if item.get("priority") == "must":
            refs.update(
                str(atom["id"])
                for atom in item.get("atomic_values", [])
                if isinstance(atom, Mapping) and atom.get("id")
            )
    return refs


def plan_pages(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [item for item in document.get("pages", []) if isinstance(item, Mapping)]


def render_pages(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [item for item in document.get("pages", []) if isinstance(item, Mapping)]


def _refs(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def page_content_refs(page: Mapping[str, Any]) -> list[str]:
    return _refs(page.get("content_refs"))


def slot_content_refs(slot: Mapping[str, Any]) -> list[str]:
    renderer = slot.get("renderer")
    return _refs(renderer.get("content_refs")) if isinstance(renderer, Mapping) else []


def render_page_content_refs(page: Mapping[str, Any]) -> list[str]:
    decision = page.get("layout_decision")
    if isinstance(decision, Mapping) and decision.get("source") == "gallery":
        payload = decision.get("payload")
        return [
            ref
            for binding in (payload.get("bindings", []) if isinstance(payload, Mapping) else [])
            if isinstance(binding, Mapping)
            for ref in _refs(binding.get("content_refs"))
        ]
    return [ref for slot in page.get("slots", []) if isinstance(slot, Mapping) for ref in slot_content_refs(slot)]


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    output: set[str] = set()
    for value in values:
        if value in seen:
            output.add(value)
        seen.add(value)
    return output


def _is_local_relative(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or value.startswith(("/", "\\")):
        return False
    return bool(parsed.path)


def _is_deck_relative(value: str) -> bool:
    if not _is_local_relative(value):
        return False
    parsed = urlparse(value)
    path = Path(unquote(parsed.path))
    return ".." not in path.parts


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _local_asset_path(content_path: Path, locator: str) -> Path | None:
    parsed = urlparse(locator)
    if parsed.scheme or parsed.netloc:
        return None
    raw = Path(unquote(parsed.path)).expanduser()
    return (raw if raw.is_absolute() else content_path.parent / raw).resolve()


def _asset_map(document: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(item["asset_id"]): item
        for item in document.get("assets", [])
        if isinstance(item, Mapping) and item.get("asset_id")
    }


def validate_content_document(
    document: Mapping[str, Any], path: Path, root: Path
) -> ValidationResult:
    result = ValidationResult()
    _require_v2(document, path, result)
    result.extend(validate_against_schema(root, "content", document, str(path)))

    sources = [item for item in document.get("sources", []) if isinstance(item, Mapping)]
    source_ids = [str(item.get("id")) for item in sources if item.get("id")]
    for duplicate in sorted(_duplicates(source_ids)):
        result.error("content.source_duplicate", str(path), f"来源 ID 重复：{duplicate}")
    source_set = set(source_ids)

    brief = document.get("brief") if isinstance(document.get("brief"), Mapping) else {}
    constraints = [
        item for item in brief.get("user_constraints", []) if isinstance(item, Mapping)
    ]
    constraint_ids = [str(item.get("constraint_id")) for item in constraints if item.get("constraint_id")]
    for duplicate in sorted(_duplicates(constraint_ids)):
        result.error("content.constraint_duplicate", str(path), f"限制 ID 重复：{duplicate}")
    for index, constraint in enumerate(constraints):
        label = f"{path}#brief.user_constraints[{index}]"
        for ref in _refs(constraint.get("source_refs")):
            if ref not in source_set:
                result.error("content.source_ref", label, f"未知来源：{ref}")
        if constraint.get("type") == "page_limit":
            exact = constraint.get("exact_pages")
            minimum = constraint.get("min_pages")
            maximum = constraint.get("max_pages")
            if minimum is not None and maximum is not None and minimum > maximum:
                result.error("content.constraint_range", label, "最少页数不能大于最多页数")
            if exact is not None and minimum is not None and exact < minimum:
                result.error("content.constraint_range", label, "指定页数小于最少页数")
            if exact is not None and maximum is not None and exact > maximum:
                result.error("content.constraint_range", label, "指定页数大于最多页数")
        if constraint.get("type") == "duration":
            exact = constraint.get("exact_minutes")
            minimum = constraint.get("min_minutes")
            maximum = constraint.get("max_minutes")
            if minimum is not None and maximum is not None and minimum > maximum:
                result.error("content.constraint_range", label, "最短时长不能大于最长时长")
            if exact is not None and minimum is not None and exact < minimum:
                result.error("content.constraint_range", label, "指定时长短于最短时长")
            if exact is not None and maximum is not None and exact > maximum:
                result.error("content.constraint_range", label, "指定时长长于最长时长")

    assets = _asset_map(document)
    raw_asset_ids = [
        str(item.get("asset_id"))
        for item in document.get("assets", [])
        if isinstance(item, Mapping) and item.get("asset_id")
    ]
    for duplicate in sorted(_duplicates(raw_asset_ids)):
        result.error("content.asset_duplicate", str(path), f"素材 ID 重复：{duplicate}")
    evidence_asset_refs = {
        ref
        for item in content_items(document)
        if item.get("epistemic_role") == "evidence"
        for ref in _refs(item.get("asset_refs"))
    }
    for asset_id, asset in assets.items():
        label = f"{path}#assets[{asset_id}]"
        for ref in _refs(asset.get("source_refs")):
            if ref not in source_set:
                result.error("content.source_ref", label, f"未知来源：{ref}")
        local_asset = _local_asset_path(path, str(asset.get("locator", "")))
        if local_asset is not None:
            if not local_asset.is_file():
                result.error("asset.file_missing", label, f"登记的素材文件不存在：{asset.get('locator')}")
            elif _sha256(local_asset) != asset.get("sha256"):
                result.error("asset.fingerprint", label, "素材文件指纹与登记的 SHA-256 不一致")
        if asset.get("role") != "reconstructed":
            continue
        if not _is_deck_relative(str(asset.get("locator", ""))):
            result.error(
                "asset.output_local",
                label,
                "重构成品必须使用 deck 内的本地相对路径",
            )
        creation_mode = asset.get("creation_mode")
        if creation_mode == "reconstruct" and asset.get("fact_change_risk") not in {
            "none",
            "possible",
        }:
            result.error(
                "asset.fact_change_risk",
                label,
                "重构成品必须明确事实变化风险为 none 或 possible",
            )
        if creation_mode == "generate" and "fact_change_risk" in asset:
            result.error(
                "asset.fact_change_risk",
                label,
                "纯文本生成图不使用重构事实变化风险字段",
            )
        if (
            creation_mode == "reconstruct"
            and asset_id in evidence_asset_refs
            and asset.get("disclosure") != "重构示意"
        ):
            result.error("asset.disclosure", label, "重构图必须标明“重构示意”")
        for source_asset_id in _refs(asset.get("derived_from")):
            source_asset = assets.get(source_asset_id)
            if source_asset is None:
                result.error("asset.derived_from", label, f"未知原素材：{source_asset_id}")
                continue
            if source_asset.get("role") != "source":
                result.error("asset.derived_from", label, f"只能从原素材重构：{source_asset_id}")
            if source_asset.get("sha256") == asset.get("sha256"):
                result.error("asset.same_fingerprint", label, "重构成品不能与原素材指纹相同")
            if str(source_asset.get("locator")) == str(asset.get("locator")):
                result.error("asset.same_path", label, "重构成品不能沿用原素材路径")

    all_refs: list[str] = []
    item_ids: list[str] = []
    relation_checks: list[tuple[str, str]] = []
    for index, item in enumerate(content_items(document)):
        label = f"{path}#content_items[{index}]"
        item_id = str(item.get("id", ""))
        if item_id:
            item_ids.append(item_id)
            all_refs.append(item_id)
        for ref in _refs(item.get("source_refs")):
            if ref not in source_set:
                result.error("content.source_ref", label, f"未知来源：{ref}")
        for ref in _refs(item.get("asset_refs")):
            if ref not in assets:
                result.error("content.asset_ref", label, f"未知素材：{ref}")
            elif (
                assets[ref].get("creation_mode") == "generate"
                and item.get("epistemic_role") == "evidence"
            ):
                result.error(
                    "asset.generated_evidence",
                    label,
                    f"生成图片不能承载原始证据：{ref}",
                )
        for atom in item.get("atomic_values", []):
            if isinstance(atom, Mapping) and atom.get("id"):
                all_refs.append(str(atom["id"]))
        for relation in item.get("relations", []):
            if isinstance(relation, Mapping) and relation.get("target_ref"):
                relation_checks.append((label, str(relation["target_ref"])))
    for duplicate in sorted(_duplicates(all_refs)):
        result.error("content.ref_duplicate", str(path), f"内容 ID 重复：{duplicate}")
    known_refs = set(all_refs)
    for label, target in relation_checks:
        if target not in known_refs:
            result.error("content.relation_ref", label, f"关系指向未知内容：{target}")
    return result


def validate_content_target(target: Path, root: Path) -> ValidationResult:
    result = ValidationResult()
    result.extend(validate_output_location(target, root, allow_internal=True))
    try:
        path = find_document(target, "content")
    except ContractError as exc:
        result.error("config.content", str(target), str(exc))
        return result
    assert path is not None
    document = _load_document(path, result, str(path))
    if document is not None:
        result.extend(validate_content_document(document, path, root))
    return result


def _constraint_overflow(
    constraints: Sequence[Mapping[str, Any]], page_count: int
) -> list[str]:
    overflow: list[str] = []
    for constraint in constraints:
        if constraint.get("type") != "page_limit":
            continue
        exact = constraint.get("exact_pages")
        minimum = constraint.get("min_pages")
        maximum = constraint.get("max_pages")
        if (
            (exact is not None and page_count != exact)
            or (minimum is not None and page_count < minimum)
            or (maximum is not None and page_count > maximum)
        ):
            overflow.append(str(constraint.get("constraint_id", "")))
    return overflow


def _assessment_has(
    assessments: Sequence[Mapping[str, Any]], trigger: str, refs: Iterable[str] = ()
) -> bool:
    wanted = set(refs)
    return any(
        item.get("trigger") == trigger
        and item.get("resolution") == "needs_user_choice"
        and (not wanted or bool(wanted & set(_refs(item.get("affected_refs")))))
        for item in assessments
    )


def _validate_confirmation(
    confirmation: Mapping[str, Any],
    content: Mapping[str, Any],
    overflow_refs: Sequence[str],
    path: Path,
    result: ValidationResult,
) -> None:
    assessments = [
        item for item in confirmation.get("assessments", []) if isinstance(item, Mapping)
    ]
    needs_choice = [item for item in assessments if item.get("resolution") == "needs_user_choice"]
    decision = confirmation.get("decision")
    questions = confirmation.get("user_questions", [])
    if needs_choice and decision != "needs_confirmation":
        result.error("confirmation.decision", str(path), "存在需要用户选择的问题，必须暂停")
    if not needs_choice and decision != "proceed":
        result.error("confirmation.decision", str(path), "没有待决定问题时应继续生成")
    if decision == "needs_confirmation":
        if not isinstance(questions, list) or not 1 <= len(questions) <= 3:
            result.error("confirmation.question_count", str(path), "暂停时只能问 1–3 个问题")
    elif questions:
        result.error("confirmation.question_count", str(path), "继续生成时不能保留待答问题")
    for index, question in enumerate(questions if isinstance(questions, list) else []):
        label = f"{path}#confirmation.user_questions[{index}]"
        question_text = str(question)
        folded = question_text.casefold()
        banned = next((term for term in PLAIN_QUESTION_BANNED if term.casefold() in folded), None)
        if banned:
            result.error("confirmation.question_jargon", label, f"问题包含内部术语：{banned}")
        if re.search(r"(?:/Users/|[A-Za-z]:\\|\.(?:json|html|py)\b|#[A-Za-z0-9_./-]+)", question_text):
            result.error("confirmation.question_path", label, "问题不能暴露文件路径、字段名或错误码")
        if not any(mark in question_text for mark in ("？", "?")):
            result.error("confirmation.question_form", label, "请用一句通俗问句说明需要用户选择什么")
        visible = re.sub(r"[\W_]+", "", question_text, flags=re.UNICODE)
        has_impact = any(cue in question_text for cue in PLAIN_QUESTION_IMPACT_CUES)
        has_choice = any(cue in question_text for cue in PLAIN_QUESTION_CHOICE_CUES)
        if len(visible) < 12 or not has_impact or not has_choice:
            result.error(
                "confirmation.question_context",
                label,
                "问题要说清发生了什么、会影响什么，以及需要用户选择什么",
            )

    unresolved = {
        str(item.get("id"))
        for item in content_items(content)
        if item.get("priority") == "must"
        and item.get("status") in {"inferred", "placeholder"}
    }
    if unresolved and not _assessment_has(assessments, "must_content_unresolved", unresolved):
        result.error(
            "confirmation.must_unresolved",
            str(path),
            "必留内容仍需猜测或占位，必须记录并暂停询问用户",
        )
    if overflow_refs and not _assessment_has(
        assessments, "user_constraint_overflow", overflow_refs
    ):
        result.error(
            "confirmation.constraint_overflow",
            str(path),
            "用户明确限制无法满足时，必须记录并暂停询问用户",
        )

    risky_reconstructions = {
        str(asset.get("asset_id"))
        for asset in content.get("assets", [])
        if isinstance(asset, Mapping)
        and asset.get("role") == "reconstructed"
        and asset.get("creation_mode") == "reconstruct"
        and asset.get("fact_change_risk") == "possible"
        and asset.get("asset_id")
    }
    missing_risk_assessments = {
        asset_id
        for asset_id in risky_reconstructions
        if not _assessment_has(
            assessments,
            "reconstruction_fact_risk",
            (asset_id,),
        )
    }
    if missing_risk_assessments:
        result.error(
            "confirmation.reconstruction_fact_risk",
            str(path),
            "重构可能改变事实，必须先用通俗问题请用户决定："
            + "、".join(sorted(missing_risk_assessments)),
        )

    assets = _asset_map(content)
    known_assessment_refs = content_ref_ids(content)
    known_assessment_refs.update(
        str(item.get("id"))
        for item in content.get("sources", [])
        if isinstance(item, Mapping) and item.get("id")
    )
    known_assessment_refs.update(assets.keys())
    brief = content.get("brief") if isinstance(content.get("brief"), Mapping) else {}
    known_assessment_refs.update(
        str(item.get("constraint_id"))
        for item in brief.get("user_constraints", [])
        if isinstance(item, Mapping) and item.get("constraint_id")
    )
    for index, assessment in enumerate(assessments):
        label = f"{path}#confirmation.assessments[{index}]"
        for ref in _refs(assessment.get("affected_refs")):
            if ref not in known_assessment_refs:
                result.error("confirmation.affected_ref", label, f"确认判断引用未知内容：{ref}")

    conflict_pairs: set[frozenset[str]] = set()
    for item in content_items(content):
        source_id = str(item.get("id", ""))
        for relation in item.get("relations", []):
            if (
                source_id
                and isinstance(relation, Mapping)
                and relation.get("type") == "contradicts"
                and relation.get("target_ref")
            ):
                conflict_pairs.add(
                    frozenset((source_id, str(relation.get("target_ref"))))
                )
    for pair in sorted(conflict_pairs, key=lambda item: sorted(item)):
        if not any(
            assessment.get("trigger") == "source_conflict"
            and set(pair).issubset(set(_refs(assessment.get("affected_refs"))))
            for assessment in assessments
        ):
            result.error(
                "confirmation.source_conflict",
                str(path),
                f"来源冲突必须评估影响和处理方式：{' / '.join(sorted(pair))}",
            )

    for index, assessment in enumerate(assessments):
        label = f"{path}#confirmation.assessments[{index}]"
        trigger = assessment.get("trigger")
        impact = assessment.get("impact")
        resolution = assessment.get("resolution")
        if trigger in {
            "must_content_unresolved",
            "user_constraint_overflow",
            "reconstruction_fact_risk",
        } and resolution != "needs_user_choice":
            result.error("confirmation.hard_pause", label, "该问题必须交给用户决定")
        if trigger in {"ambiguous_context", "source_conflict"}:
            if impact == "none" and resolution == "needs_user_choice":
                result.error("confirmation.unnecessary_pause", label, "不会改变结果的问题不应打断用户")
            if impact != "none" and resolution != "needs_user_choice":
                result.error("confirmation.missed_pause", label, "会改变结果的问题必须交给用户决定")


def validate_plan_document(
    document: Mapping[str, Any], path: Path, root: Path
) -> ValidationResult:
    result = ValidationResult()
    _require_v2(document, path, result)
    result.extend(validate_against_schema(root, "plan", document, str(path)))
    try:
        content_path = resolve_link(path, document.get("content_file"), root, "content")
    except ContractError as exc:
        result.error("config.content_link", str(path), str(exc))
        return result
    content = _load_document(content_path, result, str(content_path))
    if content is None:
        return result
    _require_v2(content, content_path, result)
    known_refs = content_ref_ids(content)
    source_ids = {
        str(item.get("id"))
        for item in content.get("sources", [])
        if isinstance(item, Mapping) and item.get("id")
    }
    brief = content.get("brief") if isinstance(content.get("brief"), Mapping) else {}
    constraints = [item for item in brief.get("user_constraints", []) if isinstance(item, Mapping)]
    constraint_ids = {
        str(item.get("constraint_id")) for item in constraints if item.get("constraint_id")
    }
    pages = plan_pages(document)
    page_ids = [str(page.get("page_id")) for page in pages if page.get("page_id")]
    for duplicate in sorted(_duplicates(page_ids)):
        result.error("plan.page_duplicate", str(path), f"页面 ID 重复：{duplicate}")
    if document.get("page_budget", {}).get("target") != len(pages):
        result.error("plan.page_budget", str(path), "推荐页数必须等于实际规划页数")
    expected_orders = list(range(1, len(pages) + 1))
    actual_orders = [page.get("order") for page in pages]
    if actual_orders != expected_orders:
        result.error("plan.page_order", str(path), "页面 order 必须从 1 连续递增")

    confirmation = document.get("confirmation") if isinstance(document.get("confirmation"), Mapping) else {}
    assessments = [
        item for item in confirmation.get("assessments", []) if isinstance(item, Mapping)
    ]
    overflow = _constraint_overflow(constraints, len(pages))
    _validate_confirmation(confirmation, content, overflow, path, result)

    planning = document.get("planning_basis") if isinstance(document.get("planning_basis"), Mapping) else {}
    for ref in _refs(planning.get("user_constraint_refs")):
        if ref not in constraint_ids:
            result.error("plan.constraint_ref", str(path), f"页数依据引用未知限制：{ref}")
    for ref in _refs(planning.get("research_source_refs")):
        if ref not in source_ids:
            result.error("plan.source_ref", str(path), f"场景依据引用未知来源：{ref}")
    page_or_duration = {
        str(item.get("constraint_id"))
        for item in constraints
        if item.get("type") in {"page_limit", "duration"}
    }
    mode = planning.get("mode")
    if mode == "user-constrained" and not (
        page_or_duration & set(_refs(planning.get("user_constraint_refs")))
    ):
        result.error("plan.basis_mode", str(path), "只有用户明确给出页数或时长时才能标为用户限制")
    if not page_or_duration and mode != "scenario-recommended":
        result.error("plan.basis_mode", str(path), "用户未给页数或时长，应按使用场景推荐页数")

    scenario_origin = planning.get("scenario_origin")
    research_refs = set(_refs(planning.get("research_source_refs")))
    for index, basis in enumerate(document.get("page_budget", {}).get("basis", [])):
        if not isinstance(basis, Mapping):
            continue
        label = f"{path}#page_budget.basis[{index}]"
        for ref in _refs(basis.get("content_refs")):
            if ref not in known_refs:
                result.error("plan.content_ref", label, f"未知内容：{ref}")
        for ref in _refs(basis.get("constraint_refs")):
            if ref not in constraint_ids:
                result.error("plan.constraint_ref", label, f"未知限制：{ref}")
        for ref in _refs(basis.get("source_refs")):
            if ref not in source_ids:
                result.error("plan.source_ref", label, f"未知来源：{ref}")
        if basis.get("type") == "scenario_research":
            basis_refs = set(_refs(basis.get("source_refs")))
            if scenario_origin != "researched":
                result.error("plan.scenario_basis", label, "只有实际调研过场景时才能使用调研依据")
            if not basis_refs.issubset(research_refs):
                result.error("plan.scenario_basis", label, "页数调研依据必须来自已登记的场景调研来源")
        if basis.get("type") == "duration":
            duration_ids = {
                str(item.get("constraint_id"))
                for item in constraints
                if item.get("type") == "duration"
            }
            for ref in _refs(basis.get("constraint_refs")):
                if ref not in duration_ids:
                    result.error("plan.constraint_ref", label, f"时长依据必须引用用户给出的时长限制：{ref}")

    section_ids: list[str] = []
    section_page_refs: list[str] = []
    for index, section in enumerate(document.get("sections", [])):
        if not isinstance(section, Mapping):
            continue
        section_id = str(section.get("section_id", ""))
        section_ids.append(section_id)
        for ref in _refs(section.get("page_refs")):
            section_page_refs.append(ref)
            if ref not in page_ids:
                result.error("plan.section_page_ref", f"{path}#sections[{index}]", f"未知页面：{ref}")
    for duplicate in sorted(_duplicates(section_ids)):
        result.error("plan.section_duplicate", str(path), f"章节 ID 重复：{duplicate}")
    if sorted(section_page_refs) != sorted(page_ids):
        result.error("plan.section_coverage", str(path), "每页必须且只能属于一个章节")

    page_refs_seen: set[str] = set()
    block_ids: set[str] = set()
    visible_refs: set[str] = set()
    for index, page in enumerate(pages):
        label = f"{path}#pages[{index}]"
        page_id = str(page.get("page_id", ""))
        if page.get("section_id") not in section_ids:
            result.error("plan.section_ref", label, f"未知章节：{page.get('section_id')}")
        refs = set(page_content_refs(page))
        page_refs_seen.update(refs)
        for ref in refs | set(_refs(page.get("evidence_refs"))):
            if ref not in known_refs:
                result.error("plan.content_ref", label, f"未知内容：{ref}")
        blocks = [item for item in page.get("blocks", []) if isinstance(item, Mapping)]
        primaries = [item for item in blocks if item.get("importance") == "primary"]
        if len(primaries) != 1:
            result.error("plan.primary_block", label, "每页必须有且只有一个主表达块")
        for block in blocks:
            block_id = str(block.get("block_id", ""))
            if block_id in block_ids:
                result.error("plan.block_duplicate", label, f"表达块 ID 重复：{block_id}")
            block_ids.add(block_id)
            block_refs = set(_refs(block.get("content_refs")))
            visible_refs.update(block_refs)
            for ref in block_refs:
                if ref not in known_refs:
                    result.error("plan.content_ref", label, f"表达块引用未知内容：{ref}")
                if ref not in refs:
                    result.error("plan.block_scope", label, f"表达块内容未列入页面内容：{ref}")

    decisions = [item for item in document.get("coverage_decisions", []) if isinstance(item, Mapping)]
    decision_refs = [str(item.get("content_ref")) for item in decisions if item.get("content_ref")]
    for duplicate in sorted(_duplicates(decision_refs)):
        result.error("coverage.duplicate", str(path), f"覆盖决定重复：{duplicate}")
    missing_decisions = coverage_required_refs(content) - set(decision_refs)
    extra_decisions = set(decision_refs) - known_refs
    for ref in sorted(missing_decisions):
        result.error("coverage.missing", str(path), f"内容缺少覆盖决定：{ref}")
    for ref in sorted(extra_decisions):
        result.error("coverage.unknown", str(path), f"覆盖决定引用未知内容：{ref}")
    must_refs = must_content_refs(content)
    for index, decision in enumerate(decisions):
        label = f"{path}#coverage_decisions[{index}]"
        ref = str(decision.get("content_ref", ""))
        disposition = decision.get("disposition")
        listed_pages = set(_refs(decision.get("page_refs")))
        if disposition == "include":
            if not listed_pages:
                result.error("coverage.page_ref", label, "纳入内容必须落到至少一页")
            for page_id in listed_pages:
                page = next((item for item in pages if item.get("page_id") == page_id), None)
                if page is None:
                    result.error("coverage.page_ref", label, f"未知页面：{page_id}")
                elif ref not in page_content_refs(page):
                    result.error("coverage.page_binding", label, f"{ref} 未出现在 {page_id} 的内容引用中")
            if ref not in visible_refs:
                result.error("coverage.visible_block", label, f"{ref} 未进入任何可见表达块")
        elif listed_pages:
            result.error("coverage.page_ref", label, "暂缓或省略的内容不能绑定页面")
        if ref in must_refs and disposition != "include":
            result.error("coverage.must", label, "priority=must 的内容不能暂缓或省略")
    return result


def validate_plan_target(target: Path, root: Path) -> ValidationResult:
    result = ValidationResult()
    try:
        path = find_document(target, "plan")
    except ContractError as exc:
        result.error("config.plan", str(target), str(exc))
        return result
    assert path is not None
    result.extend(validate_output_location(path, root, allow_internal=True))
    document = _load_document(path, result, str(path))
    if document is not None:
        result.extend(validate_plan_document(document, path, root))
    return result


def _recipe_fingerprint(recipe: Mapping[str, Any]) -> str:
    slots = [
        {
            key: slot.get(key)
            for key in ("slot_id", "required", "visual_role", "min_items", "max_items")
        }
        for slot in recipe.get("slots", [])
        if isinstance(slot, Mapping)
    ]
    canonical = {
        "reading_order": recipe.get("reading_order"),
        "structure_contract": recipe.get("structure_contract"),
        "slots": slots,
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _slot_map(recipe: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(item["slot_id"]): item
        for item in recipe.get("slots", [])
        if isinstance(item, Mapping) and item.get("slot_id")
    }


def _validate_recipe_semantics(
    planned: Mapping[str, Any],
    recipe: Mapping[str, Any],
    label: str,
    result: ValidationResult,
) -> None:
    role = str(planned.get("role", ""))
    if role not in _refs(recipe.get("roles")):
        result.error(
            "render.recipe_role",
            label,
            f"页面角色 {role} 不在所选 Gallery recipe 的适用角色中",
        )
    relation_shape = (
        planned.get("relation_shape")
        if isinstance(planned.get("relation_shape"), Mapping)
        else {}
    )
    relation = str(relation_shape.get("primary", ""))
    if relation not in _refs(recipe.get("relations")):
        result.error(
            "render.recipe_relation",
            label,
            f"页面主关系 {relation} 不在所选 Gallery recipe 的适用关系中",
        )
    contract = (
        recipe.get("structure_contract")
        if isinstance(recipe.get("structure_contract"), Mapping)
        else {}
    )
    primitive = str(planned.get("spatial_primitive", ""))
    if primitive not in _refs(contract.get("core_primitives")):
        result.error(
            "render.recipe_primitive",
            label,
            f"页面空间结构 {primitive} 不在所选 Gallery recipe 的核心结构中",
        )


def _theme_adapters(theme: ThemeRecord) -> dict[str, Mapping[str, Any]]:
    return {
        str(item["adapter_id"]): item
        for item in theme.theme_document.get("adapters", [])
        if isinstance(item, Mapping) and item.get("adapter_id")
    }


def _validate_theme_adapters(
    theme: ThemeRecord,
    catalog: CapabilityCatalog,
    result: ValidationResult,
) -> None:
    adapters = [
        item
        for item in theme.theme_document.get("adapters", [])
        if isinstance(item, Mapping)
    ]
    adapter_ids = [str(item.get("adapter_id", "")) for item in adapters]
    for duplicate in sorted(_duplicates(adapter_ids)):
        result.error(
            "theme.adapter_duplicate",
            str(theme.theme_path),
            f"主题适配器 ID 重复：{duplicate}",
        )
    for index, adapter in enumerate(adapters):
        label = f"{theme.theme_path}#adapters[{index}]"
        for renderer_kind in _refs(adapter.get("renderer_kinds")):
            for component_source in _refs(adapter.get("component_sources")):
                if (renderer_kind, component_source) not in catalog.allowed_pairs:
                    result.error(
                        "theme.adapter_capability",
                        label,
                        f"主题适配器声明了公共能力未允许的组合：{renderer_kind} × {component_source}",
                    )


def _dataset_dimensions(value: Any) -> tuple[set[str], int | None]:
    dimensions: set[str] = set()
    if isinstance(value, Mapping) and isinstance(value.get("source"), list):
        raw_dimensions = value.get("dimensions")
        if isinstance(raw_dimensions, list):
            dimensions.update(
                str(item.get("name") if isinstance(item, Mapping) else item)
                for item in raw_dimensions
            )
        value = value["source"]
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, Mapping):
            for row in value:
                if isinstance(row, Mapping):
                    dimensions.update(str(key) for key in row)
            return dimensions, None
        if isinstance(first, list):
            width = max((len(row) for row in value if isinstance(row, list)), default=0)
            if all(isinstance(item, str) for item in first):
                dimensions.update(str(item) for item in first)
            return dimensions, width
        return dimensions, 1
    if isinstance(value, Mapping):
        dimensions.update(str(key) for key in value)
        return dimensions, None
    if isinstance(value, list):
        return dimensions, 0
    return dimensions, None


def _flatten_encode(value: Any) -> list[Any]:
    if isinstance(value, list):
        return [child for item in value for child in _flatten_encode(item)]
    return [value]


def _validate_echarts_binding(
    binding: Mapping[str, Any],
    items: Mapping[str, Mapping[str, Any]],
    label: str,
    result: ValidationResult,
) -> None:
    ref = binding.get("data_ref") if isinstance(binding.get("data_ref"), Mapping) else {}
    content_id = str(ref.get("content_id", ""))
    item = items.get(content_id)
    if item is None:
        result.error("render.data_ref", label, f"图表数据引用未知内容：{content_id}")
        return
    try:
        dataset = _json_pointer_get(item, str(ref.get("json_pointer", "")))
    except ContractError as exc:
        result.error("render.data_ref", label, str(exc))
        return
    if not isinstance(dataset, (list, Mapping)):
        result.error("render.dataset", label, "ECharts dataset 必须指向数组或对象数据")
        return
    dimensions, width = _dataset_dimensions(dataset)
    encode = binding.get("encode")
    if not isinstance(encode, Mapping) or not encode:
        result.error("render.encode", label, "ECharts encode 必须明确映射字段")
        return
    for channel, raw_value in encode.items():
        for value in _flatten_encode(raw_value):
            if isinstance(value, int) and not isinstance(value, bool):
                if width is None or value < 0 or value >= width:
                    result.error("render.encode", label, f"{channel} 引用了不存在的数据列 {value}")
            elif isinstance(value, str):
                if value not in dimensions:
                    result.error("render.encode", label, f"{channel} 引用了不存在的数据字段 {value!r}")
            else:
                result.error("render.encode", label, f"{channel} 的字段映射必须是列名或列序号")


def _atlas_component_ids() -> set[str] | None:
    candidates: list[Path] = []
    configured = os.environ.get("PPT_COMPONENT_ATLAS_CATALOG")
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend(
        [
            Path.home() / ".codex/skills/ppt-component-atlas/public/catalog-data.js",
            Path.home() / ".agents/skills/ppt-component-atlas/public/catalog-data.js",
        ]
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        return None
    try:
        if path.suffix.casefold() == ".json":
            document = load_json(path)
            entries = document.get("components", []) if isinstance(document, Mapping) else []
        else:
            source = path.read_text(encoding="utf-8")
            marker = source.find("window.SWISS_CATALOG_DATA")
            start = source.find("{", marker)
            document, _ = json.JSONDecoder().raw_decode(source[start:])
            entries = document.get("entries", []) if isinstance(document, Mapping) else []
    except (OSError, ValueError, ContractError):
        return set()
    identifiers: set[str] = set()
    for item in entries:
        if not isinstance(item, Mapping):
            continue
        for key in ("component_id", "id", "name"):
            if item.get(key):
                identifiers.add(str(item[key]))
    return identifiers


def _validate_renderer(
    renderer: Mapping[str, Any],
    label: str,
    page_refs: set[str],
    content: Mapping[str, Any],
    catalog: CapabilityCatalog,
    theme: ThemeRecord,
    result: ValidationResult,
    datasets: dict[str, str],
) -> None:
    kind = str(renderer.get("renderer_kind", ""))
    source = str(renderer.get("component_source", ""))
    pair = (kind, source)
    if pair not in catalog.allowed_pairs:
        result.error("render.capability_pair", label, f"公共能力未登记组合：{kind} × {source}")
    refs = set(_refs(renderer.get("content_refs")))
    known_refs = content_ref_ids(content)
    for ref in refs:
        if ref not in known_refs:
            result.error("render.content_ref", label, f"未知内容：{ref}")
        if ref not in page_refs:
            result.error("render.content_scope", label, f"渲染内容未列入页面：{ref}")
    adapter_id = str(renderer.get("theme_adapter_id", ""))
    adapter = _theme_adapters(theme).get(adapter_id)
    if adapter is None:
        result.error("render.theme_adapter", label, f"主题未登记适配器：{adapter_id}")
    elif kind not in _refs(adapter.get("renderer_kinds")) or source not in _refs(
        adapter.get("component_sources")
    ):
        result.error("render.theme_adapter", label, f"适配器 {adapter_id} 不支持 {kind} × {source}")

    binding = renderer.get("data_binding")
    if isinstance(binding, Mapping):
        data_ref = binding.get("data_ref") if isinstance(binding.get("data_ref"), Mapping) else {}
        data_content_id = str(data_ref.get("content_id", ""))
        if data_content_id not in refs:
            result.error("render.data_ref", label, "数据来源必须同时列入该组件的内容引用")
        items = {
            str(item["id"]): item
            for item in content_items(content)
            if item.get("id")
        }
        if source == "echarts":
            _validate_echarts_binding(binding, items, label, result)
        else:
            ref = binding.get("data_ref") if isinstance(binding.get("data_ref"), Mapping) else {}
            item = items.get(str(ref.get("content_id", "")))
            if item is None:
                result.error("render.data_ref", label, "数据引用指向未知内容")
            else:
                try:
                    _json_pointer_get(item, str(ref.get("json_pointer", "")))
                except ContractError as exc:
                    result.error("render.data_ref", label, str(exc))
        dataset_id = str(binding.get("dataset_id", ""))
        signature = _json_key(binding)
        if dataset_id in datasets:
            result.error("render.dataset_id", label, f"dataset_id 必须唯一：{dataset_id}")
        datasets[dataset_id] = signature
    elif source == "echarts":
        result.error("render.data_binding", label, "ECharts 必须绑定真实 dataset 与 encode")

    if source == "ppt-component-atlas":
        known_atlas = _atlas_component_ids()
        component_id = str(renderer.get("component_id", ""))
        if known_atlas is None:
            result.error("config.atlas_catalog", label, "缺少 PPT Component Atlas catalog，无法核对组件 ID")
        elif component_id not in known_atlas:
            result.error("render.atlas_component", label, f"Atlas 中不存在组件：{component_id}")

    material = renderer.get("material_treatment")
    if kind == "image" and not isinstance(material, Mapping):
        result.error("asset.reconstruction", label, "图片只能使用有记录的重构成品")
    if isinstance(material, Mapping):
        assets = _asset_map(content)
        mode = material.get("mode")
        output_ref = str(material.get("output_asset_ref", ""))
        output = assets.get(output_ref)
        linked_items: list[Mapping[str, Any]] = []
        for item in content_items(content):
            item_refs = {str(item.get("id", ""))}
            item_refs.update(
                str(atom.get("id"))
                for atom in item.get("atomic_values", [])
                if isinstance(atom, Mapping) and atom.get("id")
            )
            if refs & item_refs:
                linked_items.append(item)
        linked_asset_refs = {
            asset_ref
            for item in linked_items
            for asset_ref in _refs(item.get("asset_refs"))
        }
        if output is None or output.get("role") != "reconstructed":
            result.error("asset.output_ref", label, "图片输出必须指向已登记的重构成品")
        elif output_ref not in linked_asset_refs:
            result.error(
                "asset.content_link",
                label,
                "图片输出必须登记在该组件承载内容的 asset_refs 中",
            )
        if mode == "reconstruct":
            if output is not None and output.get("creation_mode") != "reconstruct":
                result.error("asset.output_mode", label, "重构渲染必须指向 reconstruct 成品")
            for ref in _refs(material.get("source_asset_refs")):
                source_asset = assets.get(ref)
                if source_asset is None or source_asset.get("role") != "source":
                    result.error("asset.source_ref", label, f"重构来源不是已登记原素材：{ref}")
                elif output is not None and ref not in _refs(output.get("derived_from")):
                    result.error("asset.provenance", label, f"成品未记录来自原素材：{ref}")
            if output is not None and output.get("reconstruction_method") != material.get("strategy"):
                result.error("asset.strategy", label, "渲染方案与素材记录的重构方法不一致")
        elif mode == "generate":
            if source != "codex-host":
                result.error("asset.generate_source", label, "生成图片只能来自 Codex 宿主内置图片能力")
            if output is not None and output.get("creation_mode") != "generate":
                result.error("asset.output_mode", label, "生成渲染必须指向 generate 成品")
            evidence_refs = {
                str(item.get("id"))
                for item in content_items(content)
                if item.get("epistemic_role") == "evidence"
            }
            if refs & evidence_refs:
                result.error("asset.generated_evidence", label, "生成图片不能承载原始证据")


def validate_render_document(
    document: Mapping[str, Any],
    path: Path,
    root: Path,
    *,
    require_html: bool,
) -> ValidationResult:
    result = ValidationResult()
    _require_v2(document, path, result)
    result.extend(validate_against_schema(root, "render", document, str(path)))
    try:
        content_path = resolve_link(path, document.get("content_file"), root, "content")
        plan_path = resolve_link(path, document.get("deck_plan_file"), root, "deck plan")
    except ContractError as exc:
        result.error("config.render_link", str(path), str(exc))
        return result
    content = _load_document(content_path, result, str(content_path))
    plan = _load_document(plan_path, result, str(plan_path))
    if content is None or plan is None:
        return result
    _require_v2(content, content_path, result)
    _require_v2(plan, plan_path, result)
    confirmation = plan.get("confirmation") if isinstance(plan.get("confirmation"), Mapping) else {}
    brief = content.get("brief") if isinstance(content.get("brief"), Mapping) else {}
    constraints = [
        item
        for item in brief.get("user_constraints", [])
        if isinstance(item, Mapping)
    ]
    confirmation_result = ValidationResult()
    _validate_confirmation(
        confirmation,
        content,
        _constraint_overflow(constraints, len(plan_pages(plan))),
        plan_path,
        confirmation_result,
    )
    if not confirmation_result.ok:
        result.extend(confirmation_result)
        result.error(
            "render.gate_confirmation",
            str(path),
            "用户还有未决定的问题，必须停止渲染和 PDF 导出",
        )
        return result
    if confirmation.get("decision") != "proceed" or confirmation.get("user_questions"):
        result.error("render.gate_confirmation", str(path), "用户还有未决定的问题，必须停止渲染和 PDF 导出")
        return result
    if Path(str(plan.get("content_file", ""))).name != content_path.name:
        result.error("render.link_chain", str(path), "render 与 deck plan 没有指向同一份内容")
    try:
        catalog = load_capability_catalog(root)
        theme = resolve_theme(root, str(document.get("theme_id", "")))
    except ContractError as exc:
        result.error("config.capabilities", str(path), str(exc))
        return result
    _validate_theme_adapters(theme, catalog, result)

    plan_by_id = {str(page.get("page_id")): page for page in plan_pages(plan) if page.get("page_id")}
    render_list = render_pages(document)
    render_ids = [str(page.get("page_id")) for page in render_list if page.get("page_id")]
    if render_ids != list(plan_by_id):
        result.error("render.page_order", str(path), "渲染页必须与叙事规划逐页同序")
    for duplicate in sorted(_duplicates(render_ids)):
        result.error("render.page_duplicate", str(path), f"渲染页面 ID 重复：{duplicate}")

    datasets: dict[str, str] = {}
    for index, render_page in enumerate(render_list):
        label = f"{path}#pages[{index}]"
        page_id = str(render_page.get("page_id", ""))
        planned = plan_by_id.get(page_id)
        if planned is None:
            result.error("render.page_ref", label, f"找不到规划页面：{page_id}")
            continue
        page_refs = set(page_content_refs(planned))
        decision = render_page.get("layout_decision") if isinstance(render_page.get("layout_decision"), Mapping) else {}
        source = str(decision.get("source", ""))
        evaluations = [item for item in decision.get("candidate_evaluations", []) if isinstance(item, Mapping)]
        evaluation_ids = [str(item.get("recipe_id")) for item in evaluations if item.get("recipe_id")]
        for duplicate in sorted(_duplicates(evaluation_ids)):
            result.error("render.candidate_duplicate", label, f"布局候选重复：{duplicate}")
        for recipe_id in evaluation_ids:
            if recipe_id not in catalog.recipes:
                result.error("render.recipe_ref", label, f"布局候选不在 Gallery：{recipe_id}")
        exact = [item for item in evaluations if item.get("verdict") == "exact_fit"]
        structure = [item for item in evaluations if item.get("verdict") == "structure_fit"]
        selected_id = str(decision.get("recipe_id", ""))
        selected = catalog.recipes.get(selected_id)

        if exact and source != "gallery":
            result.error("render.gallery_termination", label, "已有完全匹配的 Gallery 版式，必须直接使用并停止组合")
        if source in {"gallery", "composition"} and selected is not None:
            _validate_recipe_semantics(planned, selected, label, result)
        if source == "gallery":
            if selected is None:
                result.error("render.recipe_ref", label, f"Gallery 中不存在版式：{selected_id}")
            if len(exact) != 1 or str(exact[0].get("recipe_id")) != selected_id:
                result.error("render.gallery_exact", label, "Gallery 来源必须选择唯一的 exact_fit 候选")
            if structure:
                result.error("render.gallery_termination", label, "Gallery 完整命中后不能继续记录组合候选")
            bindings = decision.get("payload", {}).get("bindings", []) if isinstance(decision.get("payload"), Mapping) else []
            binding_map = {
                str(item.get("slot_id")): item
                for item in bindings
                if isinstance(item, Mapping) and item.get("slot_id")
            }
            if len(binding_map) != len(bindings):
                result.error("render.payload_slot", label, "Gallery payload 槽位不能缺失或重复")
            if selected is not None:
                slots = _slot_map(selected)
                expected_order = _refs(selected.get("reading_order"))
                if [str(item.get("slot_id")) for item in bindings] != expected_order:
                    result.error("render.payload_order", label, "Gallery payload 必须完整绑定全部槽位并沿用 recipe 的阅读顺序")
                unknown = set(binding_map) - set(slots)
                missing = set(slots) - set(binding_map)
                for slot_id in sorted(unknown):
                    result.error("render.payload_slot", label, f"Gallery 不存在槽位：{slot_id}")
                for slot_id in sorted(missing):
                    result.error("render.payload_slot", label, f"Gallery 槽位未绑定：{slot_id}")
                for slot_id, binding in binding_map.items():
                    if slot_id not in slots:
                        continue
                    slot = slots[slot_id]
                    bound_refs = _refs(binding.get("content_refs"))
                    bound_assets = _refs(binding.get("asset_refs"))
                    count = len(bound_refs) + len(bound_assets)
                    if count < int(slot.get("min_items", 0)) or count > int(slot.get("max_items", count)):
                        result.error("render.payload_capacity", label, f"槽位 {slot_id} 的绑定数量超出容量")
                    for ref in bound_refs:
                        if ref not in page_refs:
                            result.error("render.content_scope", label, f"Gallery 内容未列入页面：{ref}")
                    assets = _asset_map(content)
                    for ref in bound_assets:
                        asset = assets.get(ref)
                        if asset is None or asset.get("role") != "reconstructed":
                            result.error("asset.output_ref", label, f"Gallery 图片不是已登记重构成品：{ref}")
        elif source == "composition":
            if selected is None:
                result.error("render.recipe_ref", label, f"Gallery 中不存在结构参考：{selected_id}")
            if len(structure) != 1 or str(structure[0].get("recipe_id")) != selected_id:
                result.error("render.composition_fit", label, "组合页必须选择唯一的 structure_fit 候选")
        elif source == "custom" and any(item.get("verdict") != "reject" for item in evaluations):
            result.error("render.custom_reject", label, "自定义页只能在所有候选都不合适时使用")

        slots = [item for item in render_page.get("slots", []) if isinstance(item, Mapping)]
        block_map = {
            str(item.get("block_id")): item
            for item in planned.get("blocks", [])
            if isinstance(item, Mapping) and item.get("block_id")
        }
        slot_ids = [str(item.get("slot_id")) for item in slots if item.get("slot_id")]
        for duplicate in sorted(_duplicates(slot_ids)):
            result.error("render.slot_duplicate", label, f"渲染槽位重复：{duplicate}")
        if source == "composition" and selected is not None:
            recipe_slots = _slot_map(selected)
            if set(slot_ids) != set(recipe_slots):
                result.error("render.composition_slots", label, "组合页必须完整保留 Gallery 的全部槽位结构")
            if slot_ids != _refs(selected.get("reading_order")):
                result.error("render.composition_order", label, "组合页必须保留 Gallery 的阅读顺序")
            changed = False
            for slot in slots:
                spec = recipe_slots.get(str(slot.get("slot_id")))
                renderer = slot.get("renderer") if isinstance(slot.get("renderer"), Mapping) else {}
                if spec is None:
                    continue
                if slot.get("visual_role") != spec.get("visual_role"):
                    result.error("render.slot_role", label, f"槽位 {slot.get('slot_id')} 改变了主次关系")
                if renderer.get("renderer_kind") not in spec.get("allowed_renderer_kinds", []):
                    result.error("render.slot_renderer", label, f"槽位 {slot.get('slot_id')} 不支持该渲染方式")
                if renderer.get("component_source") not in spec.get("allowed_component_sources", []):
                    result.error("render.slot_source", label, f"槽位 {slot.get('slot_id')} 不支持该组件来源")
                default = spec.get("default_renderer") if isinstance(spec.get("default_renderer"), Mapping) else {}
                triple = (renderer.get("renderer_kind"), renderer.get("component_source"), renderer.get("component_id"))
                default_triple = (default.get("renderer_kind"), default.get("component_source"), default.get("component_id"))
                changed = changed or triple != default_triple
            if slots and not changed:
                result.error("render.composition_redundant", label, "组件完全沿用默认实现时应直接使用 Gallery，不需要再次组合")
        if source == "custom":
            custom = decision.get("custom_contract") if isinstance(decision.get("custom_contract"), Mapping) else {}
            regions = [item for item in custom.get("regions", []) if isinstance(item, Mapping)]
            region_ids = [str(item.get("slot_id")) for item in regions if item.get("slot_id")]
            if set(region_ids) != set(slot_ids):
                result.error("render.custom_slots", label, "自定义结构区域必须与渲染槽位一一对应")
            if custom.get("reading_order") != region_ids:
                result.error("render.custom_order", label, "自定义阅读顺序必须与区域顺序一致")
            region_map = {str(item.get("slot_id")): item for item in regions}
            for slot in slots:
                region = region_map.get(str(slot.get("slot_id")))
                if region and (
                    region.get("block_id") != slot.get("block_id")
                    or region.get("visual_role") != slot.get("visual_role")
                ):
                    result.error("render.custom_region", label, "自定义区域与渲染槽位定义不一致")

        if source in {"composition", "custom"}:
            mapped_blocks = [str(slot.get("block_id", "")) for slot in slots]
            for duplicate in sorted(_duplicates(mapped_blocks)):
                result.error("render.block_duplicate", label, f"表达块只能映射一次：{duplicate}")
            if set(mapped_blocks) != set(block_map):
                result.error("render.block_coverage", label, "每个规划表达块必须且只能映射到一个渲染槽位")
            primary_slots = [slot for slot in slots if slot.get("visual_role") == "primary"]
            if len(primary_slots) != 1:
                result.error("render.primary_slot", label, "每页必须有且只有一个主渲染槽")

        for slot_index, slot in enumerate(slots):
            slot_label = f"{label}.slots[{slot_index}]"
            block_id = str(slot.get("block_id", ""))
            if block_id not in block_map:
                result.error("render.block_ref", slot_label, f"未知表达块：{block_id}")
            elif slot.get("visual_role") == "primary" and block_map[block_id].get("importance") != "primary":
                result.error("render.primary_binding", slot_label, "主渲染槽必须绑定主表达块")
            renderer = slot.get("renderer")
            if isinstance(renderer, Mapping):
                _validate_renderer(
                    renderer,
                    slot_label,
                    page_refs,
                    content,
                    catalog,
                    theme,
                    result,
                    datasets,
                )
        expected_refs = page_refs
        rendered_refs = set(render_page_content_refs(render_page))
        for ref in sorted(expected_refs - rendered_refs):
            result.error("render.coverage", label, f"页面内容未进入渲染：{ref}")
        emphasis = render_page.get("emphasis") if isinstance(render_page.get("emphasis"), Mapping) else {}
        if emphasis.get("mode") == "semantic-focus":
            content_ref = str(emphasis.get("content_ref", ""))
            if content_ref not in page_refs or content_ref not in rendered_refs:
                result.error("render.emphasis_ref", label, "语义强调必须指向本页实际渲染的内容")

    if require_html:
        html_path = path.parent / str(document.get("output_file", "index.html"))
        result.extend(_validate_deck_html(html_path, document, plan, content, catalog, theme))
    return result


@dataclass
class HtmlElement:
    tag: str
    attrs: dict[str, str]
    text: list[str] = field(default_factory=list)


@dataclass
class HtmlSlide:
    attrs: dict[str, str]
    elements: list[HtmlElement] = field(default_factory=list)
    text: list[str] = field(default_factory=list)


HTML_VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class DeckHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root_attrs: dict[str, str] = {}
        self.slides: list[HtmlSlide] = []
        self._stack: list[int | None] = []
        self._element_stack: list[HtmlElement] = []
        self._tag_stack: list[str] = []
        self.all_elements: list[HtmlElement] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "html":
            self.root_attrs = values
        classes = set(values.get("class", "").split())
        slide_index = self._stack[-1] if self._stack else None
        if "slide" in classes:
            self.slides.append(HtmlSlide(values))
            slide_index = len(self.slides) - 1
        element = HtmlElement(tag, values)
        self.all_elements.append(element)
        if slide_index is not None:
            self.slides[slide_index].elements.append(element)
        if tag in HTML_VOID_ELEMENTS:
            return
        self._stack.append(slide_index)
        self._element_stack.append(element)
        self._tag_stack.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in HTML_VOID_ELEMENTS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        while self._tag_stack:
            open_tag = self._tag_stack.pop()
            self._stack.pop()
            self._element_stack.pop()
            if open_tag == tag:
                break

    def handle_data(self, data: str) -> None:
        if self._element_stack:
            self._element_stack[-1].text.append(data)
        hidden_text = bool(
            self._element_stack
            and self._element_stack[-1].tag in {"script", "style"}
        )
        if self._stack and self._stack[-1] is not None and data.strip() and not hidden_text:
            self.slides[self._stack[-1]].text.append(data)


def parse_deck_html_contract(path: Path) -> DeckHtmlParser:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractError(f"HTML 无法读取：{path}: {exc}") from exc
    parser = DeckHtmlParser()
    try:
        parser.feed(source)
    except Exception as exc:  # HTMLParser can surface malformed entity errors.
        raise ContractError(f"HTML 无法解析：{path}: {exc}") from exc
    return parser


def _normalized_text(values: Iterable[str]) -> str:
    return unicodedata.normalize("NFKC", " ".join(values)).replace(" ", "")


def _resource_value(element: HtmlElement) -> str | None:
    if element.tag in {"script", "img", "source", "audio", "video", "iframe"}:
        return element.attrs.get("src")
    if element.tag == "link" and element.attrs.get("rel") != "canonical":
        return element.attrs.get("href")
    if element.tag == "object":
        return element.attrs.get("data")
    return None


CSS_URL_RE = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE | re.DOTALL)
CSS_IMPORT_RE = re.compile(
    r"@import\s+(?!url\()(['\"])(.*?)\1",
    re.IGNORECASE,
)
STYLE_BLOCK_RE = re.compile(r"<style\b[^>]*>(.*?)</style\s*>", re.IGNORECASE | re.DOTALL)
IMAGE_SUFFIXES = {
    ".apng",
    ".avif",
    ".bmp",
    ".gif",
    ".heic",
    ".heif",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".tif",
    ".tiff",
    ".webp",
}


def _css_urls(source: str) -> list[str]:
    values = [match.group(2).strip() for match in CSS_URL_RE.finditer(source)]
    values.extend(match.group(2).strip() for match in CSS_IMPORT_RE.finditer(source))
    return values


def _srcset_urls(value: str) -> list[str]:
    return [part.strip().split()[0] for part in value.split(",") if part.strip()]


def _reference_path(owner: Path, value: str) -> Path | None:
    parsed = urlparse(value.strip())
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    return (owner.parent / unquote(parsed.path)).resolve()


def _validate_local_resources(
    html_path: Path,
    source: str,
    parser: DeckHtmlParser,
    result: ValidationResult,
    *,
    code_prefix: str,
) -> None:
    pending_css: list[Path] = []

    def check(owner: Path, value: str, label: str) -> Path | None:
        value = value.strip()
        if not value or value.startswith(("#", "data:")):
            return None
        if not _is_local_relative(value):
            result.error(
                f"{code_prefix}.external_resource",
                label,
                f"资源必须使用本地相对路径：{value}",
            )
            return None
        resolved = _reference_path(owner, value)
        if resolved is None or not resolved.is_file():
            result.error(
                f"{code_prefix}.local_resource_missing",
                label,
                f"本地资源不存在：{value}",
            )
            return None
        return resolved

    for index, element in enumerate(parser.all_elements):
        label = f"{html_path}#resource[{index}]"
        values: list[str] = []
        resource = _resource_value(element)
        if resource:
            values.append(resource)
        if element.tag == "source":
            values.extend(_srcset_urls(element.attrs.get("srcset", "")))
        elif element.tag == "image":
            values.extend(element.attrs.get(name, "") for name in ("href", "xlink:href"))
        elif element.tag == "video":
            values.append(element.attrs.get("poster", ""))
        for value in values:
            resolved = check(html_path, value, label)
            if resolved is not None and resolved.suffix.casefold() == ".css":
                pending_css.append(resolved)
        for value in _css_urls(element.attrs.get("style", "")):
            resolved = check(html_path, value, label)
            if resolved is not None and resolved.suffix.casefold() == ".css":
                pending_css.append(resolved)

    for index, css in enumerate(STYLE_BLOCK_RE.findall(source)):
        for value in _css_urls(css):
            resolved = check(html_path, value, f"{html_path}#style[{index}]")
            if resolved is not None and resolved.suffix.casefold() == ".css":
                pending_css.append(resolved)

    visited: set[Path] = set()
    while pending_css:
        css_path = pending_css.pop().resolve()
        if css_path in visited:
            continue
        visited.add(css_path)
        try:
            css = css_path.read_text(encoding="utf-8")
        except OSError as exc:
            result.error(
                f"{code_prefix}.local_resource_missing",
                str(css_path),
                f"本地 CSS 无法读取：{exc}",
            )
            continue
        for value in _css_urls(css):
            resolved = check(css_path, value, str(css_path))
            if resolved is not None and resolved.suffix.casefold() == ".css":
                pending_css.append(resolved)


def _is_image_reference(value: str, resolved: Path | None) -> bool:
    folded = value.strip().casefold()
    if folded.startswith("data:image/"):
        return True
    suffix = Path(unquote(urlparse(value).path)).suffix.casefold()
    if suffix in IMAGE_SUFFIXES:
        return True
    if resolved is not None and resolved.is_file():
        try:
            head = resolved.read_bytes()[:512].lstrip()
        except OSError:
            return False
        return (
            head.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"BM"))
            or b"<svg" in head.lower()
        )
    return False


def _data_image_sha256(value: str) -> str | None:
    if not value.strip().casefold().startswith("data:image/"):
        return None
    try:
        header, payload = value.split(",", 1)
        raw = base64.b64decode(payload, validate=True) if ";base64" in header.casefold() else unquote(payload).encode("utf-8")
    except (ValueError, UnicodeError):
        return None
    return hashlib.sha256(raw).hexdigest()


def _resolve_deck_asset(deck_dir: Path, content_path: Path, locator: str) -> Path | None:
    candidates = [deck_dir / locator, content_path.parent / locator]
    return next((candidate.resolve() for candidate in candidates if candidate.is_file()), None)


def _validate_final_media_reference(
    value: str,
    owner: Path,
    attrs: Mapping[str, str] | None,
    label: str,
    deck_dir: Path,
    assets: Mapping[str, Mapping[str, Any]],
    asset_paths: Mapping[str, Path],
    evidence_asset_refs: set[str],
    result: ValidationResult,
) -> None:
    value = value.strip()
    if not value or value.startswith("#"):
        return
    resolved = _reference_path(owner, value)
    if not _is_image_reference(value, resolved):
        return

    source_assets = {
        asset_id: asset
        for asset_id, asset in assets.items()
        if asset.get("role") == "source"
    }
    reconstructed_assets = {
        asset_id: asset
        for asset_id, asset in assets.items()
        if asset.get("role") == "reconstructed"
    }
    data_hash = _data_image_sha256(value)
    if data_hash is not None:
        if any(asset.get("sha256") == data_hash for asset in source_assets.values()):
            result.error("asset.raw_media", label, "最终页面仍在使用原始图片数据")
        else:
            result.error("asset.html_unregistered", label, "内嵌图片不是登记过的重构成品")
        return
    if resolved is None:
        result.error("html.external_resource", label, f"图片必须使用 deck 内的本地相对路径：{value}")
        return
    if _relative_to(resolved, deck_dir) is None:
        result.error("asset.output_local", label, f"图片不能离开 deck 目录：{value}")
        return
    if not resolved.is_file():
        result.error("asset.html_missing", label, f"最终图片不存在：{value}")
        return
    actual_hash = _sha256(resolved)
    source_path_ids = {
        asset_id for asset_id in source_assets if asset_paths.get(asset_id) == resolved
    }
    source_hash_ids = {
        asset_id
        for asset_id, asset in source_assets.items()
        if asset.get("sha256") == actual_hash
    }
    if source_path_ids or source_hash_ids:
        result.error("asset.raw_media", label, "最终页面不能直接使用原始图片")
        return
    matched_ids = {
        asset_id
        for asset_id in reconstructed_assets
        if asset_paths.get(asset_id) == resolved
    }
    if not matched_ids:
        result.error("asset.html_unregistered", label, "最终图片不是登记过的重构成品")
        return
    matching_id = next(iter(sorted(matched_ids)))
    asset = reconstructed_assets[matching_id]
    if asset.get("sha256") != actual_hash:
        result.error("asset.html_fingerprint", label, "最终图片文件指纹与登记不一致")
        return
    if (
        matching_id in evidence_asset_refs
        and asset.get("creation_mode") == "reconstruct"
        and (attrs or {}).get("data-disclosure") != "重构示意"
    ):
        result.error("asset.html_disclosure", label, "证据重构图必须声明“重构示意”")


def _validate_embedded_media(
    html_path: Path,
    source: str,
    parser: DeckHtmlParser,
    content_path: Path,
    content: Mapping[str, Any],
    result: ValidationResult,
) -> None:
    deck_dir = html_path.parent.resolve()
    assets = _asset_map(content)
    asset_paths = {
        asset_id: path
        for asset_id, asset in assets.items()
        if (path := _local_asset_path(content_path, str(asset.get("locator", "")))) is not None
    }
    evidence_asset_refs = {
        ref
        for item in content_items(content)
        if item.get("epistemic_role") == "evidence"
        for ref in _refs(item.get("asset_refs"))
    }

    for index, element in enumerate(parser.all_elements):
        values: list[str] = []
        if element.tag == "img":
            values.append(element.attrs.get("src", ""))
        elif element.tag == "source":
            values.append(element.attrs.get("src", ""))
            values.extend(_srcset_urls(element.attrs.get("srcset", "")))
        elif element.tag == "image":
            values.extend(
                element.attrs.get(name, "") for name in ("href", "xlink:href")
            )
        elif element.tag == "video":
            values.append(element.attrs.get("poster", ""))
        if element.attrs.get("style"):
            values.extend(_css_urls(element.attrs["style"]))
        for value in values:
            _validate_final_media_reference(
                value,
                html_path,
                element.attrs,
                f"{html_path}#media[{index}]",
                deck_dir,
                assets,
                asset_paths,
                evidence_asset_refs,
                result,
            )

    for index, css in enumerate(STYLE_BLOCK_RE.findall(source)):
        for value in _css_urls(css):
            _validate_final_media_reference(
                value,
                html_path,
                None,
                f"{html_path}#style[{index}]",
                deck_dir,
                assets,
                asset_paths,
                evidence_asset_refs,
                result,
            )

    pending: list[Path] = []
    for element in parser.all_elements:
        if element.tag != "link" or "stylesheet" not in element.attrs.get("rel", "").split():
            continue
        css_path = _reference_path(html_path, element.attrs.get("href", ""))
        if css_path is not None and css_path.is_file():
            pending.append(css_path)
    visited: set[Path] = set()
    while pending:
        css_path = pending.pop().resolve()
        if css_path in visited:
            continue
        visited.add(css_path)
        try:
            css = css_path.read_text(encoding="utf-8")
        except OSError:
            continue
        for value in _css_urls(css):
            nested = _reference_path(css_path, value)
            if Path(unquote(urlparse(value).path)).suffix.casefold() == ".css":
                if nested is None or not nested.is_file():
                    result.error("html.external_resource", str(css_path), f"CSS 依赖必须是可读取的本地文件：{value}")
                else:
                    pending.append(nested)
                continue
            _validate_final_media_reference(
                value,
                css_path,
                None,
                str(css_path),
                deck_dir,
                assets,
                asset_paths,
                evidence_asset_refs,
                result,
            )


def _validate_echarts_html_binding(
    container: HtmlElement,
    renderer: Mapping[str, Any],
    slide: HtmlSlide,
    content: Mapping[str, Any],
    label: str,
    result: ValidationResult,
) -> None:
    binding = (
        renderer.get("data_binding")
        if isinstance(renderer.get("data_binding"), Mapping)
        else {}
    )
    dataset_id = str(binding.get("dataset_id", ""))
    if container.attrs.get("data-dataset-id") != dataset_id:
        result.error(
            "html.echarts_dataset_id",
            label,
            "ECharts 容器的 data-dataset-id 必须与 render plan 一致",
        )
    dataset_scripts = [
        element
        for element in slide.elements
        if element.tag == "script"
        and element.attrs.get("type", "").casefold() == "application/json"
        and element.attrs.get("data-wise-ppt-dataset") == dataset_id
    ]
    if len(dataset_scripts) != 1:
        result.error(
            "html.echarts_dataset",
            label,
            f"ECharts 数据集 {dataset_id} 必须在同一页恰好声明一次",
        )
        return
    raw = "".join(dataset_scripts[0].text).strip()
    try:
        actual = json.loads(raw)
    except (TypeError, ValueError) as exc:
        result.error(
            "html.echarts_dataset_json",
            label,
            f"ECharts 数据集不是有效 JSON：{exc}",
        )
        return
    data_ref = (
        binding.get("data_ref")
        if isinstance(binding.get("data_ref"), Mapping)
        else {}
    )
    item = next(
        (
            content_item
            for content_item in content_items(content)
            if str(content_item.get("id", "")) == str(data_ref.get("content_id", ""))
        ),
        None,
    )
    if item is None:
        return
    try:
        expected = _json_pointer_get(item, str(data_ref.get("json_pointer", "")))
    except ContractError:
        return
    if actual != expected:
        result.error(
            "html.echarts_dataset_mismatch",
            label,
            "页面内嵌的 ECharts JSON 与 content.json 中 data_ref 指向的数据不一致",
        )


def _validate_deck_html(
    path: Path,
    render: Mapping[str, Any],
    plan: Mapping[str, Any],
    content: Mapping[str, Any],
    catalog: CapabilityCatalog,
    theme: ThemeRecord,
) -> ValidationResult:
    result = ValidationResult()
    if not path.is_file():
        result.error("html.missing", str(path), "缺少可直接打开的 index.html")
        return result
    try:
        source = path.read_text(encoding="utf-8")
        parser = parse_deck_html_contract(path)
    except ContractError as exc:
        result.error("html.parse", str(path), str(exc))
        return result
    if parser.root_attrs.get("data-runtime") != "wise-ppt-deck":
        result.error("html.runtime_marker", str(path), '根节点必须声明 data-runtime="wise-ppt-deck"')
    if parser.root_attrs.get("data-typography-mode") != render.get("typography_mode"):
        result.error("html.typography_mode", str(path), "HTML 字体模式与 render plan 不一致")
    if "stageFit(" in source:
        result.error("html.stage_fit_duplicate", str(path), "正式 deck 不能再次调用页面级 stageFit")
    for element in parser.all_elements:
        for attribute in LEGACY_HTML_ATTRIBUTES & set(element.attrs):
            result.error("html.legacy_attribute", str(path), f"v2 禁止使用旧属性 {attribute}")
    _validate_local_resources(
        path,
        source,
        parser,
        result,
        code_prefix="html",
    )
    content_path = (path.parent / str(render.get("content_file", "content.json"))).resolve()
    _validate_embedded_media(path, source, parser, content_path, content, result)

    render_pages_list = render_pages(render)
    if len(parser.slides) != len(render_pages_list):
        result.error("html.page_count", str(path), "HTML 页面数与 render plan 不一致")
    plan_by_id = {str(item.get("page_id")): item for item in plan_pages(plan)}
    assets = _asset_map(content)
    evidence_asset_refs = {
        ref
        for item in content_items(content)
        if item.get("epistemic_role") == "evidence"
        for ref in _refs(item.get("asset_refs"))
    }
    render_by_id = {str(item.get("page_id")): item for item in render_pages_list}
    html_ids = [slide.attrs.get("data-page-id", "") for slide in parser.slides]
    if html_ids != [str(item.get("page_id")) for item in render_pages_list]:
        result.error("html.page_order", str(path), "HTML 页面顺序与 render plan 不一致")
    for index, slide in enumerate(parser.slides):
        page_id = slide.attrs.get("data-page-id", "")
        label = f"{path}#slide[{index}]"
        render_page = render_by_id.get(page_id)
        planned = plan_by_id.get(page_id)
        if render_page is None or planned is None:
            continue
        decision = render_page.get("layout_decision") if isinstance(render_page.get("layout_decision"), Mapping) else {}
        source_type = str(decision.get("source", ""))
        if slide.attrs.get("data-layout-source") != source_type:
            result.error("html.layout_source", label, "页面布局来源与 render plan 不一致")
        selected_id = str(decision.get("recipe_id", ""))
        if source_type in {"gallery", "composition"}:
            if slide.attrs.get("data-recipe-id") != selected_id:
                result.error("html.recipe_id", label, "页面 recipe ID 与 render plan 不一致")
        elif slide.attrs.get("data-recipe-id"):
            result.error("html.recipe_id", label, "custom 页面不能冒充 Gallery recipe")
        override = render_page.get("typography_decision")
        expected_mode = override.get("mode") if isinstance(override, Mapping) else None
        if slide.attrs.get("data-typography-mode") != (expected_mode or ""):
            if expected_mode or "data-typography-mode" in slide.attrs:
                result.error("html.typography_mode", label, "单页字体例外与 render plan 不一致")
        components = [element for element in slide.elements if element.attrs.get("data-block-id")]
        if source_type == "gallery":
            recipe = catalog.recipes.get(selected_id)
            defaults = _slot_map(recipe) if recipe else {}
            payload = decision.get("payload") if isinstance(decision.get("payload"), Mapping) else {}
            for binding in payload.get("bindings", []):
                if not isinstance(binding, Mapping):
                    continue
                slot_id = str(binding.get("slot_id", ""))
                matches = [item for item in slide.elements if item.attrs.get("data-slot-id") == slot_id]
                if len(matches) != 1:
                    result.error("html.gallery_slot", label, f"Gallery 槽位 {slot_id} 必须恰好出现一次")
                    continue
                spec = defaults.get(slot_id, {})
                default = spec.get("default_renderer") if isinstance(spec, Mapping) else {}
                attrs = matches[0].attrs
                for attr, key in (
                    ("data-renderer-kind", "renderer_kind"),
                    ("data-component-source", "component_source"),
                    ("data-component-id", "component_id"),
                ):
                    if attrs.get(attr) != default.get(key):
                        result.error("html.gallery_default", label, f"Gallery 槽位 {slot_id} 改动了默认组件")
                expected_refs = set(_refs(binding.get("content_refs")))
                actual_refs = set(attrs.get("data-content-ref", "").split())
                if not expected_refs.issubset(actual_refs):
                    result.error("html.content_binding", label, f"Gallery 槽位 {slot_id} 缺少内容绑定")
        else:
            for slot in render_page.get("slots", []):
                if not isinstance(slot, Mapping):
                    continue
                block_id = str(slot.get("block_id", ""))
                matches = [item for item in components if item.attrs.get("data-block-id") == block_id]
                if len(matches) != 1:
                    result.error("html.block_binding", label, f"表达块 {block_id} 必须恰好渲染一次")
                    continue
                attrs = matches[0].attrs
                renderer = slot.get("renderer") if isinstance(slot.get("renderer"), Mapping) else {}
                for attr, key in (
                    ("data-renderer-kind", "renderer_kind"),
                    ("data-component-source", "component_source"),
                    ("data-component-id", "component_id"),
                    ("data-theme-adapter-id", "theme_adapter_id"),
                ):
                    if attrs.get(attr) != str(renderer.get(key, "")):
                        result.error("html.renderer_binding", label, f"{block_id} 的 {attr} 与 render plan 不一致")
                expected_refs = set(_refs(renderer.get("content_refs")))
                actual_refs = set(attrs.get("data-content-ref", "").split())
                if not expected_refs.issubset(actual_refs):
                    result.error("html.content_binding", label, f"{block_id} 缺少内容引用")
                if renderer.get("component_source") == "echarts":
                    _validate_echarts_html_binding(
                        matches[0],
                        renderer,
                        slide,
                        content,
                        f"{label}#{block_id}",
                        result,
                    )

        visible = _normalized_text(slide.text)
        wanted_refs = set(page_content_refs(planned))
        for item in content_items(content):
            for atom in item.get("atomic_values", []):
                if not isinstance(atom, Mapping) or atom.get("id") not in wanted_refs:
                    continue
                value = _normalized_text([str(atom.get("value", ""))])
                if value and value not in visible:
                    result.error("coverage.atomic_value_missing", label, f"原子值未显示：{atom.get('id')}")

        for image in [item for item in slide.elements if item.tag == "img"]:
            src = image.attrs.get("src", "")
            asset_ref = image.attrs.get("data-asset-ref", "")
            asset = assets.get(asset_ref)
            if asset is None or asset.get("role") != "reconstructed":
                result.error("asset.html_unregistered", label, "最终 <img> 只能指向登记过的重构成品")
                continue
            if not _is_deck_relative(src):
                result.error("asset.output_local", label, "最终图片必须使用本地相对路径")
                continue
            resolved = _resolve_deck_asset(path.parent, path.parent / str(render.get("content_file")), src)
            if resolved is None:
                result.error("asset.html_missing", label, f"最终图片不存在：{src}")
                continue
            locator_path = _resolve_deck_asset(path.parent, path.parent / str(render.get("content_file")), str(asset.get("locator", "")))
            if locator_path is None or resolved != locator_path:
                result.error("asset.html_path", label, "最终图片路径与重构素材登记不一致")
            actual_hash = _sha256(resolved)
            if actual_hash != asset.get("sha256"):
                result.error("asset.html_fingerprint", label, "最终图片文件指纹与登记不一致")
            for source_ref in _refs(asset.get("derived_from")):
                source_asset = assets.get(source_ref)
                if source_asset and actual_hash == source_asset.get("sha256"):
                    result.error("asset.same_fingerprint", label, "最终图片仍是原素材文件")
            material_mode = ""
            block_id = image.attrs.get("data-block-id", "")
            if source_type != "gallery":
                slot = next(
                    (
                        item
                        for item in render_page.get("slots", [])
                        if isinstance(item, Mapping) and item.get("block_id") == block_id
                    ),
                    None,
                )
                if isinstance(slot, Mapping) and isinstance(slot.get("renderer"), Mapping):
                    treatment = slot["renderer"].get("material_treatment")
                    if isinstance(treatment, Mapping):
                        material_mode = str(treatment.get("mode", ""))
            expected_material = {
                "reconstruct": "reconstruction",
                "generate": "generation",
            }.get(material_mode, "")
            if image.attrs.get("data-material-mode") != expected_material:
                result.error("asset.html_disclosure", label, "最终图片的生成方式声明与 render plan 不一致")
            if (
                material_mode == "reconstruct"
                and asset_ref in evidence_asset_refs
                and image.attrs.get("data-disclosure") != "重构示意"
            ):
                result.error("asset.html_disclosure", label, "重构图片必须显示“重构示意”")
    return result


def validate_render_plan_target(target: Path, root: Path) -> ValidationResult:
    result = ValidationResult()
    try:
        path = find_document(target, "render")
    except ContractError as exc:
        result.error("config.render", str(target), str(exc))
        return result
    assert path is not None
    result.extend(validate_output_location(path, root, allow_internal=True))
    document = _load_document(path, result, str(path))
    if document is not None:
        result.extend(validate_render_document(document, path, root, require_html=False))
    return result


def validate_render_target(target: Path, root: Path) -> ValidationResult:
    result = ValidationResult()
    try:
        path = find_document(target, "render")
    except ContractError as exc:
        result.error("config.render", str(target), str(exc))
        return result
    assert path is not None
    result.extend(validate_output_location(path, root, allow_internal=True))
    document = _load_document(path, result, str(path))
    if document is not None:
        result.extend(validate_render_document(document, path, root, require_html=True))
    return result


def validate_coverage_target(target: Path, root: Path) -> ValidationResult:
    """Coverage is derived by plan and render validators; it has no second rule set."""

    result = validate_plan_target(target, root)
    result.extend(validate_render_plan_target(target, root))
    return result


def _validate_registry(catalog: CapabilityCatalog, result: ValidationResult) -> None:
    path = str(catalog.registry_path)
    if not catalog.renderer_kinds:
        result.error("capability.renderer_kinds", path, "公共能力注册表缺少 renderer_kinds")
    if not catalog.component_sources:
        result.error("capability.component_sources", path, "公共能力注册表缺少 component_sources")
    for renderer, source in catalog.allowed_pairs:
        if renderer not in catalog.renderer_kinds:
            result.error("capability.renderer_ref", path, f"组件来源引用未知渲染方式：{renderer}")
        if source not in catalog.component_sources:
            result.error("capability.source_ref", path, f"未知组件来源：{source}")


def validate_gallery(root: Path, theme_id: str | None = None) -> ValidationResult:
    result = ValidationResult()
    try:
        catalog = load_capability_catalog(root)
        theme = resolve_theme(root, theme_id)
    except ContractError as exc:
        result.error("config.gallery", str(root), str(exc))
        return result
    _validate_registry(catalog, result)
    _validate_theme_adapters(theme, catalog, result)
    manifest = catalog.manifest
    if manifest.get("recipe_count") != len(catalog.recipes):
        result.error("gallery.recipe_count", str(catalog.manifest_path), "recipe_count 与实际数量不一致")
    display_codes: list[str] = []
    for recipe_id, recipe in catalog.recipes.items():
        label = f"{catalog.manifest_path}#{recipe_id}"
        display_codes.append(str(recipe.get("display_code", "")))
        if recipe.get("structure_fingerprint") != _recipe_fingerprint(recipe):
            result.error("gallery.fingerprint", label, "结构指纹与结构合同不一致")
        slots = _slot_map(recipe)
        reading_order = _refs(recipe.get("reading_order"))
        if set(reading_order) != set(slots) or len(reading_order) != len(slots):
            result.error("gallery.reading_order", label, "阅读顺序必须完整覆盖且只覆盖槽位")
        contract = recipe.get("structure_contract") if isinstance(recipe.get("structure_contract"), Mapping) else {}
        if contract.get("region_count") != len(slots):
            result.error("gallery.region_count", label, "region_count 与槽位数量不一致")
        required = {slot_id for slot_id, slot in slots.items() if slot.get("required")}
        if set(_refs(contract.get("required_slot_ids"))) != required:
            result.error("gallery.required_slots", label, "结构合同的必填槽位与 slots 不一致")
        for slot_id, slot in slots.items():
            default = slot.get("default_renderer") if isinstance(slot.get("default_renderer"), Mapping) else {}
            pair = (str(default.get("renderer_kind", "")), str(default.get("component_source", "")))
            if pair not in catalog.allowed_pairs:
                result.error("gallery.default_renderer", label, f"槽位 {slot_id} 的默认组件组合未登记")
            if default.get("renderer_kind") not in slot.get("allowed_renderer_kinds", []):
                result.error("gallery.default_renderer", label, f"槽位 {slot_id} 默认渲染方式不在允许集合")
            if default.get("component_source") not in slot.get("allowed_component_sources", []):
                result.error("gallery.default_renderer", label, f"槽位 {slot_id} 默认组件来源不在允许集合")
            if int(slot.get("min_items", 0)) > int(slot.get("max_items", 0)):
                result.error("gallery.capacity", label, f"槽位 {slot_id} 最小容量大于最大容量")
        examples = recipe.get("examples") if isinstance(recipe.get("examples"), Mapping) else {}
        galleries = theme.theme_document.get("galleries") if isinstance(theme.theme_document.get("galleries"), Mapping) else {}
        if set(examples) != set(galleries):
            result.error("gallery.examples", label, "每个 recipe 必须覆盖主题登记的全部 Gallery 样例")
        for variant, value in examples.items():
            example = _resolve_repo_path(root, catalog.manifest_path, str(value))
            if not example.is_file():
                result.error("gallery.example_missing", label, f"样例不存在：{value}")
                continue
            expected_prefix = (root / "gallery" / theme.theme_id / str(variant) / "frames").resolve()
            if _relative_to(example, expected_prefix) is None:
                result.error("gallery.example_path", label, f"样例不在公共 Gallery 目录：{value}")
            try:
                parser = parse_deck_html_contract(example)
                source = example.read_text(encoding="utf-8")
            except ContractError as exc:
                result.error("gallery.example_parse", label, str(exc))
                continue
            if parser.root_attrs.get("data-runtime") != "wise-ppt-specimen":
                result.error("gallery.example_marker", label, "Gallery frame 必须声明 wise-ppt-specimen")
            if len(parser.slides) != 1:
                result.error("gallery.example_slide", label, "Gallery frame 必须恰好包含一页")
            stage_scripts = [
                element.attrs.get("src", "")
                for element in parser.all_elements
                if element.tag == "script" and element.attrs.get("src", "").endswith("runtime/stage-fit.js")
            ]
            if len(stage_scripts) != 1:
                result.error("gallery.stage_fit_runtime", label, "Gallery frame 必须且只能加载一次公共 stage-fit runtime")
            if re.search(r"function\s+stageFit\s*\(|(?:window|global)\.stageFit\s*=", source):
                result.error("gallery.stage_fit_duplicate", label, "Gallery frame 不能自行定义舞台缩放")
            _validate_local_resources(
                example,
                source,
                parser,
                result,
                code_prefix="gallery",
            )
            for element in parser.all_elements:
                for attribute in LEGACY_HTML_ATTRIBUTES & set(element.attrs):
                    result.error("gallery.legacy_attribute", label, f"v2 Gallery 禁止旧属性 {attribute}")
    for duplicate in sorted(_duplicates(display_codes)):
        result.error("gallery.display_code", str(catalog.manifest_path), f"display_code 重复：{duplicate}")
    for variant, relative in theme.theme_document.get("galleries", {}).items():
        index_path = _resolve_repo_path(root, theme.theme_path, str(relative))
        if not index_path.is_file():
            result.error("gallery.index_missing", str(theme.theme_path), f"Gallery 入口不存在：{relative}")
            continue
        try:
            parser = parse_deck_html_contract(index_path)
            source = index_path.read_text(encoding="utf-8")
        except ContractError as exc:
            result.error("gallery.index_parse", str(index_path), str(exc))
            continue
        if parser.root_attrs.get("data-runtime") != "wise-ppt-gallery":
            result.error("gallery.index_marker", str(index_path), "Gallery 入口必须声明 wise-ppt-gallery")
        stage_scripts = [
            element.attrs.get("src", "")
            for element in parser.all_elements
            if element.tag == "script" and element.attrs.get("src", "").endswith("runtime/stage-fit.js")
        ]
        if len(stage_scripts) != 1:
            result.error("gallery.stage_fit_runtime", str(index_path), "Gallery shell 必须且只能加载一次公共 stage-fit runtime")
        if re.search(r"function\s+stageFit\s*\(|(?:window|global)\.stageFit\s*=", source):
            result.error("gallery.stage_fit_duplicate", str(index_path), "Gallery shell 不能自行定义舞台缩放")
        _validate_local_resources(
            index_path,
            source,
            parser,
            result,
            code_prefix="gallery",
        )
    return result


def validate_core_purity(root: Path) -> ValidationResult:
    result = ValidationResult()
    targets = [root / "core" / "schemas", root / "core" / "references"]
    banned = ("themes/paper-ink", "paper-ink.")
    for target in targets:
        if not target.exists():
            continue
        for path in target.rglob("*"):
            if not path.is_file() or path.suffix.casefold() not in {".md", ".json"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for token in banned:
                if token in text:
                    result.error("core.theme_leak", str(path), f"Core 不应绑定具体主题：{token}")
    return result


def select_theme_for_target(target: Path, root: Path) -> str | None:
    raw = str(target)
    try:
        registry, _ = load_theme_registry(root)
    except ContractError:
        return None
    ids = {
        str(item.get("theme_id"))
        for item in registry.get("themes", [])
        if isinstance(item, Mapping) and item.get("theme_id")
    }
    if raw in ids:
        return raw
    resolved = target.expanduser().resolve()
    for theme_id in ids:
        if theme_id in resolved.parts:
            return theme_id
    return None


def validate_gallery_target(target: Path, root: Path) -> ValidationResult:
    return validate_gallery(root, select_theme_for_target(target, root))


def _pdf_page_count(path: Path) -> int:
    for module_name in ("pypdf", "PyPDF2"):
        try:
            module = __import__(module_name)
            reader = module.PdfReader(str(path))
            return len(reader.pages)
        except Exception:
            continue
    try:
        data = path.read_bytes()
    except OSError:
        return 0
    return len(re.findall(rb"/Type\s*/Page(?!s)\b", data))


def validate_delivery_target(target: Path, root: Path) -> ValidationResult:
    result = validate_render_target(target, root)
    deck = _deck_directory(target)
    html = deck / "index.html"
    pdfs = sorted(deck.glob("*.pdf")) if deck.is_dir() else []
    if not pdfs:
        result.error("delivery.pdf_missing", str(deck), "缺少可直接打开的 PDF")
        return result
    if len(pdfs) > 1:
        preferred = deck / f"{deck.name}.pdf"
        if preferred in pdfs:
            pdfs = [preferred]
        else:
            result.error("delivery.pdf_ambiguous", str(deck), "目录中存在多个 PDF，无法确定交付文件")
            return result
    pdf = pdfs[0]
    if pdf.stat().st_size <= 0:
        result.error("delivery.pdf_empty", str(pdf), "PDF 文件为空")
        return result
    try:
        html_pages = len(parse_deck_html_contract(html).slides)
    except ContractError:
        html_pages = 0
    pdf_pages = _pdf_page_count(pdf)
    if pdf_pages <= 0:
        result.error("delivery.pdf_parse", str(pdf), "无法读取 PDF 页数")
    elif pdf_pages != html_pages:
        result.error("delivery.page_count", str(pdf), "PDF 页数与 HTML 页面数不一致")
    return result


def validate_all(target: Path, root: Path) -> ValidationResult:
    result = ValidationResult()
    result.extend(validate_content_target(target, root))
    result.extend(validate_plan_target(target, root))
    result.extend(validate_render_target(target, root))
    result.extend(validate_core_purity(root))
    return result


VALIDATORS = {
    "content": validate_content_target,
    "plan": validate_plan_target,
    "render-plan": validate_render_plan_target,
    "render": validate_render_target,
    "coverage": validate_coverage_target,
    "gallery": validate_gallery_target,
    "core": lambda target, root: validate_core_purity(root),
    "delivery": validate_delivery_target,
    "all": validate_all,
}


def run_validation(kind: str, target: Path, root: Path) -> ValidationResult:
    validator = VALIDATORS.get(kind)
    if validator is None:
        result = ValidationResult()
        result.error("config.validator", str(target), f"未知校验阶段：{kind}")
        return result
    return validator(target, root)
