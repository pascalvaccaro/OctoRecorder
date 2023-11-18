from typing import List, Union
from midi.messages import InternalMessage, SysexCmd, SysexReq
from .params import Pot, Pad, Bipolar, LFO, Switch


class Instrument:
    params: List[Union[Pot, Pad]] = []

    def __init__(self, instr: int):
        self._instr = instr

    @property
    def instr(self):
        return self._instr

    @property
    def range(self):
        return range(self._instr, self._instr + 11)

    @property
    def idx(self):
        return divmod(self._instr - 10, 11)[0]

    @property
    def request(self):
        for param in self.params:
            for request in param.request:
                yield SysexReq("patch", [self.instr, *request])

    def receive(self, address: int, data: "list[int]"):
        """Called with the SY100 answer to a synth params request for this instrument"""
        for param in self.params:
            if param.origin == address:
                yield from param.to_internal(self.idx, data)

    def send(self, msg: InternalMessage):
        """Called when the APC40 sends a params command to this SY1000 instrument"""
        for param in self.params:
            if param.select_message(msg):
                yield SysexCmd("patch", [self.instr, *param.from_internal(msg)])


class OscSynth(Instrument):
    params = [
        Pot((2, 1), 48, (8, 56)),  # pitch
        Pot((8, 1), 52, (4, 28)),  # pitch env. depth
        Bipolar((27, 11, 3), 49),  # filter type + cutoff
        Pot((31, -4), 53),  # resonance
        Pot((33, -6), 50),  # f. env. attack
        Pot((37, -10), 54, (14, 144)),  # f. env. depth
        LFO((45, 3), 51, (100, 118)),  # lfo 1 rate
        LFO((55, 3), 55, (100, 118)),  # lfo 2 rate
    ]

    @property
    def instr(self):
        return self._instr + 3


class GR300(Instrument):
    params = [
        Pot((8, 3), 48, (4, 28)),  # pitch A
        Pot((10, 0), 52, (4, 28)),  # pitch B
        Pot((2, 2), 49),  # cutoff
        Pot((3, -1), 53),  # resonance
        Switch((13, 3), 54),  # sweep switch + rise
        Pot((15, -2), 50),  # sweep fall
        Switch((16, 3), 55),  # vibrato switch + rate
        Pot((18, -2), 51),  # vibrato depth
    ]

    @property
    def instr(self):
        return self._instr + 4


class EGuitar(Instrument):
    @property
    def instr(self):
        return self._instr + 5


class AGuitar(Instrument):
    @property
    def instr(self):
        return self._instr + 6


class EBass(Instrument):
    @property
    def instr(self):
        return self._instr + 7


class VioGuitar(Instrument):
    @property
    def instr(self):
        return self._instr + 8


class PolyFx(Instrument):
    @property
    def instr(self):
        return self._instr + 9


from .dynasynth import DynaSynth


class Instruments(List[Instrument]):
    types = (DynaSynth, OscSynth, GR300, EGuitar, AGuitar, EBass, VioGuitar, PolyFx)

    def __init__(self, *args: int):
        super().__init__([Instrument(arg) for arg in args])

    def get(self, idx: int):
        if idx < len(self):
            return self[idx]
        for instr in self:
            if idx in instr.range:
                return instr
        raise Exception("No instrument with idx %i", idx)

    def set(self, idx: int, typx: int):
        if typx not in range(0, 8):
            return
        synth = Instruments.types[typx](idx)
        if synth is None:
            return
        for i, ridx in enumerate([s.range for s in self]):
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
