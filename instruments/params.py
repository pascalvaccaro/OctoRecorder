from utils import clip


class Param:
    def __init__(
        self,
        origin: tuple[int, ...],
        macro=None,
        boundaries: tuple[int, int] = (0, 100),
    ):
        self.address, self.offset = origin
        self.min_value, self.max_value = boundaries
        self.macro = macro

    @property
    def request(self):
        if self.offset > 0:
            yield [self.address, 0, 0, 0, self.offset]

    @property
    def origin(self):
        return self.address + min(0, self.offset)

    def from_vel(self, velocity):
        value = velocity / 127 * (self.max_value - self.min_value) + self.min_value
        return clip(value, self.min_value, self.max_value)

    def to_vel(self, value):
        return clip((value - self.min_value) * 128 / self.max_value)

    def send(self, values: "list[int]"):
        return [self.address, *values]

    def receive(self, data: "list[int]"):
        yield [self.macro, self.to_vel(data[self.offset * -(self.offset < 0)])]


class Switch(Param):
    def send(self, values: list[int]):
        value = values[0]
        if value > 0:
            return [self.address, 1, values[0]]
        return [self.address, 0]

    def receive(self, data: list[int]):
        yield [self.macro, self.to_vel(data[1]) * (data[0] == 1)]


class Filter(Param):
    def __init__(
        self,
        origin: tuple[int, ...],
        macro=None,
        boundaries: tuple[int, int] = (0, 100),
    ):
        super().__init__(origin, macro, boundaries)
        self.data_idx = origin[2] or 2

    def from_vel(self, velocity):
        return super().from_vel(velocity) * 2

    def to_vel(self, ftype, value):
        if ftype == 0:
            return clip(64 - value / self.max_value * 64, self.min_value, 64)
        if ftype == 1:
            return clip(value / self.max_value * 64 + 64, 64, 127)

    def send(self, values: "list[int]"):
        return (
            super().send([0, 1, (self.max_value - values[0])])
            if values[0] < self.max_value
            else super().send([1, 1, values[0] - self.max_value])
        )

    def receive(self, data: "list[int]"):
        yield [self.macro, self.to_vel(data[0], data[self.data_idx])]


class LFO(Param):
    shape = 0

    def send(self, values: "list[int]"):
        if values[0] > 0:
            return [self.address, 1, self.shape, values[0]]
        return [self.address, 0]

    def receive(self, data: list[int]):
        self.shape = data[1]
        yield [self.macro, 0 if data[2] <= 100 else self.to_vel(data[2])]


class StepSequencer(Param):
    seq_rates = [115, 112, 110, 109, 108, 107, 106, 106]
    min_values = [[0] * 32] * 3
    sequencers = [
        Param((160, 3)),
        Param((182, 3)),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.targets = [
            Param((self.address + 3, 32), None, (8, 56)),  # pitch
            Param((self.address + 35, 32)),  # cutoff
            Param((self.address + 67, 32)),  # level
        ]

    @property
    def request(self):
        yield from super().request
        yield from self.set_bars()

    def receive(self, data: "list[int]"):
        targets, steps = data[0:3], data[3:]
        for i, target in enumerate(self.targets):
            seq_steps = enumerate(steps[i * target.offset : (i + 1) * target.offset])
            max_values = []
            for j, s in seq_steps:
                if j % 2 == 1:
                    max_values += [target.to_vel(s)]
                else:
                    self.min_values[i][j] = s
            yield [i, targets[i], max_values]

    def get_steps(self, data):
        idx, *steps = list(data)
        all_values = []
        target = self.targets[int(idx)]
        for i, step in enumerate(steps):
            all_values += [self.min_values[idx][i], target.from_vel(step)]
        return [target.address, *all_values]

    def get_seq(self, data):
        return [self.address + data[0], data[1]]

    def set_bars(self, bars=2):
        rate = self.seq_rates[clip(bars, 1, 8) - 1]
        for seq in self.sequencers:
            yield [seq.address, 16, rate]
