from reactivex import merge, of, operators as ops
from midi import MidiNote, MidiCC, MidiDevice, InternalMessage as Msg, make_note
from midi.clock import beat, start


class APC40(MidiDevice):
    @property
    def select_message(self):
        return lambda msg: msg.type in [
            "control_change",
            "note_on",
            "note_off",
        ]

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
    def external_message(self):
        return lambda msg: msg.type in ["strings"]

    def __init__(self, port):
        super().__init__(port)
        for sched in (beat, start):
            self.subs = sched.schedule_with(self)

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
        elif control == 19:
            for ctl in [16, 17, 18]:
                yield MidiCC(channel, ctl, value)
                msg.control = ctl
                yield from self._control_change_in(msg)
        elif control in range(16, 23):
            self.channel = channel
            yield Msg("strings", channel, control, value)
            if channel == 8:
                for ch in range(0, 8):
                    yield MidiCC(ch, control, value)
        elif control in range(48, 56):
            yield Msg("xfade", control - 48, value)
        elif control == 64:
            yield Msg("toggle", None)
        elif control == 67:
            yield Msg("stop", None)

    def _note_on_in(self, msg: MidiNote):
        note = msg.note
        if note == 91:
            yield Msg("play")
            for ch in range(0, 9):
                yield MidiNote(ch, 62)
        elif note == 92:
            yield Msg("stop")
            for ch in range(0, 9):
                yield MidiNote(ch, 62, 0)
        elif note == 93:
            stopper = lambda msg: msg.type in ["play", "stop"]
            return merge(
                of(Msg("rec")),
                beat.signal.pipe(
                    ops.take_until(self.pipe(ops.filter(stopper))),
                    ops.flat_map(lambda _: make_note(self.channel, 62)),
                ),
            )
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
        yield from self._note_in(msg)

    def _strings_in(self, msg: Msg):
        yield MidiCC(*msg.data)

    def _beat_in(self, _):
        return make_note(self.channel, 63)

    def _start_in(self, _):
        return merge(*(make_note(self.channel, note) for note in (65, 63)))
