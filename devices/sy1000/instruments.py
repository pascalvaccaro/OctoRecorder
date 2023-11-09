from typing import List
from midi.messages import InternalMessage as Msg, SysexReq, SysexCmd
from utils import clip


class Synth:
    def __init__(self, idx: int):
        self._idx = idx

    @property
    def idx(self):
        return self._idx
    
    @property
    def ridx(self):
        return range(self._idx, self._idx + 11)

    def request(self, _):
        yield

    @property
    def has_sequencer(self):
        return False

    def update(self, _: int, __: "list[int]"):
        yield

    def _strings_in(self, msg: Msg):
        channel, control, velocity = msg.data
        param = 6 if control <= 19 else 12
        string = channel + param if channel < 6 else param
        value = clip(velocity / 127 * 100, 0, 100)
        values = [value] * 6 if channel == 8 else [value]
        yield SysexCmd("patch", [self._idx, string, *values])

    def _control_in(self, _):
        yield

    def _steps_in(self, _):
        yield

    def _seq_in(self, _):
        yield


class DynaSynth(Synth):
    seq_rates = [115, 112, 110, 109, 108, 107, 106, 106]

    def __init__(self, idx: int) -> None:
        super().__init__(idx)

    @property
    def idx(self):
        return self.idx + 1

    @property
    def has_sequencer(self):
        return True

    def request(self, bars=2):
        # synth pitch
        yield SysexReq("patch", [self.idx, 5, 0, 0, 0, 1])
        # synth pitch env. depth
        yield SysexReq("patch", [self.idx, 16, 0, 0, 0, 1])
        # synth filter
        yield SysexReq("patch", [self.idx, 29, 0, 0, 0, 7])
        # lfo 1
        yield SysexReq("patch", [self.idx, 39, 0, 0, 0, 3])
        # lfo 2
        yield SysexReq("patch", [self.idx, 49, 0, 0, 0, 3])
        # sequencer length/rate
        rate = self.seq_rates[bars - 1]
        yield SysexCmd("patch", [self.idx + 1, 32, 16, rate])
        yield SysexCmd("patch", [self.idx + 1, 54, 16, rate])
        # sequencer steps + targets
        yield SysexReq("patch", [self.idx, 59, 0, 0, 0, 99])

    def update(self, param: int, data: "list[int]"):
        if param == 5:  # pitch
            value = clip((data[0] - 8) * 128 / 48)  # 8 => 0, 32 => 64, 56 => 127
            yield Msg("control", self.idx, 1, value)
        elif param == 16:  # pitch env. depth
            value = clip((data[0] - 14) / 100 * 127)
            yield Msg("control", self.idx, 5, value)
        elif param == 29:  # filter
            ftype = data[0]
            if ftype in [0, 1]:
                if ftype == 0:
                    value = clip(64 - data[3] / 100 * 64, 0, 64)
                else:
                    value = clip(data[3] / 100 * 64 + 64, 64, 127)
                yield Msg("control", self.idx, 2, value)
                yield Msg("control", self.idx, 6, clip(data[3] / 100 * 127))
                yield Msg("control", self.idx, 3, clip(data[4] / 100 * 127))
                yield Msg("control", self.idx, 7, clip(data[5] / 100 * 127))
        elif param in [39, 49]:  # lfo 1/2
            control = 4 if param == 39 else 8
            value = (
                0
                if data[0] == 0
                else data[2] * 128 / 100
                if data[2] <= 100
                else data[2] * 128 / 18
            )
            yield Msg("control", self.idx, control, clip(value))
        elif param == 59:  # sequencer steps
            seq, steps = data[0:3], data[3:]
            for i, seq_param in enumerate(["pitch", "cutoff", "level"]):
                seq_steps = enumerate(steps[i * 32 : (i + 1) * 32])
                max_values = [s for j, s in seq_steps if j % 2 == 1]
                yield Msg(seq_param, seq, max_values)

    def _control_in(self, msg: Msg):
        control, value = msg.data[1:]
        if control == 0:
            yield SysexCmd("patch", [self.idx, 5, clip(value / 127 * 48 + 8, 8, 56)])
        elif control == 1:
            yield SysexCmd(
                "patch", [self.idx, 16, clip(value / 127 * 100 + 14, 14, 114)]
            )
        elif control == 2:
            percent = clip(value / 127 * 200, 0, 200)
            if percent < 100:
                yield SysexCmd("patch", [self.idx, 29, 0, 1, (100 - percent)])
            else:
                yield SysexCmd("patch", [self.idx, 29, 1, 1, percent - 100])
        elif control == 3:
            yield SysexCmd("patch", [self.idx, 32, clip(value / 127 * 100, 0, 100)])
        elif control == 4:
            yield SysexCmd(
                "patch", [self.idx, 34, clip(value / 127 * 100 + 14, 14, 114)]
            )
        elif control == 5:
            yield SysexCmd(
                "patch", [self.idx, 33, clip(value / 127 * 100 + 14, 14, 114)]
            )
        elif control == 6:
            if value >= 0:
                yield SysexCmd("patch", [self.idx, 39, 1])
                yield SysexCmd("patch", [self.idx, 41, clip(value / 127 * 118, 0, 118)])

            else:
                yield SysexCmd("patch", [self.idx, 39, 0])
        elif control == 7:
            if value >= 0:
                yield SysexCmd("patch", [self.idx, 49, 1])
                yield SysexCmd("patch", [self.idx, 51, clip(value / 127 * 118, 0, 118)])
            else:
                yield SysexCmd("patch", [self.idx, 49, 0])

    def _steps_in(self, msg: Msg):
        target, steps = msg.data[1:]
        min_value = min(steps)
        all_values = [(min_value, step) for step in steps]
        yield SysexCmd("patch", [self.idx, 62 + target * 32, *all_values])

    def _seq_in(self, msg: Msg):
        param, seq = msg.data[1:]
        yield SysexCmd("patch", [self.idx, 59 + param, seq])


