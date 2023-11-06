import logging
import threading
import reactivex as rx
import reactivex.operators as ops
from reactivex.abc import ObserverBase, SchedulerBase
from reactivex.scheduler import EventLoopScheduler, CatchScheduler
from typing import Optional
from bridge import Bridge
from midi import InternalMessage as Msg, MidiDevice
from utils import clip, t2i, scroll


class Sequencer(MidiDevice):
    _bars = 2
    _playing = False
    _recording = False
    _overdub = False

    def __init__(self, device):
        super().__init__(device)
        self.name = "[SEQ] Sequencer"

    @property
    def select_message(self):
        return lambda msg: msg.type in ["clock", "start"]

    @property
    def external_message(self):
        params = ["bars", "play", "rec", "stop", "toggle", "overdub"]
        return lambda msg: msg.type in params

    @property
    def bars(self):
        return self._bars

    @bars.setter
    def bars(self, value):
        self._bars = clip(t2i(value), 1, 8)

    @property
    def playing(self):
        return self._playing

    @playing.setter
    def playing(self, value: bool):
        self._playing = value
        if value and not self.overdub:
            self._recording = False

    @property
    def recording(self):
        return self._recording

    @recording.setter
    def recording(self, value: bool):
        self._recording = value
        if value and not self.overdub:
            self._playing = False

    @property
    def overdub(self):
        return self._overdub

    @overdub.setter
    def overdub(self, value: bool):
        self._overdub = value
        self.recording = value
        self.playing = value or True

    @property
    def state(self):
        state = []
        if self.playing:
            state += ["Play"]
        if self.recording:
            state += ["Record"]
        if not self.overdub:
            state += ["Stream"]
        return state

    @property
    def size(self):
        return self.bars * 4 * 24

    def subscriber(self, observer, scheduler):
        def clocker(acc, msg):
            return 0 if msg.type == "start" else scroll(acc + 1, 0, self.size - 1)

        # inport iterable is blocking code, need to use a dedicated thread for a nice sync
        return (
            rx.from_iterable(self.inport, EventLoopScheduler()).pipe(
                ops.filter(self.select_message),
                ops.do_action(self.server.send),
                ops.scan(clocker, -1),
                ops.flat_map(self._beat_in),
            )
            # now the clock can run the common thread
            .subscribe(observer, scheduler=scheduler)
        )

    def start(self, *devices: Bridge):
        def on_error(e):
            return logging.exception(e) or True

        stop_event = threading.Event()
        all_devices = (self, *devices)
        scheduler = CatchScheduler(EventLoopScheduler(), on_error)
        for dev in all_devices:
            dev.subs = rx.merge(*[dev.attach(d) for d in all_devices]).subscribe(
                on_next=dev.send, on_completed=stop_event.set, scheduler=scheduler
            )
        logging.info("%s syncing %i devices", self.name, len(devices))
        return stop_event

    def _beat_in(self, beat):
        if beat % 24 == 0:
            yield Msg("beat")
            if beat == 0:
                yield Msg("start", self.state, self.bars)
        elif self.size - beat == 1:
            yield Msg("end", self.state, self.bars)

    def _bars_in(self, msg):
        self.bars = msg.data

    def _play_in(self, _):
        self.playing = True

    def _rec_in(self, _):
        self.recording = True

    def _stop_in(self, _):
        self.playing = False
        self.recording = False

    def _overdub_in(self, msg):
        self.overdub = msg.data[0]

    def _toggle_in(self, _):
        self.overdub = False
        self.playing = not self.playing
        if not self.playing:
            self.recording = True
