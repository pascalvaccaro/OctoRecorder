import logging
import numpy as np
import sounddevice as sd
from audioop import tostereo, tomono
from midi import beat, start
from utils import split, minmax, scroll, t2i, Bridge


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


class OctoRecorder(Bridge):
    _x = 0.5
    _phrase = 0
    _bars = 2
    _playing = False
    _recording = False

    @property
    def maxsize(self):
        # '6' is 4 * 60 seconds / 40 BPM (min tempo sets the largest size)
        return int(self.port.samplerate * self.bars * 6)

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

        start.schedule(wrapped)

    @recording.setter
    def recording(self, value: bool):
        def wrapped(_, __):
            self._recording = value
            self._playing = False if value else self._playing

        start.schedule(wrapped)

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

        beat.schedule(wrapped)

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

    def __init__(self, name):
        self.port = connect(name)
        sd.default.device = self.port.name
        sd.default.samplerate = self.port.samplerate
        sd.default.channels = (
            self.port.max_input_channels,
            self.port.max_output_channels,
        )
        super(OctoRecorder, self).__init__(self.port.name)
        self.vsliders = np.ones((1, 8), dtype=np.float32)
        self.xfaders = np.array(([self.x] * 8), dtype=np.float32)
        self.data = np.zeros((16, self.maxsize, 8), dtype=np.float32)
        self.stream = sd.RawStream(callback=self._callback)
        self.subs = start.schedule_periodic(self._start_in)
        logging.info(
            "[SD] Connected device %s with samplerate %f",
            self.name,
            self.port.samplerate,
        )

    def send(self, _):
        return None

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
