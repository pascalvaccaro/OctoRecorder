import logging
import mido
from typing import Optional, Union
from reactivex import from_iterable, Observer
from reactivex.abc import SchedulerBase, ObserverBase
from reactivex.disposable import MultipleAssignmentDisposable, CompositeDisposable
from reactivex.scheduler import CatchScheduler

from midi.messages import clean_messages, InternalMessage, MidiMessage, ControlException
from midi.server import MidiServer
from utils import retry
from bridge import Bridge


class MidiDevice(Bridge):
    def __init__(self, name, port=None):
        super(MidiDevice, self).__init__(name[0:8])
        self.channel = 0
        self.inport: mido.ports.BaseInput = retry(mido.open_input, [name])  # type: ignore
        self.outport: mido.ports.BaseOutput = retry(mido.open_output, [name])  # type: ignore
        self.server = MidiServer(port)
        logging.info("[MID] %s connected", self.name)

    @property
    def is_closed(self):
        return self.inport.closed

    def __del__(self):
        super().__del__()
        if self.inport is not None and not self.inport.closed:
            self.inport.close()
        if self.outport is not None and not self.outport.closed:
            self.outport.close()

    def subscriber(
        self,
        final: ObserverBase[Union[InternalMessage, MidiMessage]],
        scheduler: Optional[SchedulerBase] = None,
    ):
        disp = MultipleAssignmentDisposable()

        def on_error(e):
            final.on_error(e)
            return True

        def scheduled_action(sched, state=None):
            if not isinstance(state, MultipleAssignmentDisposable):
                state = MultipleAssignmentDisposable()
            if self.is_closed:
                final.on_completed()
                state.dispose()
                return state

            proxy = Observer(self.send, final.on_error)
            disp = CompositeDisposable(state.disposable)
            midi_in = [m for m in self.inport.iter_pending() if m.type != "clock"]
            (self.server.send(msg) for msg in midi_in)
            client_in = []
            for port in self.server:
                client_in += [m for m in port.iter_pending()]
            all_messages: "list[MidiMessage]" = [*midi_in, *client_in]
            messages = [m for m in all_messages if self.select_message(m)]

            while len(messages) > 0:
                item = messages.pop()
                disp.add(self.to_messages(item).subscribe(proxy, scheduler=sched))
                try:
                    messages = clean_messages(item, messages)
                except ControlException as e:
                    self.channel = e.channel
                    messages.clear()
                finally:
                    self.debug(item)

            if isinstance(sched, SchedulerBase):
                disp.add(sched.schedule_relative(0.12, scheduled_action, state))

            state.disposable = disp
            return state

        sched = CatchScheduler(scheduler or self._loop, on_error)
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
