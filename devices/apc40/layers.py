from typing import List
from midi.messages import MidiNote
from utils import clip


class Layer:
    controls = [64, 64, 64, 0, 64, 0, 64, 0]
    pads = [[0] * 9] * 6

    def __init__(self, idx: int):
        self._idx = idx
        if idx < 21: # audio params
            self.controls = [64] * 8

    @property
    def ridx(self):
        return range(self._idx, self._idx + 11)

    @property
    def request(self):
        for idx, val in enumerate(self.controls):
            yield MidiNote(0, idx + 48, val)
        for idx, row in enumerate(self.pads):
            for ch, val in enumerate(row):
                if ch == 8: # sequencer target selection
                    yield MidiNote(0, idx + 81, val * 127)
                else: # common pads
                    yield MidiNote(ch, idx + 52, val * 127)

    def update_controls(self, idx: int, value: int):
        self.controls[idx] = clip(value)
        return self

    def update_pads(self, note: int, channel: int):
        if self.pads[note - 52][channel] == 0:
            self.pads[note - 52][channel] = 1
        else:
            self.pads[note - 52][channel] = 0
        if note in [53, 54]:
            param = 0
            pads = map(lambda x: min(32, x * 44), [*self.pads[1], *self.pads[2]])
        elif note in [55, 56]:
            param = 1
            pads = map(lambda x: min(30, x * 80), [*self.pads[3], *self.pads[4]])
        else:
            param = 2
            pads = map(lambda x: x * 100, [*self.pads[5], *self.pads[0]])
        return param, list(pads)


class Layers(List[Layer]):
    _idx = 1
    _toggles: "set[int]" = set()

    def __init__(self, *args: int):
        super().__init__([Layer(arg) for arg in args])

    @property
    def current(self):
        return self[self._idx]

    @property
    def toggles(self):
        return self._toggles
    
    @property
    def request(self):
        yield from self.current.request
        yield from self.toggle_amongst(self._idx + 87, range(87, 91))

    def get(self, idx: int):
        for layer in self:
            if idx in layer.ridx:
                return layer
        return self[idx]

    def set(self, idx: int):
        for i, ridx in enumerate([l.ridx for l in self]):
            if idx in ridx:
                self._idx = i
                return
        if idx < len(self):
            self._idx = idx
        self.toggle(idx + 87)
        

    def toggle(self, note: int):
        if note in self.toggles:
            self.toggles.remove(note)
        else:
            self.toggles.add(note)

    def toggle_pad(self, note: int, channel: int):
        if self.current.pads[note - 52][channel] == 1:
            yield MidiNote(channel, note, 127)

    def toggle_amongst(self, note: int, rnote, channel=0):
        if note in self.toggles:
            for n in rnote:
                if n != note:
                    self.toggles.discard(n)
                    yield MidiNote(channel, n, 0)
            yield MidiNote(channel, note, 127)

    def toggle_special(self, note: int):
        if note in self.toggles:
            yield MidiNote(0, note)
            opposite_note = (
                86
                if note == 81
                else 81
                if note == 86
                else note + (1 if note % 2 == 1 else -1)
            )
            yield MidiNote(0, opposite_note, 0)
