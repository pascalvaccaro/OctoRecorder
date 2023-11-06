import logging
from numpy import frombuffer, zeros, ones, float32
from audioop import add, mul
from sounddevice import Stream, CallbackStop, query_devices
from bridge import Bridge
from utils import minmax, t2i, retry, scroll


class Recorder(Bridge, Stream):
    _phrase = 0
    _volumes = ones(8, dtype=float32)
    _data = zeros((16, 576000, 8), dtype=float32)

    def __init__(self, name, phrases=16, channels=8, samplerate=48000.0):
        super(Recorder, self).__init__(name)
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
        logging.info("[AUD] Recording device %s at %i.Hz", self.name, self.samplerate)

    def __del__(self):
        self.close()

    @property
    def external_message(self):
        return lambda msg: msg.type in ["start", "stop", "volumes", "phrase"]

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
    def volumes(self):
        return self._volumes

    @volumes.setter
    def volumes(self, values):
        track, value = values
        self._volumes[track] = minmax(value / 127)

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
            for ch, vol in enumerate(self.volumes):
                track_in = indata[:, ch].tobytes()
                track_out = mul(buffer[:, ch].tobytes(), 4, vol)
                outdata[:, ch] = frombuffer(add(track_in, track_out, 4), dtype=float32)
            self.cursor += offset
        except Exception as e:
            logging.exception(e)

    def _start_in(self, msg):
        self.stop()
        self.state, bars = msg.data
        # '6' is 4 * 60 seconds / 40 BPM (min tempo sets the largest size)
        maxsize = int(self.samplerate * bars * 6)
        self._data.resize((len(self._data), maxsize, self.channels[0]))
        self.cursor = 0
        self.start()
        logging.info(
            "[AUD] %sing %i bars sample (%i chunks)",
            "ing/".join(self.state),
            bars,
            maxsize,
        )

    def _phrase_in(self, msg):
        self.phrase = msg.data

    def _volume_in(self, msg):
        self.volumes = msg.data

    def _stop_in(self, _):
        self.stop()
