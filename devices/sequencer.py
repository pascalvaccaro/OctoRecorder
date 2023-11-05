import logging
import threading
import reactivex as rx
import reactivex.operators as ops
from reactivex.scheduler import EventLoopScheduler, CatchScheduler
from midi import InternalMessage as Msg, MidiDevice, MidiScheduler
from bridge import Bridge
from utils import clip, t2i, scroll


class Sequencer(MidiDevice):
    _bars = 2
    _playing = False
    _recording = False

    @property
    def external_message(self):
        return lambda msg: msg.type in ["bars", "play", "rec", "stop", "toggle"]

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
        if value:
            self._recording = False

    @property
    def recording(self):
        return self._recording

    @recording.setter
    def recording(self, value: bool):
        self._recording = value
        if value:
            self._playing = False

    @property
    def state(self):
        return "Play" if self.playing else "Record" if self.recording else "Stream"

    @property
    def size(self):
        return self.bars * 4 * 24

    def subscriber(self, observer, _):
        clock = self.clock if hasattr(self, "clock") else rx.interval(1000 / 24)
        return clock.pipe(
            ops.scan(
                lambda acc, c: c
                if isinstance(c, int)
                else scroll(acc + 1, 0, self.size),
                -1,
            ),
            ops.flat_map(self._beat_in),
        ).subscribe(observer)

    def start(self, *devices: Bridge):
        def on_error(e):
            logging.exception(e)
            return True

        def subscriber(observer, _):
            def on_next(msg):
                if msg.type in ["clock", "start"]:
                    self.server.send(msg)
                    observer.on_next(0 if msg.type == "start" else None)

            # inport iterable is blocking code, need to use a dedicated thread for a nice sync
            return rx.from_iterable(self.inport, EventLoopScheduler()).subscribe(
                on_next, logging.exception, stop_event.set
            )

        # now the clock can run the common thread
        self.clock = MidiScheduler(subscriber)
        stop_event = threading.Event()
        for dev in (self, *devices):
            dev.subs = rx.merge(*[dev.attach(d) for d in devices]).subscribe(
                on_completed=stop_event.set,
                scheduler=CatchScheduler(self.clock, on_error),
            )
        logging.info("[SEQ] %i devices synced", len(devices))
        return stop_event

    def _bars_in(self, msg):
        self.bars = msg.data

    def _beat_in(self, beat):
        if beat % 24 == 0:
            yield Msg("beat")
            if beat == 0:
                yield Msg("start", self.state, self.bars)
        elif self.size - beat <= 3:  # last 1/32th beat
            yield Msg("end", self.state, self.bars)

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
