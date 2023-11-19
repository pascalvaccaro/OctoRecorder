from typing import Optional, Union
from midi.messages import MidiCC, MidiNote
from .messages import InternalMessage, MacroMessage, StringMessage
from utils import scroll, clip


class Block:
    row_idx = 0
    col_idx = 0
    parent: Optional["Block"] = None
    values: list[list[int]] = []

    def __init__(self, name: str, macro: int, shape: Union[int, tuple[int, ...]] = 1):
        self.name = name
        self.macro: int = macro
        if isinstance(shape, int):
            shape = tuple([shape, 1])
        self.row_size, self.col_size = shape[0], min(8, shape[1])
        self.max_col_page = divmod(shape[1] - 1, 8)[0]
        self.values = [[0 for _ in range(0, shape[1])] for _ in range(0, shape[0])]

    @property
    def address(self):
        address = [self.root.row_idx]
        current = self
        while current.parent is not None:
            address.insert(1, current.row_idx)
            current = current.parent
        return address

    @property
    def root(self):
        parent = self
        while parent.parent is not None:
            parent = parent.parent
        return parent

    @property
    def cursor(self):
        return self.col_idx * self.col_size

    @property
    def range(self):
        return range(self.macro, self.macro + self.row_size)

    @property
    def off(self):
        kw = "velocity" if self.macro < 128 else "value"
        for msg in self.current:
            setattr(msg, kw, 0)
            yield msg

    @property
    def current(self):
        """Output the block MIDI messages for the current page"""
        MidiMessage = MidiNote if self.macro < 128 else MidiCC
        macro = self.macro if self.macro < 128 else self.macro - 128
        for note, values in enumerate(self.values, macro):
            for ch, val in enumerate(values[self.cursor : self.cursor + self.col_size]):
                yield MidiMessage(ch, note, val)

    @current.setter
    def current(self, args: tuple[int, ...]):
        """Sets the block values on the current page"""
        note, ch = args[0:2]
        value = args[2] if len(args) == 3 else 127 * self.empty(note, ch)
        self.update_value(note - self.macro, ch + self.cursor, value)

    def empty(self, *args: int):
        return self.value_at(*args) == 0

    def value_at(self, *args: int):
        if len(args) < 2:
            args = args[0], 0
        note, ch = args[0:2]
        return self.values[note - self.macro][ch + self.cursor]

    def update_value(self, *args: int):
        """Update the block values (value=None toggles 0~127)"""
        if len(args) < 2:  # toggle
            args = args[0], 0, -1
        if len(args) < 3:
            args = args[0], 0, args[1]
        row, col, value = args[0:3]
        if value < 0:
            value = 127 * (self.values[row][col] == 0)
        self.values[row][col] = value

    def get(self, macro: int):
        """Get a block by its index"""
        if macro in self.range:
            return self

    def set(self, macro: int, *args: int):
        block = self.get(macro)
        if block:
            block.update_value(macro - block.macro, *args)

    def next(self):
        return self.go_to(self.col_idx + 1)

    def previous(self):
        return self.go_to(self.col_idx - 1)

    def go_to(self, col_idx):
        self.col_idx = scroll(col_idx, 0, self.max_col_page)
        yield from self.current

    def message(self, *args: int):
        yield MacroMessage(
            self.name, self.root.row_idx, self.macro, self.value_at(*args)
        )


class Stack(Block):
    def empty(self, *_: int):
        return True

    def value_at(self, *args: int):
        if len(args) < 2:
            args = self.macro, args[0]
        row = args[0] - self.macro
        for i, val in enumerate(self.values[row]):
            if val == 0:
                return i
        return len(self.values[row])

    def update_value(self, *args: int):
        if len(args) == 1:  # channel only, acts as value
            args = 0, args[0], 127
        if len(args) == 2:
            args = 0, *args
        row, col, value = args[0:3]
        for i, _ in enumerate(self.values[row]):
            self.values[row][i] = value * (i <= col)


class CCBlock(Block):
    def __init__(self, name: str, macro: int, shape):
        super().__init__(name, 128 + macro, shape)

    def message(self, *args: int):
        root_page = self.root.row_idx
        if len(args) < 2:
            args = args[0], 0
        control, ch = args
        value = args[2] if len(args) > 2 else self.value_at(control, ch)
        if root_page == 0:
            yield InternalMessage("xfade", control - self.macro, value)
        else:
            yield MacroMessage("synth", root_page - 1, control, value)


