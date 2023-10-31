import logging
import numpy as np
import sounddevice as sd
from audioop import tostereo, tomono
from midi import start
from utils import split, Mixer


def connect(name: str):
    class SoundDevice:
        def __init__(self, device):
            self.name = device.get("name")
            self.samplerate = device.get("default_samplerate")
            self.max_input_channels = device.get("max_input_channels")
            self.max_output_channels = device.get("max_output_channels")

    try:
        return SoundDevice(sd.query_devices(name))
    except ValueError as err:
        if str(err) == "No input/output device matching '" + name + "'":
            return SoundDevice(
                {
                    "name": "SY-1000: USB Audio",
                    "default_samplerate": 48000.0,
                    "max_input_channels": 8,
                    "max_output_channels": 8,
                }
            )
        else:
            raise err


class OctoRecorder(Mixer):
    @property
    def maxsize(self):
        # '6' is 4 * 60 seconds / 40 BPM (min tempo sets the largest size)
        return int(self.port.samplerate * self.bars * 6)

    def __init__(self, name):
        super(OctoRecorder, self).__init__(name, 8)
        self.port = connect(name)
        sd.default.device = self.port.name
        sd.default.samplerate = self.port.samplerate
        sd.default.channels = (
            self.port.max_input_channels,
            self.port.max_output_channels,
        )
        self.data = np.zeros((16, self.maxsize, 8), dtype=np.float32)
        self.stream = sd.RawStream(callback=self._callback)
        self.subs = start.schedule_periodic(self._start_in)
        logging.info(
            "[SD] Connected device %s with samplerate %f",
            self.name,
            self.port.samplerate,
        )

    def _callback(self, indata, outdata, frames, time, status):
        if status:
            logging.warn(status)
        if self.playing:
            phrase = self.data[self.phrase]
            chunksize = min(len(phrase) - self.current_frame, frames)
            outdata[:chunksize] = self._transform(
                phrase[self.current_frame : self.current_frame + chunksize,]
            )
            if chunksize < frames:
                outdata[:chunksize] = 0
                self.current_frame = 0
            else:
                self.current_frame += chunksize
        elif self.recording:
            phrase = self.data[self.phrase]
            cursor = min(len(phrase), self.current_frame + frames)
            phrase[self.current_frame : cursor] = indata
            if cursor >= len(phrase):
                phrase[:cursor] = 0
                self.current_frame = 0
            else:
                self.current_frame += cursor
        else:
            self.current_frame = 0
            outdata[:] = self._transform(indata)

    def _start_in(self, bars):
        self.bars = bars
        self.current_frame = 0
        self.data.resize(16, self.maxsize, 8)
        logging.info("[SD] %s %i chunk of data", self.state, self.maxsize)

    def _transform(self, data):
        for i, f in enumerate(self.xfaders):
            s = tostereo(data[:, i], 4, *split(f))
            data[:, i] = tomono(s, 4, *split(self.x))
        return np.multiply(np.array(data, dtype=np.float32), self.vsliders)
