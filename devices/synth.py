from typing import Union
from midi import MidiDevice, SysexCmd, SysexReq, InternalMessage as Msg
from utils import clip, scroll, split_hex, to_observable
from instruments import Instruments


class SY1000(MidiDevice):
    instruments = Instruments(21, 32, 43)
    patch = 0
    bars = 2

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
        controls = ["patch", "strings", "synth_param", "steps", "seq", "xfader", "bars"]
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
        src_instr = self.instruments.get(msg.data[instr_idx])
        if src_instr is not None:
            messages = getattr(src_instr, method_name)(msg)
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
        left, right = (200 - value, value) if value < 100 else (value, 200 - value)
        data = [*split_hex(left), *split_hex(right)] * 2
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
                yield from self.instruments.get(instr).request(self.bars)
            elif data[3] == 6:  # inst string vol, pan
                yield Msg("strings", instr, data[4:-1])
            elif instr in range(21, 55):  # inst synth params
                yield from self.instruments.get(instr).update(data[3], data[4:-1])

    def _strings_in(self, msg: Msg):
        if msg.data[0] in [6, 7]:
            return
        for instr in self.instruments.select_by_control(msg.data[1]):
            yield from instr._strings_in(msg)

    def _bars_in(self, msg: Msg):
        self.bars = clip(msg.data[0], 1, 8)
