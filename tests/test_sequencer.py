import unittest
from midi.messages import InternalMessage, MacroMessage, StepMessage
from instruments.sequencer import Bar, Grid, Sequencer


class TestGridPad(unittest.TestCase):
    def setUp(self) -> None:
        self.pad = Grid((62, 32), 82, (8, 56), [96, 88, 80, 72, 64])
        return super().setUp()

    def test_from_vel(self):
        self.assertEqual(self.pad.from_vel(0, 0), 44, "value is 44")
        self.assertEqual(self.pad.from_vel(4, 0), 32, "value is 32")

    def test_to_vel(self):
        self.assertEqual(self.pad.to_vel(32), [0, 0, 0, 0, 127], "value is 0")
        self.assertEqual(self.pad.to_vel(38), [0, 0, 127, 127, 127], "value is 64")
        self.assertEqual(self.pad.to_vel(44), [127] * 5, "value is 127")


class TestBarPad(unittest.TestCase):
    def setUp(self) -> None:
        self.pad = Bar((158, -99), 85, (0, 118))
        return super().setUp()

    def test_from_internal(self):
        bars = InternalMessage("bars", 0, 4)
        length = MacroMessage("length", 0, 86, 8)
        off = MacroMessage("length", 0, 81, 0)
        self.assertEqual(self.pad.from_internal(bars), [161, 109], "rate is 109")
        self.assertEqual(self.pad.from_internal(length), [160, 8], "length is 8")
        self.assertEqual(self.pad.from_internal(off), [158, 0], "state is off")

    def test_to_internal(self):
        data_99 = [1, 0, 8, *[0] * 19, 0, 0, 8]
        self.assertEqual(self.pad.to_internal(0, data_99), 8, "length is 8")
        self.assertEqual(
            self.pad.to_internal(1, data_99), 0, "seq 2 is off,. length = 0"
        )


class TestSequencerPad(unittest.TestCase):
    def setUp(self) -> None:
        self.pad = Sequencer(
            (59, 125),
            53,
            Grid((62, -3), 82, (8, 56), [96, 77, 72, 66, 64]),  # pitch
            Grid((94, -35), 83),  # cutoff
            Grid((126, -67), 84),  # level
            Bar((158, -99), 85, (0, 118)),  # sequencer 1
            Bar((180, -121), 86, (0, 118)),  # sequencer 2
        )
        self.test_data = [
            *range(0, 3),
            *[32] * 32,
            *[50] * 32,
            *[100] * 32,
            1,
            0,
            8,
            *[0] * 19,
            0,
            0,
            8,
        ]
        return super().setUp()

    def test_to_internal_steps(self):
        for msg in self.pad.to_internal(0, self.test_data):
            self.assertEqual(msg.idx, 0, "idx is 0")
            if isinstance(msg, StepMessage):  # pitch
                self.assertEqual(msg.macro, 53, "macro is 53")
                self.assertIn(msg.value, range(82, 85), "value is 82")
                if msg.value == 82:
                    self.assertEqual(
                        msg.steps,
                        [[0, 0, 0, 0, 127]] * 16,
                        "pitch steps are one pad per step (0)",
                    )
                elif msg.value == 83:
                    self.assertEqual(
                        msg.steps,
                        [[0, 0, 0, 127, 127]] * 16,
                        "cutoff steps are 2 pads per step (0)",
                    )
                elif msg.value == 84:
                    self.assertEqual(
                        msg.steps, [[127] * 5] * 16, "level is max everywhere"
                    )

    def test_to_internal_target(self):
        for msg in self.pad.to_internal(0, self.test_data):
            self.assertEqual(msg.idx, 0, "idx is 0")
            if msg.type == "target":
                self.assertIn(msg.macro, range(82, 85), "macro is between 82 and 85")
                if msg.macro == 82:
                    self.assertEqual(msg.value, 0, "value is 0")
                elif msg.macro == 83:
                    self.assertEqual(msg.value, 1, "value is 1")
                elif msg.macro == 84:
                    self.assertEqual(msg.value, 2, "value is 2")

    def test_to_internal_seq(self):
        for msg in self.pad.to_internal(0, self.test_data):
            self.assertEqual(msg.idx, 0, "idx is 0")
            if msg.type == "seq":
                self.assertIn(msg.macro, [85, 86], "macro is between 85~86")
                if msg.macro == 85:
                    self.assertEqual(msg.value, 8, "seq 1 length is 8")
                if msg.macro == 86:
                    self.assertEqual(msg.value, 0, "seq 2 length is 0")

    def test_from_internal(self):
        step_message = MacroMessage("steps", 0, 55, 82, 2, 3, 127)
        target_message = MacroMessage("target", 0, 83, 1)
        seq_message = MacroMessage("length", 0, 85, 4)
        self.assertEqual(
            self.pad.from_internal(step_message),
            [66, 35],
            "address is 66/value is 35 (+3st)",
        )
        self.assertEqual(
            self.pad.from_internal(target_message), [60, 1], "address is 60/value is 1"
        )
        self.assertEqual(
            self.pad.from_internal(seq_message), [160, 4], "address is 85/value is 4"
        )
