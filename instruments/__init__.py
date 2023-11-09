from typing import List
from .instrument import Instrument
from .dynasynth import DynaSynth
from .oscsynth import OscSynth
from .gr300 import GR300
from .layers import Layers


class EGuitar(Instrument):
    pass


class AGuitar(Instrument):
    pass


class EBass(Instrument):
    pass


class VioGuitar(Instrument):
    pass


class PolyFx(Instrument):
    pass


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
        for i, ridx in enumerate([s.ridx for s in self]):
            if idx in ridx:
                self[i] = synth
                return
        if synth:
            self[0] = synth

    def select_by_control(self, control):
        instrs: "set[Instrument]" = set()
        if control in [16, 19, 20, 23]:
            instrs.add(self[0])
        if control in [17, 19, 21, 23]:
            instrs.add(self[1])
        if control in [18, 19, 22, 23]:
            instrs.add(self[2])
        return instrs
