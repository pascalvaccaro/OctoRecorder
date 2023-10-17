import logging
import numpy as np
import sounddevice as sd
from audioop import tostereo, tomono
from midi import MidiDevice
from utils import split, minmax, scroll

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
    playing = False
    recording = False
    phrase = 0
    x = 0.5

    def __init__(self, synth, control):
        self.tempo = int(synth.tempo)
        self.bars = int(control.bars)
        self.vsliders = np.ones((1, 8), dtype=np.float32)
        self.xfaders = np.array(([OctoRecorder.x] * 8), dtype=np.float32)
        self.data = np.zeros((16, self.maxsize, 8), dtype=np.float32)
        self.stream = sd.RawStream(callback=self._callback)
        logging.info(
            "[SD] Connected device %s with samplerate %f",
            sy1000.name,
            sy1000.samplerate,
        )
        self._listen(synth, control)

    @property
    def maxsize(self):
        # length in seconds = bars * 4 beats * 60 seconds / BPM
        seconds = self.bars * 240 / self.tempo
        # samplerate * seconds
        return int(sy1000.samplerate * seconds)

    def _listen(self, synth: MidiDevice, control: MidiDevice):
        synth.on("start", self._start)
        start = synth.on("start")
        for dev in (synth, control):
            dev.on("stop", self._stop)
        for ev in ("play", "rec", "toggle"):
            control.sync(ev, start, getattr(self, "_" + ev))
        for ev in ("volume", "xfade", "xfader"):
            control.on(ev, getattr(self, "_" + ev))
        for ev in ("phrase", "bars"):
            control.on(ev, getattr(self, "_set_" + ev))

    def _callback(self, indata, outdata, frames, time, status):
        if status:
            logging.warn(status)
        if OctoRecorder.playing:
            phrase = self.data[OctoRecorder.phrase]
            chunksize = min(len(phrase) - self.current_frame, frames)
            outdata[:chunksize] = self._transform(
                phrase[self.current_frame : self.current_frame + chunksize,]
            )
            if chunksize < frames:
                outdata[:chunksize] = 0
                self.current_frame = 0
            else:
                self.current_frame += chunksize
        elif OctoRecorder.recording:
            phrase = self.data[OctoRecorder.phrase]
            cursor = min(len(phrase), self.current_frame + frames)
            phrase[self.current_frame : cursor] = indata
            if cursor >= len(phrase):
                self.data[OctoRecorder.phrase, :cursor] = 0
                self.current_frame = 0
            else:
                self.current_frame += cursor
        else:
            self.current_frame = 0
            outdata[:] = self._transform(indata)

    def _transform(self, data):
        for i, f in enumerate(self.xfaders):
            s = tostereo(data[:, i], 4, *split(f))
            data[:, i] = tomono(s, 4, *split(OctoRecorder.x))
        return np.multiply(np.array(data, dtype=np.float32), self.vsliders)

    def _start(self, values):
        self.tempo, self.bars = (int(x) for x in values)
        self.data.resize(16, self.maxsize, 8)
        self.current_frame = 0
        if OctoRecorder.playing:
            logging.info("[SD] Start playing %i chunk of data", self.maxsize)
        elif OctoRecorder.recording:
            logging.info("[SD] Start recording %i chunk of data", self.maxsize)
        else:
            logging.info("[SD] Start streaming %i chunk of data", self.maxsize)

    def _play(self, _):
        OctoRecorder.playing = True
        OctoRecorder.recording = False

    def _rec(self, _):
        OctoRecorder.playing = False
        OctoRecorder.recording = True

    def _stop(self, _):
        OctoRecorder.playing = False
        OctoRecorder.recording = False

    def _toggle(self, _):
        OctoRecorder.playing = not OctoRecorder.playing
        OctoRecorder.recording = not OctoRecorder.recording

    def _volume(self, values):
        track, value = values
        self.vsliders[0][track] = minmax(value)

    def _xfade(self, values):
        track, value = values
        self.xfaders[0][track] = minmax(value)

    def _xfader(self, values):
        OctoRecorder.x = minmax(values[0])

    def _set_bars(self, values=[2]):
        self.bars = values[0]

    def _set_phrase(self, values):
        phrase = OctoRecorder.phrase + values[0]
        OctoRecorder.phrase = scroll(phrase, 0, 15)
