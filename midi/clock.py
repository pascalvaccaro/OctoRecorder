from reactivex import from_iterable, operators as ops
from reactivex.subject import BehaviorSubject
from reactivex.scheduler import EventLoopScheduler, CurrentThreadScheduler
from midi import InternalMessage
from utils import clip, scroll, t2i, Bridge


class ClockScheduler(CurrentThreadScheduler):
    def __init__(self, name, *args, **kwargs):
        super(ClockScheduler, self).__init__(*args, **kwargs)
        self.name = InternalMessage(name)
        self._signal = BehaviorSubject(2)

    @property
    def signal(self):
        return self._signal

    @signal.setter
    def signal(self, value):
        self._signal.on_next(value)

    def schedule(self, action, state=None):
        def on_next(val):
            super(ClockScheduler, self).schedule(action, val or state)

        return self.signal.subscribe(on_next)

    def sync(self, device: Bridge):
        return self.schedule(
            lambda _, __: device.to_messages(self.name).subscribe(device.send)
        )

    def schedule_periodic(self, action):
        return self.signal.subscribe(action)


start = ClockScheduler("start")
end = ClockScheduler("end")
beat = ClockScheduler("beat")
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
            .pipe(ops.filter(self.is_clock))
            .subscribe(self._clock_in)
        )

    def _bars_in(self, msg):
        self.bars = msg.data

    def _start_in(self, _=None):
        self.counter = 0
        start.signal = self.bars

    def _clock_in(self, _):
        self.counter += 1
        if self.counter == 0:
            start.signal = self.bars
        elif self.counter == self.size:
            end.signal = self.bars
        elif self.counter % 24 == 0:
            beat.signal = self.bars
