import os
import time
import logging
import mido
from typing import Callable, Tuple, Union, MutableSet, overload
from reactivex import operators as ops, merge, from_iterable, of, timer
from reactivex.abc import DisposableBase
from reactivex.observable import GroupedObservable, Observable
from reactivex.scheduler import TimeoutScheduler, CurrentThreadScheduler
from midi import Metronome, InternalMessage
from utils import doubleclick

MIDO_BACKEND = os.environ.get("__MIDO_BACKEND__", "mido.backends.portmidi")
mido.set_backend(MIDO_BACKEND, load=True)
logging.info("Midi Backend started on %s", MIDO_BACKEND)
(logging.debug("Found device %s", d) for d in mido.get_ioport_names())  # type: ignore


def connect(port: str, timeout=3) -> Tuple[mido.ports.BaseInput, mido.ports.BaseOutput]:
    try:
        return mido.open_input(port), mido.open_output(port)  # type: ignore
    except SystemError:
        time.sleep(timeout)
        return connect(port, timeout)


ct_scheduler = CurrentThreadScheduler()
ts_scheduler = TimeoutScheduler()


class MidiDevice(Metronome):
    def __init__(self, port, external=None):
        super(MidiDevice, self).__init__(InternalMessage("init", 0))
        self.name = port[0:8]
        self.inport, self.outport = connect(port)
        self.channel = 0
        self.subs: MutableSet[DisposableBase] = set()
        if isinstance(external, MidiDevice):
            self.external = external
        logging.info("[MID] %s connected via %s", self.name, MIDO_BACKEND)

    def __del__(self):
        if self.inport is not None and not self.inport.closed:
            self.inport.close()
        if self.outport is not None and not self.outport.closed:
            self.outport.close()
        for sub in self.subs:
            sub.dispose()

    def start(self):
        select_clock = lambda msg: msg.type == "clock"
        clock, messages = from_iterable(self.inport.__iter__()).pipe(
            ops.do_action(self.debug), ops.partition(select_clock)
        )
        clock = clock.pipe(ops.map(self._clock_in), ops.observe_on(ct_scheduler))

        is_cc = lambda m: m.is_cc()
        cc, rest = messages.pipe(ops.partition(is_cc))

        gate = lambda msg: msg.is_cc() and msg.control == 23
        last = (
            lambda src: lambda msg: msg.is_cc()
            and msg.control == src.control - 1
            and msg.channel == src.channel
        )
        gate_control = lambda m: cc.pipe(ops.filter(last(m))) if gate(m) else of(m)
        throttle_control = lambda obs: obs.pipe(
            ops.throttle_with_mapper(gate_control),
            ops.throttle_first(0.25),
        )
        channel_key = lambda msg: msg.channel
        controls = cc.pipe(ops.group_by(channel_key), ops.map(throttle_control))

        to_action = lambda msg: getattr(self, "_" + msg.type + "_in")(msg)
        all = merge(controls, rest).pipe(
            ops.flat_map(to_action), ops.observe_on(ts_scheduler)
        )

        self.subs.add(merge(clock, all).pipe(ops.filter(bool)).subscribe(self.send))

    def send(self, msg):
        try:
            if isinstance(msg, InternalMessage):
                self.on_next(msg)
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
            logging.debug("Stacktrace %s", e.with_traceback(None))

    def receive(self, _):
        return NotImplemented

    def debug(self, msg):
        if msg.type != "clock":
            logging.debug(
                "[IN] %s message from %s: %s",
                msg.type.capitalize(),
                self.name,
                msg.dict(),
            )

    @overload
    def on(self, event: str, cb: Callable) -> DisposableBase:
        ...

    @overload
    def on(self, event: str) -> Observable[Tuple[int, ...]]:
        ...

    def on(
        self, event: str, cb=None
    ) -> Union[DisposableBase, Observable[Tuple[int, ...]]]:
        obs = self.pipe(
            ops.as_observable(),
            ops.filter(lambda ev: ev.command.find(event) >= 0),
            ops.map(lambda ev: ev.values),
        )
        if cb is None:
            return obs
        sub = obs.subscribe(cb)
        self.subs.add(sub)
        return sub

    def sync(self, event: str, obs: Observable, cb: Callable):
        self.subs.add(self.on(event).pipe(ops.buffer(obs)).subscribe(cb))

    @doubleclick(0.4)
    def shutdown(self):
        logging.debug("[IN] Shutdown signal")
        os.system("sudo shutdown now")
