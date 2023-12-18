import unittest
from utils import (
    minmax,
    clip,
    split,
    split_hex,
    scroll,
    t2i,
    checksum,
    MaxByteException,
)


class TestUtils(unittest.TestCase):
    def test_minmax(self):
        """Returns a number between 2 others"""
        self.assertEqual(minmax(0.5), 0.5, "value is 0.5")
        self.assertEqual(minmax(1.5), 1.0, "value is 1.0")
        self.assertEqual(minmax(0, 1), 1, "value is 1")
        self.assertEqual(minmax(2, 1, 2.5), 2, "value is 2")

    def test_clip(self):
        """Returns an integer between 2 numbers"""
        self.assertEqual(clip(64), 64, "value is 64")
        self.assertEqual(clip(-1), 0, "value is 0")
        self.assertEqual(clip(128), 127, "value is 127")
        self.assertEqual(clip(2.0, 3, 4), 3, "value is 3")
        self.assertEqual(clip(0.35, 0.3, 0.4), 0, "value is 0")

    def test_split(self):
        """Returns a tuple with a value and its opposite"""
        self.assertEqual(split(0.5), (0.5, 0.5), "value is 0.5*2")
        self.assertEqual(split(0.25), (0.25, 0.75), "value is 0.25,0.75")
        self.assertEqual(split(1.25), (1.0, 0.0), "value is 1,0")

    def test_scroll(self):
        """Returns an integer that scrolls b/w 2 numbers"""
        self.assertEqual(scroll(4), 4, "value is 4")
        self.assertEqual(scroll(-1), 127, "value is 127")
        self.assertEqual(scroll(128), 0, "value is 0")
        self.assertEqual(scroll(4, 0, 3), 0, "value is 0")

    def test_t2i(self):
        """Returns an integer from a tuple"""
        self.assertEqual(t2i((4, 0)), 4, "value is 4")
        self.assertEqual(t2i(4), 4, "value is 4")

    def test_split_hex(self):
        "Returns a list of integers as each byte of a hex number" ""
        self.assertEqual(split_hex(16), [1, 0], "value is [1, 0]")
        self.assertEqual(split_hex(130), [8, 2], "value is [8, 2]")

    def test_checksum(self):
        """Checksums a list of bytes, flattening them below 128 if necessary"""
        self.assertEqual(
            checksum([16, 0], [22, 16, 0, 0, 0, 1]),
            [16, 0, 22, 16, 0, 0, 0, 1, 73],
            "easy checksum",
        )
        self.assertEqual(
            checksum([16, 0], [22, 45, 1, 0, 109]),
            [16, 0, 22, 45, 1, 0, 109, 63],
            "classic checksum",
        )
        self.assertEqual(
            checksum([16, 0], [22, 158, 0]), [16, 0, 23, 30, 0, 59], "hard checksum"
        )
        self.assertEqual(
            checksum([16, 0], [22, 160, 108]),
            [16, 0, 23, 32, 108, 77],
            "super hard checksum",
        )
        try:
            value = checksum([216, 0], [22, 158, 0])
            self.assertNotIsInstance(value, int, "value is never")
        except Exception as e:
            self.assertIsInstance(e, MaxByteException, "checksum is impossible")
