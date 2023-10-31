import threading
import logging
import reactivex.operators as ops
import reactivex.disposable as dsp
import reactivex.scheduler as sch
from reactivex import Observable, from_iterable, merge, never, of
from reactivex.abc import DisposableBase
from reactivex.subject import BehaviorSubject
from typing import Iterable, MutableSet
from midi import InternalMessage

event_loop = sch.EventLoopScheduler()


class Bridge(BehaviorSubject[InternalMessage]):
    _subs: MutableSet[DisposableBase] = set()

    def __init__(self, name):
        super(Bridge, self).__init__(InternalMessage("init"))
        self.name = name

    def __del__(self):
        for sub in self.subs:
            sub.dispose()

    @property
    def subs(self):
        return self._subs

    @subs.setter
    def subs(self, sub):
        self._subs.add(sub)

    def to_messages(self, msg):
        if msg is None:
            return never()
        method = getattr(self, "_" + msg.type + "_in")
        messages = method(msg) if method is not None else None

        if isinstance(messages, Observable):
            return messages
        if isinstance(messages, Iterable):
            return from_iterable(messages)
        if messages is not None:
            return of(messages)
        return never()

    @classmethod
    def start(cls, *devices: "Bridge"):
        stop_event = threading.Event()

        def on_complete():
            stop_event.set()

        def on_error(e):
            logging.error(e)

        for dev in devices:
            dev.subs = merge(*(dev.attach(d) for d in devices)).subscribe(
                on_error=on_error,
                on_completed=on_complete,
                scheduler=event_loop,
            )
        logging.info("[MID] Connected & started")
        return stop_event

    def attach(self, device: "Bridge"):
        return (
            Observable(self.subscriber)
            if self.name == device.name
            else device.pipe(
                ops.filter(self.external_message),
                ops.flat_map(self.to_messages),
                ops.map(self.send),
            )
        )

    def debug(self, msg):
        if msg is not None:
            logging.debug(
                "[IN] %s message from %s: %s",
                msg.type.capitalize(),
                self.name,
                msg.dict(),
            )

    def subscriber(self, _, __):
        return dsp.SingleAssignmentDisposable()

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
