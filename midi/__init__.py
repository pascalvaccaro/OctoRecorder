from midi.messages import (
    MidiNote,
    MidiCC,
    SysexCmd,
    SysexReq,
    Sysex,
    MidoMessage,
    MidiMessage,
)
from midi.device import MidiDevice
import reactivex as rx
import reactivex.operators as ops


def make_note(channel: int, note: int):
    return rx.merge(rx.of(127), rx.timer(0.125)).pipe(
        ops.map(lambda vel: MidiNote(channel, note, vel)),
    )


def make_notes(channel: int, notes: list[int]):
    return rx.merge(*map(lambda note: make_note(channel, note), notes))
