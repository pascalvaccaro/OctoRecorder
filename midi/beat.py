from reactivex.subject import BehaviorSubject
from reactivex.scheduler import EventLoopScheduler
from reactivex.disposable import SingleAssignmentDisposable, Disposable, CompositeDisposable
from threading import Timer
from midi import InternalMessage
from utils import clip, scroll, t2i

class ClockScheduler(EventLoopScheduler):
    def __init__(self, timeout: float, *args, **kwargs):
        super(ClockScheduler, self).__init__(*args, **kwargs)
        self.timeout = timeout

    def schedule(self, action, state=None):
        sad = SingleAssignmentDisposable()

        def interval() -> None:
            sad.disposable = self.invoke_action(action, state)

        timer = Timer(self.timeout, interval)
        timer.daemon = True
        timer.start()

        def dispose() -> None:
            timer.cancel()

        return CompositeDisposable(sad, Disposable(dispose))

class Metronome(object):
    _bars = 2
    def __init__(self, *args, **kwargs):
        super(Metronome, self).__init__(*args, **kwargs)
        self.clock = BehaviorSubject(-1)

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
        return self.clock.value

    def _bars_in(self, msg: InternalMessage):
        self.bars = msg.data

    def _start_in(self, _=None):
        self.clock.on_next(0)
        yield InternalMessage("start", self.bars)

    def _clock_in(self, _=None):
        self.clock.on_next(scroll(self.counter + 1, 0, self.size))
        counter = int(self.counter)
        if counter == 0:
            yield InternalMessage("start", self.bars)
        elif counter == self.size:
            yield InternalMessage("end", self.bars)
        elif counter % 24 == 0:
            yield InternalMessage("beat", self.bars)

    def _stop_in(self, _=None):
        yield InternalMessage("stop", 0)
