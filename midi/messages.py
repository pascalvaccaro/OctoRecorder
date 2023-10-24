from typing import Union
from reactivex import from_iterable, scheduler as sch
from reactivex.typing import ScheduledAction, _TState
from reactivex.abc import DisposableBase
from reactivex.disposable import Disposable
import mido
import logging
from datetime import datetime, timedelta

SYNTH_SYSEX_HEAD = [65, 0, 0, 0, 0, 105]
SYNTH_SYSEX_REQ = [*SYNTH_SYSEX_HEAD, 17]
SYNTH_SYSEX_CMD = [*SYNTH_SYSEX_HEAD, 18]
SYNTH_ADDRESSES = {"common": [0, 1], "patch": [16, 0]}


def checksum(addr, body=[]):
    head = SYNTH_ADDRESSES[addr]
    try:
        result = 128 - sum(x if x is not None else 0 for x in [*head, *body]) % 128
        return [*head, *body, 0 if result == 128 else result]
    except Exception as e:
        logging.warning("Failed checksum", e)
        return [*head, *body, 0]


class Sysex(mido.messages.Message):
    data: "list[int]"

    def __init__(self, type, addr, data, *args, **kwargs):
        dest = SYNTH_SYSEX_REQ if type == "REQ" else SYNTH_SYSEX_CMD
        super(Sysex, self).__init__(
            "sysex", data=[*dest, *checksum(addr, data)], *args, **kwargs
        )


class SysexCmd(Sysex):
    def __init__(self, *args, **kwargs):
        super(SysexCmd, self).__init__("CMD", *args, **kwargs)


class SysexReq(Sysex):
    def __init__(self, *args, **kwargs):
        super(SysexReq, self).__init__("REQ", *args, **kwargs)


class MidiNote(mido.messages.Message):
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


class MidiCC(mido.messages.Message):
    channel: int
    control: int
    value: int

    def __init__(self, channel, control, value):
        super(MidiCC, self).__init__(
            "control_change", channel=channel, control=control, value=value
        )


class InternalMessage(object):
    def __init__(self, type: str, *args):
        super(InternalMessage, self).__init__()
        self.type = type
        self.data = tuple(args)

    def dict(self):
        return list(self.data)

    def is_cc(self):
        return False


class BottleNeckScheduler(sch.EventLoopScheduler):
    def __init__(self, timeout=0.0, *args, **kwargs):
        self.timeout = timedelta(seconds=timeout)
        self.last = datetime.now()
        super(BottleNeckScheduler, self).__init__(*args, **kwargs)

    def schedule(
        self, action: ScheduledAction[Sysex], state: Union[Sysex, None] = None
    ) -> DisposableBase:
        if datetime.now() - self.last < self.timeout:
            return self.schedule_relative(self.timeout, action, state)
        self.last = datetime.now()
        return super(BottleNeckScheduler, self).schedule(action, state)


def throttle(timeout: float):
    scheduler = BottleNeckScheduler(timeout)
    return lambda func: lambda *args, **kwargs: from_iterable(
        func(*args, **kwargs), scheduler
    )

