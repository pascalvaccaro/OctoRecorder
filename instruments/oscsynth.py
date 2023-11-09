from midi.messages import SysexReq, SysexCmd, InternalMessage as Msg
from utils import clip
from .instrument import Instrument


class OscSynth(Instrument):
    def __init__(self, idx: int) -> None:
        super().__init__(idx)

    @property
    def idx(self):
        return self._idx + 3

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
            yield Msg("synth_param", self.idx, 0, value)
        elif param == 8:  # pitch env. depth
            value = clip((data[0] - 4) * 128 / 24)
            yield Msg("synth_param", self.idx, 4, value)
        elif param == 27:  # filter
            ftype = data[0]
            if ftype in [0, 1]:
                if ftype == 0:
                    value = clip(64 - data[3] / 100 * 64, 0, 64)
                else:
                    value = clip(data[3] / 100 * 64 + 64, 64, 127)
                yield Msg("synth_param", self.idx, 1, value)
            yield Msg("synth_param", self.idx, 5, clip(data[4] * 127 / 100))
            yield Msg("synth_param", self.idx, 2, clip(data[6] * 127 / 100))
            yield Msg("synth_param", self.idx, 6, clip((data[10] - 14) * 128 / 100))
        elif param in [45, 55]:  # lfo 1/2
            control = 3 if param == 45 else 7
            value = (
                0
                if data[0] == 0
                else data[2] * 127 / 100
                if data[2] <= 100
                else data[2] * 127 / 18
            )
            yield Msg("synth_param", self.idx, control, clip(value))

    def _synth_param_in(self, msg: Msg):
        control, value = msg.data[1:]
        if control == 0:
            yield SysexCmd("patch", [self.idx, 2, clip(value / 127 * 48 + 8, 8, 56)])
        elif control == 1:
            percent = clip(value / 127 * 200, 0, 200)
            if percent < 100:
                yield SysexCmd("patch", [self.idx, 27, 0, 1, (100 - percent)])
            else:
                yield SysexCmd("patch", [self.idx, 27, 1, 1, percent - 100])
        elif control == 2:
            yield SysexCmd(
                "patch", [self.idx, 37, clip(value / 127 * 100 + 14, 14, 114)]
            )
        elif control == 3:
            if value >= 0:
                yield SysexCmd("patch", [self.idx, 45, 1])
                yield SysexCmd("patch", [self.idx, 47, clip(value / 127 * 118, 0, 118)])

            else:
                yield SysexCmd("patch", [self.idx, 45, 0])
        elif control == 4:
            yield SysexCmd("patch", [self.idx, 8, clip(value / 127 * 24 + 4, 4, 28)])
        elif control == 5:
            yield SysexCmd("patch", [self.idx, 31, clip(value / 127 * 100, 0, 100)])
        elif control == 6:
            yield SysexCmd(
                "patch", [self.idx, 33, clip(value / 127 * 100 + 14, 14, 114)]
            )
        elif control == 7:
            if value >= 0:
                yield SysexCmd("patch", [self.idx, 55, 1])
                yield SysexCmd("patch", [self.idx, 57, clip(value / 127 * 118, 0, 118)])
            else:
                yield SysexCmd("patch", [self.idx, 55, 0])

