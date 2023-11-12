from typing import List
from midi.messages import InternalMessage, SysexCmd, SysexReq
from utils import clip
from .params import Param, Filter, LFO, Switch


class Instrument:
    params: list[Param] = []

    def __init__(self, idx: int):
        self._idx = idx

    @property
    def idx(self):
        return self._idx

    @property
    def ridx(self):
        return range(self._idx, self._idx + 11)

    @property
    def request(self):
        for param in self.params:
            for request in param.request:
                yield SysexReq("patch", [self.idx, *request])

    def receive(self, address: int, data: "list[int]"):
        """Called with the SY100 answer to a synth params request for this instrument"""
        for param in self.params:
            if param.origin == address:
                for values in param.receive(data):
                    yield InternalMessage("synth", self.idx, *values)

    def _strings_in(self, msg: InternalMessage):
        channel, control, velocity = msg.data
        param = 6 if control <= 19 else 12
        string = channel + param if channel < 6 else param
        value = clip(velocity / 127 * 100, 0, 100)
        values = [value] * 6 if channel == 8 else [value]
        yield SysexCmd("patch", [self._idx, string, *values])

    def _synth_in(self, msg: InternalMessage):
        """Called when the APC40 sends a params command to this SY1000 instrument"""
        for param in self.params:
            if msg.data[1] == param.macro:
                values = [param.from_vel(d) for d in msg.data[2:]]
                yield SysexCmd("patch", [self.idx, *param.send(values)])


class OscSynth(Instrument):
    params = [
        Param((2, 1), 0, (8, 56)),  # pitch
        Param((8, 1), 4, (4, 28)),  # pitch env. depth
        Filter((27, 11, 3), 1),  # filter type + cutoff
        Param((31, -4), 5),  # resonance
        Param((33, -6), 2),  # f. env. attack
        Param((37, -10), 6, (14, 144)),  # f. env. depth
        LFO((45, 3), 3, (100, 118)),  # lfo 1 rate
        LFO((55, 3), 7, (100, 118)),  # lfo 2 rate
    ]

    @property
    def idx(self):
        return self._idx + 3


class GR300(Instrument):
    params = [
        Param((8, 3), 0, (4, 28)),  # pitch A
        Param((10, 0), 4, (4, 28)),  # pitch B
        Param((2, 2), 1),  # cutoff
        Param((3, -1), 5),  # resonance
        Switch((13, 3), 6),  # sweep switch + rise
        Param((15, -2), 2),  # sweep fall
        Switch((16, 3), 7),  # vibrato switch + rate
        Param((18, -2), 3),  # vibrato depth
    ]

    @property
    def idx(self):
        return self._idx + 4


class EGuitar(Instrument):
    @property
    def idx(self):
        return self._idx + 5


class AGuitar(Instrument):
    @property
    def idx(self):
        return self._idx + 6


class EBass(Instrument):
    @property
    def idx(self):
        return self._idx + 7


class VioGuitar(Instrument):
    @property
    def idx(self):
        return self._idx + 8


class PolyFx(Instrument):
    @property
    def idx(self):
        return self._idx + 9


from .dynasynth import DynaSynth


class Instruments(List[Instrument]):
    types = (DynaSynth, OscSynth, GR300, EGuitar, AGuitar, EBass, VioGuitar, PolyFx)

    def __init__(self, *args: int):
        super().__init__([Instrument(arg) for arg in args])

    def get(self, idx: int):
        for instr in self:
            if idx in instr.ridx:
                return instr
        return self[idx]

    def set(self, idx: int, typx: int):
        if typx not in range(0, 8):
            return
        synth = Instruments.types[typx](idx)
        if synth is None:
            return
        for i, ridx in enumerate([s.ridx for s in self]):
            if idx in ridx:
                self._set(i, synth)
                return
        if idx < len(Instruments.types):
            self._set(idx, synth)
        elif synth:
            self._set(0, synth)

    def _set(self, i, synth):
        self[i] = synth

    def select_by_control(self, control):
        instrs: "set[Instrument]" = set()
        if control in [16, 19, 20, 23]:
            instrs.add(self[0])
        if control in [17, 19, 21, 23]:
            instrs.add(self[1])
        if control in [18, 19, 22, 23]:
            instrs.add(self[2])
        return instrs


from .layers import Layers
