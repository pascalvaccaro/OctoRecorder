from . import Instrument
from .params import Pot, Bipolar, LFO, String
from .sequencer import Sequencer, Grid, Bar


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
