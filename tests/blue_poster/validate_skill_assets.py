#!/usr/bin/env python3
"""Validate the Blue Poster release Skill and its bundled user examples."""

from __future__ import annotations

import re
import struct
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPO_ROOT / "blue-poster"
STYLES = {
    "S01": ("Blue Exposure Laboratory", "blue-exposure-laboratory"),
    "S02": ("Optical Field Array", "optical-field-array"),
    "S03": ("EdgeLoom Effect Sampler", "edgeloom-effect-sampler"),
    "S04": ("Quiet Effect Cabinet", "quiet-effect-cabinet"),
    "S05": ("Ink Grid Interference", "ink-grid-interference"),
    "S06": ("Cyanotype Optical Plates", "cyanotype-optical-plates"),
    "S07": ("Registration Weather", "registration-weather"),
    "S08": ("Material Tectonics", "material-tectonics"),
    "S09": ("Monochrome Data Garden", "monochrome-data-garden"),
    "S10": ("Selected Synthesis", "selected-synthesis"),
    "S11": ("Cyanotype Ma Registry", "cyanotype-ma-registry"),
}


def webp_size(head: bytes) -> tuple[int, int]:
    chunk = head[12:16]
    if chunk == b"VP8X":
        return int.from_bytes(head[24:27], "little") + 1, int.from_bytes(head[27:30], "little") + 1
    if chunk == b"VP8 ":
        return int.from_bytes(head[26:28], "little") & 0x3FFF, int.from_bytes(head[28:30], "little") & 0x3FFF
    if chunk == b"VP8L":
        bits = int.from_bytes(head[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    raise ValueError(f"unsupported WebP chunk: {chunk}")


def image_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        head = stream.read(32)
        if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
            return webp_size(head)
        if head.startswith(b"\x89PNG\r\n\x1a\n"):
            return struct.unpack(">II", head[16:24])
        if head[:2] != b"\xff\xd8":
            raise ValueError(f"unsupported image format: {path}")
        stream.seek(2)
        while True:
            marker_start = stream.read(1)
            if not marker_start:
                break
            if marker_start != b"\xff":
                continue
            marker = stream.read(1)
            while marker == b"\xff":
                marker = stream.read(1)
            if marker in {b"\xd8", b"\xd9"}:
                continue
            length_bytes = stream.read(2)
            if len(length_bytes) != 2:
                break
            length = struct.unpack(">H", length_bytes)[0]
            if marker and marker[0] in range(0xC0, 0xC4):
                data = stream.read(5)
                if len(data) != 5:
                    break
                height, width = struct.unpack(">HH", data[1:5])
                return width, height
            stream.seek(length - 2, 1)
    raise ValueError(f"could not read image dimensions: {path}")


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    programs_path = SKILL_ROOT / "references/style-programs.md"
    programs = programs_path.read_text(encoding="utf-8")
    headings = re.findall(r"^## (S\d{2}) · (.+)$", programs, flags=re.MULTILINE)
    found_ids = [style_id for style_id, _ in headings]
    require(len(found_ids) == len(set(found_ids)), "duplicate style heading IDs", errors)
    require(set(found_ids) == set(STYLES), f"style heading set mismatch: {found_ids}", errors)

    for style_id, (name, slug) in STYLES.items():
        require((style_id, name) in headings, f"heading mismatch for {style_id} {name}", errors)
        require(programs.count(f"EFFECT PROGRAM — {style_id} ") == 1, f"{style_id} must have one effect program", errors)
        references = (
            SKILL_ROOT / "assets/style-references/split-1x1" / f"R-{style_id}-A-{slug}-split.webp",
            SKILL_ROOT / "assets/style-references/tokyo-tower-full" / f"R-{style_id}-A-{slug}-full.webp",
        )
        for image in references:
            require(image.is_file(), f"missing style reference: {image}", errors)
            if image.is_file():
                width, height = image_size(image)
                require(width * 4 == height * 3, f"style reference is not exact 3:4: {image} ({width}x{height})", errors)

    selection = (SKILL_ROOT / "references/style-selection.md").read_text(encoding="utf-8")
    for style_id in STYLES:
        require(selection.count(f"| {style_id} |") == 1, f"selection matrix missing or duplicates {style_id}", errors)

    for template_name, mode_token in (
        ("prompt-full-design.md", "FULL DESIGN TRANSLATION"),
        ("prompt-split-1x1.md", "ONE-PASS SPLIT 1:1"),
    ):
        template = (SKILL_ROOT / "references" / template_name).read_text(encoding="utf-8")
        require(template.count("{{EFFECT_PROGRAM}}") == 2, f"{template_name} must document and contain one template placeholder", errors)
        require(mode_token in template, f"{template_name} missing mode token", errors)
        require("Image 1" in template, f"{template_name} missing original Image 1 contract", errors)
        template_match = re.search(r"```text\n(.*?)\n```", template, flags=re.DOTALL)
        require(template_match is not None, f"could not extract prompt body from {template_name}", errors)
        s08_match = re.search(r"```text\n(EFFECT PROGRAM — S08 .*?)\n```", programs, flags=re.DOTALL)
        require(s08_match is not None, "could not extract S08 program", errors)
        if template_match and s08_match:
            prompt_body = template_match.group(1)
            require(prompt_body.count("{{EFFECT_PROGRAM}}") == 1, f"{template_name} prompt body must contain one placeholder", errors)
            assembled = prompt_body.replace("{{EFFECT_PROGRAM}}", s08_match.group(1))
            require(assembled.count("EFFECT PROGRAM — S08") == 1, f"{template_name} S08 dry-run did not produce one program", errors)
            require("{{EFFECT_PROGRAM}}" not in assembled, f"{template_name} S08 dry-run left a placeholder", errors)

    catalog_path = SKILL_ROOT / "references/style-catalog.html"
    catalog = catalog_path.read_text(encoding="utf-8")
    links = re.findall(r"(?:src|href)=\"([^\"]+)\"", catalog)
    local_links = [
        link
        for link in links
        if not re.match(r"^[a-z]+:", link)
        and not link.startswith("#")
        and "${" not in link
    ]
    for link in local_links:
        require((catalog_path.parent / link).resolve().is_file(), f"broken catalog link: {link}", errors)
    for style_id in STYLES:
        require(catalog.count(f'id: "{style_id}"') == 1, f"catalog data missing or duplicates {style_id}", errors)
    require('id="split-1x1"' in catalog, "catalog missing split 1:1 section", errors)
    require('id="tokyo-tower-full"' in catalog, "catalog missing Tokyo Tower full section", errors)

    secondary = SKILL_ROOT / "assets/style-references/secondary/R-S08-B-material-tectonics-aesthetic-only-2x3.webp"
    require(secondary.is_file(), "missing S08 aesthetic-only secondary reference", errors)
    if secondary.is_file():
        width, height = image_size(secondary)
        require(width * 4 != height * 3, "S08 secondary should remain explicitly non-3:4", errors)
        require("aesthetic-only" in secondary.name, "non-delivery secondary reference is not labeled aesthetic-only", errors)

    for example_name in (
        "E01-FULL-S08-material-tectonics.webp",
        "E01-SPLIT-S08-material-tectonics.webp",
    ):
        example = SKILL_ROOT / "assets/examples" / example_name
        require(example.is_file(), f"missing E01 output: {example}", errors)
        if example.is_file():
            width, height = image_size(example)
            require(width * 4 == height * 3, f"E01 output is not exact 3:4: {example}", errors)
    require((SKILL_ROOT / "assets/examples/E01-SOURCE-tokyo-tower.jpg").is_file(), "missing E01 source", errors)

    if errors:
        print("FAIL skill assets")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS skill assets: 11 styles, 2 reference sections, templates, catalog links, and E01 case")
    return 0


if __name__ == "__main__":
    sys.exit(main())
