import numpy as np
from audioop import tostereo, tomono
from audio import Recorder
from utils import split, minmax, t2i, scroll


class Mixer(Recorder):
    _x = 0.5
    _phrase = 0

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, values):
        self._x = minmax(t2i(values) / 127)

    @property
    def phrase(self):
        return self._phrase

    @phrase.setter
    def phrase(self, values):
        phrase = self._phrase + t2i(values)
        max_phrase = len(self._data) - 1
        self._phrase = scroll(phrase, 0, max_phrase)

    @property
    def data(self):
        return self._data[self.phrase]

    @property
    def external_message(self):
        controls = ["volume", "xfade", "xfader", "phrase"]
        return lambda msg: super().external_message(msg) or msg.type in controls

    def _phrase_in(self, values):
        self.phrase = values

    def _volume_in(self, values):
        track, value = values
        copy = np.array(self.data[:, track], dtype=np.float32)
        self.data[:, track] = np.multiply(copy, minmax(value / 127))

    def _xfade_in(self, values):
        track, value = values
        stereo = tostereo(self.data[:, track], 4, *split(minmax(value / 127)))
        self.data[:, track] = tomono(stereo, 4, *split(self.x))

    def _xfader_in(self, values):
        self.x = values
