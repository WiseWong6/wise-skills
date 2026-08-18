import struct
import unittest

from scripts.extract_mpo import MPOError, extract_frame, parse_mpo


def build_fixture_mpo() -> tuple[bytes, bytes, bytes]:
    """Build a small valid MPF index around two JPEG-shaped byte streams."""

    second = b"\xff\xd8SECOND\xff\xd9"
    tiff_offset = 10  # SOI (2) + APP2 marker/length (4) + MPF signature (4)
    image_list_offset = 38  # TIFF header (8) + IFD (30)

    def build_primary(second_offset: int, primary_size: int) -> bytes:
        entries = b"".join(
            (
                struct.pack("<HHI", 0xB001, 4, 1) + struct.pack("<I", 2),
                struct.pack("<HHI", 0xB002, 7, 32) + struct.pack("<I", image_list_offset),
            )
        )
        mp_entries = b"".join(
            (
                struct.pack("<IIIHH", 0x00030000, primary_size, 0, 0, 0),
                struct.pack("<IIIHH", 0x00000000, len(second), second_offset, 0, 0),
            )
        )
        tiff = b"II*\x00" + struct.pack("<I", 8) + struct.pack("<H", 2) + entries + struct.pack("<I", 0) + mp_entries
        payload = b"MPF\x00" + tiff
        app2 = b"\xff\xe2" + struct.pack(">H", len(payload) + 2) + payload
        primary = b"\xff\xd8" + app2 + b"PRIMARY" + b"\xff\xd9"
        return primary

    primary = build_primary(0, 0)
    primary = build_primary(len(primary) - tiff_offset, len(primary))
    return primary + second, primary, second


class ExtractMPOTests(unittest.TestCase):
    def test_parse_and_extract_primary_and_secondary_frames(self) -> None:
        mpo, primary, second = build_fixture_mpo()
        info = parse_mpo(mpo)
        self.assertEqual(len(info.frames), 2)
        self.assertEqual(info.frames[0].absolute_offset, 0)
        self.assertEqual(info.frames[1].absolute_offset, len(primary))
        self.assertEqual(extract_frame(mpo, 0), primary)
        self.assertEqual(extract_frame(mpo, 1), second)

    def test_out_of_range_frame_is_rejected(self) -> None:
        mpo, _, _ = build_fixture_mpo()
        with self.assertRaises(MPOError):
            extract_frame(mpo, 2)

    def test_missing_mpf_is_rejected(self) -> None:
        with self.assertRaises(MPOError):
            parse_mpo(b"\xff\xd8\xff\xd9")


if __name__ == "__main__":
    unittest.main()
