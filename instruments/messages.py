class InternalMessage(object):
    def __init__(self, type: str, *args):
        super(InternalMessage, self).__init__()
        self.type = type
        self.data = tuple(args)

    def dict(self):
        return list(self.data)

    def is_cc(self):
        return False

    def bytes(self):
        return list(self.data)

    @classmethod
    def to_internal_message(cls, msg):
        if msg is None:
            return
        if msg.type == "sysex":
            return InternalMessage(msg.type, *msg.bytes()[1:-1])
        elif msg.type == "program_change":
            return InternalMessage(msg.type, msg.channel, msg.program)  # type: ignore
        elif msg.type == "stop":
            return InternalMessage(msg.type)


class MacroMessage(InternalMessage):
    def __init__(self, typ, *args: int):
        super().__init__(typ, *args)
        self.idx, self.macro, self.value = [int(d) for d in args[0:3]]


class StepMessage(MacroMessage):
    def __init__(self, *args):
        super().__init__("steps", *args)
        self.steps: list[list[int]] = list(args[3:])


class StringMessage(MacroMessage):
    def __init__(self, *args: int):
        super().__init__("strings", *args)
        self.values = [int(d) for d in args[2:]]
