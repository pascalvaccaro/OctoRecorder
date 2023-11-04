from reactivex import from_iterable, operators as ops
from reactivex.scheduler import EventLoopScheduler
from midi import InternalMessage as Msg, MidiDevice
from bridge import Bridge
from utils import clip, t2i, scroll


class Sequencer(Bridge):
    _bars = 2
    _playing = False
    _recording = False

    def __init__(self, device: MidiDevice):
        super().__init__("Sequencer")
        self.inport = device.inport
        self.server = device.server

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
        return self.bars * 4

    @property
    def is_clock(self):
        return lambda msg: msg.type == "clock"

    @property
    def is_start(self):
        return lambda msg: msg.type == "start"

    def subscriber(self, obs, sched):
        # inport iterable is blocking code, need to use up a single thread for a nice sync
        clock, messages = from_iterable(self.inport, EventLoopScheduler()).pipe(
            ops.partition(self.is_clock)
        )
        # now the clock can run on the same thread as other devices
        return clock.pipe(
            ops.do_action(self.server.send),
            ops.buffer_with_count(24),
            ops.merge(messages.pipe(ops.filter(self.is_start))),
            ops.scan(
                lambda a, c: scroll(a + 1, 0, self.size - 1)
                if isinstance(c, list)
                else 0,
                -1,
            ),
            ops.flat_map(self._beat_in),
        ).subscribe(self.send, obs.on_error, obs.on_completed, scheduler=sched)

    def _bars_in(self, msg):
        self.bars = msg.data

    def _beat_in(self, beat):
        yield Msg("beat")
        if beat == 0:
            yield Msg("start", self.state, self.bars)
        elif self.size - beat == 1:
            yield Msg("end", self.bars)

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
