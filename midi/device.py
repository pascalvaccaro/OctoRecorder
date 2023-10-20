import os
import time
import logging
import mido
from typing import Callable, Tuple, Union, overload
from reactivex import (
    Observable,
    from_iterable,
    operators as ops,
    scheduler as sch,
)
from reactivex.subject import BehaviorSubject

from midi import Metronome, InternalMessage
from utils import doubleclick

MIDO_BACKEND = os.environ.get("__MIDO_BACKEND__", "mido.backends.portmidi")
mido.set_backend(MIDO_BACKEND, load=True)
logging.info("Midi Backend started on %s", MIDO_BACKEND)
(logging.debug("Found device %s", d) for d in mido.get_ioport_names())  # type: ignore


def connect(port: str, timeout=3) -> Tuple[mido.ports.BaseInput, mido.ports.BaseOutput,]:
    try:
        return mido.open_input(port), mido.open_output(port)  # type: ignore
    except SystemError:
        time.sleep(timeout)
        return connect(port, timeout)


timeout_scheduler = sch.TimeoutScheduler()


class MidiDevice(Metronome):
    _suspend = None

    def __init__(self, port, external=None):
        super(MidiDevice, self).__init__()
        self.name = port[0:8]
        self.inport, self.outport = connect(port)
        self.bridge = BehaviorSubject(InternalMessage("init", 0))
        self.channel = 0
        if isinstance(external, MidiDevice):
            self.external = external
        logging.info("[MID] %s connected via %s", self.name, MIDO_BACKEND)

    def __del__(self):
        if self.inport is not None and not self.inport.closed:
            self.inport.close()
        if self.outport is not None and not self.outport.closed:
            self.outport.close()

    @property
    def suspend(self):
        return self._suspend

    @suspend.setter
    def suspend(self, value: Union[Callable, None]):
        self._suspend = value

    @property
    def to_action(self):
        def wrapped(msg):
            action = getattr(self, "_" + msg.type + "_in")
            if self.suspend is not None:
                if self.suspend(msg):
                    self.suspend = None
                yield
            elif action is not None:
                yield from action(msg)

        return wrapped

    @property
    def messages(self):
        logging.info("[MID] Listening to messages from %s", self.name)
        return from_iterable(self.inport, scheduler=sch.NewThreadScheduler()).pipe(
            ops.filter(self.select_messages),
            ops.do_action(self.debug),
            ops.flat_map(self.to_action),
            ops.filter(bool),
        )

    @overload
    def on(self, event: str, cb: Callable) -> None:
        ...

    @overload
    def on(self, event: str) -> Observable[Tuple[int, ...]]:
        ...

    def on(self, event: str, cb=None) -> Union[None, Observable[Tuple[int, ...]]]:
        obs = self.bridge.pipe(
            ops.filter(lambda ev: event in ev.command),
            ops.map(lambda ev: ev.values),
        )
        return obs if cb is None else self.subs.add(obs.subscribe(cb))

    def sync(self, event: str, sync: str, cb: Callable):
        self.subs.add(
            self.on(event)
            .pipe(ops.buffer(self.on(sync)), ops.filter(lambda b: len(b) > 0))
            .subscribe(cb)
        )

    def send(self, msg):
        try:
            if isinstance(msg, InternalMessage):
                logging.debug(
                    "[OUT] %s message from %s: %s",
                    msg.command.capitalize(),
                    self.name,
                    msg.values,
                )
                self.bridge.on_next(msg)
            elif isinstance(msg, mido.messages.Message):
                if (
                    self.outport is None
                    or self.outport.closed
                    or self.outport.name is None
                ):
                    logging.warning(
                        "[OUT] No device %s, skipping message: %d",
                        self.name,
                        msg.dict(),
                    )
                else:
                    logging.debug(
                        "[OUT] %s message to %s: %s",
                        msg.type.capitalize(),  # type: ignore
                        self.name,
                        msg.dict(),
                    )
                    self.outport.send(msg)
        except Exception as e:
            logging.error("[OUT] %s %s", self.name, e)

    def debug(self, msg):
        if msg.type != "clock":
            logging.debug(
                "[IN] %s message from %s: %s",
                msg.type.capitalize(),
                self.name,
                msg.dict(),
            )

    @doubleclick(0.4)
    def shutdown(self):
        os.system("sudo shutdown now")

    @property
    def select_messages(self):
        return NotImplemented
