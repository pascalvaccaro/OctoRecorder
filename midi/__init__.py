from midi.messages import (
    MidiNote,
    MidiCC,
    SysexCmd,
    SysexReq,
    InternalMessage,
    Sysex,
    MidiMessage,
)
from midi.device import MidiDevice
from reactivex import merge, of, timer, operators as ops


def make_note(channel, note: int):
    return merge(of(127), timer(0.125)).pipe(
        ops.map(lambda vel: MidiNote(channel, note, vel)),
    )

def make_notes(channel, notes):
    return merge(*map(lambda note: make_note(channel, note), notes))