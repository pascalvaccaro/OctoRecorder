import logging
import numpy as np
import sounddevice as sd
from audioop import tostereo, tomono
from midi import MidiDevice
from utils import split, minmax, scroll, t2i


class SoundDevice:
    def __init__(self, device):
        self.name = device.get("name")
        self.samplerate = device.get("default_samplerate")
        self.max_input_channels = device.get("max_input_channels")
        self.max_output_channels = device.get("max_output_channels")


try:
    sy1000 = SoundDevice(sd.query_devices("SY-1000"))
except ValueError as err:
    if str(err) == "No input/output device matching 'SY-1000'":
        sy1000 = SoundDevice(
            {
                "name": "SY-1000: USB Audio",
                "default_samplerate": 48000.0,
                "max_input_channels": 8,
                "max_output_channels": 8,
            }
        )
    else:
        raise err

sd.default.device = sy1000.name
sd.default.samplerate = sy1000.samplerate
sd.default.channels = (sy1000.max_input_channels, sy1000.max_output_channels)


class OctoRecorder:
    _x = 0.5
    _phrase = 0
    _bars = 2
    _playing = False
    _recording = False

    @property
    def maxsize(self):
        # '6' is 4 * 60 seconds / 40 BPM (min tempo sets the largest size)
        return int(sy1000.samplerate * self.bars * 6)

    @property
    def playing(self):
        return self._playing

    @property
    def recording(self):
        return self._recording

    @playing.setter
    def playing(self, value: bool):
        self._playing = value
        self._recording = False if value else self._recording

    @recording.setter
    def recording(self, value: bool):
        self._recording = value
        self._playing = False if value else self._playing

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
        self._bars = t2i(values)

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
        self._x = minmax(t2i(values))

    def __init__(self, bars=2):
        self.bars = bars
        self.vsliders = np.ones((1, 8), dtype=np.float32)
        self.xfaders = np.array(([self.x] * 8), dtype=np.float32)
        self.data = np.zeros((16, self.maxsize, 8), dtype=np.float32)
        self.stream = sd.RawStream(callback=self._callback)
        logging.info(
            "[SD] Connected device %s with samplerate %f",
            sy1000.name,
            sy1000.samplerate,
        )

    def bind(self, synth: MidiDevice, control: MidiDevice):
        synth.on("start", self._start)
        for dev in (synth, control):
            dev.on("stop", self._stop)
        for ev in ("play", "rec", "toggle"):
            control.sync(ev, "start", getattr(self, "_" + ev))
        for ev in ("volume", "xfade", "xfader"):
            control.on(ev, getattr(self, "_" + ev))
        for ev in ("phrase", "bars"):
            control.on(ev, getattr(self, "_set_" + ev))

    def _start(self, bars):
        self.bars = bars
        self.current_frame = 0
        self.data.resize(16, self.maxsize, 8)
        logging.debug("[SD] %s %i chunk of data", self.state, self.maxsize)

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

    def _transform(self, data):
        for i, f in enumerate(self.xfaders):
            s = tostereo(data[:, i], 4, *split(f))
            data[:, i] = tomono(s, 4, *split(self.x))
        return np.multiply(np.array(data, dtype=np.float32), self.vsliders)

    def _play(self, _):
        self.playing = True

    def _rec(self, _):
        self.recording = True

    def _stop(self, _):
        self.playing = False
        self.recording = False

    def _toggle(self, _):
        self.playing = not self.playing
        if not self.playing:
            self.recording = True

    def _volume(self, values):
        track, value = values
        self.vsliders[0][track] = minmax(value)

    def _xfade(self, values):
        track, value = values
        self.xfaders[0][track] = minmax(value)

    def _xfader(self, values):
        self.x = values

    def _set_bars(self, values):
        self.bars = values

    def _set_phrase(self, values):
        self.phrase = values
