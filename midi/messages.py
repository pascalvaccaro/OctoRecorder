import mido
import logging
from typing import List, Optional, TypeVar

SYNTH_SYSEX_HEAD = [65, 0, 0, 0, 0, 105]
SYNTH_SYSEX_REQ = [*SYNTH_SYSEX_HEAD, 17]
SYNTH_SYSEX_CMD = [*SYNTH_SYSEX_HEAD, 18]
SYNTH_ADDRESSES = {"common": [0, 1], "patch": [16, 0], "inout": [0, 4]}

CONTROL_FORBIDDEN_CC = range(16, 24)
CONTROL_FORBIDDEN_CHECKSUM = sum(CONTROL_FORBIDDEN_CC)  # 156


def checksum(addr, body=[]):
    head = SYNTH_ADDRESSES[addr]
    try:
        result = 128 - sum(x if x is not None else 0 for x in [*head, *body]) % 128
        return [*head, *body, 0 if result == 128 else result]
    except Exception as e:
        logging.warning("Failed checksum", e)
        return [*head, *body, 0]


class MidiMessage(mido.messages.Message):
    type: str

    @property
    def is_after(self):
        return lambda _: False

    def bytes(self):
        return super().bytes()


class Sysex(MidiMessage):
    data: "list[int]"

    def __init__(self, type, addr, data, *args, **kwargs):
        dest = SYNTH_SYSEX_REQ if type == "REQ" else SYNTH_SYSEX_CMD
        super(Sysex, self).__init__(
            "sysex", data=[*dest, *checksum(addr, data)], *args, **kwargs
        )

    @property
    def is_after(self):
        def wrapped(msg):
            return (
                isinstance(msg, Sysex)
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


class SysexCmd(Sysex):
    def __init__(self, *args, **kwargs):
        super(SysexCmd, self).__init__("CMD", *args, **kwargs)


class SysexReq(Sysex):
    def __init__(self, *args, **kwargs):
        super(SysexReq, self).__init__("REQ", *args, **kwargs)


class MidiNote(MidiMessage):
    channel: int
    note: int
    velocity: int

    def __init__(self, channel, note, value=127):
        state = "on" if value > 0 else "off"
        super(MidiNote, self).__init__(
            "note_" + state,
            channel=channel,
            note=note,
            velocity=value,
        )


class MidiCC(MidiMessage):
    channel: int
    control: int
    value: int

    def __init__(self, channel, control, value):
        super(MidiCC, self).__init__(
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


class InternalMessage(object):
    def __init__(self, type: str, *args):
        super(InternalMessage, self).__init__()
        self.type = type
        self.data = tuple(args)

    def dict(self):
        return list(self.data)

    def is_cc(self):
        return False

    def bytes(self):
        return list(self.data)
    
    @classmethod
    def to_internal_message(cls, msg: Optional[MidiMessage]):
        if msg is None:
            return
        if msg.type == "sysex":
            return InternalMessage(msg.type, *msg.bytes()[1:-1])
        elif msg.type == "program_change":
            return InternalMessage(msg.type, msg.channel, msg.program) # type: ignore
        elif msg.type == "stop":
            return InternalMessage(msg.type)

T = TypeVar("T", MidiMessage, MidiNote, MidiCC, Sysex)

class QMidiMessage(List[T]):
    def __init__(self, iterable=None):
        super().__init__()
        if isinstance(iterable, list):
            for el in iterable:
                self.add(el)

    def pop(self):
        msg = super().pop()
        if isinstance(msg, (Sysex, MidiCC)):
            for el in self:
                if msg.is_after(el):
                    self.remove(el)

        return msg

    def add(self, msg: T):
        if msg.type in ["control_change", "sysex"]:
            # the last cc/sysex must be at the top of the queue (LIFO)
            super().append(msg)
        else:
            # otherwise keep the original order of events when dequeuing (FIFO)
            self.insert(0, msg)


def is_track_selection(item, upcoming: QMidiMessage):
    """Target the message list of CC sent on track selection"""
    return (
        item.control in CONTROL_FORBIDDEN_CC
        and sum(
            map(
                lambda m: m.control,
                [item, *filter(lambda m: m.type == "control_change", upcoming)],
            )
        )
        == CONTROL_FORBIDDEN_CHECKSUM
    )
