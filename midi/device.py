import logging
import mido
from reactivex.abc import ObserverBase
from typing import Union

from bridge import Bridge
from midi.messages import MidiMessage, MidoMessage
from midi.server import MidiServer
from midi.scheduler import MidiScheduler
from instruments.messages import InternalMessage
from utils import retry


class MidiDevice(Bridge):
    scheduler = MidiScheduler()

    def __init__(self, port: Union[str, "MidiDevice"], portno=None):
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

    @property
    def messages(self) -> list[MidoMessage]:
        midi_in = [
            m for m in self.inport.iter_pending() if m.type not in ["clock", "start"]
        ]
        for msg in midi_in:
            self.server.send(msg)
        client_in = []
        for port in self.server:
            client_in += [m for m in port.iter_pending()]
        return [m for m in [*midi_in, *client_in] if self.select_message(m)]

    def __del__(self):
        super().__del__()
        if self.inport is not None and not self.inport.closed:
            self.inport.close()
        if self.outport is not None and not self.outport.closed:
            self.outport.close()

    def receive(self, observer: ObserverBase[MidoMessage], scheduler: MidiScheduler):
        return scheduler.schedule_in(self, observer)

    def send(self, msg):
        try:
            if isinstance(msg, InternalMessage):
                self.on_next(msg)
                debug_infos = [self.name, msg.type.capitalize(), msg.dict()]
                logging.debug("%s %s message THRU: %s", *debug_infos)
            elif isinstance(msg, MidiMessage):
                MidiDevice.scheduler.schedule_out(self.send_action, msg)
            else:
                super().send(msg)
        except Exception as e:
            logging.error("%s error OUT", self.name)
            logging.exception(e)

    def send_action(self, _, msg):
        if msg is not None:
            self.outport.send(msg)
            debug_infos = [self.name, msg.type.capitalize(), msg.dict()]
            logging.debug("%s %s message OUT: %s", *debug_infos)

    def debug(self, msg):
        if msg is not None:
            debug_infos = [self.name, msg.type.capitalize(), msg.dict()]
            logging.debug("%s %s message IN: %s", *debug_infos)
