import logging
from numpy import frombuffer, zeros, ones, float32, array
from audioop import add, mul, tomono, tostereo
from sounddevice import Stream, CallbackStop, query_devices
from bridge import Bridge
from utils import minmax, t2i, retry, scroll


class Recorder(Bridge, Stream):
    x = 0.5
    _phrase = 0
    _volumes = ones(8, dtype=float32)
    _pans = array([0.5] * 8, dtype=float32)
    _data = zeros((16, 576000, 8), dtype=float32)

    def __init__(self, name, phrases=16, channels=8, samplerate=48000.0):
        super(Recorder, self).__init__("[AUD] " + name)
        device = retry(query_devices, [name])
        if not isinstance(device, dict):
            device = dict()
        self._data.resize((phrases, int(samplerate * 12), channels))
        Stream.__init__(
            self,
            device=device.get("name", name),
            channels=device.get("max_input_channels", channels),
            samplerate=device.get("default_samplerate", samplerate),
            dtype=float32,
            callback=self.play_rec,
        )
        logging.info("%s recording at %i.Hz", self.name, self.samplerate)

    def __del__(self):
        self.close()

    @property
    def external_message(self):
        controls = ["start", "stop", "volumes", "phrase", "xfade", "xfader"]
        return lambda msg: msg.type in controls

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
    def faders(self):
        faders = []
        for ch, vol in enumerate(self._volumes):
            if ch < 6:  # strings
                faders += [(vol, self._pans[ch])]
            elif ch == 6:  # OUT-L
                faders += [(vol * (1 - self._pans[ch]), None)]
            elif ch == 7:  # OUT-R
                faders += [(vol * self._pans[ch], None)]
        return faders

    @property
    def is_closed(self):
        return self.closed

    def play_rec(self, indata, outdata, frames, _, status):
        if status:
            logging.warn(status)
        try:
            remainder = len(self.data) - self.cursor
            if remainder <= 0:
                raise CallbackStop
            offset = frames if remainder >= frames else remainder
            buffer = zeros((frames, self.channels[0]), dtype=float32)
            if "Play" in self.state:
                buffer[:offset][:] = self.data[self.cursor : self.cursor + offset]
                buffer[offset:] = 0
            if "Record" in self.state:
                self.data[self.cursor : self.cursor + offset] = indata[:offset]
            for ch, values in enumerate(self.faders):
                vol, pan = values
                track_in = indata[:, ch].tobytes()
                track_out = mul(buffer[:, ch].tobytes(), 4, vol)
                if pan is not None:  # string pan
                    stereo = tostereo(track_out, 4, 1 - pan, pan)
                    track_out = tomono(stereo, 4, 1 - self.x, self.x)
                outdata[:offset, ch] = frombuffer(
                    add(track_in, track_out, 4), dtype=float32
                )
            outdata[offset:] = 0
            self.cursor += offset
        except Exception as e:
            logging.exception(e)

    def _start_in(self, msg):
        self.state, bars = msg.data
        # '6' is 4 * 60 seconds / 40 BPM (min tempo sets the largest size)
        maxsize = int(self.samplerate * bars * 6)
        self._data.resize((len(self._data), maxsize, self.channels[0]))
        self.cursor = 0
        label = "ing/".join(self.state)
        logging.debug("[AUD] %sing %i bars sample (%i chunks)", label, bars, maxsize)

    def _phrase_in(self, msg):
        self.phrase = msg.data

    def _volume_in(self, msg):
        track, value = msg.data
        self._volumes[track] = minmax(value / 127)

    def _stop_in(self, _):
        self.stop()

    def _xfade_in(self, msg):
        track, value = msg.data[1:]
        self._pans[track] = minmax(value / 127)

    def _xfader_in(self, msg):
        self.x = minmax(msg.data[0] / 127)
