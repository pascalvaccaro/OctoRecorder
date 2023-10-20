from typing import MutableSet
from reactivex.subject import BehaviorSubject
from reactivex.abc import DisposableBase
from midi import InternalMessage
from utils import clip, scroll


class Metronome(object):
    def __init__(self, *args, **kwargs):
        super(Metronome, self).__init__(*args, **kwargs)
        self.subs: MutableSet[DisposableBase] = set()
        self.clock = BehaviorSubject(-1)
        self.bars = 2

    def __del__(self):
        for sub in self.subs:
            sub.dispose()

    @property
    def size(self):
        return self.bars * 96 - 1

    @property
    def counter(self):
        return self.clock.value

    def set_bars(self, bars=[2]):
        self.bars = clip(bars[0], 1, 8)

    def _start_in(self, _=None):
        self.clock.on_next(0)
        yield InternalMessage("beat:start", self.bars)

    def _clock_in(self, _=None):
        self.clock.on_next(scroll(self.counter + 1, 0, self.size))
        if self.counter == 0:
            yield InternalMessage("beat:start", self.bars)
        elif self.counter == self.size:
            yield InternalMessage("end", self.bars)
        elif self.counter % 24 == 0:
            yield InternalMessage("beat", self.bars)

    def _stop_in(self, _=None):
        yield InternalMessage("stop", 0)
