import logging
import mido
from reactivex import from_iterable, Observer
from reactivex.abc import SchedulerBase, ObserverBase
from reactivex.disposable import MultipleAssignmentDisposable, CompositeDisposable

from bridge import Bridge
from midi.messages import clean_messages, InternalMessage, MidiMessage, ControlException
from midi.server import MidiServer
from utils import retry


class MidiDevice(Bridge):
    def __init__(self, port, portno=None):
        self.channel = 0
        if isinstance(port, str):
            super(MidiDevice, self).__init__("[MID] " + port[0:-7])
            self.inport: mido.ports.BaseInput = retry(mido.open_input, [port])  # type: ignore
            self.outport: mido.ports.BaseOutput = retry(mido.open_output, [port])  # type: ignore
            if isinstance(portno, int):
                self.server = MidiServer(portno)
            logging.info("%s connected", self.name)
        elif isinstance(port, MidiDevice):
            super(MidiDevice, self).__init__(port.name)
            self.inport = port.inport
            self.outport = port.outport
            self.server = port.server

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
        final: ObserverBase,
        scheduler: SchedulerBase,
    ):
        disp = MultipleAssignmentDisposable()
        disp.disposable = from_iterable(self.init_actions).subscribe(self.send)

        def action(sched: SchedulerBase, state=[]):
            if self.is_closed:
                final.on_completed()
                disp.dispose()
                return disp

            proxy = Observer(self.send, final.on_error)
            cdisp = CompositeDisposable(disp.disposable)
            midi_in = [
                m
                for m in self.inport.iter_pending()
                if m.type not in ["clock", "start"]
            ]
            (self.server.send(msg) for msg in midi_in)
            client_in = []
            for port in self.server:
                client_in += [m for m in port.iter_pending()]
            all_messages: "list[MidiMessage]" = [*midi_in, *client_in]
            messages = [m for m in all_messages if self.select_message(m)]

            while len(messages) > 0:
                item = messages.pop()
                if item.bytes() != state:
                    cdisp.add(self.to_messages(item).subscribe(proxy))
                try:
                    messages = clean_messages(item, messages)
                except ControlException as e:
                    self.channel = e.channel
                    messages.clear()
                finally:
                    self.debug(item)
                    state = item.bytes()

            cdisp.add(sched.schedule_relative(0.01, action, state))
            disp.disposable = cdisp
            return disp

        return action(scheduler, disp)

    def send(self, msg):
        if msg is None:
            return
        try:
            if isinstance(msg, tuple):
                msg = msg[0]
            log = [self.name, msg.type.capitalize(), msg.dict()]
            if isinstance(msg, InternalMessage):
                self.on_next(msg)
                log.insert(0, "%s %s message THRU: %s")
            elif isinstance(msg, MidiMessage):
                self.outport.send(msg)
                log.insert(0, "%s %s message OUT: %s")
            logging.debug(*log)
        except Exception as e:
            logging.error("%s error OUT %s", self.name, e)
