from midi import MidiCC, SysexCmd, SysexReq, MidiDevice
from devices import APC40
from utils import clip, scroll

class SY1000(MidiDevice):
    def __init__(self, *args, **kwargs):
        super(SY1000, self).__init__(*args, **kwargs)
        self._get_strings()
        self.patch = 0

    def start(self):
        MidiDevice.start(self)
        if isinstance(self.external, APC40):
            self.on("beat", self.external.blink(63))
            self.on("start", self.external.blink(65))
            self.external.on("bars", self.set_bars)
            self.external.on("patch", self._set_patch)
            self.external.on("strings", self._set_strings)

    def receive(self, msg):
        if msg.type == "clock":
            self._clock_in()
        elif msg.type == "start":
            self._start_in()
        elif msg.type == "stop":
            self._stop_in()
        elif msg.type == "sysex":
            self._sysex_in(msg)
        elif msg.type == "program_change":
            self._program_change_in(msg)

    def _sysex_in(self, msg):
        if msg.data[0] != 65:
            return
        data = msg.data[6:]
        if data[0] != 18:
            return
        if data[3] == 0:
            self.patch = int("0x" + "".join(map(lambda a: hex(a)[2:], data[5:9])), 16)
        else:
            for i, d in enumerate(data[5:-1]):
                channel = divmod(i, 6)[1] if data[4] != 2 else 8
                control = clip((data[3] + 155) / 11 + (4 if i >= 6 else 0))
                value = clip(d / 100 * 127)
                self.external.send(MidiCC(channel, control, value))

    def _program_change_in(self, _):
        self._get_patch()

    def _get_patch(self):
        self.send(SysexReq("common", [0, 0, 0, 0, 0, 4]))
        self._get_strings()

    def _set_patch(self, values):
        offset = values[0]
        self.patch = scroll(self.patch + offset, 0, 399)
        data = map(lambda x: int(x, 16), list(hex(self.patch)[2:].zfill(4)))
        self.send(SysexCmd("common", [0, 0, *data]))

    def _get_strings(self, instrs=[1, 2, 3]):
        for i in instrs:
            instr = 11 * i + 10
            self.send(SysexReq("patch", [instr, 2, 0, 0, 0, 1]))
            self.send(SysexReq("patch", [instr, 6, 0, 0, 12]))

    def _set_strings(self, values):
        channel, control, value = values
        instr = (
            21
            if control == 16 or control == 20
            else 32
            if control == 17 or control == 21
            else 18
        )
        string = channel + (6 if control < 20 else 12)
        value = clip(value / 127 * 100)

        if channel < 8:
            self.send(SysexCmd("patch", [instr, string, value]))
        elif channel == 8:
            if control < 19:
                self.send(SysexCmd("patch", [instr, 6, *[value] * 6]))
            elif control < 23:
                for instr in [21, 32, 43]:
                    self.send(SysexCmd("patch", [instr, 12, *[value] * 6]))