class OscSynth(Synth):
    def __init__(self, idx: int) -> None:
        super().__init__(idx)

    @property
    def idx(self):
        return self.idx + 3

    def request(self, _):
        # pitch
        yield SysexReq("patch", [self.idx, 2, 0, 0, 0, 1])
        # pitch env. depth
        yield SysexReq("patch", [self.idx, 8, 0, 0, 0, 1])
        # filter
        yield SysexReq("patch", [self.idx, 27, 0, 0, 0, 11])
        # lfo 1
        yield SysexReq("patch", [self.idx, 45, 0, 0, 0, 3])
        # lfo 2
        yield SysexReq("patch", [self.idx, 55, 0, 0, 0, 3])

    def update(self, param: int, data: "list[int]"):
        if param == 2:  # pitch
            value = clip((data[0] - 8) * 128 / 48)
            yield Msg("control", self.idx, 1, value)
        elif param == 8:  # pitch env. depth
            value = clip((data[0] - 4) * 128 / 24)
            yield Msg("control", self.idx, 5, value)
        elif param == 27:  # filter
            ftype = data[0]
            if ftype in [0, 1]:
                yield Msg("control", self.idx, 2, ftype, clip(data[2] * 127 / 100))
                yield Msg("control", self.idx, 6, clip(data[4] * 127 / 100))
                yield Msg("control", self.idx, 3, clip(data[6] * 127 / 100))
                yield Msg("control", self.idx, 7, clip((data[10] - 14) * 128 / 100))
        elif param in [45, 55]:  # lfo 1/2
            control = 4 if param == 45 else 8
            value = (
                0
                if data[4] == 0
                else data[6] * 127 / 100
                if data[6] <= 100
                else data[6] * 127 / 18
            )
            yield Msg("control", self.idx, control, clip(value))

    def _control_in(self, msg: Msg):
        control, value = msg.data[1:]
        if control == 0:
            yield SysexCmd("patch", [self.idx, 2, clip(value / 127 * 48 + 8, 8, 56)])
        elif control == 1:
            yield SysexCmd("patch", [self.idx, 8, clip(value / 127 * 24 + 4, 4, 28)])
        elif control == 2:
            percent = clip(value / 127 * 200, 0, 200)
            if percent < 100:
                yield SysexCmd("patch", [self.idx, 27, 0, 1, (100 - percent)])
            else:
                yield SysexCmd("patch", [self.idx, 27, 1, 1, percent - 100])
        elif control == 3:
            yield SysexCmd("patch", [self.idx, 31, clip(value / 127 * 100, 0, 100)])
        elif control == 4:
            yield SysexCmd(
                "patch", [self.idx, 37, clip(value / 127 * 100 + 14, 14, 114)]
            )
        elif control == 5:
            yield SysexCmd(
                "patch", [self.idx, 33, clip(value / 127 * 100 + 14, 14, 114)]
            )
        elif control == 6:
            if value >= 0:
                yield SysexCmd("patch", [self.idx, 45, 1])
                yield SysexCmd("patch", [self.idx, 47, clip(value / 127 * 118, 0, 118)])

            else:
                yield SysexCmd("patch", [self.idx, 45, 0])
        elif control == 7:
            if value >= 0:
                yield SysexCmd("patch", [self.idx, 55, 1])
                yield SysexCmd("patch", [self.idx, 57, clip(value / 127 * 118, 0, 118)])
            else:
                yield SysexCmd("patch", [self.idx, 55, 0])


