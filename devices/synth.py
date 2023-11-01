from midi import Metronome, SysexCmd, SysexReq, MidiDevice, InternalMessage
from utils import clip, scroll


class SY1000(MidiDevice, Metronome):
    patch = 0

    @property
    def init_actions(self):
        for i in range(3):
            instr = 11 * i + 21
            yield SysexReq("patch", [instr, 2, 0, 0, 0, 1])
            yield SysexReq("patch", [instr, 6, 0, 0, 0, 12])
        yield SysexReq("common", [0, 0, 0, 0, 0, 4])

    @property
    def select_message(self):
        return lambda msg: msg.type in [
            "program_change",
            "sysex",
            "start",
            "stop",
        ]

    @property
    def external_message(self):
        return lambda msg: msg.type in ["bars", "patch", "strings"]

    def __init__(self, port):
        super(SY1000, self).__init__(port)
        self.subs = Metronome.__init__(self, self.inport)

    def _sysex_in(self, msg: SysexCmd):
        if msg.data[0] != 65 or msg.data[6] != 18:
            yield
        data = msg.data[6:]
        if data[3] == 0:
            self.patch = int("0x" + "".join(map(lambda a: hex(a)[2:], data[5:9])), 16)
        else:
            for i, d in enumerate(data[5:-1]):
                channel = divmod(i, 6)[1] if data[4] != 2 else 8
                control = clip((data[3] + 155) / 11 + (4 if i >= 6 else 0))
                value = clip(d / 100 * 127)
                yield InternalMessage("strings", channel, control, value)

    def _program_change_in(self, _):
        yield from self.init_actions

    def _stop_in(self, _=None):
        yield InternalMessage("stop", 0)

    def _patch_in(self, msg: InternalMessage):
        offset = msg.data[0]
        self.patch = scroll(self.patch + offset, 0, 399)
        data = map(lambda x: int(x, 16), list(hex(self.patch)[2:].zfill(4)))
        yield SysexCmd("common", [0, 0, *data])

    def _strings_in(self, msg: InternalMessage):
        channel, control, value = msg.data
        instr = (
            21
            if control == 16 or control == 20
            else 32
            if control == 17 or control == 21
            else 18
        )
        string = channel + (6 if control < 20 else 12)
        value = clip(value / 127 * 100)

        if channel < 8:
            yield SysexCmd("patch", [instr, string, value])
        elif channel == 8:
            all_values = [value] * 6
            if control < 19:
                yield SysexCmd("patch", [instr, 6, *all_values])
            elif control < 23:
                for instr in [21, 32, 43]:
                    yield SysexCmd("patch", [instr, 12, *all_values])
