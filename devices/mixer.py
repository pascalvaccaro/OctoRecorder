from audio import Recorder, fade
from utils import minmax, t2i, scroll


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
        params = ["volume", "xfade", "xfader", "phrase"]
        super_external = super().external_message
        return lambda msg: super_external(msg) or msg.type in params

    def _phrase_in(self, msg):
        self.phrase = msg.data

    def _volume_in(self, msg):
        track, value = msg.data
        self.data[:, track] = fade(self.data[:, track], value / 127)

    def _xfade_in(self, msg):
        track, value = msg.data
        self.data[:, track] = fade(self.data[:, track], value / 127, self.x)

    def _xfader_in(self, msg):
        self.x = msg.data
