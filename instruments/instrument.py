from midi.messages import InternalMessage, SysexCmd
from utils import clip


class Instrument:
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

    def _strings_in(self, msg: InternalMessage):
        channel, control, velocity = msg.data
        param = 6 if control <= 19 else 12
        string = channel + param if channel < 6 else param
        value = clip(velocity / 127 * 100, 0, 100)
        values = [value] * 6 if channel == 8 else [value]
        yield SysexCmd("patch", [self._idx, string, *values])

    def _synth_param_in(self, _):
        yield

    def _steps_in(self, _):
        yield

    def _seq_in(self, _):
        yield
