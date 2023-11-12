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

    def send(self, values):
        return [self.address, *values]

    def receive(self, data):
        yield [self.macro, self.to_vel(data[abs(min(0, self.offset))])]


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.targets = [
            Param((self.address + 3, 32), None, (8, 56)),  # pitch
            Param((self.address + 35, 32)),  # cutoff
            Param((self.address + 67, 32)),  # level
        ]
        self.sequencers = [
            Param((self.address + 99, 4), None, (0, 118)),
            Param((self.address + 121, 4), None, (0, 118)),
        ]

    def _steps_out(self, data: "list[int]"):
        targets, all_steps = data[0:3], data[3:99]
        for t_idx, target in enumerate(self.targets):
            steps = all_steps[t_idx * target.offset : (t_idx + 1) * target.offset]
            max_values = []
            for s, val in enumerate(steps):
                if s % 2 == 1:
                    max_values += [target.to_vel(val)]
                else:
                    self.min_values[t_idx][s] = val
            yield [t_idx, targets[t_idx], max_values]

    def _length_out(self, data: "list[int]"):
        seq_data = data[99:]
        status = max(seq_data[0], seq_data[22])
        length = max(seq_data[2], seq_data[24])
        yield [status, length]

    def get_steps(self, data):
        idx, *steps = list(data)
        all_values = []
        target = self.targets[int(idx)]
        for i, val in enumerate(steps):
            all_values += [self.min_values[idx][i], target.from_vel(val)]
        return [target.address, *all_values]

    def get_target(self, data):
        target_idx, value = data
        target = self.targets[int(target_idx)]
        return [target.address, value]

    def to_bars(self, bars=2):
        rate = self.seq_rates[clip(bars, 1, 8) - 1]
        for seq in self.sequencers:
            yield [seq.address + 3, rate]

    def to_status(self, data):
        for seq in self.sequencers:
            yield [seq.address, data[0]]

    def to_length(self, data):
        for seq in self.sequencers:
            yield [seq.address + 2, data[0]]
