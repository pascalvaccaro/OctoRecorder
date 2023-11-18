import unittest
from instruments.blocks import Block, CCBlock


class TestBlock(unittest.TestCase):
    def setUp(self) -> None:
        self.block = Block("step", 53, (5, 16))
        return super().setUp()

    def test_block(self):
        """Block is correctly formed"""
        self.assertEqual(self.block.name, "step", "block name is step")
        self.assertEqual(self.block.macro, 53, "block macro is 53")
        self.assertEqual(self.block.row_size, 5, "block row size is 5")
        self.assertEqual(self.block.col_size, 8, "block col size is 8")
        self.assertEqual(self.block.max_col_page, 1, "block max page is 1")
        self.assertIsNone(self.block.parent, "block is orphan")
        self.assertEqual(
            self.block.range, range(53, 58), "block macro ranges from 53 to 58"
        )

    def test_current(self):
        """Set the block's value and display it"""
        self.block.set(55, 4, 127)
        for msg in self.block.current:
            if msg.channel == 4 and msg.note == 55:
                self.assertEqual(msg.velocity, 127, "value at 55 4 is 127")
            else:
                self.assertEqual(
                    msg.velocity, 0, "value at [%i][%i] is 0" % (msg.channel, msg.note)
                )

    def test_off(self):
        """Turn off all displays"""
        self.block.current = 55, 4, 127
        for msg in self.block.off:  # type: ignore
            self.assertEqual(msg.velocity, 0, "off outputs 0 everywhere")

    def test_empty(self):
        """Value at current page is 0"""
        self.block.current = 55, 4, 127
        self.assertFalse(self.block.empty(55, 4), "55 4 should have value")
        self.assertTrue(self.block.empty(53), "53 0 should be empty")

    def test_value_at(self):
        """Value at current page"""
        self.block.current = 55, 4, 127
        self.assertEqual(self.block.value_at(55, 4), 127, "value at 55 4 is 127")
        self.assertEqual(self.block.value_at(55), 0, "value at 55 0 is 0")

    def test_update_value(self):
        """Update value"""
        self.assertEqual(self.block.values[2][4], 0, "value at 2 4 is 0")
        self.block.update_value(2, 4, 127)
        self.assertEqual(self.block.values[2][4], 127, "value at 2 4 is 127")
        self.block.update_value(3, 127)
        self.assertEqual(self.block.values[3][0], 127, "value at 3 0 is 127")
        self.block.update_value(3)
        self.assertEqual(self.block.values[3][0], 0, "value at 3 0 is 0 (toggled)")

    def test_get_block(self):
        """Get a block by its macro"""
        block = self.block.get(55)
        self.assertIsNotNone(block, "block should exist")
        no_block = self.block.get(65)
        self.assertIsNone(no_block, "block should not exist")

    def test_set_block(self):
        """Set a block value by its macro and column"""
        self.assertEqual(self.block.values[2][4], 0, "value at 2 4 is 0")
        self.block.set(55, 4, 127)
        self.assertEqual(self.block.values[2][4], 127, "value at 2 4 is 127")
        self.block.set(56, 127)
        self.assertEqual(self.block.values[3][0], 127, "value at 3 0 is 127")
        self.block.set(56)
        self.assertEqual(self.block.values[3][0], 0, "value at 3 0 is 0 (toggled)")

    def test_next(self):
        """Scroll to the next page"""
        self.assertEqual(0, self.block.cursor, "cursor is 0")
        for _ in self.block.next():
            pass
        self.assertEqual(8, self.block.cursor, "cursor is 8")

    def test_previous(self):
        """Scroll to the previous page"""
        self.assertEqual(0, self.block.cursor, "cursor is 0")
        for _ in self.block.previous():
            pass
        self.assertEqual(8, self.block.cursor, "cursor is 8")

    def test_message(self):
        """Send a message to the world"""
        self.block.current = 55, 5
        for msg in self.block.message(55, 5):
            self.assertEqual(msg.type, "step", "msg type is step")
            self.assertEqual(msg.idx, 0, "msg idx is 0")
            self.assertEqual(msg.macro, 53, "msg macro is 53")
            self.assertEqual(msg.value, 127, "msg value is 127")

    def test_pagination(self):
        """Change values across pages"""
        self.block.current = 55, 5
        for _ in self.block.next():
            pass
        self.assertEqual(self.block.values[2][5], 127, "value at 2 5 is 127")
        self.block.current = 55, 5
        for _ in self.block.previous():
            pass
        self.assertEqual(self.block.values[2][5], 127, "value at 2 5 is 127")
        self.block.current = 55, 5
        self.assertEqual(self.block.values[2][5], 0, "value at 2 5 is 0")
        self.assertEqual(self.block.values[2][13], 127, "value at 2 13 is 127")


class TestCCBlock(unittest.TestCase):
    def setUp(self) -> None:
        self.block = CCBlock("synth", 48, 8)
        return super().setUp()

    def test_block(self):
        """CCBlock is correctly formed"""
        self.assertEqual(self.block.name, "synth", "block name is synth")
        self.assertEqual(self.block.macro, 176, "block macro is 176")
        self.assertEqual(self.block.row_size, 8, "block row size is 8")
        self.assertEqual(self.block.col_size, 1, "block col size is 1")
        self.assertEqual(self.block.max_col_page, 0, "block max page is 0")
        self.assertIsNone(self.block.parent, "block is orphan")
        self.assertEqual(
            self.block.range, range(176, 184), "block macro ranges from 176 to 184"
        )

    def test_message(self):
        """Sends a control message (xfade or synth)"""
        self.block.current = 178, 0, 64
        for msg in self.block.message(178):
            self.assertEqual(msg.type, "xfade", "msg type is xfade")
            self.assertEqual(msg.data, (2, 64), "data is (2, 64)")
        self.block.row_idx = 1
        for msg in self.block.message(178):
            self.assertEqual(msg.type, "synth", "msg type is synth")
            self.assertEqual(msg.data, (0, 178, 64), "data is (0, 178, 64)")

    def test_current(self):
        """Displays the current page with MidiCC"""
        self.block.set(55, 4, 127)
        for msg in self.block.current:  # type: ignore
            if msg.channel == 4 and msg.control == 55:
                self.assertEqual(msg.value, 127, "value at 55 4 is 127")
            else:
                self.assertEqual(
                    msg.value, 0, "value at [%i][%i] is 0" % (msg.channel, msg.control)
                )
