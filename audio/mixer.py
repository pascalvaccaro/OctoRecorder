from bridge import Bridge
from utils import minmax, t2i


class Mixer(Bridge):
    _x = 0.5
    _faders = [(1.0, 0.5)] * 8

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, values):
        self._x = minmax(t2i(values) / 127)

    @property
    def faders(self):
        return self._faders, self._x

    @faders.setter
    def faders(self, values):
        control, track, value = values
        self._faders[track][control] = minmax(value / 127)

    @property
    def external_message(self):
        return lambda msg: msg.type in ["volume", "xfade", "xfader"]

    def _volume_in(self, msg):
        self.faders = [0, *msg.data]

    def _xfade_in(self, msg):
        self.faders = [1, *msg.data]

    def _xfader_in(self, msg):
        self.x = msg.data
