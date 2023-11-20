import mido
from contextlib import contextmanager
from utils import checksum


class TrackSelection(Exception):
    CONTROL_FORBIDDEN_CC = range(16, 24)
    CONTROL_FORBIDDEN_CHECKSUM = sum(CONTROL_FORBIDDEN_CC)  # 156

    def __init__(self, msg: mido.messages.Message, *args: object) -> None:
        super().__init__(*args)
        self.channel = msg.channel  # type: ignore

    @classmethod
    def check(cls, iterable: list[mido.messages.Message]):
        """Target the message list of CC sent on track selection"""
        item, *rest = iterable
        return (
            item is not None
            and item.type == "control_change"  #  type: ignore
            and item.control in TrackSelection.CONTROL_FORBIDDEN_CC  # type: ignore
            and sum(
                map(
                    lambda m: m.control,  # type: ignore
                    [item, *filter(lambda m: m.type == "control_change", rest)],  # type: ignore
                )
            )
            == TrackSelection.CONTROL_FORBIDDEN_CHECKSUM
        )


class MidoMessage(mido.messages.Message):
    type: str

    @property
    def is_after(self):
        return lambda _: False

    def bytes(self):
        return super().bytes()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        return True


class MessageQueue(list[MidoMessage]):
    def __init__(self, iterable=None, types=["control_change", "sysex"]):
        super().__init__()
        self.types = types
        if isinstance(iterable, list):
            if TrackSelection.check(iterable):
                raise TrackSelection(iterable[0])
            for el in iterable:
                self.add(el)

    def __enter__(self):
        while len(self) > 0:
            yield self.pop()

    def __exit__(self, type, value, tr):
        return True

    def pop(self):
        msg = super().pop()
        if msg.type in self.types:
            for el in self:
                if msg.is_after(el):
                    self.remove(el)
        return msg

    def add(self, msg):
        if msg.type in self.types:
            # the last cc/sysex must be at the top of the queue (LIFO)
            super().append(msg)
        else:
            # otherwise keep the original order of events when dequeuing (FIFO)
            self.insert(0, msg)


class MidiMessage(MidoMessage):
    _out_q: MessageQueue = MessageQueue()

    def __init__(self, type, *args, **kwargs):
        super().__init__(type, *args, **kwargs)
        MidiMessage._out_q.add(self)

    @classmethod
    @contextmanager
    def from_mido(cls, messages: list[MidoMessage]):
        yield from MessageQueue(messages)

    @classmethod
    @contextmanager
    def to_mido(cls):
        yield from MidiMessage._out_q


class MidiNote(MidoMessage):
    channel: int
    note: int
    velocity: int

    def __init__(self, channel: int, note: int, value=127):
        state = "on" if value > 0 else "off"
        super(MidiNote, self).__init__(
            "note_" + state,
            channel=channel,
            note=note,
            velocity=127 * value if isinstance(value, bool) else value,
        )


class MidiCC(MidiMessage):
    channel: int
    control: int
    value: int

    def __init__(self, channel: int, control: int, value: int):
        super().__init__(
            "control_change", channel=channel, control=control, value=value
        )

    @property
    def is_after(self):
        def wrapped(msg):
            return (
                msg.type == "control_change"
                and self.channel == msg.channel
                and self.control == msg.control
            )

        return wrapped


class Sysex(MidiMessage):
    data: "list[int]"

    def __init__(self, *args: int, **kwargs):
        super(Sysex, self).__init__("sysex", *args, **kwargs)

    @property
    def is_after(self):
        def wrapped(msg):
            return (
                msg.type == "sysex"
                and self.address == msg.address
                and len(self.body) == len(msg.body)
            )

        return wrapped

    @property
    def address(self):
        return self.data[7:11]

    @property
    def body(self):
        return self.data[11:-1]

    @property
    def checksum(self):
        return self.data[-1]


SYNTH_SYSEX_HEAD = [65, 0, 0, 0, 0, 105]
SYNTH_SYSEX_REQ = [*SYNTH_SYSEX_HEAD, 17]
SYNTH_SYSEX_CMD = [*SYNTH_SYSEX_HEAD, 18]
SYNTH_ADDRESSES = {"common": [0, 1], "patch": [16, 0], "inout": [0, 4]}


class SysexCmd(Sysex):
    def __init__(self, addr: str, data: list[int], *args, **kwargs):
        head = SYNTH_ADDRESSES[addr]
        super(SysexCmd, self).__init__(
            data=[*SYNTH_SYSEX_CMD, *checksum(head, data)], *args, **kwargs
        )


class SysexReq(Sysex):
    def __init__(self, addr: str, data: list[int], *args, **kwargs):
        head = SYNTH_ADDRESSES[addr]
        super(SysexReq, self).__init__(
            data=[*SYNTH_SYSEX_REQ, *checksum(head, data)], *args, **kwargs
        )
