from midi.messages import (
    MidiNote,
    MidiCC,
    InternalMessage as Msg,
    MacroMessage,
    StepMessage,
)
from midi import MidiDevice, make_notes
from instruments.blocks import Block, Nav, CCBlock, Stack, Pager
from utils import clip


class APC40(MidiDevice):
    blinks: "set[int]" = set([65])
    blocks = Nav(
        "instr",
        87,
        4,
        CCBlock("synth", 48, 8),
        Nav(
            "target",
            82,
            3,
            Pager(
                97,
                Block("steps", 53, (5, 16)),
                Nav("seq", 85, 2, Stack("length", 52, (1, 16))),
            ),
        ),
    )

    @property
    def init_actions(self):
        for ch in range(0, 8):
            yield MidiCC(ch, 7, 127)
            for ctl in range(16, 20):
                yield MidiCC(ch, ctl, 127)
            for ctl in range(20, 24):
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
        controls = ["beat", "start", "strings", "synth", "steps", "seq"]
        return lambda msg: msg.type in controls

    def _control_change_in(self, msg: MidiCC):
        channel = msg.channel
        control = msg.control
        value = msg.value
        block = self.blocks.get(control + 128)
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
        elif control == 64:  # footswitch 1
            yield Msg("toggle", None)
        elif control == 67:  # footswitch 2
            yield Msg("stop", None)
        elif block:
            block.current = control, channel, value
            yield from block.message(control + 128)

    def _note_on_in(self, msg: MidiNote):
        note = msg.note
        block = self.blocks.get(msg.note)
        if block:
            block.current = msg.note, msg.channel
            yield from block.message(msg.note, msg.channel)
        elif note == 48:  # reds
            yield Msg("arm", msg.channel, msg.velocity)
        elif note == 49:  # blues
            yield Msg("mute", msg.channel, msg.velocity)
        elif note == 50:  # bars
            yield MacroMessage("bars", self.blocks.root.row_idx, msg.channel + 1)
        elif note == 58:  # clip
            pass
        elif note == 59:  # device
            pass
        elif note == 60:  # <=
            yield Msg("patch", -1)
        elif note == 61:  # =>
            yield Msg("patch", 1)
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
        block = self.blocks.get(msg.note)
        if note in [48, 49] and msg.channel == 7:  # reds/blues
            for ch in range(0, 7):
                yield MidiNote(ch, note, msg.velocity)
        elif note == 50:  # bars
            for ch in range(0, 8):
                yield MidiNote(ch, 50, ch <= msg.channel)
        elif block:
            yield from block.current  # type: ignore

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

    def _synth_in(self, msg: MacroMessage):
        yield from self.blocks.set(msg.idx, msg.macro, msg.value)

    def _steps_in(self, msg: StepMessage):
        target = self.blocks.get(msg.idx, msg.macro)
        if isinstance(target, Nav):
            page = msg.macro - target.macro
            for col, values in enumerate(msg.steps):
                for row, value in enumerate(values):
                    target.set(page, 53, row, col, value)
            yield from target.set(page, msg.macro, msg.value)

    def _seq_in(self, msg: MacroMessage):
        yield from self.blocks.set(msg.idx, msg.macro, msg.value)
