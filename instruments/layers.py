from typing import List
from midi.messages import MidiNote, MidiCC
from utils import clip


class Layer:
    steps = [[32] * 8, [32] * 8, [30] * 8, [30] * 8, [0] * 8, [0] * 8]
    controls = [64, 64, 64, 0, 64, 0, 64, 0]
    targets = [0] * 6

    def __init__(self, idx: int):
        self._idx = idx
        if idx < 21:  # audio params
            self.controls = [64] * 8

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
                note = 52 + i
                if note in [53, 54]:  # pitch
                    yield MidiNote(ch, note, 127 * (val > 32))
                elif note in [55, 56]:  # cutoff
                    yield MidiNote(ch, note, 127 * (val > 30))
                elif note in [57, 52]:  # level
                    yield MidiNote(ch, note, 127 * (val > 0))

    def has_step(self, note: int, channel=0):
        step = self.steps[note - 52][channel]
        if note in [53, 54]:  # pitch
            return step > 32
        elif note in [55, 56]:  # cutoff
            return step > 30
        elif note in [57, 52]:  # level
            return step > 0
        return False

    def update_controls(self, idx: int, value: int):
        self.controls[idx] = clip(value)
        return self

    def update_steps(self, note: int, channel: int, value=None):
        if value is not None:
            self.steps[note - 52][channel] = value
        elif note in [53, 54]:  # pitch
            if self.steps[note - 52][channel] > 32:
                self.steps[note - 52][channel] = 32
            else:
                self.steps[note - 52][channel] = 44
        elif note in [55, 56]:  # cutoff
            if self.steps[note - 52][channel] > 30:
                self.steps[note - 52][channel] = 30
            else:
                self.steps[note - 52][channel] = 80
        elif note in [57, 52]:  # level
            if self.steps[note - 52][channel] > 0:
                self.steps[note - 52][channel] = 0
            else:
                self.steps[note - 52][channel] = 100
        return self

    def update_targets(self, note, value=None):
        opp_note = self.get_opposite_target(note)
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
        return self

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
    def get_opposite_target(cls, note: int):
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

    def toggle_targets(self, note: int):
        opp_note = Layer.get_opposite_target(note)
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
        yield MidiNote(channel, note, 127 * (note in self.toggles))
