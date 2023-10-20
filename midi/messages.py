import mido
import logging

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
    def __init__(self, channel, note, value=127):
        state = "on" if value > 0 else "off"
        super(MidiNote, self).__init__(
            "note_" + state,
            channel=channel,
            note=note,
            velocity=value,
        )


class MidiCC(mido.messages.Message):
    def __init__(self, channel, control, value):
        super(MidiCC, self).__init__(
            "control_change", channel=channel, control=control, value=value
        )


class InternalMessage(object):
    def __init__(self, command: str, *args):
        super(InternalMessage, self).__init__()
        self.command = command
        self.values = tuple(map(lambda x: int(x), args))
