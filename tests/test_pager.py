import unittest
from instruments.blocks import Pager, Block, Stack
from midi.messages import MidiNote


class TestPager(unittest.TestCase):
    def setUp(self) -> None:
        self.block = Pager(97, Block("step", 53, (5, 16)), Stack("length", 52, (1, 16)))
        return super().setUp()

    def test_block(self):
        """Pager is correctly formed"""
        self.assertEqual(self.block.name, "_", "block name is _")
        self.assertEqual(self.block.macro, 97, "block macro is 97")
        self.assertEqual(self.block.row_size, 1, "block row size is 1")
        self.assertEqual(self.block.col_size, 1, "block col size is 1")
        self.assertEqual(self.block.max_col_page, 0, "block max page is 0")
        self.assertIsNone(self.block.parent, "block is orphan")
        self.assertEqual(len(self.block.children), 2, "block has two children")
        self.assertEqual(self.block.range, [97, 96], "block macros are 96, 97")

    def test_get_block(self):
        """Get a pager block"""
        block = self.block.get(96)
        self.assertIsNotNone(block, "block should exist")
        block = self.block.get(97)
        self.assertIsNotNone(block, "block should exist")

    def test_get_child(self):
        """Get a pager's child block"""
        block = self.block.get(55)
        assert block is not None, "block should exist"
        self.assertEqual(block.macro, 53, "block macro is 53")
        no_block = self.block.get(65)
        self.assertIsNone(no_block, "block should not exist")

    def test_set_child(self):
        """Sets a pager's child's values"""
        self.block.set(55, 2, 127)
        for msg in self.block.current:
            assert isinstance(msg, MidiNote), "message is note"
            if msg.channel == 2 and msg.note == 55:
                return self.assertEqual(msg.velocity, 127, "value is 127")
        self.assertTrue(False, "value not found at 55 2")

    def test_current(self):
        """Displays the current values of the pager's children"""
        self.block.current = 97
        for child in self.block.children:
            self.assertEqual(child.cursor, 8, "cursor is 8")
        self.block.current = 97
        for child in self.block.children:
            self.assertEqual(child.cursor, 0, "cursor is 0")
