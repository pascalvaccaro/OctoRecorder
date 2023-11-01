import logging
from sounddevice import Stream
from audio import AudioDevice
from midi import start


class Recorder(AudioDevice):
    @property
    def maxsize(self):
        # '6' is 4 * 60 seconds / 40 BPM (min tempo sets the largest size)
        return int(self.samplerate * self.bars * 6)

    def __init__(self, name, tracks=8):
        super(Recorder, self).__init__(name, tracks)
        self.stream = Stream(
            device=self.device.get("name"),
            samplerate=self.samplerate,
            channels=self.channels,
            callback=self._callback,
        )
        self.subs = start.schedule_periodic(self._start_in)
        logging.info(
            "[SD] Connected device %s (%fHz)",
            self.name,
            int(self.samplerate),
        )

    def _callback(self, indata, outdata, frames, time, status):
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
        self.current_frame = 0
        self.data = (16, self.maxsize, self.channels)
        logging.info("[SD] %s %i chunk of data", self.state, self.maxsize)
