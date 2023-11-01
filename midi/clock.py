from reactivex import from_iterable, operators as ops
from reactivex.disposable import Disposable
from reactivex.subject import BehaviorSubject
from reactivex.scheduler import EventLoopScheduler, CurrentThreadScheduler
from midi import InternalMessage
from bridge import Bridge
from utils import clip, t2i


class Metronome(CurrentThreadScheduler, BehaviorSubject):
    def __init__(self, name, *args, **kwargs):
        super(Metronome, self).__init__(*args, **kwargs)
        BehaviorSubject.__init__(self, 2)
        self.message = InternalMessage(name)

    def schedule(self, action, state=None):
        def on_next(val):
            super(Metronome, self).schedule(action, val or state)

        return self.subscribe(on_next)

    def schedule_periodic(self, action):
        return self.subscribe(action)

    def schedule_with(self, device: Bridge):
        return self.schedule(
            lambda _, __: device.to_messages(self.message).subscribe(device.send)
        )


class Sequencer(EventLoopScheduler):
    _bars = 2
    _counter = -1
    _start = Metronome("start")
    _end = Metronome("end")
    _beat = Metronome("beat")

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

    def _bars_in(self, msg):
        self.bars = msg.data

    def _start_in(self, _=None):
        self._start.on_next(self.bars)
        messages = getattr(self, "inport")
        if messages is not None:
            return (
                from_iterable(messages, EventLoopScheduler())
                .pipe(
                    ops.filter(self.is_clock),
                    ops.buffer_with_count(24),
                    ops.scan(lambda acc, _: acc + 1, 0),
                )
                .subscribe(self._beat_in)
            )

    def _beat_in(self, value):
        self._beat.on_next(self.bars)
        _, counter = divmod(value, self.size)
        if counter == 0:
            self._start.on_next(self.bars)
        elif self.size - counter == 1:
            self._end.on_next(self.bars)
