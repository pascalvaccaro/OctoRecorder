import unittest
from instruments.blocks import Block, Nav, CCBlock, Stack
from midi.messages import MidiCC, MidiNote


class TestNavInstr(unittest.TestCase):
    def setUp(self) -> None:
        self.block = Nav("instr", 87, 4, CCBlock("synth", 48, 8))
        return super().setUp()

    def test_block(self):
        """Nav is correctly formed"""
        self.assertEqual(self.block.name, "instr", "block name is instr")
        self.assertEqual(self.block.macro, 87, "block macro is 87")
        self.assertEqual(self.block.row_size, 4, "block row size is 4")
        self.assertEqual(self.block.col_size, 1, "block col size is 1")
        self.assertEqual(self.block.max_row_page, 3, "block max page is 3")
        self.assertIsNone(self.block.parent, "block is orphan")
        self.assertEqual(
            self.block.range, range(87, 91), "block macro ranges from 87 to 91"
        )
        self.assertEqual(
            len(self.block.children), 4, "block has 4 versions of its children"
        )

    def test_child(self):
        """Nav children are correctly created"""
        for i, row in enumerate(self.block.children):
            with self.subTest("child", i=i):
                self.assertEqual(len(row), 1, "block has 1 child")
                self.assertIsInstance(row[0], CCBlock, "child is a CC block")
                self.assertEqual(row[0].parent, self.block, "child has parent")
                self.assertEqual(row[0].macro, 176, "child macro is 176")
                self.assertEqual(row[0].address, [0, 0], "address is 0,0")

    def test_get(self):
        """Get a nav block"""
        block = self.block.get(1, 87)
        assert block is not None, "block should exist"
        self.assertEqual(87, block.macro, "block macro is 87")

    def test_navigation(self):
        """Change values scrolling through nav pages"""
        self.assertEqual(0, self.block.row_idx, "block page is 0")
        self.block.current = 88, 0, 127
        messages = list(self.block.message(88, 0))
        self.assertEqual(1, self.block.row_idx, "block page is 1")
        self.assertEqual(len(messages), 12, "there are 12 messages")
        for msg in messages[0:4]:
            assert isinstance(msg, MidiNote), "message is note"
            self.assertIn(msg.note, range(87, 91), "note is between 87 and 90")
            if msg.note == 88:
                self.assertEqual(msg.velocity, 127, "velocity is 127 for note 88")
            else:
                self.assertEqual(msg.velocity, 0, "velocity is 0 for other notes")
        for msg in messages[4:12]:
            assert isinstance(msg, MidiCC), "message is control"
            self.assertIn(msg.control, range(48, 56), "control is between 48 and 55")
            self.assertEqual(msg.value, 0, "value is 127")

    def test_set(self):
        """Sets a nav child's value and display it on the current page"""
        no_messages = list(self.block.set(1, 178, 64))
        self.assertEqual(len(no_messages), 0, "nothing to display, page is not current")
        block = self.block.get(1, 178)
        assert block is not None, "block should exist"
        self.assertEqual(block.values[2][0], 64, "value is 64")
        messages = list(self.block.set(0, 178, 100))
        self.assertEqual(len(messages), 8, "8 midi messages to display")
        for i, msg in enumerate(messages):
            with self.subTest("messages", i=i):
                assert isinstance(msg, MidiCC), "message is control"
                self.assertEqual(msg.channel, 0, "msg channel is 0")
                self.assertEqual(msg.control, 48 + i, "msg control is %i" % (48 + i))
                if msg.control == 50:
                    self.assertEqual(msg.value, 100, "msg value is 100")
                else:
                    self.assertEqual(msg.value, 0, "msg value is 0")
