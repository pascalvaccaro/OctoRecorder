from typing import List
from midi.messages import MidiNote, MidiCC
from utils import clip


class Layer:
    controls = [64] * 8
    steps = [[0] * 8] * 6
    targets = [0] * 6

    def __init__(self, idx: int):
        self._idx = idx

    @property
    def ridx(self):
        return range(self._idx, self._idx + 11)

    @property
    def request(self):
        for i, val in enumerate(self.controls):
            yield MidiCC(0, i + 48, val)
        for i, val in enumerate(self.targets):
            yield MidiNote(0, i + 81, val * 127)
        for i, row in enumerate(self.steps):
            for ch, val in enumerate(row):
                yield MidiNote(ch, 52 + i, val > 64)

    def has_step(self, note: int, channel=0):
        step = self.steps[note - 52][channel]
        return step > 64

    def update_controls(self, idx: int, value: int):
        self.controls[idx] = clip(value)

    def update_steps(self, note: int, channel: int, value=None):
        if value is not None:
            self.steps[note - 52][channel] = value
        elif self.steps[note - 52][channel] > 64:
            self.steps[note - 52][channel] = 0
        else:
            self.steps[note - 52][channel] = 127

    def update_targets(self, note, value=None):
        opp_note = self.get_opposite(note)
        if value is not None:
            if value:
                self.targets[note - 81] = 1
                self.targets[opp_note - 81] = 0
            else:
                self.targets[note - 81] = 0
        else:
            if self.targets[note - 81] == 0:
                self.targets[note - 81] = 1
                self.targets[opp_note - 81] = 0
            else:
                self.targets[note - 81] = 0

    def get_param_steps(self, note):
        if note in [53, 54]:
            param = 0
            steps = [*self.steps[1], *self.steps[2]]
        elif note in [55, 56]:
            param = 1
            steps = [*self.steps[3], *self.steps[4]]
        else:
            param = 2
            steps = [*self.steps[5], *self.steps[0]]
        return [self._idx, param, steps]

    @classmethod
    def get_opposite(cls, note: int):
        return (
            86
            if note == 81
            else 81
            if note == 86
            else note + (1 if note % 2 == 0 else -1)
        )


class Layers(List[Layer]):
    _idx = 1
    _toggles: "set[int]" = set([88])

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
        yield from self.toggle_by_range(self._idx + 87, range(87, 91))

    def is_current(self, idx: int):
        return idx in self.current.ridx

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

    def toggle(self, note: int):
        if note in self.toggles:
            self.toggles.remove(note)
        else:
            self.toggles.add(note)

        if note in range(81, 87):
            self.current.update_targets(note)

    def toggle_targets(self, note: int):
        opp_note = Layer.get_opposite(note)
        if note in self.toggles:
            yield MidiNote(0, note)
            yield MidiNote(0, opp_note, 0)
            self.toggles.discard(opp_note)

    def toggle_by_range(self, note: int, rnote, channel=0):
        if note in self.toggles:
            for n in rnote:
                if n != note:
                    self.toggles.discard(n)
                    yield MidiNote(channel, n, 0)
        yield MidiNote(channel, note, note in self.toggles)
