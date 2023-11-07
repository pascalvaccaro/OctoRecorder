import logging
import reactivex as rx
import reactivex.operators as ops
from reactivex.abc import DisposableBase
from reactivex.disposable import SingleAssignmentDisposable
from reactivex.subject import BehaviorSubject
from typing import Iterable, MutableSet
from midi import InternalMessage
from utils import doubleclick


class Bridge(BehaviorSubject[InternalMessage]):
    _subs: MutableSet[DisposableBase] = set()

    def __init__(self, name):
        super(Bridge, self).__init__(InternalMessage("init", name))
        self.name = name

    @property
    def subs(self):
        return self._subs

    @subs.setter
    def subs(self, sub):
        self._subs.add(sub)

    def __del__(self):
        for sub in self.subs:
            sub.dispose()

    def to_messages(self, msg):
        if msg is None:
            return rx.never()
        method = getattr(self, "_" + msg.type + "_in")
        messages = method(msg) if method is not None else None

        if isinstance(messages, rx.Observable):
            return messages
        if isinstance(messages, Iterable):
            return rx.from_iterable(messages)
        if messages is not None:
            return rx.of(messages)
        return rx.never()

    def connect(self, device: "Bridge"):
        return (
            rx.Observable(self.receive)
            if self.name == device.name
            else device.pipe(
                ops.filter(self.external_message),
                ops.flat_map(self.to_messages),
                ops.map(self.send),
            )
        )

    @doubleclick(0.4)
    def shutdown(self):
        logging.info("[ALL] Shutting down")
        self.on_completed()

    def debug(self, msg):
        if msg is not None:
            debug_infos = [self.name, msg.type.capitalize(), msg.dict()]
            logging.debug("%s %s message IN: %s", *debug_infos)

    def receive(self, _, __):
        return SingleAssignmentDisposable()

    def send(self, msg):
        if isinstance(msg, InternalMessage):
            self.on_next(msg)
            debug_infos = [self.name, msg.type.capitalize(), msg.dict()]
            logging.debug("%s %s message THRU: %s", *debug_infos)

    @property
    def init_actions(self):
        return []

    @property
    def is_closed(self):
        return False

    @property
    def select_message(self):
        return lambda _: False

    @property
    def external_message(self):
        return lambda _: False
