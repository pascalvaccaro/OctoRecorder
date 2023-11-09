import logging
import reactivex as rx
import reactivex.operators as ops
from reactivex.abc import DisposableBase
from reactivex.disposable import SingleAssignmentDisposable
from reactivex.subject import Subject
from typing import MutableSet
from utils import doubleclick, to_observable


class Bridge(Subject):
    _subs: MutableSet[DisposableBase] = set()

    def __init__(self, name):
        super(Bridge, self).__init__()
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
        method = "_" + msg.type + "_in"
        if not hasattr(self, method):
            return rx.never()
        messages = getattr(self, method)(msg)
        return to_observable(messages)
        

    def connect(self, device: "Bridge"):
        return (
            rx.Observable(self.receive)
            if self.name == device.name
            else device.pipe(
                ops.filter(self.external_message), ops.flat_map(self.to_messages)
            )
        )

    @doubleclick(0.4)
    def shutdown(self):
        logging.info("[ALL] Shutting down")
        self.on_completed()

    def receive(self, _, __):
        return SingleAssignmentDisposable()

    def send(self, _):
        return

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
