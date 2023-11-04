import os
from typing import Iterator
import logging
import mido


class ClientSet(set):
    def __iter__(self) -> Iterator[mido.sockets.SocketPort]:
        for client in super().__iter__():
            if client.closed:
                logging.warn("%s disconnected", client.name)
                self.remove(client)
        return super().__iter__()


HOSTNAME = os.environ.get("__HOST_NAME__", "localhost")


class MidiServer(mido.sockets.PortServer):
    def __init__(self, portno=None):
        super().__init__(HOSTNAME, portno)
        self.clients = ClientSet()
        logging.info("[NET] Started midi server on %s:%i", HOSTNAME, portno)

    def __iter__(self):
        new_client = self.accept(block=False)
        if new_client:
            logging.info("Connection from %s", new_client.name)
            self.clients.add(new_client)
        return self.clients.__iter__()

    def __del__(self):
        if not self.closed:
            self.close()
