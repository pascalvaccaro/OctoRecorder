from typing import Union
from midi import MidiDevice, SysexCmd, SysexReq
from instruments import Instruments
from instruments.messages import InternalMessage as Msg
from utils import clip, scroll, split_hex, to_observable


class SY1000(MidiDevice):
    instruments = Instruments(21, 32, 43)
    patch = 0

    @property
    def init_actions(self):
        yield from self._program_change_in()
        # Stereo Link (Main = ON, Sub = OFF)
        yield SysexCmd("inout", [0, 52, 1, 0])
        # L/R output levels
        yield from self._xfader_in(Msg("xfader", 64))

    @property
    def select_message(self):
        return lambda msg: msg.type in ["program_change", "sysex", "stop"]

    @property
    def external_message(self):
        controls = [
            "patch",
            "xfader",
            "strings",
            "bars",
            "synth",
            "steps",
            "target",
            "length",
        ]
        return lambda msg: self.select_message(msg) or msg.type in controls

    @property
    def get_strings(self):
        for i in range(3):
            instr = 11 * i + 21
            # instr type + volume
            yield SysexReq("patch", [instr, 1, 0, 0, 0, 2])
            # instr strings volume + pan
            yield SysexReq("patch", [instr, 6, 0, 0, 0, 12])

    def to_messages(self, msg):
        method_name = "_" + msg.type + "_in"
        if hasattr(self, method_name):
            return super().to_messages(msg)
        messages = None
        instr_idx = 0 if isinstance(msg, Msg) else 9
        instr = self.instruments.get(msg.data[instr_idx])
        if instr is not None:
            messages = instr.send(msg)
        return to_observable(messages)

    def _program_change_in(self, _=None):
        # patch number
        yield SysexReq("common", [0, 0, 0, 0, 0, 4])

    def _stop_in(self, _=None):
        yield Msg("stop", 0)

    def _patch_in(self, msg: Msg):
        self.patch = scroll(self.patch + msg.data[0], 0, 399)
        data = map(lambda x: int(x, 16), list(hex(self.patch)[2:].zfill(4)))
        yield SysexCmd("common", [0, 0, *data])

    def _xfader_in(self, msg: Msg):
        value = clip(msg.data[0] / 127 * 200, 0, 200)
        data = [*split_hex(200 - value), *split_hex(value)] * 2
        yield SysexCmd("inout", [0, 44, *data])

    def _sysex_in(self, msg: Union[SysexCmd, Msg]):
        if msg.data[0] != 65 or msg.data[6] != 18:
            yield
        data = list(msg.data[7:])
        if data[1] == 1:  # "common" message
            self.patch = int("0x" + "".join(map(lambda a: hex(a)[2:], data[4:-1])), 16)
            yield from self.get_strings
        elif data[0] == 16:  # "patch" message
            instr = data[2]
            if data[3] == 1:  # inst type
                self.instruments.set(instr, data[4])
                yield from self.instruments.get(instr).request
            elif data[3] == 6:  # inst string vol, pan
                yield Msg("strings", instr, data[4:-1])
            elif instr in range(21, 55):  # inst synth params
                yield from self.instruments.get(instr).receive(data[3], data[4:-1])

    def _strings_in(self, msg: Msg):
        if msg.data[0] in [6, 7]:
            return
        for instr in self.instruments.select_by_control(msg.data[1]):
            channel, control, velocity = msg.data
            param = 6 if control <= 19 else 12
            string = channel + param if channel < 6 else param
            value = clip(velocity / 127 * 100, 0, 100)
            values = [value] * 6 if channel == 8 else [value]
            yield SysexCmd("patch", [instr._instr, string, *values])
