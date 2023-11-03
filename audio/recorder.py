import logging
import numpy as np
from sounddevice import Stream, query_devices
from bridge import Bridge
from utils import t2i, retry


class Recorder(Bridge):
    _playing = False
    _playing_sync = False
    _recording = False
    _recording_sync = False
    _bars = 2

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
        self._data = np.zeros((phrases, self.maxsize, channels), dtype=np.float32)
        self.stream = Stream(
            device=self.device.get("name"),
            samplerate=self.samplerate,
            channels=(channels) * 2,
            callback=self.callback,
        )
        logging.info("[AUD] Recording device %s at %i.Hz", self.name, self.samplerate)

    @property
    def external_message(self):
        controls = ["start", "play", "rec", "stop", "toggle", "bars"]
        return lambda msg: super().external_message(msg) or msg.type in controls

    @property
    def state(self):
        return (
            "Playing"
            if self.playing
            else "Recording"
            if self.recording
            else "Streaming"
        )

    @property
    def playing(self):
        return self._playing

    @playing.setter
    def playing(self, value: bool):
        self._playing = value
        self._playing_sync = self._playing
        self._recording = False if value else self._recording
        self._recording_sync = self._recording

    @property
    def recording(self):
        return self._recording

    @recording.setter
    def recording(self, value: bool):
        self._recording = value
        self._recording_sync = self._recording
        self._playing = False if value else self._playing
        self._playing_sync = self._playing

    @property
    def bars(self):
        return self._bars

    @bars.setter
    def bars(self, values):
        self._bars = t2i(values)

    @property
    def samplerate(self):
        return self.device.get("default_samplerate", 48000.0)

    @property
    def channels(self):
        input_channels = self.device.get("max_input_channels", 8)
        output_channels = self.device.get("max_output_channels", 8)
        return max(input_channels, output_channels)

    @property
    def maxsize(self):
        # '6' is 4 * 60 seconds / 40 BPM (min tempo sets the largest size)
        return int(self.samplerate * self.bars * 6)

    @property
    def data(self):
        return self._data

    @property
    def is_closed(self):
        return True

    def callback(self, indata, outdata, frames, time, status):
        if status:
            logging.warn(status)
        if self.recording:
            cursor = min(len(self.data), self.current_frame + frames)
            self.data[self.current_frame : cursor] = indata
            if cursor >= len(self.data):
                self.data[:cursor] = 0
                self.current_frame = 0
            else:
                self.current_frame += cursor
        elif self.playing:
            chunksize = min(len(self.data) - self.current_frame, frames)
            outdata[:chunksize] = self.data[
                self.current_frame : self.current_frame + chunksize,
            ]
            if chunksize < frames:
                outdata[:chunksize] = 0
                self.current_frame = 0
            else:
                self.current_frame += chunksize
        else:
            self.current_frame = 0
            outdata[:] = indata

    def _start_in(self, bars):
        self.bars = bars
        self._data.resize((16, self.maxsize, self.channels))
        self.playing = self._playing_sync
        self.recording = self._recording_sync
        logging.info("[AUD] %s %i chunk of data", self.state, self.maxsize)
        self.current_frame = 0

    def _bars_in(self, values):
        self.bars = values

    def _play_in(self, _):
        self._playing_sync = True

    def _rec_in(self, _):
        self._recording_sync = True

    def _stop_in(self, _):
        self.playing = False
        self.recording = False

    def _toggle_in(self, _):
        self._playing_sync = not self._playing_sync
        if not self._playing_sync:
            self._recording_sync = True
