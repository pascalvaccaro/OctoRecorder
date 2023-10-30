from reactivex import from_iterable, operators as ops
from reactivex.subject import BehaviorSubject
from reactivex.scheduler import EventLoopScheduler
from utils import clip, scroll, t2i


start = BehaviorSubject(0)
end = BehaviorSubject(0)
beat = BehaviorSubject(0)
loop = EventLoopScheduler()
clock = EventLoopScheduler()


class Metronome(object):
    _bars = 2
    _counter = -1

    @property
    def bars(self):
        return self._bars

    @bars.setter
    def bars(self, value):
        self._bars = clip(t2i(value), 1, 8)

    @property
    def size(self):
        return self.bars * 96 - 1

    @property
    def counter(self):
        return self._counter

    @counter.setter
    def counter(self, value):
        self._counter = scroll(value, 0, self.size)

    @property
    def is_clock(self):
        return lambda msg: msg.type == "clock"

    def start_clock(self, messages):
        return (
            from_iterable(messages, clock)
            .pipe(ops.filter(lambda msg: msg.type == "clock"))  # type: ignore
            .subscribe(self._clock_in)
        )

    def _bars_in(self, msg):
        self.bars = msg.data

    def _start_in(self, _=None):
        self.counter = 0
        start.on_next(self.bars)

    def _clock_in(self, _):
        self.counter += 1
        subject = (
            start
            if self.counter == 0
            else end
            if self.counter == self.size
            else beat
            if self.counter % 24 == 0
            else None
        )
        if subject is not None:
            subject.on_next(self.bars)
