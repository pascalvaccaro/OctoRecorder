import reactivex.operators as ops
import reactivex.scheduler as sch
from reactivex import merge, interval, of, concat, timer, from_iterable
from midi import MidiNote, MidiCC, MidiDevice, InternalMessage as Msg
from utils import throttle


class APC40(MidiDevice):
    scheduler = sch.TimeoutScheduler()

    @property
    def select_messages(self):
        def wrapped(msg):
            print(msg.type)
            return msg.type in [
                "control_change",
                "note_on",
                "note_off",
            ]

        return wrapped

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
        self.subs.add(
            concat(from_iterable(self._bars_out()), self.messages).subscribe(self.send)
        )

    def blink(self, note):
        def wrapped(_):
            concat(of(127), timer(0.125)).subscribe(
                lambda x: self.send(MidiNote(self.channel, note, x))
            )

        return wrapped

    def _bars_out(self, bars=2):
        for ch in range(0, bars):
            yield MidiNote(ch, 50)
        for ch in range(bars, 8):
            yield MidiNote(ch, 50, 0)
        yield Msg("bars", bars)

    @throttle(0.250)
    def _control_change_in(self, msg):
        channel = msg.channel
        control = msg.control
        value = msg.value
        if control == 23:
            self.suspend = (
                lambda msg: msg.is_cc() and msg.channel == 8 and msg.control == 22
            )
        elif control == 64:
            yield Msg("toggle", None)
        elif control == 67:
            yield Msg("stop", None)
        elif control == 7:
            yield Msg("volume", channel, value / 127)
        elif control == 14:
            for ch in range(0, 8):
                yield Msg("volume", ch, value / 127)
        elif control == 15:
            yield Msg("xfader", value / 127)
        elif control >= 48 and control <= 55:
            yield Msg("xfade", control - 48, value / 127)
        elif control == 19:
            for ctl in [16, 17, 18]:
                yield from self._control_change_in(
                    dict(channel=channel, control=ctl, value=value)
                )
                yield MidiCC(channel, ctl, value)
        elif control >= 16 and control <= 22:
            if channel < 6:
                yield Msg("strings", channel, control, value)
            elif channel == 8:
                if control < 23:
                    for ch in range(0, 8):
                        yield MidiCC(ch, control, value)

    def _note_on_in(self, msg):
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
            signal = merge(self.on("play"), self.on("stop"))
            interval(0.250).pipe(ops.take_until(signal)).subscribe(self.blink(62))
            yield Msg("rec")
        elif note == 94:  # up
            yield Msg("patch", -1)
        elif note == 95:  # down
            yield Msg("patch", 1)
        elif note == 96:  # right
            yield Msg("patch", 4)
        elif note == 97:  # left
            yield Msg("patch", -4)
        elif note == 100:
            yield Msg("phrase", 1)
        elif note == 101:
            yield Msg("phrase", -1)
        elif note == 98:
            yield self.shutdown()
        else:
            yield from self._note_in(msg)

    def _note_in(self, msg):
        channel = msg.channel
        note = msg.note
        value = msg.velocity
        if note == 48 or note == 49:
            if channel == 7:
                for ch in range(0, 7):
                    yield MidiNote(ch, note, value)
        elif note == 50:
            yield from self._bars_out(channel + 1)

    def _note_off_in(self, msg):
        yield from self._note_in(msg)
