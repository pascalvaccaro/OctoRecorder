import os
import time
import logging
import mido
from typing import Tuple, Optional, Union
from reactivex import from_iterable, disposable as dsp, Observer, scheduler as sch
from reactivex.abc import SchedulerBase, ObserverBase

from midi.messages import clean_messages, InternalMessage, MidiMessage
from utils import doubleclick, Bridge

MIDO_BACKEND = os.environ.get("__MIDO_BACKEND__", "mido.backends.portmidi")
mido.set_backend(MIDO_BACKEND, load=True)
logging.info("[MID] Midi Backend started on %s", MIDO_BACKEND)


def connect(port: str, timeout=3) -> Tuple[mido.ports.BaseInput, mido.ports.BaseOutput]:
    try:
        return mido.open_input(port), mido.open_output(port)  # type: ignore
    except SystemError:
        time.sleep(timeout)
        return connect(port, timeout)


class MidiDevice(Bridge):
    def __init__(self, port):
        self.channel = 0
        self.name: str = port[0:8]
        self.inport, self.outport = connect(port)
        super(MidiDevice, self).__init__(self.name)
        logging.info("[MID] %s connected via %s", self.name, MIDO_BACKEND)

    def __del__(self):
        if self.inport is not None and not self.inport.closed:
            self.inport.close()
        if self.outport is not None and not self.outport.closed:
            self.outport.close()
        super(MidiDevice, self).__del__()

    @property
    def is_closed(self):
        return self.inport.closed

    def subscriber(
        self,
        final: ObserverBase[Union[InternalMessage, MidiMessage]],
        scheduler: Optional[SchedulerBase] = None,
    ):
        disp = dsp.MultipleAssignmentDisposable()

        def on_error(e):
            final.on_error(e)
            return True

        def scheduled_action(sched, state=None):
            if state is None:
                state = dsp.MultipleAssignmentDisposable()
            if self.is_closed:
                final.on_completed()
                state.dispose()
                return state

            proxy = Observer(self.send, final.on_error)
            disp = dsp.CompositeDisposable(state.disposable)
            pending = list(filter(self.select_message, self.inport.iter_pending()))

            while len(pending) > 0:
                item: Union[MidiMessage, InternalMessage] = pending.pop()
                self.debug(item)
                disp.add(self.to_messages(item).subscribe(proxy, scheduler=sched))
                pending = clean_messages(item, pending)

            if isinstance(sched, SchedulerBase):
                disp.add(sched.schedule_relative(0.12, scheduled_action, state))

            state.disposable = disp
            return state

        sched = sch.CatchScheduler(scheduler or sch.EventLoopScheduler(), on_error)
        disp.disposable = from_iterable(self.init_actions, sched).subscribe(self.send)
        return scheduled_action(sched, disp)

    def send(self, msg):
        if msg is None:
            return
        try:
            if isinstance(msg, tuple):
                msg = msg[0]
            log = [msg.type.capitalize(), self.name, msg.dict()]
            if isinstance(msg, InternalMessage):
                self.on_next(msg)
                log.insert(0, "[SUB] %s message through %s: %s")
            elif isinstance(msg, MidiMessage):
                self.outport.send(msg)
                log.insert(0, "[OUT] %s message to %s: %s")
            logging.debug(*log)
        except Exception as e:
            logging.error("[OUT] %s %s", self.name, e)

    @doubleclick(0.4)
    def shutdown(self):
        os.system("sudo shutdown now")
