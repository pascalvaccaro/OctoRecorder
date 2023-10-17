from reactivex.subject import BehaviorSubject
from reactivex import operators as ops
from reactivex.scheduler import CurrentThreadScheduler
from midi import InternalMessage
from utils import clip, scroll

class Metronome(BehaviorSubject[InternalMessage]):
    def __init__(self, *args, **kwargs):
        super(Metronome, self).__init__(*args, **kwargs)
        self.clock = BehaviorSubject(-1)
        self.bars = 2
        self.tempo = 120
        current_thread = CurrentThreadScheduler()
        self.sub = self.clock.pipe(
            ops.filter(lambda x: x == 0 or x % 24 == 0),
            ops.time_interval(),
            ops.map(lambda t: round(t.interval.microseconds / 1e6, 3)),
            ops.map(lambda t: int(t * 240)),
            ops.distinct_until_changed(),
        ).subscribe(self.set_tempo, scheduler=current_thread)

    def __del__(self):
        self.sub.dispose()

    @property
    def size(self):
        return self.bars * 96

    @property
    def counter(self):
        return self.clock.value

    def set_tempo(self, tempo=120):
        print("tempo", tempo)
        # self.tempo = clip(tempo, 40, 240)

    def set_bars(self, bars=[2]):
        self.bars = clip(bars[0], 1, 8)

    def _start_in(self):
        self.clock.on_next(0)
        return InternalMessage("beat:start", self.tempo, self.bars)

    def _clock_in(self, _=None):
        self.clock.on_next(scroll(self.counter + 1, 0, self.size))
        clock = self.counter
        if clock == 0:
            return InternalMessage("beat:start", self.tempo, self.bars)
        elif clock == self.size:
            return InternalMessage("end", self.tempo, self.bars)
        elif clock % 24 == 0:
            return InternalMessage("beat", self.tempo)

    def _stop_in(self):
        return InternalMessage("stop", 0)

