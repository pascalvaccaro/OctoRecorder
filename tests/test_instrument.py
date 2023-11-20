import unittest
from instruments import DynaSynth
from instruments.messages import MacroMessage, StepMessage

request_values = [
    (65, 0, 0, 0, 0, 105, 17, 16, 0, 22, 5, 0, 0, 0, 1, 84),
    (65, 0, 0, 0, 0, 105, 17, 16, 0, 22, 16, 0, 0, 0, 1, 73),
    (65, 0, 0, 0, 0, 105, 17, 16, 0, 22, 29, 0, 0, 0, 6, 55),
    (65, 0, 0, 0, 0, 105, 17, 16, 0, 22, 39, 0, 0, 0, 3, 48),
    (65, 0, 0, 0, 0, 105, 17, 16, 0, 22, 49, 0, 0, 0, 3, 38),
    (65, 0, 0, 0, 0, 105, 17, 16, 0, 22, 59, 0, 0, 0, 125, 34),
]


class TestInstrument(unittest.TestCase):
    def setUp(self) -> None:
        self.instr = DynaSynth(21)
        return super().setUp()

    def test_instr(self):
        self.assertEqual(self.instr.instr, 22, "instr is 22")

    def test_idx(self):
        self.assertEqual(self.instr.idx, 1, "instr idx is 1")

    def test_request(self):
        for i, msg in enumerate(self.instr.request):
            with self.subTest(i=i):
                if msg is not None:
                    self.assertEqual(len(msg.data), 16, "request has 16 bytes")
                    self.assertEqual(msg.data, request_values[i], "values are correct")

    def test_receive(self):
        for msg in self.instr.receive(5, [32]):
            assert isinstance(msg, MacroMessage), "message is macro message"
            self.assertEqual(msg.macro, 176, "macro is 176")
            self.assertEqual(msg.idx, 1, "inst idx is 1")
            self.assertEqual(msg.value, 64, "value is 64")
        for msg in self.instr.receive(16, [64]):
            assert isinstance(msg, MacroMessage), "message is macro message"
            self.assertEqual(msg.macro, 180, "macro is 180")
            self.assertEqual(msg.idx, 1, "inst idx is 1")
            self.assertEqual(msg.value, 64, "value is 64")
        for i, msg in enumerate(self.instr.receive(29, [1, 1, 0, 50, 114, 14])):
            with self.subTest(i=i):
                assert isinstance(msg, MacroMessage), "message is macro message"
                if i == 1:
                    self.assertEqual(msg.macro, 181, "macro is 181")
                    self.assertEqual(msg.idx, 1, "inst idx is 1")
                    self.assertEqual(msg.value, 64, "value is 64")
                elif i == 2:
                    self.assertEqual(msg.macro, 178, "macro is 178")
                    self.assertEqual(msg.idx, 1, "inst idx is 1")
                    self.assertEqual(msg.value, 127, "value is 127")
                elif i == 3:
                    self.assertEqual(msg.macro, 182, "macro is 182")
                    self.assertEqual(msg.idx, 1, "inst idx is 1")
                    self.assertEqual(msg.value, 0, "value is 0")

    def test_send(self):
        lfo_msg = MacroMessage("synth", 1, 179, 64)
        grid_msg = StepMessage(1, 53, 82, 3, 12, 127)
        for msg in self.instr.send(lfo_msg):
            self.assertEqual(msg.address, (16, 0, 22, 39), "address is correct")
            self.assertEqual(msg.body, (1, 0, 109), "address is correct")
        for msg in self.instr.send(grid_msg):
            self.assertEqual(msg.address, (16, 0, 22, 75), "address is correct")
            self.assertEqual(msg.body[0], 33, "value is 33 (+1st)")