class StringBlock(CCBlock):
    def set(self, page: int, macro: int, *args: int):
        for channel, value in enumerate(args):
            self.update_value(macro, channel, value)
            if channel == page:
                yield MidiCC(channel, macro, value)

    def message(self, *args: int):
        if len(args) < 2:
            args = args[0], 0
        control, channel = args
        if channel in [6, 7]:
            return
        value = args[2] or self.value_at(control, channel)
        instr_idx = 1 + control - self.macro
        base = int(1 + control > 19) * 6
        macro = channel + base if channel < 6 else base
        values = [value] * (1 if channel != 8 else 6)
        if instr_idx == 4:  # master string volume (all instrs)
            for instr in range(1, instr_idx):
                yield StringMessage(instr, macro, *values)
        else:
            yield StringMessage(instr_idx, macro, *values)
        channels = [channel]
        if channel == 8:
            channels += [*range(0, 6)]
        controls = range(control - 3, control) if control in [19, 23] else [control]
        for ch in channels: # master channel
            for ctl in controls: # master knob [19, 23]
                if ctl != control and ch != channel:
                    yield MidiCC(ch, ctl, value)


class Pager(Block):
    def __init__(self, macros, *children: Block):
        if not isinstance(macros, tuple):
            macros = int(macros) - 1, int(macros)
        self.prev_macro, self.next_macro = macros
        super().__init__("_", self.next_macro, 1)
        self.children = [*children]

    @property
    def range(self):
        return [self.next_macro, self.prev_macro]

    def get(self, *args: int):
        if len(args) != 2:
            args = 0, *args
        page, macro = args
        if macro in self.range:
            return self
        for child in self.children:
            if isinstance(child, (Pager, Nav)):
                block = child.get(page, macro)
            else:
                block = child.get(macro)
            if block:
                return block

    @property
    def current(self):
        for block in self.children:
            yield from block.current

    @current.setter
    def current(self, note, *_):
        for block in self.children:
            if note == self.next_macro:
                for _ in block.next():
                    pass
            elif note == self.prev_macro:
                for _ in block.previous():
                    pass

    def message(self, _):
        return
        yield


class Nav(Block):
    children: list[list[Block]] = []

    def __init__(self, name: str, macro: int, shape: int, *children: Block):
        super().__init__(name, macro, (shape, 1))
        self.max_row_page = shape - 1
        self.children = [[] * len(children)] * self.row_size

        for i in range(0, self.row_size):
            self.children[i] = [self.from_block(block) for block in children]

    @Block.current.getter
    def current(self):
        yield from super(Nav, self).current
        for block in self.children[self.row_idx]:
            yield from block.current

    def from_block(self, block: "Union[Block, Pager, Nav, CCBlock]"):
        if isinstance(block, Nav):
            shape = len(block.children)
            fresh = Nav(block.name, block.macro, shape, *block.children[0])
        elif isinstance(block, Pager):
            macros = block.next_macro, block.prev_macro
            fresh = Pager(macros, *block.children)
        elif isinstance(block, CCBlock):
            shape = len(block.values), len(block.values[0])
            fresh = CCBlock(block.name, block.macro - 128, shape)
        else:
            shape = len(block.values), len(block.values[0])
            fresh = Block(block.name, block.macro, shape)
        fresh.parent = self
        return fresh

    def update_value(self, *args: int):
        if len(args) < 3:
            args = args[0], 0, args[1]
        super().update_value(*args)
        row, col = args[0:2]
        if self.values[row][col] > 0:
            for i, cols in enumerate(self.values):
                self.values[i][col] = cols[col] * (i == row)

    def get(self, *args: int):
        """Get a block by its index, looking through children too"""
        if len(args) == 1:
            args = 0, args[0]
        page, macro = args[0:2]
        if macro in self.range:
            return self
        for child in self.children[page]:
            block = child.get(macro)
            if block:
                return block

    def set(self, *args: int):
        if len(args) == 2:
            args = 0, *args
        page, macro, *rest = args
        block = self.get(page, macro)
        if block:
            block.update_value(macro - block.macro, *rest)
            if page == self.row_idx:
                yield from block.current

    def message(self, *args: int):
        if not self.empty(*args):
            row_idx = args[0] - self.macro
            if row_idx != self.row_idx:
                self.row_idx = clip(row_idx, 0, self.max_row_page)
                yield from self.current
