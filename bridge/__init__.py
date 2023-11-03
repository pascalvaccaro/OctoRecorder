import os
import logging
import threading
import reactivex as rx
import reactivex.operators as ops
from reactivex.abc import DisposableBase
from reactivex.disposable import SingleAssignmentDisposable
from reactivex.scheduler import EventLoopScheduler
from reactivex.subject import BehaviorSubject
from typing import Iterable, MutableSet
from midi import InternalMessage
from utils import doubleclick


class Bridge(BehaviorSubject[InternalMessage]):
    _subs: MutableSet[DisposableBase] = set()
    _loop = EventLoopScheduler()

    def __init__(self, name):
        super(Bridge, self).__init__(InternalMessage("init"))
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

    @classmethod
    def start(cls, *devices: "Bridge"):
        stop_event = threading.Event()

        def on_complete():
            stop_event.set()

        def on_error(e):
            logging.error(e)

        for dev in devices:
            dev.subs = rx.merge(*(dev.attach(d) for d in devices)).subscribe(
                on_error=on_error,
                on_completed=on_complete,
                scheduler=Bridge._loop,
            )
        logging.info("[ALL] Connected & started %i devices", len(devices))
        return stop_event

    def attach(self, device: "Bridge"):
        return (
            rx.Observable(self.subscriber)
            if self.name == device.name
            else device.pipe(
                ops.filter(self.external_message),
                ops.flat_map(self.to_messages),
                ops.map(self.send),
            )
        )

    @doubleclick(0.4)
    def shutdown(self):
        self.on_completed()
        os.system("sudo shutdown now")

    def debug(self, msg):
        if msg is not None:
            logging.debug(
                "[IN] %s message from %s: %s",
                msg.type.capitalize(),
                self.name,
                msg.dict(),
            )

    def subscriber(self, _, __):
        return SingleAssignmentDisposable()

    def send(self, _):
        return None

    @property
    def init_actions(self):
        return []

    @property
    def is_closed(self):
        return False

    @property
    def select_message(self):
        return NotImplemented

    @property
    def external_message(self):
        return NotImplemented
