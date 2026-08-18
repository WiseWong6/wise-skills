#!/usr/bin/env python3
"""Validate PNG/JPEG dimensions for a Blue Poster output."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path


def image_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        head = stream.read(24)
        if head.startswith(b"\x89PNG\r\n\x1a\n"):
            return struct.unpack(">II", head[16:24])
        if head[:2] != b"\xff\xd8":
            raise ValueError("only PNG and JPEG outputs are supported")
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
                height, width = struct.unpack(">HH", data[1:5])
                return width, height
            stream.seek(length - 2, 1)
    raise ValueError("could not read image dimensions")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--mode", choices=("full", "split"), required=True)
    parser.add_argument("--require-size", metavar="WIDTHxHEIGHT")
    args = parser.parse_args()

    if not args.image.is_file():
        parser.error(f"image does not exist: {args.image}")
    try:
        width, height = image_size(args.image)
    except ValueError as exc:
        print(f"FAIL {args.image}: {exc}")
        return 1

    failures: list[str] = []
    if width * 4 != height * 3:
        failures.append(f"ratio is {width}:{height}, not exact 3:4")
    if args.require_size:
        try:
            required_width, required_height = (int(value) for value in args.require_size.lower().split("x", 1))
        except (TypeError, ValueError):
            parser.error("--require-size must look like 1086x1448")
        if (width, height) != (required_width, required_height):
            failures.append(f"size is {width}x{height}, expected {required_width}x{required_height}")
    if args.mode == "split" and height % 2:
        failures.append("split output height is odd, so an exact integer midpoint is impossible")

    if failures:
        print(f"FAIL {args.image}")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"PASS {args.mode}: {args.image} is {width}x{height}, exact 3:4")
    if args.mode == "split":
        print(f"MANUAL CHECK REQUIRED: verify one visible boundary at y={height // 2} and equal upper/lower regions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
