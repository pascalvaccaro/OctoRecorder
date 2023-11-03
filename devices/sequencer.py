from reactivex import from_iterable, operators as ops
from reactivex.scheduler import EventLoopScheduler
from midi import InternalMessage as Msg
from bridge import Bridge
from utils import clip, t2i, scroll


class Sequencer(Bridge):
    _bars = 2

    def __init__(self, inport):
        super().__init__("Sequencer")
        self.inport = inport

    @property
    def external_message(self):
        return lambda msg: msg.type in ["bars"]

    @property
    def bars(self):
        return self._bars

    @bars.setter
    def bars(self, value):
        self._bars = clip(t2i(value), 1, 8)

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
            ops.buffer_with_count(24),
            ops.merge(messages.pipe(ops.filter(self.is_start))),
            ops.scan(
                lambda a, c: scroll(a + 1, 9, self.size - 1)
                if isinstance(c, list)
                else 0,
                -1,
            ),
            ops.flat_map(self._beat_in),
        ).subscribe(self.send, obs.on_error, obs.on_completed, scheduler=sched)

    def _bars_in(self, msg):
        self.bars = msg.data

    def _beat_in(self, beat):
        yield Msg("beat", self.bars)
        if beat == 0:
            yield Msg("start", self.bars)
        elif self.size - beat == 1:
            yield Msg("end", self.bars)
