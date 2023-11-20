from typing import List, Union
from midi.messages import SysexReq
from .params import Pot, Pad, Bipolar, LFO, Switch, String
from .sequencer import Sequencer, Grid, Bar


class Instrument:
    params: List[Union[String, Pot, Pad]] = [
        String((6, 12), 16),
        String((12, -6), 20),
    ]

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
            for request in [r for r in param.request if r is not None]:
                yield SysexReq("patch", [self.instr, *request])

    def receive(self, address: int, data: "list[int]"):
        """Called with the SY100 answer to an instr request"""
        for param in self.params:
            if param.origin == address:
                yield from param.to_internal(self.idx, data)

    def send(self, msg):
        """Called when the APC40 sends a command to this SY1000 instrument"""
        for param in self.params:
            if param.select_message(msg):
                yield from param.from_internal(self.instr, msg)


class DynaSynth(Instrument):
    params = [
        String((6, 12), 16),
        String((12, -6), 20),
        Pot((5, 1), 48, (8, 56)),  # pitch
        Pot((16, 1), 52, (14, 114)),  # pitch env. depth
        Bipolar((29, 6), 49),  # filter type + cutoff
        Pot((32, -3), 53),  # resonance
        Pot((33, -4), 50, (14, 114)),  # f. env. attack
        Pot((34, -5), 54, (14, 114)),  # f. env. depth
        LFO((39, 3), 51, (100, 118)),  # lfo 1 rate
        LFO((49, 3), 55, (100, 118)),  # lfo 2 rate
        Sequencer(
            (59, 125),
            53,
            # pitch: +12, +5, +3, +1, 0
            Grid((62, -3), 82, (8, 56), [96, 77, 72, 66, 64]),
            Grid((94, -35), 83),  # cutoff
            Grid((126, -67), 84),  # level
            Bar((158, -99), 85, (0, 118)),  # sequencer 1
            Bar((180, -121), 86, (0, 118)),  # sequencer 2
        ),
    ]

    @property
    def instr(self):
        return self._instr + 1


class OscSynth(Instrument):
    params = [
        String((6, 12), 16),
        String((12, -6), 20),
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
        String((6, 12), 16),
        String((12, -6), 20),
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
    params = [
        String((6, 12), 16),
        String((12, -6), 20),
    ]
    @property
    def instr(self):
        return self._instr + 5


class AGuitar(Instrument):
    params = [
        String((6, 12), 16),
        String((12, -6), 20),
    ]
    @property
    def instr(self):
        return self._instr + 6


class EBass(Instrument):
    params = [
        String((6, 12), 16),
        String((12, -6), 20),
    ]
    @property
    def instr(self):
        return self._instr + 7


class VioGuitar(Instrument):
    params = [
        String((6, 12), 16),
        String((12, -6), 20),
    ]
    @property
    def instr(self):
        return self._instr + 8


class PolyFx(Instrument):
    params = [
        String((6, 12), 16),
        String((12, -6), 20),
    ]
    @property
    def instr(self):
        return self._instr + 9


class Instruments(List[Instrument]):
    types = (DynaSynth, OscSynth, GR300, EGuitar, AGuitar, EBass, VioGuitar, PolyFx)

    def __init__(self, *args: int):
        super().__init__([Instrument(arg) for arg in args])

    @property
    def request(self):
        for instr in self:
            # instr type + volume
            yield SysexReq("patch", [instr._instr, 1, 0, 0, 0, 2])
            # instr strings volume + pan
            yield SysexReq("patch", [instr._instr, 6, 0, 0, 0, 12])

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

    def _set(self, idx: int, synth: Instrument):
        self[idx] = synth

