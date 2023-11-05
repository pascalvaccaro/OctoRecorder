import logging
import numpy as np
from sounddevice import Stream, CallbackStop, query_devices
from audio import Mixer
from utils import t2i, retry, scroll


class Recorder(Mixer, Stream):
    _phrase = 0
    _data = np.zeros((16, 576000, 8), dtype=np.float32)

    def __init__(self, name, phrases=16, channels=8, samplerate=48000.0):
        super(Recorder, self).__init__(name)
        device = retry(query_devices, [name])
        if not isinstance(device, dict):
            device = dict()
        self._data.resize((phrases, int(samplerate * 12), channels))
        Stream.__init__(
            self,
            device=device.get("name", name),
            samplerate=device.get("default_samplerate", samplerate),
            channels=device.get("max_input_channels", channels),
            callback=self.play_rec,
        )
        logging.info("[AUD] Recording device %s at %i.Hz", self.name, self.samplerate)

    def __del__(self):
        self.close()

    @property
    def external_message(self):
        params = ["start", "stop", "phrase"]
        super_external = super().external_message
        return lambda msg: super_external(msg) or msg.type in params

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
            buffer = np.zeros((frames, self.channels[0]), dtype=np.float32)
            if "Play" in self.state:
                buffer[:offset] = self.data[self.cursor : self.cursor + offset]
                buffer[offset:] = 0
            if "Record" in self.state:
                self.data[self.cursor : self.cursor + offset] = indata[:offset]
            outdata[:] = self.master_out(indata, buffer)
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

    def _stop_in(self, _):
        self.stop()
