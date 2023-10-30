import os
import threading
import time
import logging
import mido
from collections.abc import Iterable
from typing import Callable, MutableSet, Optional, Tuple, Union, overload, List, Any
from reactivex import Observer, Observable, from_iterable, merge, never, of
from reactivex.abc import DisposableBase, ObserverBase, SchedulerBase
from reactivex.subject import BehaviorSubject
import reactivex.operators as ops
import reactivex.disposable as dsp
import reactivex.scheduler as sch

from midi.messages import InternalMessage
from midi.beat import loop as event_loop
from utils import doubleclick

MIDO_BACKEND = os.environ.get("__MIDO_BACKEND__", "mido.backends.portmidi")
mido.set_backend(MIDO_BACKEND, load=True)
logging.info("[MID] Midi Backend started on %s", MIDO_BACKEND)
(logging.debug("[MID] Found device %s", d) for d in mido.get_ioport_names())  # type: ignore


def connect(
    port: str, timeout=3
) -> Tuple[mido.ports.BaseInput, mido.ports.BaseOutput,]:
    try:
        return mido.open_input(port), mido.open_output(port)  # type: ignore
    except SystemError:
        time.sleep(timeout)
        return connect(port, timeout)


class MidiDevice(object):
    _suspend = None
    _subs: MutableSet[DisposableBase] = set()
    _devices: MutableSet["MidiDevice"] = set()

    def __init__(self, port):
        super(MidiDevice, self).__init__()
        self.channel = 0
        self.name: str = port[0:8]
        self.inport, self.outport = connect(port)
        self.bridge = BehaviorSubject(InternalMessage("init", 0))
        MidiDevice._devices.add(self)
        logging.info("[MID] %s connected via %s", self.name, MIDO_BACKEND)

    def __del__(self):
        if self.inport is not None and not self.inport.closed:
            self.inport.close()
        if self.outport is not None and not self.outport.closed:
            self.outport.close()
        for sub in self.subs:
            sub.dispose()

    @property
    def subs(self):
        return self._subs

    @subs.setter
    def subs(self, sub):
        self._subs.add(sub)

    @property
    def suspend(self):
        return self._suspend

    @suspend.setter
    def suspend(self, value: Union[Callable[[Any], bool], None]):
        self._suspend = value

    def messages(self, msg):
        if msg is None:
            return never()
        if self.suspend is not None:
            if self.suspend(msg):
                self.suspend = None
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

    def observer(
        self,
        final: ObserverBase[mido.messages.Message],
        scheduler: Optional[SchedulerBase] = event_loop,
    ):
        def on_error(e):
            final.on_error(e)
            return True

        def action(sched, state=None):
            if state is None:
                state = dsp.MultipleAssignmentDisposable()
            if self.inport.closed:
                final.on_completed()
                state.dispose()
                return state
            proxy = Observer(self.send, final.on_error)
            disp = dsp.CompositeDisposable(state.disposable)
            for item in self.inport.iter_pending():
                if self.select_message(item):
                    self.debug_in(item)
                    disp.add(self.messages(item).subscribe(proxy, scheduler=sched))
            if isinstance(sched, SchedulerBase):
                state.disposable = dsp.CompositeDisposable(
                    disp.disposable, sched.schedule_relative(0.12, action, state)
                )
            return state

        sched = sch.CatchScheduler(scheduler or event_loop, on_error)
        disp = dsp.MultipleAssignmentDisposable()
        disp.disposable = from_iterable(self.init_actions, sched).subscribe(self.send)
        return action(sched, disp)

    @classmethod
    def start(cls, debug=False):
        stop_event = threading.Event()

        def on_complete():
            stop_event.set()

        def on_error(e):
            logging.error(e)
            if debug:
                stop_event.set()
                raise e

        for dev in cls._devices:
            dev.subs = merge(*(dev.attach(d) for d in cls._devices)).subscribe(
                on_error=on_error,
                on_completed=on_complete,
                scheduler=event_loop,
            )
        logging.info("[MID] Connected & started")
        return stop_event

    def attach(self, device: "MidiDevice"):
        return (
            Observable(self.observer)
            if self.name == device.name
            else device.bridge.pipe(
                ops.filter(self.external_message),
                ops.flat_map(self.messages),
                ops.map(self.send),
            )
        )

    @overload
    def on(self, event: Union[str, List[str]], cb: Callable) -> None:
        ...

    @overload
    def on(
        self, event: Union[str, List[str]], cb: Callable, signal: Observable[int]
    ) -> None:
        ...

    @overload
    def on(self, event: Union[str, List[str]]) -> Observable[Tuple[int, ...]]:
        ...

    def on(
        self, event: Union[str, List[str]], cb=None, signal=None
    ) -> Union[None, Observable[Tuple[int, ...]]]:
        if isinstance(event, list):
            event = ":".join(event)
        obs = self.bridge.pipe(
            ops.filter(lambda ev: ev.type in event),
            ops.map(lambda ev: ev.data),
        )
        if signal:
            obs = obs.pipe(ops.buffer(signal), ops.map(lambda b: b.pop()))
        if cb is None:
            return obs
        self.subs = obs.subscribe(cb)

    def send(self, msg):
        if isinstance(msg, tuple):
            msg = msg[0]
        try:
            if msg is not None:
                if isinstance(msg, InternalMessage):
                    self.bridge.on_next(msg)
                elif isinstance(msg, mido.messages.Message):
                    if self.outport is None or self.outport.closed:
                        logging.warning(
                            "[OUT] No device %s, skipping message: %d",
                            self.name,
                            msg.dict(),
                        )
                    else:
                        self.outport.send(msg)
        except Exception as e:
            logging.error("[OUT] %s %s", self.name, e)

    def debug_in(self, msg):
        if msg is None:
            return
        logging.debug(
            "[IN] %s message from %s: %s",
            msg.type.capitalize(),
            self.name,
            msg.dict(),
        )

    def debug_out(self, msg):
        if msg is None:
            return
        if isinstance(msg, tuple):
            msg = msg[0]
        log = [msg.type.capitalize(), self.name, msg.dict()]
        if isinstance(msg, InternalMessage):
            log.insert(0, "[SUB] %s message through %s: %s")
        elif isinstance(msg, mido.messages.Message):
            log.insert(0, "[OUT] %s message to %s: %s")
        logging.debug(*log)

    @doubleclick(0.4)
    def shutdown(self):
        os.system("sudo shutdown now")

    @property
    def init_actions(self):
        return []

    @property
    def select_message(self) -> Callable[[Union[InternalMessage, None]], bool]:
        return NotImplemented

    @property
    def external_message(self) -> Callable[[Union[InternalMessage, None]], bool]:
        return NotImplemented
