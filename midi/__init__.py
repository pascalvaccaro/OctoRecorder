from midi.messages import (
    MidiCC,
    MidiNote,
    SysexCmd,
    SysexReq,
    InternalMessage,
    Sysex,
    MidiMessage,
)
from midi.clock import Metronome, beat, start, end
from midi.device import MidiDevice
from reactivex import merge, of, timer, operators as ops


def make_note(channel, note: int):
    return merge(of(127), timer(0.125)).pipe(
        ops.map(lambda vel: MidiNote(channel, note, vel)),
    )
