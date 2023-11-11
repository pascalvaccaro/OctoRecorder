from midi.messages import MidiNote, MidiCC, InternalMessage as Msg
from midi import MidiDevice, make_notes
from instruments import Layers
from utils import clip


class APC40(MidiDevice):
    blinks: "set[int]" = set([63])
    layers = Layers(10, 21, 32, 43)

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
        yield from self.layers.request

    @property
    def select_message(self):
        return lambda msg: msg.type in ["control_change", "note_on", "note_off"]

    @property
    def external_message(self):
        controls = ["beat", "start", "strings", "synth", "sequence"]
        return lambda msg: msg.type in controls

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
        elif control in range(16, 24):
            self.channel = channel
            yield Msg("strings", channel, control, value)
            channels = [channel]
            if channel == 8:
                channels += [*range(0, 6)]
            controls = range(control - 3, control) if control in [19, 23] else [control]
            for ch in channels:
                for ctl in controls:
                    if ctl != control or ch != channel:
                        yield MidiCC(ch, ctl, value)
        elif control in range(48, 56):
            self.layers.current.update_controls(control - 48, value)
            idx = self.layers.current._idx
            msg_type = "xfade" if idx < 21 else "synth"
            yield Msg(msg_type, idx, control - 48, value)
        elif control == 64:
            yield Msg("toggle", None)
        elif control == 67:
            yield Msg("stop", None)

    def _note_on_in(self, msg: MidiNote):
        note = msg.note
        if note in range(52, 58):  # synth params
            self.layers.current.update_steps(note, msg.channel)
            yield Msg("steps", *self.layers.current.get_param_steps(note))
        elif note == 64:  # overdub
            self.layers.toggle(note)
            yield Msg("overdub", note in self.layers.toggles)
        elif note in range(81, 87):  # target sequencer
            self.layers.toggle(note)
            param = 0 if note in [82, 83] else 1 if note in [84, 85] else 2
            value = ((note + 1) % 2 or 2) if note in self.layers.toggles else 0
            yield Msg("seq", self.layers.current._idx, param, value)
        elif note in range(87, 91):  # select instr
            self.layers.set(note - 87)
            self.layers.toggle(note)
            yield from self.layers.request
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

    def _note_off_in(self, msg: MidiNote):
        note = msg.note
        if note in range(52, 58):
            if self.layers.current.has_step(note, msg.channel):
                yield MidiNote(msg.channel, note)
        elif note == 64:
            yield MidiNote(msg.channel, note, note in self.layers.toggles)
        elif note in range(81, 87):
            yield from self.layers.toggle_targets(note)
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

    def _strings_in(self, msg: Msg):
        instr, data = msg.data
        for i, d in enumerate(data):
            channel = divmod(i, 6)[1]
            control = clip((instr + 155) / 11 + (4 if i >= 6 else 0))
            value = clip(d / 100 * 127)
            yield MidiCC(channel, control, value)

    def _beat_in(self, _=None):
        return make_notes(self.channel, [*self.blinks])

    def _start_in(self, _):
        self.blinks.add(65)
        res = self._beat_in()
        self.blinks.discard(65)
        return res

    def _synth_in(self, msg: Msg):
        idx, control, value = msg.data
        self.layers.get(idx).update_controls(control, value)
        if self.layers.is_current(idx):
            yield MidiCC(0, control + 48, value)

    def _sequence_in(self, msg: Msg):
        idx, target, seq, steps = msg.data
        layer = self.layers.get(idx)
        is_current = layer._idx in self.layers.current.ridx
        # steps
        step_rows = [53 + 2 * target, 54 + 2 * target]
        targets = [82 + 2 * target, 83 + 2 * target]
        if target == 2:  # last row
            step_rows[1] -= 6
            targets[1] -= 6
        for i, step in enumerate(steps):
            row, channel = divmod(i, 8)
            note = step_rows[row]
            layer.update_steps(note, channel, step)
            if is_current:
                yield MidiNote(channel, note, step > 64)
        # sequencers
        for i, note in enumerate(targets, 1):
            is_selected = seq == i
            layer.update_targets(note, is_selected)
            if is_current:
                if is_selected:
                    self.layers.toggle(note)
                else:
                    self.layers.toggles.discard(note)
                yield MidiNote(0, note, is_selected)
