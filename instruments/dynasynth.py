from midi.messages import SysexReq, SysexCmd, InternalMessage as Msg
from utils import clip
from .instrument import Instrument


class DynaSynth(Instrument):
    seq_rates = [115, 112, 110, 109, 108, 107, 106, 106]
    min_values = [[0] * 32] * 3

    def __init__(self, idx: int) -> None:
        super().__init__(idx)

    @property
    def idx(self):
        return self._idx + 1

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
            yield Msg("synth_param", self.idx, 0, value)
        elif param == 16:  # pitch env. depth
            value = clip((data[0] - 14) / 100 * 128)
            yield Msg("synth_param", self.idx, 4, value)
        elif param == 29:  # filter
            ftype = data[0]
            if ftype in [0, 1]:
                if ftype == 0:
                    value = clip(64 - data[3] / 100 * 64, 0, 64)
                else:
                    value = clip(data[3] / 100 * 64 + 64, 64, 127)
                yield Msg("synth_param", self.idx, 1, value)
            yield Msg("synth_param", self.idx, 5, clip(data[3] / 100 * 128))
            yield Msg("synth_param", self.idx, 2, clip(data[4] / 100 * 128))
            yield Msg("synth_param", self.idx, 6, clip(data[5] / 100 * 128))
        elif param in [39, 49]:  # lfo 1/2
            control = 3 if param == 39 else 7
            value = (
                0
                if data[0] == 0
                else data[2] * 128 / 100
                if data[2] <= 100
                else data[2] * 128 / 18
            )
            yield Msg("synth_param", self.idx, control, clip(value))
        elif param == 59:  # sequencer steps
            targets, steps = data[0:3], data[3:]
            for i, seq_param in enumerate(["pitch", "cutoff", "level"]):
                seq_steps = enumerate(steps[i * 32 : (i + 1) * 32])
                max_values = []
                for j, s in seq_steps:
                    if j % 2 == 1:
                        max_values += [s]
                    else:
                        self.min_values[i][j] = s
                yield Msg(seq_param, self.idx, targets[i], max_values)

    def _synth_param_in(self, msg: Msg):
        control, value = msg.data[1:]
        if control == 0:
            yield SysexCmd("patch", [self.idx, 5, clip(value / 127 * 48 + 8, 8, 56)])
        elif control == 1:
            percent = clip(value / 127 * 200, 0, 200)
            if percent < 100:
                yield SysexCmd("patch", [self.idx, 29, 0, 1, (100 - percent)])
            else:
                yield SysexCmd("patch", [self.idx, 29, 1, 1, percent - 100])
        elif control == 2:
            yield SysexCmd(
                "patch", [self.idx, 34, clip(value / 127 * 100 + 14, 14, 114)]
            )
        elif control == 3:
            if value >= 0:
                yield SysexCmd("patch", [self.idx, 39, 1])
                yield SysexCmd("patch", [self.idx, 41, clip(value / 127 * 118, 0, 118)])

            else:
                yield SysexCmd("patch", [self.idx, 39, 0])
        elif control == 4:
            yield SysexCmd(
                "patch", [self.idx, 16, clip(value / 127 * 100 + 14, 14, 114)]
            )
        elif control == 5:
            yield SysexCmd("patch", [self.idx, 32, clip(value / 127 * 100, 0, 100)])
        elif control == 6:
            yield SysexCmd(
                "patch", [self.idx, 33, clip(value / 127 * 100 + 14, 14, 114)]
            )
        elif control == 7:
            if value >= 0:
                yield SysexCmd("patch", [self.idx, 49, 1])
                yield SysexCmd("patch", [self.idx, 51, clip(value / 127 * 118, 0, 118)])
            else:
                yield SysexCmd("patch", [self.idx, 49, 0])

    def _steps_in(self, msg: Msg):
        target, steps = msg.data[1:]
        all_values = []
        for i, step in enumerate(steps):
            all_values += [self.min_values[target][i], step]
        yield SysexCmd("patch", [self.idx, 62 + target * 32, *all_values])

    def _seq_in(self, msg: Msg):
        param, seq = msg.data[1:]
        yield SysexCmd("patch", [self.idx, 59 + param, seq])
