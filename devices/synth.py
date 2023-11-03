from midi import Sequencer, SysexCmd, SysexReq, MidiDevice, InternalMessage as Msg
from utils import clip, scroll


class SY1000(MidiDevice, Sequencer):
    patch = 0
    dynasynths: "set[int]" = set()

    @property
    def init_actions(self):
        # patch number
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
        return lambda msg: msg.type in ["bars", "patch", "strings", "steps", "target"]

    @property
    def strings(self):
        for i in range(3):
            instr = 11 * i + 21
            # instr type + volume
            yield SysexReq("patch", [instr, 1, 0, 0, 0, 2])
            # instr strings volume + pan
            yield SysexReq("patch", [instr, 6, 0, 0, 0, 12])

    def __init__(self, port):
        super(SY1000, self).__init__(port)
        self.subs = Sequencer._start_in(self)

    def _sysex_in(self, msg: SysexCmd):
        if msg.data[0] != 65 or msg.data[6] != 18:
            yield
        data = msg.data[7:]
        if data[0] == 0:  # "common" message
            self.patch = int("0x" + "".join(map(lambda a: hex(a)[2:], data[4:-1])), 16)
            yield from self.strings
        elif data[0] == 16:  # "patch" message
            instr = data[2]
            if data[3] == 1:  # inst type, volume
                if data[4] == 0:  # instr is dynasynth
                    self.dynasynths.add(instr + 1)
                    yield SysexReq("patch", [instr + 1, 59, 0, 0, 0, 99])
                else:
                    self.dynasynths.discard(instr + 1)
                # master instr volume
                control = clip((instr + 155) / 11)
                yield Msg("strings", 8, control, clip(data[5] / 100 * 127))
            elif data[3] == 6:  # inst string vol, pan
                for i, d in enumerate(data[4:-1]):
                    channel = divmod(i, 6)[1]
                    control = clip((instr + 155) / 11 + (4 if i >= 6 else 0))
                    value = clip(d / 100 * 127)
                    yield Msg("strings", channel, control, value)
            elif data[3] == 59:  # sequencer steps
                targets, steps = data[4:7], data[7:]
                for i, param in enumerate(["pitch", "cutoff", "level"]):
                    param_steps = enumerate(steps[i * 32 : (i + 1) * 32])
                    max_values = (s for i, s in param_steps if i % 2 == 1)
                    yield Msg(param, targets[i], max_values)

    def _program_change_in(self, _):
        yield from self.init_actions

    def _stop_in(self, _=None):
        yield Msg("stop", 0)

    def _patch_in(self, msg: Msg):
        offset = msg.data[0]
        self.patch = scroll(self.patch + offset, 0, 399)
        data = map(lambda x: int(x, 16), list(hex(self.patch)[2:].zfill(4)))
        yield SysexCmd("common", [0, 0, *data])

    def _strings_in(self, msg: Msg):
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

    def _steps_in(self, msg: Msg):
        param, steps = msg.data
        min_value = min(steps)
        all_values = []
        for step in steps:
            all_values.extend((min_value, step))
        for instr in self.dynasynths:
            yield SysexCmd("patch", [instr, 62 + param * 32, *all_values])

    def _target_in(self, msg: Msg):
        param, target = msg.data
        if param >= 0:
            for instr in self.dynasynths:
                yield SysexCmd("patch", [instr, 59 + param, target])
