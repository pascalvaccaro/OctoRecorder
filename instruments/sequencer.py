from midi.messages import SysexCmd
from .params import Pad
from .messages import InternalMessage, MacroMessage, StepMessage
from utils import clip


class Grid(Pad):
    name = "target"

    def __init__(
        self,
        origin: tuple[int, int],
        macro: int,
        boundaries: tuple[int, int] = (0, 100),
        values=[127, 100, 75, 50, 25],
    ):
        super().__init__(origin, macro, boundaries)
        self.values = values

    def from_vel(self, idx: int, vel: int):
        for i, value in enumerate(self.values):
            if idx == i:
                return super().from_vel(value)
        return super().from_vel(vel)

    def to_vel(self, val: int):
        vel = super().to_vel(val)
        return [127 * (vel >= v) for v in self.values]


class Bar(Pad):
    name = "seq"
    values = [115, 112, 110, 109, 108, 107, 106, 106]

    @property
    def select_message(self):
        return lambda msg: msg.type in ["bars", "length"]

    def from_vel(self, idx: int):
        for i, value in enumerate(self.values):
            if idx == i:
                return value
        return self.values[0]

    def from_internal(self, idx: int, msg: InternalMessage):
        if msg.type == "bars":
            value = clip(msg.data[1], 1, len(self.values)) - 1
            yield SysexCmd("patch", [idx, self.address + 3, self.from_vel(value)])
        elif msg.type == "length":
            value = msg.data[2]
            yield SysexCmd("patch", [idx, self.address + 2 * (value > 0), value])


class Sequencer(Pad):
    name = "steps"

    def __init__(self, origin: tuple[int, int], macro: int, *args: Pad):
        super().__init__(origin, macro)
        self.params = [param for param in args if isinstance(param, Grid)]
        self.sequencers = [seq for seq in args if isinstance(seq, Bar)]

    def to_internal(self, idx: int, data: "list[int]"):
        params, all_steps = data[0:3], data[3:99]
        for i, param in enumerate(self.params):
            values = all_steps[i * 32 : (i + 1) * 32]
            steps = [
                param.to_vel(val)
                for j, val in enumerate(values)
                if divmod(j, 2)[1] == 1
            ]
            yield StepMessage(idx, self.macro, param.macro, *steps)
            yield MacroMessage(param.name, idx, param.macro, params[i])
        for i, seq in enumerate(self.sequencers):
            # off=0 or length=1~16
            value = 0 if data[99 + i * 22] == 0 else data[101 + i * 22]
            yield MacroMessage(seq.name, idx, seq.macro, value)

    def from_internal(self, idx: int, msg: MacroMessage):
        if msg.type == Sequencer.name:
            for param in self.params:
                if param.macro == msg.value:
                    row, col, val = list(msg.data[3:])
                    address = param.address + col + 1  # +1 to update max value only
                    yield SysexCmd("patch", [idx, address, param.from_vel(row, val)])
        elif msg.type == Grid.name:
            for i, param in enumerate(self.params):
                if param.macro == msg.macro:
                    yield SysexCmd("patch", [idx, self.address + i, msg.value])
        elif msg.type in ["length", "bars"]:
            for target in self.sequencers:
                if target.macro == msg.macro or msg.type == "bars":
                    yield from target.from_internal(idx, msg)
        else:
            raise Exception("Wrong type of message %s", msg.type)
