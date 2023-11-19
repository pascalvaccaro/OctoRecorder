from midi.messages import (
    MidiNote,
    MidiCC,
    SysexCmd,
    SysexReq,
    Sysex,
    MidoMessage,
)
from midi.device import MidiDevice
import reactivex as rx
import reactivex.operators as ops


def make_note(channel, note: int):
    return rx.merge(rx.of(127), rx.timer(0.125)).pipe(
        ops.map(lambda vel: MidiNote(channel, note, vel)),
    )


def make_notes(channel, notes):
    return rx.merge(*map(lambda note: make_note(channel, note), notes))
