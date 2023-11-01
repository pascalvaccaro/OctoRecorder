import numpy as np
from audioop import tostereo, tomono
from bridge import Bridge
from utils import split, minmax, scroll, t2i


class Mixer(Bridge):
    MAX_PHRASES = 16
    _x = 0.5
    _phrase = 0
    _bars = 2

    @property
    def bars(self):
        return self._bars

    @bars.setter
    def bars(self, values):
        self._bars = t2i(values)

    @property
    def phrase(self):
        return self._phrase

    @phrase.setter
    def phrase(self, values):
        phrase = self._phrase + t2i(values)
        self._phrase = scroll(phrase, 0, self.MAX_PHRASES - 1)

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, values):
        self._x = minmax(t2i(values) / 127)

    @property
    def data(self):
        return self._data[self.phrase]

    @data.setter
    def data(self, values):
        self._data.resize(values)

    def __init__(self, name, tracks):
        super(Mixer, self).__init__(name)
        self._data = np.zeros((self.MAX_PHRASES, 576000, tracks), dtype=np.float32)

    def _play_in(self, _):
        self.playing = True

    def _rec_in(self, _):
        self.recording = True

    def _stop_in(self, _):
        self.playing = False
        self.recording = False

    def _toggle_in(self, _):
        self.playing = not self.playing
        if not self.playing:
            self.recording = True

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

    def _bars_in(self, values):
        self.bars = values

    def _phrase_in(self, values):
        self.phrase = values

