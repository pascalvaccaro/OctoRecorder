import numpy as np
import midi.clock as clock
from utils import minmax, scroll, t2i, Bridge


class Mixer(Bridge):
    _x = 0.5
    _phrase = 0
    _bars = 2
    _playing = False
    _recording = False

    @property
    def playing(self):
        return self._playing

    @property
    def recording(self):
        return self._recording

    @playing.setter
    def playing(self, value: bool):
        def wrapped(_, __):
            self._playing = value
            self._recording = False if value else self._recording

        clock.start.schedule(wrapped)

    @recording.setter
    def recording(self, value: bool):
        def wrapped(_, __):
            self._recording = value
            self._playing = False if value else self._playing

        clock.start.schedule(wrapped)

    @property
    def state(self):
        if self.playing:
            return "Playing"
        if self.recording:
            return "Recording"
        return "Streaming"

    @property
    def bars(self):
        return self._bars

    @bars.setter
    def bars(self, values):
        def wrapped(_, __):
            self._bars = t2i(values)

        clock.beat.schedule(wrapped)

    @property
    def phrase(self):
        return self._phrase

    @phrase.setter
    def phrase(self, values):
        phrase = self._phrase + t2i(values)
        self._phrase = scroll(phrase, 0, 15)

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, values):
        self._x = minmax(t2i(values) / 127)

    @property
    def is_closed(self):
        return True

    @property
    def external_message(self):
        return lambda msg: msg.type in [
            "volume",
            "xfade",
            "xfader",
            "play",
            "rec",
            "stop",
            "toggle",
            "phrase",
            "bars",
        ]

    def __init__(self, name, tracks):
        super(Mixer, self).__init__(name)
        self.vsliders = np.ones((1, tracks), dtype=np.float32)
        self.xfaders = np.array(([self.x] * tracks), dtype=np.float32)

    def send(self, _):
        return None

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
        self.vsliders[0][track] = minmax(value / 127)

    def _xfade_in(self, values):
        track, value = values
        self.xfaders[0][track] = minmax(value / 127)

    def _xfader_in(self, values):
        self.x = values

    def _bars_in(self, values):
        self.bars = values

    def _phrase_in(self, values):
        self.phrase = values
