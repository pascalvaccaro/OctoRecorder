import os
import time
import logging
import mido
from collections.abc import Iterable
from typing import Callable, MutableSet, Tuple, Union, overload, List, Any
import reactivex.operators as ops
import reactivex.scheduler as sch
from reactivex import Observable, from_iterable, never, of
from reactivex.abc import DisposableBase
from reactivex.subject import BehaviorSubject


from midi import Metronome, InternalMessage
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

    def __init__(self, port):
        super(MidiDevice, self).__init__()
        self.name = port[0:8]
        self.inport, self.outport = connect(port)
        self.bridge = BehaviorSubject(InternalMessage("init", 0))
        self.channel = 0
        self.subs: MutableSet[DisposableBase] = set()
        self.subs.add(self.messages)
        logging.info("[MID] %s connected via %s", self.name, MIDO_BACKEND)

    def __del__(self):
        if self.inport is not None and not self.inport.closed:
            self.inport.close()
        if self.outport is not None and not self.outport.closed:
            self.outport.close()
        for sub in self.subs:
            sub.dispose()

    @property
    def suspend(self):
        return self._suspend

    @suspend.setter
    def suspend(self, value: Union[Callable[[Any], bool], None]):
        self._suspend = value

    @property
    def scheduler(self):
        return sch.CurrentThreadScheduler()

    @property
    def to_action(self):
        event_loop = sch.EventLoopScheduler()

        def wrapped(msg: Union[InternalMessage, None]) -> Observable[InternalMessage]:
            if msg is None:
                return never()
            if self.suspend is not None:
                if self.suspend(msg):
                    self.suspend = None
                return never()
            action = getattr(self, "_" + msg.type + "_in")
            source = action(msg) if action is not None else None
            observer = ops.observe_on(event_loop)

            if isinstance(source, Observable):
                return source.pipe(observer)
            if isinstance(source, Iterable):
                return from_iterable(source).pipe(observer)
            if source is not None:
                return of(source).pipe(observer)
            return never()

        return wrapped

    @property
    def messages(self):
        logging.info("[MID] Listening to messages from %s", self.name)
        return (
            from_iterable(self.inport, sch.EventLoopScheduler())
            .pipe(
                ops.filter(self.select_message),
                ops.do_action(self.debug),
                ops.flat_map(self.to_action),
                ops.start_with(*self.init_actions),
            )
            .subscribe(self.send, scheduler=self.scheduler)
        )

    def bind(self, device: "MidiDevice"):
        self.subs.add(
            device.bridge.pipe(
                ops.filter(self.external_message),
                ops.flat_map(self.to_action),
            ).subscribe(self.send, scheduler=self.scheduler)
        )

    @overload
    def on(self, event: Union[str, List[str]], cb: Callable) -> None:
        ...

    @overload
    def on(self, event: Union[str, List[str]], cb: Callable, signal: str) -> None:
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
            obs = obs.pipe(ops.buffer(self.on(signal)), ops.map(lambda b: b.pop()))
        return obs if cb is None else self.subs.add(obs.subscribe(cb))

    def send(self, msg):
        try:
            if isinstance(msg, tuple):
                msg = msg[0]
            if msg is not None:
                log = [msg.type.capitalize(), self.name, msg.dict()]
                if isinstance(msg, InternalMessage):
                    log.insert(0, "[SUB] %s message through %s: %s")
                    self.bridge.on_next(msg)
                elif isinstance(msg, mido.messages.Message):
                    if self.outport is None or self.outport.closed:
                        logging.warning(
                            "[OUT] No device %s, skipping message: %d",
                            self.name,
                            msg.dict(),
                        )
                    else:
                        log.insert(0, "[OUT] %s message to %s: %s")
                        self.outport.send(msg)
                if msg.type not in ["beat", "note_on", "note_off"]:  # type: ignore
                    logging.debug(*log)
        except Exception as e:
            logging.error("[OUT] %s %s", self.name, e)

    @property
    def debug(self):
        return (
            lambda msg: logging.debug(
                "[IN] %s message from %s: %s",
                msg.type.capitalize(),
                self.name,
                msg.dict(),
            )
            if msg.type not in ["clock", "beat", "note_on", "note_off"]
            else None
        )

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
