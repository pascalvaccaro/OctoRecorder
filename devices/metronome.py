import logging
import threading
import reactivex as rx
import reactivex.operators as ops
from reactivex.disposable import CompositeDisposable
from reactivex.scheduler import EventLoopScheduler
from bridge import Bridge
from midi import MidiDevice
from instruments.messages import InternalMessage as Msg
from utils import clip, t2i, scroll


class Metronome(MidiDevice):
    _bars = 2
    _playing = False
    _recording = False
    _overdub = False

    def __init__(self, device: MidiDevice):
        super().__init__(device)
        self.name = "[TEM] Metronome"

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

    def receive(self, observer, scheduler):
        def clocker(acc, msg):
            return 0 if msg.type == "start" else scroll(acc + 1, 0, self.size - 1)

        # inport iterable is blocking code, need to use a dedicated thread for a nice sync
        clock, messages = rx.from_iterable(self.inport, EventLoopScheduler()).pipe(
            ops.partition(self.select_message),
        )
        # now the clock can run the common thread
        return clock.pipe(
            ops.do_action(self.server.send),
            ops.scan(clocker, -1),
            ops.flat_map(self._beat_in),
            ops.merge(messages.pipe(ops.map(Msg.to_internal_message)))
        ).subscribe(observer, scheduler=scheduler)

    def start(self, *devices: Bridge):
        stop_event = threading.Event()
        all_devices = (self, *devices)
        try:
            main_disp = CompositeDisposable()
            for dev in all_devices:
                disp = rx.merge(*[dev.connect(d) for d in all_devices]).subscribe(
                    on_next=dev.send,
                    on_error=logging.exception,
                    on_completed=stop_event.set,
                    scheduler=MidiDevice.scheduler,
                )
                main_disp.add(disp)
            logging.info("%s syncing %i devices", self.name, len(devices))
            stop_event.wait()
            main_disp.dispose()
        except KeyboardInterrupt:
            logging.info("[ALL] Stopped by user")
            stop_event.set()

    def _beat_in(self, beat: int):
        if beat % 24 == 0:
            yield Msg("beat")
            if beat == 0:
                yield Msg("start", self.state, self.bars)
        elif self.size - beat == 1:
            yield Msg("end", self.state, self.bars)

    def _bars_in(self, msg: Msg):
        self.bars = msg.data

    def _play_in(self, _):
        self.playing = True

    def _rec_in(self, _):
        self.recording = True

    def _stop_in(self, _):
        self.playing = False
        self.recording = False

    def _overdub_in(self, msg: Msg):
        self.overdub = msg.data[0]

    def _toggle_in(self, _):
        self.overdub = False
        self.playing = not self.playing
        if not self.playing:
            self.recording = True
