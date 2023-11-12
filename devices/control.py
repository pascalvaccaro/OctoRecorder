from midi.messages import MidiNote, MidiCC, InternalMessage as Msg
from midi import MidiDevice, make_notes
from instruments import Layers
from utils import clip


class APC40(MidiDevice):
    blinks: "set[int]" = set([65])
    instruments = Layers(10, 21, 32, 43)

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
        yield from self._note_on_in(MidiNote(0, 88))
        yield from self._note_off_in(MidiNote(1, 50))

    @property
    def select_message(self):
        return lambda msg: msg.type in ["control_change", "note_on", "note_off"]

    @property
    def external_message(self):
        controls = ["beat", "start", "strings", "synth", "steps", "length"]
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
            self.instruments.controller.update_controls(control - 48, value)
            idx = self.instruments.controller._idx
            msg_type = "xfade" if idx < 21 else "synth"
            yield Msg(msg_type, idx, control - 48, value)
        elif control == 64:  # footswitch 1
            yield Msg("toggle", None)
        elif control == 67:  # footswitch 2
            yield Msg("stop", None)

    def _note_on_in(self, msg: MidiNote):
        note = msg.note
        if note == 48:  # reds
            yield Msg("t_record", msg.channel, msg.velocity)
        elif note == 49:  # blues
            yield Msg("t_play", msg.channel, msg.velocity)
        elif note == 50:
            yield Msg("bars", msg.channel + 1)
        elif note == 52:  # sequencer length
            self.instruments.controller.update_length(msg.channel)
            yield Msg("length", *self.instruments.controller.length)
        elif note in range(53, 58):  # sequencer steps
            self.instruments.sequencer.update_pads(msg.channel, note - 53)
            yield Msg("steps", *self.instruments.controller.steps)
        elif note in [58, 59]:  # clip, device
            pass
        elif note == 60:  # <=
            yield Msg("patch", -1)
        elif note == 61:  # =>
            yield Msg("patch", 1)
        elif note == 64:  # overdub
            value = self.instruments.toggle(note)
            yield Msg("overdub", value)
        elif note == 81:  # switch sequencers on/off (no light...)
            value = 1 * self.instruments.toggle(note)
            yield Msg("status", self.instruments.controller._idx, value)
        elif note in range(82, 85):  # select target
            self.instruments.toggle(note)
            yield from self.instruments.controller.set(note - 82)
        elif note in range(85, 87):  # select target sequencer
            value = self.instruments.toggle(note)
            self.instruments.sequencer.update_target(note - 84, value)
            yield Msg("target", *self.instruments.controller.target)
        elif note in range(87, 91):  # select instr
            self.instruments.toggle(note)
            yield from self.instruments.set(note - 87)
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
        elif note == 90:  # up
            pass
        elif note == 95:  # down
            pass
        elif note == 96:  # right
            yield from self.instruments.sequencer.next()
        elif note == 97:  # left
            yield from self.instruments.sequencer.previous()
        elif note == 98:  # shift
            yield self.shutdown()
        elif note == 99:  # tap
            pass
        elif note == 100:  # +
            yield Msg("phrase", 1)
        elif note == 101:  # -
            yield Msg("phrase", -1)

    def _note_off_in(self, msg: MidiNote):
        note = msg.note
        is_toggled = note in self.instruments.toggles
        if note in [48, 49] and msg.channel == 7:  # reds/blues
            for ch in range(0, 7):
                yield MidiNote(ch, note, msg.velocity)
        elif note == 50:  # bars
            for ch in range(0, 8):
                yield MidiNote(ch, 50, ch <= msg.channel)
        if note == 52:  # sequencer length
            for ch, val in enumerate(self.instruments.controller.length_pads):
                yield MidiNote(ch, note, val)
        elif note in range(53, 58):  # steps
            if self.instruments.sequencer.has_pad(msg.channel, note - 53):
                yield MidiNote(msg.channel, note)
        elif note == 64:  # overdub
            yield MidiNote(msg.channel, note, is_toggled)
        elif note == 81:  # sequencer on/off
            if is_toggled:
                yield from self.instruments.sequencer.request
            else:
                for note in range(85, 87):
                    yield MidiNote(0, note, 0)
        # targets, sequencers, instruments
        for rnote in [range(82, 85), range(85, 87), range(87, 91)]:
            if note in rnote:
                yield MidiNote(msg.channel, note, is_toggled)
                if is_toggled:
                    for n in rnote:
                        if n != note:
                            self.instruments.toggles.discard(n)
                            yield MidiNote(msg.channel, n, 0)

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
        self.blinks.add(63)
        res = self._beat_in()
        self.blinks.discard(63)
        return res

    def _synth_in(self, msg: Msg):
        instr_idx, ctl_idx, value = msg.data
        self.instruments.get(instr_idx).update_controls(ctl_idx, value)
        if self.instruments.is_current(instr_idx):
            yield MidiCC(0, ctl_idx + 48, value)

    def _steps_in(self, msg: Msg):
        instr_idx, target, target_idx, steps = msg.data
        layer = self.instruments.get(instr_idx)
        sequencer = layer.get(target)
        sequencer.update_target(target_idx)
        for ch, step in enumerate(steps):
            for note, value in enumerate(sequencer._values):
                sequencer.update_pads(ch, note, 127 * (step >= value))
        if self.instruments.is_current(instr_idx, target):
            for note, val in enumerate(range(0, 3), 82):
                self.instruments.toggle(note, target == val)
                yield MidiNote(0, note, target == val)
            for note, val in enumerate([1, 2], 85):
                self.instruments.toggle(note, target_idx == val)
                yield MidiNote(0, note, target_idx == val)

    def _length_in(self, msg: Msg):
        instr_idx, status, length = msg.data
        layer = self.instruments.get(instr_idx)
        layer.update_length(length)
        layer.update_state(status)
        if self.instruments.is_current(instr_idx):
            for ch, val in enumerate(layer.length_pads):
                yield MidiNote(ch, 52, val)
            if status > 0:
                self.instruments.toggles.add(81)
                yield from layer.current.request
            else:
                self.instruments.toggles.discard(81)