class GR300(Synth):
    def __init__(self, idx: int) -> None:
        super().__init__(idx)

    @property
    def idx(self):
        return self.idx + 4

    def request(self, _):
        # synth pitch A + B
        yield SysexReq("patch", [self.idx, 8, 0, 0, 0, 3])
        # synth filter cutoff + resonance
        yield SysexReq("patch", [self.idx, 2, 0, 0, 0, 2])
        # sweep + vibrato status, rise and fall
        yield SysexReq("patch", [self.idx, 13, 0, 0, 0, 6])

    def update(self, param: int, data: "list[int]"):
        if param == 8:  # pitch A/B
            yield Msg("control", self.idx, 1, clip((data[0] - 4) * 128 / 24))
            yield Msg("control", 5, clip((data[2] - 4) * 128 / 24))
        elif param == 2:  # filter
            yield Msg("control", self.idx, 2, clip(data[0] * 127 / 100))
            yield Msg("control", self.idx, 6, clip(data[1] * 127 / 100))
        elif param == 13:  # sweep/vibrato
            if data[0] == 1:  # sweep on
                yield Msg("control", self.idx, 3, clip(data[1] * 128 / 100))
                yield Msg("control", self.idx, 7, clip(data[2] * 128 / 100))
            if data[3] == 1:  # vibrato on
                yield Msg("control", self.idx, 4, clip(data[4] * 128 / 100))
                yield Msg("control", self.idx, 8, clip(data[5] * 128 / 100))

    def _control_in(self, msg: Msg):
        control, value = msg.data[1:]
        if control == 0:
            yield SysexCmd("patch", [self.idx, 8, clip(value / 127 * 24 + 4, 4, 28)])
        elif control == 1:
            yield SysexCmd("patch", [self.idx, 10, clip(value / 127 * 24 + 4, 4, 28)])
        elif control == 2:
            yield SysexCmd("patch", [self.idx, 2, clip(value / 127 * 100, 0, 100)])
        elif control == 3:
            yield SysexCmd("patch", [self.idx, 3, clip(value / 127 * 100, 0, 100)])
        elif control == 4:
            if value >= 0:
                yield SysexCmd(
                    "patch", [self.idx, 13, 1, clip(value / 127 * 100, 0, 100)]
                )
            else:
                yield SysexCmd("patch", [self.idx, 13, 0])
        elif control == 5:
            yield SysexCmd("patch", [self.idx, 15, clip(value / 127 * 100, 0, 100)])
        elif control == 6:
            if value >= 0:
                yield SysexCmd(
                    "patch", [self.idx, 16, 1, clip(value / 127 * 100, 0, 100)]
                )
            else:
                yield SysexCmd("patch", [self.idx, 16, 0])
        elif control == 7:
            yield SysexCmd("patch", [self.idx, 17, clip(value / 127 * 100, 0, 100)])


class EGuitar(Synth):
    pass


class AGuitar(Synth):
    pass


class EBass(Synth):
    pass


class VioGuitar(Synth):
    pass


class PolyFx(Synth):
    pass


class Instruments(List[Synth]):
    types = (DynaSynth, OscSynth, GR300, EGuitar, AGuitar, EBass, VioGuitar, PolyFx)

    def __init__(self, *args: int):
        super().__init__([Synth(arg) for arg in args])

    def get(self, idx: int):
        for instr in self:
            if idx in instr.ridx:
                return instr
        return self[idx]

    def set(self, idx: int, typx: int):
        if typx not in range(0, 8):
            return
        synth = Instruments.types[typx](idx)
        for i, ridx in enumerate([s.ridx for s in self]):
            if idx in ridx:
                self[i] = synth
                return
        if synth:
            self[0] = synth

    def select_by_control(self, control):
        instrs: "set[Synth]" = set()
        if control in [16, 19, 20, 23]:
            instrs.add(self[0])
        if control in [17, 19, 21, 23]:
            instrs.add(self[1])
        if control in [18, 19, 22, 23]:
            instrs.add(self[2])
        return instrs
