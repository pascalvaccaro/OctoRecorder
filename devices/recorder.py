import logging
import numpy as np
from sounddevice import CallbackStop, query_devices
from audio import Stream, Mixer
from utils import t2i, retry, scroll


class Recorder(Mixer):
    _phrase = 0

    def __init__(self, name, phrases=16, channels=8, samplerate=48000.0):
        device = retry(query_devices, [name])
        if isinstance(device, dict):
            self.device = device
        else:
            self.device = dict(
                name=name,
                max_input_channels=channels,
                max_output_channels=channels,
                default_samplerate=samplerate,
            )
        super(Recorder, self).__init__(name)
        self._data = np.zeros((phrases, 576000, channels), dtype=np.float32)
        self.stream = Stream(
            faders=self.faders,
            device=self.device.get("name"),
            samplerate=self.samplerate,
            channels=self.channels,
            callback=self.playrec,
        )
        logging.info("[AUD] Recording device %s at %i.Hz", self.name, self.samplerate)

    def __del__(self):
        self.stream.close()

    @property
    def external_message(self):
        params = ["start", "stop", "phrase"]
        super_external = super().external_message
        return lambda msg: super_external(msg) or msg.type in params

    @property
    def samplerate(self):
        return self.device.get("default_samplerate", 48000.0)

    @property
    def channels(self):
        input_channels = self.device.get("max_input_channels", 8)
        output_channels = self.device.get("max_output_channels", 8)
        return min(input_channels, output_channels)

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
        return self.stream.closed

    def playrec(self, indata, outdata, frames, time, status):
        if status:
            logging.warn(status)
        try:
            remainder = len(self.data) - self.cursor
            if remainder <= 0:
                raise CallbackStop
            offset = frames if remainder >= frames else remainder
            if "Record" in self.state:
                self.data[self.cursor : self.cursor + offset] = indata
            if "Play" in self.state:
                outdata[:offset] = self.data[self.cursor : self.cursor + offset]
                outdata[offset:] = 0
            elif "Stream" in self.state:
                outdata[:] = indata
            self.cursor += offset
        except Exception as e:
            logging.exception(e)

    def _start_in(self, msg):
        self.stream.stop()
        self.state, bars = msg.data
        # '6' is 4 * 60 seconds / 40 BPM (min tempo sets the largest size)
        maxsize = int(self.samplerate * bars * 6)
        self._data.resize((len(self._data), maxsize, self.channels))
        self.cursor = 0
        self.stream.start()
        logging.info(
            "[AUD] %sing %i bars sample (%i chunks)",
            "ing/".join(self.state),
            bars,
            maxsize,
        )

    def _phrase_in(self, msg):
        self.phrase = msg.data

    def _stop_in(self, _):
        self.stream.stop()
