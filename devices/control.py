from reactivex import merge, interval, of, concat, timer, operators as ops
from midi import MidiNote, MidiCC, MidiDevice, InternalMessage as Msg


class APC40(MidiDevice):
    def __init__(self, *args, **kwargs):
        super(APC40, self).__init__(*args, **kwargs)
        for ch in range(0, 8):
            self.send(MidiCC(ch, 7, 127))
            for ctl in range(16, 20):
                self.send(MidiCC(ch, ctl, 127))
            for ctl in [*range(20, 24), *range(48, 56)]:
                self.send(MidiCC(ch, ctl, 64))
            for note in [48, 49]:
                self.send(MidiNote(ch, note))
        self.send(MidiCC(0, 14, 127))
        self.send(MidiCC(0, 15, 64))
        self.set_bars()

    def receive(self, msg):
        if msg.type == "control_change":
            self._control_change_in(msg)
        elif msg.type == "note_on":
            self._note_on_in(msg)
    
    
    def blink(self, note):
        def wrapped(_):
            concat(of(127), timer(0.125)).subscribe(
                lambda x: self.send(MidiNote(self.channel, note, x))
            )

        return wrapped

    def set_bars(self, bars=2):
        for ch in range(0, bars):
            yield MidiNote(ch, 50)
        for ch in range(bars, 8):
            yield MidiNote(ch, 50, 0)
        return Msg("bars", bars)

    def _control_change_in(self, msg):
        channel = msg.channel
        control = msg.control
        value = msg.value
        if control == 64:
            return Msg("toggle", None)
        if control == 67:
            return Msg("stop", None)
        if control == 7:
            return Msg("volume", channel, value / 127)
        if control == 14:
            for ch in range(0, 8):
                yield Msg("volume", ch, value / 127)
        if control == 15:
            return Msg("xfader", value / 127)
        if control >= 48 and control <= 55:
            return Msg("xfade", control - 48, value / 127)
        if control == 19:
            for ctl in [16, 17, 18]:
                yield self._control_change_in(dict(channel=channel, control=ctl, value=value))
                yield MidiCC(channel, ctl, value)
        elif control >= 16 and control <= 22:
            if channel < 6:
                return Msg("strings", channel, control, value)
            elif channel == 8:
                if control < 23:
                    for ch in range(0, 8):
                        yield self.send(MidiCC(ch, control, value))

    def _note_on_in(self, msg):
        note = msg.note
        if note == 91:
            for ch in range(0, 9):
                yield self.send(MidiNote(ch, 62))
            return Msg("play")
        if note == 92:
            for ch in range(0, 9):
                yield MidiNote(ch, 62, 0)
            return Msg("stop")
        if note == 93:
            signal = merge(self.on("play"), self.on("stop"))
            interval(0.250).pipe(ops.take_until(signal)).subscribe(self.blink(62))
            return Msg("rec")
        if note == 94:  # up
            return Msg("patch", -1)
        if note == 95:  # down
            return Msg("patch", 1)
        if note == 96:  # right
            return Msg("patch", 4)
        if note == 97:  # left
            return Msg("patch", -4)
        if note == 100:
            return Msg("phrase", 1)
        if note == 101:
            return Msg("phrase", -1)
        if note == 98:
            return self.shutdown()
        yield self._note_in(msg)

    def _note_in(self, msg):
        channel = msg.channel
        note = msg.note
        value = msg.velocity
        if note == 48 or note == 49:
            if channel == 7:
                for ch in range(0, 7):
                    yield MidiNote(ch, note, value)
            return MidiNote(channel, note, value)
        if note == 50:
            return self.set_bars(channel + 1)

    def _note_off_in(self, msg):
        yield self._note_in(msg)
