import logging
import numpy as np
from sounddevice import Stream, query_devices, CallbackStop
from bridge import Bridge
from utils import t2i, retry


class Recorder(Bridge):
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
        return lambda msg: msg.type in ["start", "stop"]

    @property
    def samplerate(self):
        return self.device.get("default_samplerate", 48000.0)

    @property
    def channels(self):
        input_channels = self.device.get("max_input_channels", 8)
        output_channels = self.device.get("max_output_channels", 8)
        return min(input_channels, output_channels)

    @property
    def data(self):
        return self._data

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
            outdata[:] = indata[:remainder]
            offset = frames if remainder >= frames else remainder
            if "Play" in self.state:
                outdata[:offset] = self.data[self.cursor : self.cursor + offset]
                outdata[offset:] = 0
            if "Record" in self.state:
                self.data[self.cursor : self.cursor + offset] = outdata
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
            "[AUD] %sing %i bars sample (%i chunks)", self.state, bars, maxsize
        )

    def _stop_in(self, _):
        self.stream.stop()
