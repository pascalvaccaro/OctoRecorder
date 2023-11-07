from midi import MidiDevice, SysexCmd, SysexReq, InternalMessage as Msg
from utils import clip, scroll, split_hex


class SY1000(MidiDevice):
    patch = 0
    dynasynths: "set[int]" = set()

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
        controls = ["patch", "strings", "steps", "target", "xfader"]
        return lambda msg: msg.type in controls

    @property
    def get_strings(self):
        for i in range(3):
            instr = 11 * i + 21
            # instr type + volume
            yield SysexReq("patch", [instr, 1, 0, 0, 0, 2])
            # instr strings volume + pan
            yield SysexReq("patch", [instr, 6, 0, 0, 0, 12])

    def _sysex_in(self, msg: SysexCmd):
        if msg.data[0] != 65 or msg.data[6] != 18:
            yield
        data = msg.data[7:]
        if data[0] == 0:  # "common" message
            self.patch = int("0x" + "".join(map(lambda a: hex(a)[2:], data[4:-1])), 16)
            yield from self.get_strings
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

    def _program_change_in(self, _=None):
        # patch number
        yield SysexReq("common", [0, 0, 0, 0, 0, 4])

    def _stop_in(self, _=None):
        yield Msg("stop", 0)

    def _patch_in(self, msg: Msg):
        offset = msg.data[0]
        self.patch = scroll(self.patch + offset, 0, 399)
        data = map(lambda x: int(x, 16), list(hex(self.patch)[2:].zfill(4)))
        yield SysexCmd("common", [0, 0, *data])

    def _strings_in(self, msg: Msg):
        channel, control, velocity = msg.data
        if channel == 6 or channel == 7:
            return
        instrs = set()
        if control in [16, 19, 20, 23]:
            instrs.add(21)
        if control in [17, 19, 21, 23]:
            instrs.add(32)
        if control in [18, 19, 22, 23]:
            instrs.add(43)
        param = 6 if control <= 19 else 12
        string = channel + param if channel < 6 else param
        decimal = clip(velocity / 127 * 100)
        value = [decimal] * 6 if channel == 8 else [decimal]

        for instr in instrs:
            yield SysexCmd("patch", [instr, string, *value])

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

    def _xfader_in(self, msg: Msg):
        left = clip(int(msg.data[0] / 127 * 200), 0, 200)
        data = [*split_hex(left), *split_hex(200 - left)]
        yield SysexCmd("inout", [0, 44, *data])
