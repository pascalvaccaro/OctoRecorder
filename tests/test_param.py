import unittest
from instruments.params import Pot, Switch, LFO, Bipolar
from instruments.messages import MacroMessage


class TestPotParam(unittest.TestCase):
    def setUp(self) -> None:
        self.param = Pot((8, 3), 48, (4, 28))
        return super().setUp()

    def test_param(self):
        """Pot is correctly formed"""
        self.assertEqual(self.param.address, 8, "param address is 8")
        self.assertEqual(self.param.offset, 3, "param offset is 3")
        self.assertEqual(self.param.min_value, 4, "param min value is 4")
        self.assertEqual(self.param.max_value, 28, "param max value is 28")
        self.assertEqual(self.param.macro, 176, "param macro is 176")

    def test_request(self):
        """Request the param address and offset"""
        for request in self.param.request:
            self.assertEqual(
                request, [8, 0, 0, 0, 3], "param request is [8, 0, 0, 0, 3]"
            )

    def test_origin(self):
        """Origin equals address"""
        self.assertEqual(self.param.origin, 8, "origin is 8")

    def test_to_internal(self):
        """Takes the first item in data"""
        for msg in self.param.to_internal(0, [16, 0]):
            self.assertEqual(msg.macro, 176, "macro is 176")
            self.assertEqual(msg.value, 64, "value is 64")

    def test_from_internal(self):
        """Takes all values to send"""
        for msg in self.param.from_internal(22, MacroMessage("synth", 0, 176, 64)):
            self.assertEqual(msg.address, (16, 0, 22, 8), "address is 8")
            self.assertEqual(len(msg.body), 1, "1 value")
            self.assertEqual(msg.body[0], 16, "value is 16")

    def test_from_vel(self):
        """Converts values to velocity"""
        self.assertEqual(self.param.from_vel(64), 16, "64 -> 16")
        self.assertEqual(self.param.from_vel(0), 4, "0 -> 4")
        self.assertEqual(self.param.from_vel(127), 28, "127 -> 28")


class TestOffsetParam(unittest.TestCase):
    def setUp(self) -> None:
        self.param = Pot((3, -1), 53)
        return super().setUp()

    def test_param(self):
        """Param offset is correctly formed"""
        self.assertEqual(self.param.address, 3, "param address is 3")
        self.assertEqual(self.param.offset, -1, "param offset is -1")
        self.assertEqual(self.param.min_value, 0, "param min value is 0")
        self.assertEqual(self.param.max_value, 100, "param max value is 100")
        self.assertEqual(self.param.macro, 181, "param macro is 181")

    def test_request(self):
        """Nothing is output"""
        request = list(self.param.request)
        self.assertEqual(len(request), 0, "request outputs nothing")

    def test_origin(self):
        """Origin is the address minus offset"""
        self.assertEqual(self.param.origin, 2, "origin is 3 - 1")

    def test_to_internal(self):
        """Offset the received data"""
        for msg in self.param.to_internal(0, [0, 50]):
            self.assertEqual(msg.macro, 181, "macro is 181")
            self.assertEqual(msg.value, 64, "value is 64")


class TestSwitchPot(unittest.TestCase):
    def setUp(self) -> None:
        self.param = Switch((13, 3), 54)
        return super().setUp()

    def test_from_internal(self):
        off_message = MacroMessage("synth", 0, 182, 0)
        message = MacroMessage("synth", 0, 182, 64)
        for msg in self.param.from_internal(22, off_message):
            self.assertEqual(msg.address, (16, 0, 22, 13), "address is 16, 0, 22, 13")
            self.assertEqual(msg.body[0], 0, "value is 0, switch off")
        for msg in self.param.from_internal(33, message):
            self.assertEqual(msg.address, (16, 0, 33, 13), "address is 16, 0, 22, 13")
            self.assertEqual(msg.body, (1, 50), "value is 50, switch on")

    def test_to_internal(self):
        off_message = list(self.param.to_internal(0, [0, 50]))
        on_message = list(self.param.to_internal(0, [1, 50]))
        self.assertEqual(off_message[0].value, 0, "switch is off, value = 0")
        self.assertEqual(on_message[0].value, 64, "value is on, value = 64")


class TestLFOPot(unittest.TestCase):
    def setUp(self) -> None:
        self.param = LFO((45, 3), 51, (100, 118))
        return super().setUp()

    def test_from_internal(self):
        off_message = MacroMessage("synth", 0, 179, 0)
        message = MacroMessage("synth", 0, 179, 64)
        for msg in self.param.from_internal(22, off_message):
            self.assertEqual(msg.address, (16, 0, 22, 45), "address is 16, 0, 22, 45")
            self.assertEqual(msg.body[0], 0, "value is 0, switch off")
        for msg in self.param.from_internal(22, message):
            self.assertEqual(msg.body, (1, 0, 109), "value is 109, switch on")

    def test_to_internal(self):
        off_message = list(self.param.to_internal(0, [0, 2, 50]))
        on_message = list(self.param.to_internal(0, [0, 2, 109]))
        self.assertEqual(off_message[0].value, 0, "lfo is unsynced, value = 0")
        self.assertEqual(on_message[0].value, 64, "value is on, value = 64")


class TestBipolarPot(unittest.TestCase):
    def setUp(self) -> None:
        self.param = Bipolar((27, 11, 3), 49)
        return super().setUp()

    def test_from_vel(self):
        self.assertEqual(self.param.from_vel(0), 0, "value is 0")
        self.assertEqual(self.param.from_vel(64), 100, "value is 50")
        self.assertEqual(self.param.from_vel(127), 200, "value is 200")

    def test_to_vel(self):
        self.assertEqual(self.param.to_vel(0, 100), 0, "lpf value is 0")
        self.assertEqual(self.param.to_vel(0, 50), 32, "lpf value is 64 / 2")
        self.assertEqual(self.param.to_vel(1, 0), 64, "hpf value is 64")
        self.assertEqual(self.param.to_vel(1, 50), 96, "hpf value is 64 + 64 / 2")
        self.assertEqual(self.param.to_vel(1, 100), 127, "hpf value is 127")

    def test_from_internal(self):
        lpf_message = MacroMessage("synth", 0, 177, 32)
        for msg in self.param.from_internal(22, lpf_message):
            self.assertEqual(msg.address, (16, 0, 22, 27), "address is 16, 0, 22, 27")
            self.assertEqual(msg.body, (0, 1, 50), "lpf set to 50")
        hpf_message = MacroMessage("synth", 0, 177, 96)
        for msg in self.param.from_internal(22, hpf_message):
            self.assertEqual(msg.body, (1, 1, 50), "hpf set to 50")

    def test_to_internal(self):
        hpf_message = list(self.param.to_internal(0, [1, 0, 1, 100]))
        self.assertEqual(hpf_message[0].value, 127, "value is 127")
        lpf_message = list(self.param.to_internal(0, [0, 1, 2, 50]))
        self.assertEqual(lpf_message[0].value, 32, "value is 32")
        self.assertEqual(lpf_message[0].macro, 177, "macro is 177")
