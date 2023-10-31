import mido
import logging

SYNTH_SYSEX_HEAD = [65, 0, 0, 0, 0, 105]
SYNTH_SYSEX_REQ = [*SYNTH_SYSEX_HEAD, 17]
SYNTH_SYSEX_CMD = [*SYNTH_SYSEX_HEAD, 18]
SYNTH_ADDRESSES = {"common": [0, 1], "patch": [16, 0]}

CONTROL_FORBIDDEN_CC = range(16, 24)
CONTROL_FORBIDDEN_CHECKSUM = sum(CONTROL_FORBIDDEN_CC)


def clean_messages(item, messages=[]):
    if item.type == "control_change":
        cc = filter(lambda m: m.type == "control_change", messages)
        # Block CC messages sent on track selection
        if item.control in CONTROL_FORBIDDEN_CC:
            if sum(map(lambda m: m.control, cc)) == CONTROL_FORBIDDEN_CHECKSUM:
                item.channel = item.channel
                return list(filter(lambda m: m.type != "control_change", messages))
        # Buffer identical CC messages
        return list(filter(lambda m: m.control != item.control, cc))
    return messages


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


class Sysex(MidiMessage):
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


class InternalMessage(object):
    def __init__(self, type: str, *args):
        super(InternalMessage, self).__init__()
        self.type = type
        self.data = tuple(args)

    def dict(self):
        return list(self.data)

    def is_cc(self):
        return False
