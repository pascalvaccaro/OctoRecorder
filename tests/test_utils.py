import unittest
import utils as u

class TestUtils(unittest.TestCase):
    def test_minmax(self):
        """Returns a number between 2 others"""
        self.assertEqual(u.minmax(0.5), 0.5, "value is 0.5")
        self.assertEqual(u.minmax(1.5), 1.0, "value is 1.0")
        self.assertEqual(u.minmax(0, 1), 1, "value is 1")
        self.assertEqual(u.minmax(2, 1, 2.5), 2, "value is 2")

    def test_clip(self):
        """Returns an integer between 2 numbers"""
        self.assertEqual(u.clip(64), 64, "value is 64")
        self.assertEqual(u.clip(-1), 0, "value is 0")
        self.assertEqual(u.clip(128), 127, "value is 127")
        self.assertEqual(u.clip(2.0, 3, 4), 3, "value is 3")
        self.assertEqual(u.clip(0.35, 0.3, 0.4), 0, "value is 0")

    def test_split(self):
        """Returns a tuple with a value and its opposite"""
        self.assertEqual(u.split(0.5), (0.5, 0.5), "value is 0.5*2")
        self.assertEqual(u.split(0.25), (0.25, 0.75), "value is 0.25,0.75")
        self.assertEqual(u.split(1.25), (1., 0.), "value is 1,0")

    def test_scroll(self):
        """Returns an integer that scrolls b/w 2 numbers"""
        self.assertEqual(u.scroll(4), 4, "value is 4")
        self.assertEqual(u.scroll(-1), 127, "value is 127")
        self.assertEqual(u.scroll(128), 0, "value is 0")
        self.assertEqual(u.scroll(4, 0, 3), 0, "value is 0")

    def test_t2i(self):
        """Returns an integer from a tuple"""
        self.assertEqual(u.t2i((4, 0)), 4, "value is 4")
        self.assertEqual(u.t2i(4), 4, "value is 4")

    def test_split_hex(self):
        "Returns a list of integers as each byte of a hex number"""
        self.assertEqual(u.split_hex(16), [1, 0], "value is [1, 0]")
        self.assertEqual(u.split_hex(130), [8, 2], "value is [8, 2]")

    def test_checksum(self):
        """Checksums a list of bytes, flattening them below 128 if necessary"""
        self.assertEqual(u.checksum([16, 0], [22, 16, 0, 0, 0, 1]), [16, 0, 22, 16, 0, 0, 0, 1, 73], "easy checksum")
        self.assertEqual(u.checksum([16, 0], [22, 45, 1, 0, 109]), [16, 0, 22, 45, 1, 0, 109, 63], "classic checksum")
        self.assertEqual(u.checksum([16, 0], [22, 158, 0]), [16, 0, 23, 30, 0, 59], "hard checksum")
        self.assertEqual(u.checksum([16, 0], [22, 160, 108]), [16, 0, 23, 32, 108, 77], "super hard checksum")
        try:
            value = u.checksum([216, 0], [22, 158, 0])
            self.assertNotIsInstance(value, int, "value is never")
        except Exception as e:
            self.assertIsInstance(e, u.MaxByteException, "checksum is impossible")
