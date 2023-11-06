from midi.messages import MidiNote, MidiCC, InternalMessage as Msg
from midi import MidiDevice, make_notes


class APC40(MidiDevice):
    blinks: "set[int]" = set([63])
    targets: "set[int]" = set()
    steps = [[0] * 8] * 6

    @property
    def init_actions(self):
        for ch in range(0, 8):
            yield MidiCC(ch, 7, 127)
            for ctl in range(16, 20):
                yield MidiCC(ch, ctl, 127)
            for ctl in [*range(20, 24), *range(48, 56)]:
                yield MidiCC(ch, ctl, 64)
            for note in [48, 49]:
                yield MidiNote(ch, note)
        yield MidiCC(0, 14, 127)
        yield MidiCC(0, 15, 64)
        for ctl in range(16, 20):
            yield MidiCC(8, ctl, 127)
        for ctl in range(20, 24):
            yield MidiCC(8, ctl, 64)
        yield from self._note_in(MidiNote(1, 50))

    @property
    def select_message(self):
        return lambda msg: msg.type in ["control_change", "note_on", "note_off"]

    @property
    def external_message(self):
        return lambda msg: msg.type in [
            "strings",
            "pitch",
            "cutoff",
            "level",
            "beat",
            "start",
        ]

    def _control_change_in(self, msg: MidiCC):
        channel = msg.channel
        control = msg.control
        value = msg.value
        if control == 7:
            yield Msg("volume", channel, value)
        elif control == 14:
            for ch in range(0, 8):
                yield Msg("volume", ch, value)
        elif control == 15:
            yield Msg("xfader", value)
        elif control == 19 or control == 23:
            for ctl in range(control - 3, control):
                yield MidiCC(channel, ctl, value)
                msg.control = ctl
                yield from self._control_change_in(msg)
        elif control in range(16, 23):
            self.channel = channel
            yield Msg("strings", channel, control, value)
            if channel == 8:
                for ch in range(0, 8):
                    yield MidiCC(ch, control, value)
        elif control == 64:
            yield Msg("toggle", None)
        elif control == 67:
            yield Msg("stop", None)

    def _note_on_in(self, msg: MidiNote):
        note = msg.note
        if note in range(52, 58):
            if self.steps[note - 52][msg.channel] == 0:
                self.steps[note - 52][msg.channel] = 1
            else:
                self.steps[note - 52][msg.channel] = 0
            if note in [53, 54]:
                steps = map(lambda x: min(32, x * 44), [*self.steps[1], *self.steps[2]])
                param = 0
            elif note in [55, 56]:
                steps = map(lambda x: min(30, x * 80), [*self.steps[3], *self.steps[4]])
                param = 1
            else:
                steps = map(lambda x: x * 100, [*self.steps[5], *self.steps[0]])
                param = 2
            yield Msg("steps", param, list(steps))
        elif note == 64:
            isintarget = note in self.targets
            if isintarget:
                self.targets.remove(note)
            else:
                self.targets.add(note)
            yield Msg("overdub", not isintarget)
        elif note in range(81, 87):
            param = 0 if note in [82, 83] else 1 if note in [84, 85] else 2
            if note in self.targets:
                self.targets.remove(note)
                target = 0
            else:
                self.targets.add(note)
                target = note % 2 or 2
            yield Msg("target", param, target)
        elif note == 91:
            self.blinks.discard(62)
            yield Msg("play")
            for ch in range(0, 9):
                yield MidiNote(ch, 62)
        elif note == 92:
            self.blinks.discard(62)
            yield Msg("stop")
            for ch in range(0, 9):
                yield MidiNote(ch, 62, 0)
        elif note == 93:
            self.blinks.add(62)
            yield Msg("rec")
        elif note == 94:  # up
            yield Msg("patch", -1)
        elif note == 95:  # down
            yield Msg("patch", 1)
        elif note == 96:  # right
            yield Msg("patch", 4)
        elif note == 97:  # left
            yield Msg("patch", -4)
        elif note == 98:
            yield self.shutdown()
        elif note == 100:
            yield Msg("phrase", 1)
        elif note == 101:
            yield Msg("phrase", -1)
        yield from self._note_in(msg)

    def _note_in(self, msg: MidiNote):
        channel = msg.channel
        note = msg.note
        value = msg.velocity
        if note == 48 or note == 49:
            if channel == 7:
                for ch in range(0, 7):
                    yield MidiNote(ch, note, value)
        elif note == 50:
            bars = channel + 1
            yield Msg("bars", bars)
            for ch in range(0, bars):
                yield MidiNote(ch, 50)
            for ch in range(bars, 8):
                yield MidiNote(ch, 50, 0)

    def _note_off_in(self, msg: MidiNote):
        note = msg.note
        if note in range(52, 58):
            if self.steps[note - 52][msg.channel] == 1:
                yield MidiNote(msg.channel, note)
        elif note in range(81, 87):
            if note in self.targets:
                yield MidiNote(0, note)
                opposite = (
                    86
                    if note == 81
                    else 81
                    if note == 86
                    else note + (1 if note % 2 == 1 else -1)
                )
                yield MidiNote(0, opposite, 0)
        elif note == 64:
            if note in self.targets:
                yield MidiNote(self.channel, note)
        yield from self._note_in(msg)

    def _strings_in(self, msg: Msg):
        yield MidiCC(*msg.data)

    def _beat_in(self, _=None):
        return make_notes(self.channel, [*self.blinks])

    def _start_in(self, _):
        self.blinks.add(65)
        res = self._beat_in()
        self.blinks.discard(65)
        return res

    def _pitch_in(self, msg: Msg):
        target, steps = msg.data
        for i, step in enumerate(steps):
            channel = divmod(i, 8)[1]
            note = 53 if i < 8 else 54
            value = 0 if step - 32 <= 0 else 127
            yield MidiNote(channel, note, value)
        yield from self._target_in(target, 82, 83)

    def _cutoff_in(self, msg: Msg):
        target, steps = msg.data
        for i, step in enumerate(steps):
            channel = divmod(i, 8)[1]
            note = 55 if i < 8 else 56
            value = 0 if step <= 30 else 127
            yield MidiNote(channel, note, value)
        yield from self._target_in(target, 84, 85)

    def _level_in(self, msg: Msg):
        target, steps = msg.data
        for i, step in enumerate(steps):
            channel = divmod(i, 8)[1]
            note = 57 if i < 8 else 52
            value = 0 if step <= 20 else 127
            yield MidiNote(channel, note, value)
        yield from self._target_in(target, 86, 81)

    def _target_in(self, target, one, two):
        yield MidiNote(0, one, 127 * (target == 1))
        yield MidiNote(0, two, 127 * (target == 2))
