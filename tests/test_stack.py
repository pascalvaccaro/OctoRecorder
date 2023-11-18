import unittest
from instruments.blocks import Stack

class TestStack(unittest.TestCase):
    def setUp(self) -> None:
        self.block = Stack("length", 52, (1, 16))
        return super().setUp()
    
    def test_stack(self):
        """Stack is correctly formed"""
        self.assertEqual(self.block.name, "length", "block name is length")
        self.assertEqual(self.block.macro, 52, "block macro is 52")
        self.assertEqual(self.block.row_size, 1, "block row size is 1")
        self.assertEqual(self.block.col_size, 8, "block col size is 8")
        self.assertEqual(self.block.max_col_page, 1, "block max page is 1")
        self.assertIsNone(self.block.parent, "block is orphan")
        self.assertEqual(
            self.block.range, range(52, 53), "block macro ranges from 52 to 53"
        )

    def test_value_at(self):
        """Value at current page"""
        self.assertEqual(self.block.value_at(0), 0, "value is 0")
    
    def test_update_value(self):
        """Update value with a single arg"""
        self.block.update_value(0)
        self.assertListEqual(self.block.values[0], [127, *[0] * 15], "value is [127] + 15 * [0]")
        self.assertEqual(self.block.value_at(0), 1, "value is 1")
        self.block.update_value(15)
        self.assertListEqual(self.block.values[0], [127] * 16, "value is [127] * 16")

    def test_pagination(self):
        """Change value scrolling through pages"""
        for _ in self.block.next():
            pass
        self.assertEqual(self.block.cursor, 8, "cursor is 8")
        self.block.current = 52, 7
        for msg in self.block.message(52, 7):
            self.assertEqual(msg.value, 16, "value is 16")
        for _ in self.block.previous():
            pass
        self.assertEqual(self.block.cursor, 0, "cursor is 0")
        self.block.current = 52, 7
        for msg in self.block.message(52, 7):
            self.assertEqual(msg.value, 8, "value is 8")