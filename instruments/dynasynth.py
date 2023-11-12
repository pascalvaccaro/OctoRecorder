from midi.messages import SysexCmd, SysexReq, InternalMessage
from . import Instrument
from .params import Param, Filter, LFO, StepSequencer


class DynaSynth(Instrument):
    params = [
        Param((5, 1), 0, (8, 56)),  # pitch
        Param((16, 1), 4, (14, 114)),  # pitch env. depth
        Filter((29, 6), 1),  # filter type + cutoff
        Param((32, -3), 5),  # resonance
        Param((33, -4), 2, (14, 144)),  # f. env. attack
        Param((34, -5), 6, (14, 144)),  # f. env. depth
        LFO((39, 3), 3, (100, 118)),  # lfo 1 rate
        LFO((49, 3), 7, (100, 118)),  # lfo 2 rate
    ]
    sequencer = StepSequencer((59, 125))

    @property
    def idx(self):
        return self._idx + 1

    @property
    def request(self):
        yield from super().request
        for values in self.sequencer.request:
            yield SysexReq("patch", [self.idx, *values])

    def receive(self, address: int, data: list[int]):
        yield from super().receive(address, data)
        if address == self.sequencer.origin:
            for values in self.sequencer._steps_out(data):
                yield InternalMessage("steps", self.idx, *values)
            for values in self.sequencer._length_out(data):
                yield InternalMessage("length", self.idx, *values)

    def _bars_in(self, msg: InternalMessage):
        for values in self.sequencer.to_bars(msg.data[1]):
            yield SysexCmd("patch", [self.idx, *values])

    def _length_in(self, msg: InternalMessage):
        for values in self.sequencer.to_length(msg.data[1:]):
            yield SysexCmd("patch", [self.idx, *values])

    def _status_in(self, msg: InternalMessage):
        for values in self.sequencer.to_status(msg.data[1:]):
            yield SysexCmd("patch", [self.idx, *values])

    def _steps_in(self, msg: InternalMessage):
        values = self.sequencer.get_steps(msg.data[1:])
        yield SysexCmd("patch", [self.idx, *values])

    def _target_in(self, msg: InternalMessage):
        values = self.sequencer.get_target(msg.data[1:])
        yield SysexCmd("patch", [self.idx, *values])
