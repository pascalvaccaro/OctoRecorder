from typing import List
from .controller import Controller


class Layers(List[Controller]):
    _idx = 1
    _toggles: "set[int]" = set()

    def __init__(self, *args: int):
        super().__init__([Controller(arg) for arg in args])

    @property
    def controller(self):
        return self[self._idx]
    
    @property
    def sequencer(self):
        return self.controller.current

    @property
    def toggles(self):
        return self._toggles

    def is_current(self, idx: int, target_idx=None, page_idx=None):
        is_current_layer = idx in self.controller.ridx
        is_current_target = self.sequencer._idx == target_idx
        is_current_page = self.sequencer._page == page_idx
        if page_idx is not None:
            return is_current_page and is_current_layer and is_current_target
        if target_idx is not None:
            return is_current_layer and is_current_target
        return is_current_layer

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
        yield from self.controller.request

    def toggle(self, note: int, force=None):
        if force is not None:
            if force:
                self.toggles.add(note)
            else:
                self.toggles.discard(note)
        elif note in self.toggles:
            self.toggles.remove(note)
        else:
            self.toggles.add(note)
        return note in self.toggles
