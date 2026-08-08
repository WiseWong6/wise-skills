#!/usr/bin/env python3
"""Decode QR codes from a final screenshot and compare an expected payload."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decode QR codes from a rendered screenshot and verify the payload."
    )
    parser.add_argument("image", type=Path, help="Final PNG/JPEG screenshot")
    parser.add_argument("expected", help="Expected QR payload")
    return parser.parse_args()


def decode(path: Path) -> list[str]:
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "ERROR QR verification requires Python OpenCV (cv2); "
            "no decoder fallback was used."
        ) from exc

    image = cv2.imread(str(path))
    if image is None:
        raise SystemExit(f"ERROR cannot read image: {path}")

    detector = cv2.QRCodeDetector()
    decoded: list[str] = []
    try:
        ok, values, _points, _straight = detector.detectAndDecodeMulti(image)
        if ok:
            decoded.extend(value for value in values if value)
    except (AttributeError, cv2.error):
        pass

    if not decoded:
        value, _points, _straight = detector.detectAndDecode(image)
        if value:
            decoded.append(value)
    return decoded


def main() -> int:
    args = parse_args()
    if not args.image.is_file():
        raise SystemExit(f"ERROR image does not exist: {args.image}")
    values = decode(args.image)
    if args.expected not in values:
        actual = repr(values) if values else "no QR payload decoded"
        raise SystemExit(
            f"FAIL QR {args.image}: expected {args.expected!r}; actual {actual}"
        )
    print(f"PASS QR {args.image}: {args.expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
