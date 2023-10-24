from reactivex.subject import BehaviorSubject
from midi import InternalMessage
from utils import clip, scroll


class Metronome(object):
    def __init__(self, *args, **kwargs):
        super(Metronome, self).__init__(*args, **kwargs)
        self.clock = BehaviorSubject(-1)
        self.bars = 2

    @property
    def size(self):
        return self.bars * 96 - 1

    @property
    def counter(self):
        return self.clock.value

    def _bars_in(self, msg: InternalMessage):
        self.bars = clip(msg.data[0], 1, 8)

    def _start_in(self, _=None):
        self.clock.on_next(0)
        yield InternalMessage("start", self.bars)

    def _clock_in(self, _=None):
        self.clock.on_next(scroll(self.counter + 1, 0, self.size))
        if self.counter == 0:
            yield InternalMessage("start", self.bars)
        elif self.counter == self.size:
            yield InternalMessage("end", self.bars)
        elif self.counter % 24 == 0:
            yield InternalMessage("beat", self.bars)

    def _stop_in(self, _=None):
        yield InternalMessage("stop", 0)
