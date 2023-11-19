from .messages import InternalMessage, MacroMessage
from utils import clip


class Param:
    name: str

    def __init__(
        self,
        origin: tuple[int, int],
        macro: int,
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

    @property
    def select_message(self):
        return lambda msg: isinstance(msg, MacroMessage) and msg.macro == self.macro

    def from_vel(self, velocity):
        value = velocity / 127 * (self.max_value - self.min_value) + self.min_value
        return clip(value, self.min_value, self.max_value)

    def to_vel(self, value):
        return clip((value - self.min_value) / (self.max_value - self.min_value) * 128)

    def from_internal(self, msg: InternalMessage):
        values = [self.from_vel(d) for d in msg.data[2:]]
        return [self.address, *values]

    def to_internal(self, idx: int, data: "list[int]"):
        yield [idx, self.macro, self.to_vel(data[abs(min(0, self.offset))])]


class Pad(Param):
    pass


class Pot(Param):
    name = "synth"

    def __init__(
        self,
        origin: tuple[int, int],
        macro: int,
        boundaries: tuple[int, int] = (0, 100),
    ):
        super().__init__(origin, macro + 128, boundaries)

    def to_internal(self, idx: int, data: "list[int]"):
        for values in super().to_internal(idx, data):
            yield MacroMessage(self.name, *values)


class Switch(Pot):
    def from_internal(self, msg: MacroMessage):
        value = self.from_vel(msg.data[2])
        if value > self.min_value:
            return [self.address, 1, value]
        return [self.address, 0]

    def to_internal(self, idx: int, data: list[int]):
        value = self.to_vel(data[1]) * (data[0] == 1)
        yield MacroMessage(self.name, idx, self.macro, value)


class LFO(Pot):
    shape = 0

    def from_internal(self, msg: MacroMessage):
        value = self.from_vel(msg.data[2])
        if value > self.min_value:
            return [self.address, 1, self.shape, value]
        return [self.address, 0]

    def to_internal(self, idx: int, data: list[int]):
        self.shape = data[1]
        value = 0 if data[2] <= 100 else self.to_vel(data[2])
        yield MacroMessage(self.name, idx, self.macro, value)


class Bipolar(Pot):
    def __init__(
        self,
        data_origin: tuple[int, ...],
        macro: int,
        boundaries: tuple[int, int] = (0, 100),
    ):
        origin = data_origin[0], data_origin[1]
        super().__init__(origin, macro, boundaries)
        self.data_idx = data_origin[2] if len(data_origin) == 3 else 2

    def from_vel(self, velocity):
        value = int(velocity * (self.max_value - self.min_value) / 127) + self.min_value
        return clip(value, self.min_value, self.max_value) * 2

    def to_vel(self, ftype, value):
        if ftype == 0:
            return clip(64 - value / self.max_value * 64, self.min_value, 64)
        if ftype == 1:
            return clip(value / self.max_value * 64 + 64, 64, 127)

    def from_internal(self, msg: MacroMessage):
        value = self.from_vel(msg.data[2])
        values = (
            [0, 1, (self.max_value - value)]
            if value < self.max_value
            else [1, 1, value - self.max_value]
        )
        return [self.address, *values]

    def to_internal(self, idx: int, data: "list[int]"):
        value = self.to_vel(data[0], data[self.data_idx])
        if value is not None:
            yield MacroMessage(self.name, idx, self.macro, value)
