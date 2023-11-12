from midi.messages import MidiNote, MidiCC
from utils import scroll

class Pads:
    _pads = [[0] * 5] * 16
    _page = 0
    _target = 0

    def __init__(self, idx: int, values=[127, 101, 76, 50, 25]):
        self._idx = idx
        self._values = values

    @property
    def page_pads(self):
        return self._pads[self._page * 8 : (self._page + 1) * 8]

    @property
    def request(self):
        for ch, col in enumerate(self.page_pads):
            for note, val in enumerate(col, 53):
                yield MidiNote(ch, note, val)
        for note, val in enumerate(range(0, 3), 82):
            yield MidiNote(0, note, self._idx == val)
        for note, val in enumerate([1, 2], 85):
            yield MidiNote(0, note, self._target == val)

    @property
    def pads(self):
        pads = [0] * 16
        for i, col in enumerate(self._pads):
            for j, vel in enumerate(self._values):
                if col[j] == 127:
                    pads[i] = vel
                    break
        return [self._idx, pads]

    def has_pad(self, col: int, row: int):
        return self.page_pads[col][row] > 0

    def next(self):
        self._page = scroll(self._page + 1, 0, 1)
        yield from self.request

    def previous(self):
        self._page = scroll(self._page - 1, 0, 1)
        yield from self.request

    def update_pads(self, channel: int, row: int, value=None):
        col = channel * (1 + self._page)
        if value is not None:
            self._pads[col][row] = value
        elif self._pads[col][row] > 0:
            self._pads[col][row] = 0
        else:
            self._pads[col][row] = 127

    def update_target(self, idx, value=None):
        self._target = int(idx * value) if value is not None else idx


class Controller:
    _controls = [64] * 8
    _length = [127] * 16
    _targets = [
        Pads(0, [127, 74, 54, 32, 10]),  # pitch
        Pads(1),  # cutoff
        Pads(2),  # level
    ]
    _target_idx = 0
    _state = 0

    def __init__(self, instr_id: int):
        self._idx = instr_id

    @property
    def current(self):
        return self._targets[self._target_idx]

    @property
    def ridx(self):
        return range(self._idx, self._idx + 11)

    @property
    def target(self):
        return [self._idx, self.current._target]

    @property
    def length(self):
        for l, val in enumerate(self._length):
            if val == 0:
                return [self._idx, l]
        return [self._idx, len(self._length)]

    @property
    def length_pads(self):
        offset = self.current._page
        return self._length[offset * 8 : (offset + 1) * 8]

    @property
    def steps(self):
        return [self._idx, *self.current.pads]

    @property
    def request(self):
        for i, val in enumerate(self._controls):
            yield MidiCC(0, i + 48, val)
        for ch, val in enumerate(self.length_pads):
            yield MidiNote(ch, 52, val)
        yield from self.current.request

    def get(self, idx: int):
        return self._targets[idx]

    def set(self, target):
        self._target_idx = target
        yield from self.current.request

    def update_controls(self, idx: int, value: int):
        self._controls[idx] = value

    def update_length(self, value: int):
        length = value * (1 + self.current._page)
        for i, _ in enumerate(self._length):
            self._length[i] = 127 * (i <= length)

    def update_state(self, value):
        self._state = int(value)
