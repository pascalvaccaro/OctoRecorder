from typing import Union
from midi import MidiDevice, SysexCmd, SysexReq
from instruments import Instruments
from instruments.messages import InternalMessage as Msg, MacroMessage
from utils import clip, scroll, split_hex, to_observable


class SY1000(MidiDevice):
    instruments = Instruments(10, 21, 32, 43)
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

    def to_messages(self, msg):
        method_name = "_" + msg.type + "_in"
        if hasattr(self, method_name):
            return super().to_messages(msg)
        messages = None
        instr_idx = None
        if isinstance(msg, Msg):
            instr_idx = msg.data[0]
        elif isinstance(msg, MacroMessage):
            instr_idx = msg.idx
        elif len(msg.data) > 9:
            instr_idx = msg.data[9]
        if instr_idx is not None:
            messages = self.instruments.get(instr_idx).send(msg)
        return to_observable(messages)

    def _program_change_in(self, _=None):
        yield SysexReq("common", [0, 0, 0, 0, 0, 4])  # patch number

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
            return
        data = list(msg.data[7:])
        if data[1] == 1:  # "common" message
            self.patch = int("0x" + "".join(map(lambda a: hex(a)[2:], data[4:-1])), 16)
            yield from self.instruments.request
        elif data[0] == 16:  # "patch" message
            instr = data[2]
            if data[3] == 1:  # instr type
                self.instruments.set(instr, data[4])
                yield from self.instruments.get(instr).request
            elif instr in range(21, 55):  # instr params
                yield from self.instruments.get(instr).receive(data[3], data[4:-1])
