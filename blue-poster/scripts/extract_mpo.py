#!/usr/bin/env python3
"""Inspect and extract JPEG frames from a CIPA Multi-Picture Object file.

MPO is a JPEG stream with an APP2/MPF index and one or more JPEG frames.  This
module intentionally uses only the Python standard library so the input can be
normalized before it is handed to the host image-generation tool.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


class MPOError(ValueError):
    """Raised when an input is not a readable MPO file."""


@dataclass(frozen=True)
class MPImage:
    """One JPEG frame listed by the MPF index."""

    index: int
    attributes: int
    size: int
    data_offset: int
    absolute_offset: int
    dependent_image_1: int
    dependent_image_2: int

    @property
    def image_format(self) -> int:
        return (self.attributes >> 24) & 0x07

    @property
    def image_type(self) -> int:
        return self.attributes & 0x00FFFFFF


@dataclass(frozen=True)
class MPOInfo:
    """Parsed MPO metadata and frame index."""

    endian: str
    tiff_offset: int
    frames: tuple[MPImage, ...]


_TIFF_TYPE_SIZES = {
    1: 1,  # BYTE
    2: 1,  # ASCII
    3: 2,  # SHORT
    4: 4,  # LONG
    5: 8,  # RATIONAL
    7: 1,  # UNDEFINED
    9: 4,  # SLONG
    10: 8,  # SRATIONAL
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MPOError(message)


def _u16(data: bytes, offset: int, endian: str) -> int:
    _require(offset >= 0 and offset + 2 <= len(data), "MPO TIFF field exceeds file bounds")
    return struct.unpack_from(endian + "H", data, offset)[0]


def _u32(data: bytes, offset: int, endian: str) -> int:
    _require(offset >= 0 and offset + 4 <= len(data), "MPO TIFF field exceeds file bounds")
    return struct.unpack_from(endian + "I", data, offset)[0]


def _find_mpf_tiff_offset(data: bytes) -> int:
    """Return the file offset of the TIFF endian field in APP2/MPF."""

    _require(data[:2] == b"\xff\xd8", "input does not start with a JPEG SOI marker")
    position = 2
    while position + 4 <= len(data):
        _require(data[position] == 0xFF, "malformed JPEG marker before MPF segment")
        while position < len(data) and data[position] == 0xFF:
            position += 1
        _require(position < len(data), "truncated JPEG marker before MPF segment")
        marker = data[position]
        position += 1

        # These markers have no length field.  SOI/EOI should not occur here,
        # while TEM and restart markers can legally be skipped.
        if marker in {0x01, *range(0xD0, 0xD8)}:
            continue
        if marker == 0xDA:
            break  # MPF must be in the header, before compressed scan data.
        _require(position + 2 <= len(data), "truncated JPEG segment length")
        segment_length = struct.unpack_from(">H", data, position)[0]
        _require(segment_length >= 2, "invalid JPEG segment length")
        payload_start = position + 2
        segment_end = payload_start + segment_length - 2
        _require(segment_end <= len(data), "JPEG segment exceeds file bounds")
        if marker == 0xE2 and data[payload_start:payload_start + 4] == b"MPF\x00":
            tiff_offset = payload_start + 4
            _require(data[tiff_offset:tiff_offset + 4] in {b"II*\x00", b"MM\x00*"}, "MPF TIFF header is invalid")
            return tiff_offset
        position = segment_end

    raise MPOError("JPEG does not contain an APP2/MPF segment")


def _entry_value(data: bytes, tiff_offset: int, entry_offset: int, endian: str) -> tuple[int, int, bytes]:
    type_code = _u16(data, entry_offset + 2, endian)
    count = _u32(data, entry_offset + 4, endian)
    type_size = _TIFF_TYPE_SIZES.get(type_code)
    _require(type_size is not None, f"unsupported MPF TIFF type {type_code}")
    value_size = type_size * count
    raw_value = data[entry_offset + 8:entry_offset + 12]
    if value_size <= 4:
        value = raw_value[:value_size]
    else:
        value_offset = _u32(raw_value, 0, endian)
        value_start = tiff_offset + value_offset
        value_end = value_start + value_size
        _require(value_end <= len(data), "MPF TIFF value exceeds file bounds")
        value = data[value_start:value_end]
    return type_code, count, value


def _scalar(value: bytes, type_code: int, endian: str) -> int:
    if type_code == 3:
        _require(len(value) >= 2, "short MPF TIFF value is truncated")
        return struct.unpack(endian + "H", value[:2])[0]
    if type_code in {4, 9}:
        _require(len(value) >= 4, "long MPF TIFF value is truncated")
        return struct.unpack(endian + "I", value[:4])[0]
    raise MPOError(f"MPF scalar uses unsupported TIFF type {type_code}")


def parse_mpo(data: bytes) -> MPOInfo:
    """Parse an MPO byte stream and validate every listed JPEG frame."""

    tiff_offset = _find_mpf_tiff_offset(data)
    endian_marker = data[tiff_offset:tiff_offset + 2]
    endian = "<" if endian_marker == b"II" else ">"
    _require(_u16(data, tiff_offset + 2, endian) == 42, "MPF TIFF magic is invalid")
    first_ifd = _u32(data, tiff_offset + 4, endian)
    ifd_offset = tiff_offset + first_ifd
    entry_count = _u16(data, ifd_offset, endian)
    entries_start = ifd_offset + 2
    entries_end = entries_start + entry_count * 12
    _require(entries_end + 4 <= len(data), "MPF index IFD exceeds file bounds")

    number_of_images: int | None = None
    image_list: bytes | None = None
    for entry_index in range(entry_count):
        entry_offset = entries_start + entry_index * 12
        tag = _u16(data, entry_offset, endian)
        type_code, count, value = _entry_value(data, tiff_offset, entry_offset, endian)
        if tag == 0xB001:
            _require(count == 1, "MPF NumberOfImages must contain one value")
            number_of_images = _scalar(value, type_code, endian)
        elif tag == 0xB002:
            image_list = value

    _require(number_of_images is not None and number_of_images > 0, "MPF NumberOfImages is missing or invalid")
    _require(image_list is not None, "MPF MPImageList is missing")
    expected_list_size = number_of_images * 16
    _require(len(image_list) >= expected_list_size, "MPF MPImageList is truncated")

    frames: list[MPImage] = []
    for index in range(number_of_images):
        entry = image_list[index * 16:(index + 1) * 16]
        attributes, size, data_offset, dependent_1, dependent_2 = struct.unpack(endian + "IIIHH", entry)
        # Per CIPA MPF, the first individual image is the primary JPEG and its
        # data offset is NULL. Other offsets are relative to the MP endian field.
        absolute_offset = 0 if index == 0 else tiff_offset + data_offset
        absolute_end = absolute_offset + size
        _require(size > 0 and absolute_end <= len(data), f"MPF frame {index} exceeds file bounds")
        frame = data[absolute_offset:absolute_end]
        _require(frame[:2] == b"\xff\xd8" and frame[-2:] == b"\xff\xd9", f"MPF frame {index} is not a complete JPEG")
        frames.append(MPImage(index, attributes, size, data_offset, absolute_offset, dependent_1, dependent_2))

    return MPOInfo(endian, tiff_offset, tuple(frames))


def extract_frame(data: bytes, frame_index: int = 0) -> bytes:
    """Extract one complete JPEG frame from an MPO byte stream."""

    info = parse_mpo(data)
    if frame_index < 0 or frame_index >= len(info.frames):
        raise MPOError(f"frame index {frame_index} is out of range; file contains {len(info.frames)} frame(s)")
    frame = info.frames[frame_index]
    return data[frame.absolute_offset:frame.absolute_offset + frame.size]


def _json_info(path: Path, info: MPOInfo) -> dict[str, object]:
    return {
        "path": str(path),
        "format": "MPO",
        "frame_count": len(info.frames),
        "frames": [
            {
                **asdict(frame),
                "image_format": frame.image_format,
                "image_type": frame.image_type,
            }
            for frame in info.frames
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect or extract JPEG frames from an MPO file.")
    parser.add_argument("input", type=Path, help="MPO input path")
    parser.add_argument("--frame", type=int, default=0, help="zero-based frame to extract (default: 0)")
    parser.add_argument("--output", type=Path, help="output JPEG path; required unless --list is used")
    parser.add_argument("--list", action="store_true", help="print MPF frame metadata as JSON")
    parser.add_argument("--force", action="store_true", help="allow replacing an existing output file")
    args = parser.parse_args()

    try:
        data = args.input.read_bytes()
        info = parse_mpo(data)
        if args.list:
            print(json.dumps(_json_info(args.input, info), ensure_ascii=False, indent=2))
        if args.output is None:
            if not args.list:
                parser.error("--output is required unless --list is used")
            return 0
        if args.output.exists() and not args.force:
            raise MPOError(f"output already exists: {args.output} (use --force to replace it)")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(extract_frame(data, args.frame))
        print(f"PASS extracted frame {args.frame}/{len(info.frames) - 1}: {args.output}")
        return 0
    except (OSError, MPOError) as exc:
        print(f"FAIL {args.input}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
