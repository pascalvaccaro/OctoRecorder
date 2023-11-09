from midi.messages import SysexReq, SysexCmd, InternalMessage as Msg
from utils import clip
from .instrument import Instrument


class GR300(Instrument):
    def __init__(self, idx: int) -> None:
        super().__init__(idx)

    @property
    def idx(self):
        return self._idx + 4

    def request(self, _):
        # synth pitch A + B
        yield SysexReq("patch", [self.idx, 8, 0, 0, 0, 3])
        # synth filter cutoff + resonance
        yield SysexReq("patch", [self.idx, 2, 0, 0, 0, 2])
        # sweep + vibrato status, rise and fall
        yield SysexReq("patch", [self.idx, 13, 0, 0, 0, 6])

    def update(self, param: int, data: "list[int]"):
        if param == 8:  # pitch A/B
            yield Msg("synth_param", self.idx, 0, clip((data[0] - 4) * 128 / 24))
            yield Msg("synth_param", self.idx, 4, clip((data[2] - 4) * 128 / 24))
        elif param == 2:  # filter
            yield Msg("synth_param", self.idx, 1, clip(data[0] * 128 / 100))
            yield Msg("synth_param", self.idx, 5, clip(data[1] * 128 / 100))
        elif param == 13:  # sweep/vibrato
            if data[0] == 1:  # sweep on
                yield Msg("synth_param", self.idx, 2, clip(data[1] * 128 / 100))
                yield Msg("synth_param", self.idx, 6, clip(data[2] * 128 / 100))
            if data[3] == 1:  # vibrato on
                yield Msg("synth_param", self.idx, 3, clip(data[4] * 128 / 100))
                yield Msg("synth_param", self.idx, 7, clip(data[5] * 128 / 100))

    def _synth_param_in(self, msg: Msg):
        control, value = msg.data[1:]
        if control == 0:
            yield SysexCmd("patch", [self.idx, 8, clip(value / 127 * 24 + 4, 4, 28)])
        elif control == 1:
            yield SysexCmd("patch", [self.idx, 2, clip(value / 127 * 100, 0, 100)])
        elif control == 2:
            if value >= 0:
                yield SysexCmd(
                    "patch", [self.idx, 13, 1, clip(value / 127 * 100, 0, 100)]
                )
            else:
                yield SysexCmd("patch", [self.idx, 13, 0])
        elif control == 3:
            if value >= 0:
                yield SysexCmd(
                    "patch", [self.idx, 16, 1, clip(value / 127 * 100, 0, 100)]
                )
            else:
                yield SysexCmd("patch", [self.idx, 16, 0])
        elif control == 4:
            yield SysexCmd("patch", [self.idx, 10, clip(value / 127 * 24 + 4, 4, 28)])
        elif control == 5:
            yield SysexCmd("patch", [self.idx, 3, clip(value / 127 * 100, 0, 100)])
        elif control == 6:
            yield SysexCmd("patch", [self.idx, 15, clip(value / 127 * 100, 0, 100)])
        elif control == 7:
            yield SysexCmd("patch", [self.idx, 18, clip(value / 127 * 100, 0, 100)])
