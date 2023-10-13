from typing import List, Tuple
from dotenv import load_dotenv

load_dotenv()
import os
import time
import logging
import mido

logging.basicConfig(
    level=os.environ.get("DEBUG", logging.INFO),
    format="%(asctime)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
SYNTH_DEVICE_NAME = os.environ.get("SYNTH_DEVICE", "SY-1000 MIDI 1")
CONTROL_DEVICE_NAME = os.environ.get("CONTROL_DEVICE", "Akai APC40 MIDI 1")
MIDO_BACKEND = os.environ.get("__MIDO_BACKEND__", "mido.backends.portmidi")
mido.set_backend(MIDO_BACKEND, load=True)

SYNTH_SYSEX_HEAD = [65, 0, 0, 0, 0, 105]
SYNTH_SYSEX_REQ = [*SYNTH_SYSEX_HEAD, 17]
SYNTH_SYSEX_CMD = [*SYNTH_SYSEX_HEAD, 18]
SYNTH_ADDRESSES = {"common": [0, 1], "patch": [16, 0]}


def clip(n, smallest=0, largest=127):
    return round(max(smallest, min(n, largest)))


def scroll(n, smallest=0, largest=127):
    if n < smallest:
        return largest
    if n > largest:
        return smallest
    return n


def throttle(s, *indexes):
    """Decorator ensures function that can only be called once every `s` seconds if `arg` is the same value."""

    def decorate(f):
        t = None
        l = [None] * (len(indexes) + 1)

        def wrapped(*args, **kwargs):
            nonlocal t
            nonlocal l
            t_ = time.time()
            for i in indexes:
                v = l[i]
                if args[i] != v or t is None or t_ - t >= s:
                    result = f(*args, **kwargs)
                    l[i] = args[i]
                    t = time.time()
                    return result
                l[i] = args[i]

        return wrapped

    return decorate


def doubleclick(s):
    """Decorator ensures function only runs if called twice under `s` seconds."""

    def decorate(f):
        start = time.time()

        def wrapped(*args, **kwargs):
            nonlocal start
            end = time.time()
            if end - start < s:
                return f(*args, **kwargs)
            start = time.time()

        return wrapped

    return decorate


def checksum(addr, data=[]):
    first = SYNTH_ADDRESSES[addr]
    try:
        result = 128 - sum(x if x is not None else 0 for x in [*first, *data]) % 128
        return [*first, *data, 0 if result == 128 else result]
    except Exception as e:
        logging.warning("Failed checksum", e)
        return [*first, *data, 0]


def get_instrument(control):
    if control == 16 or control == 20:
        return 21
    if control == 17 or control == 21:
        return 32
    if control == 18 or control == 22:
        return 43


def connect(
    timeout=3,
) -> Tuple[List[mido.ports.BaseInput], List[mido.ports.BaseOutput]]:
    try:
        ioports: List[str] = mido.get_ioport_names()
        for device in ioports:
            if device.startswith(SYNTH_DEVICE_NAME):
                logging.debug("Found SYNTH device %s", device)
            elif device.startswith(CONTROL_DEVICE_NAME):
                logging.debug("Found CONTROL device %s", device)
            else:
                logging.debug("Found device %s", device)
        inports = [
            mido.open_input(SYNTH_DEVICE_NAME),
            mido.open_input(CONTROL_DEVICE_NAME),
        ]
        outports = [
            mido.open_output(SYNTH_DEVICE_NAME),
            mido.open_output(CONTROL_DEVICE_NAME),
        ]
        return inports, outports
    except SystemError:
        time.sleep(timeout)
        return connect(timeout)


class MidiBridge:
    inports = tuple()
    outports = tuple()

    def __init__(self):
        self.patch = 0
        "".rstrip
        self.inports, self.outports = connect()
        for port, device in enumerate(self.inports):
            logging.info("[IN] MidiBridge connected to external device %s", device.name)
            device.callback = self.receive(port)
        for device in self.outports:
            logging.info(
                "[OUT] MidiBridge connected to external device %s", device.name
            )
        self._get_patch()

    def __del__(self):
        for port in [*self.inports, *self.outports]:
            if port is not None and not port.closed:
                port.close()

    def send(self, msg, port=0):
        device = self.outports[port]
        if device is None or device.closed:
            logging.warning(
                "[OUT] No device on port %i, skipping message: %d", port, msg.dict()
            )
        else:
            logging.info(
                "[OUT] %s message to %s", msg.type.capitalize(), device.name[0:8]
            )
            logging.debug(msg.dict())
            try:
                device.send(msg)
            except Exception as e:
                logging.error("[OUT] %i %s", port, e)

    def receive(self, port):
        device = self.outports[port]

        def wrapped(msg):
            if msg.type == "clock":
                return
            logging.info(
                "[IN] %s message from %s", msg.type.capitalize(), device.name[0:8]
            )
            logging.debug(msg.dict())
            try:
                if port == 0:
                    if msg.type == "sysex":
                        if msg.data[0] == 65:
                            self._sysex_in(msg.data[6:])
                    elif msg.type == "program_change":
                        self._program_in(msg.channel, msg.program)
                elif port == 1:
                    if msg.type == "control_change":
                        self._control_in(msg.channel, msg.control, msg.value)
                    elif msg.type == "note_on":
                        self._note_in(msg.channel, msg.note, msg.velocity)
            except Exception as e:
                logging.error("[IN] %i %s", port, e)

        return wrapped

    def _program_in(self, channel, program):
        self._get_patch()

    @throttle(0.05, 1, 2)
    def _control_in(self, channel, control, value):
        if control < 16 or control > 22 or control == 19:
            return

        msg = mido.Message("sysex", data=SYNTH_SYSEX_CMD)
        instr = get_instrument(control)
        string = channel + (6 if control < 20 else 12)
        value = clip(value / 127 * 100)

        if channel < 6:
            msg.data += checksum("patch", [instr, string, value])
        elif channel == 8 and control < 19:
            msg.data += checksum("patch", [instr, 2, value])
        self.send(msg)

    def _note_in(self, channel, note, velocity):
        if note == 98 and velocity == 127:
            self._shutdown()
        elif note == 94:  # up
            self._set_patch(-1)
        elif note == 95:  # down
            self._set_patch(1)
        elif note == 96:  # right
            self._set_patch(4)
        elif note == 97:  # left
            self._set_patch(-4)

    def _sysex_in(self, data):
        if data[0] != 18:
            return
        if data[3] == 0:
            self.patch = int("0x" + "".join(map(lambda a: hex(a)[2:], data[5:9])), 16)
            return
        control = clip((data[3] + 155) / 11 + (4 if data[4] >= 12 else 0))
        # channel = 8 if data[4] == 2 else data[4] % 6
        values = map(lambda d: clip(d / 100 * 127), data[5:-2])
        for index, value in enumerate(values):
            channel = divmod(index, 6)[1] if data[4] != 2 else 8
            msg = mido.Message(
                "control_change", channel=channel, control=control, value=value
            )
            self.send(msg, 1)

    def _get_patch(self):
        msg = mido.Message(
            "sysex",
            data=[*SYNTH_SYSEX_REQ, *checksum("common", [0, 0, 0, 0, 0, 4])],
        )
        self.send(msg)
        self._get_strings()

    def _set_patch(self, offset):
        self.patch = scroll(self.patch + offset, 0, 399)
        values = map(lambda x: int(x, 16), list(hex(self.patch)[2:].zfill(4)))
        msg = mido.Message(
            "sysex", data=[*SYNTH_SYSEX_CMD, *checksum("common", [0, 0, *values])]
        )
        self.send(msg)

    def _get_strings(self, instrs=[1, 2, 3]):
        for i in instrs:
            instr = 11 * i + 10
            msg = mido.Message("sysex")
            msg.data = [*SYNTH_SYSEX_REQ, *checksum("patch", [instr, 2, 0, 0, 0, 1])]
            self.send(msg)
            msg.data = [*SYNTH_SYSEX_REQ, *checksum("patch", [instr, 6, 0, 0, 0, 12])]
            self.send(msg)
            # for string in range(6, 18):
            #     msg.data = [
            #         *SYNTH_SYSEX_REQ,
            #         *checksum("patch", [instr, string, 0, 0, 0, 1]),
            #     ]
            #     self.send(msg)

    @doubleclick(0.4)
    def _shutdown(self):
        logging.info("[IN] 1 Shutdown signal")
        os.system("sudo shutdown now")


if __name__ == "__main__":
    try:
        logging.info(
            "Starting MidiBridge: %s <--> %s via %s",
            SYNTH_DEVICE_NAME,
            CONTROL_DEVICE_NAME,
            MIDO_BACKEND,
        )
        MidiBridge()
        while True:
            continue
    except Exception as e:
        logging.error(e)
