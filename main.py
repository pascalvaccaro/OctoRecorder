from dotenv import load_dotenv

load_dotenv()
import os
import logging
import mido

DEBUG = int(os.environ.get("DEBUG", logging.INFO))
SYNTH_DEVICE_NAME = os.environ.get("SYNTH_DEVICE", "SY-1000 MIDI 1")
CONTROL_DEVICE_NAME = os.environ.get("CONTROL_DEVICE", "Akai APC40 MIDI 1")
AUDIO_DEVICE_NAME = os.environ.get("AUDIO_DEVICE", "SY-1000")
MIDO_BACKEND = os.environ.get("__MIDO_BACKEND__", "mido.backends.portmidi")
logging.basicConfig(
    level=DEBUG,
    format="%(asctime)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from devices import APC40, SY1000, Mixer, Sequencer
from bridge import Bridge

if __name__ == "__main__":
    try:
        mido.set_backend(MIDO_BACKEND, load=True)
        logging.info("[MID] Midi Backend started on %s", MIDO_BACKEND)
        control = APC40(CONTROL_DEVICE_NAME)
        synth = SY1000(SYNTH_DEVICE_NAME)
        audio = Mixer(AUDIO_DEVICE_NAME, 16, 8)
        sequencer = Sequencer(synth.inport)
        Bridge.start(control, synth, audio, sequencer).wait()
    except KeyboardInterrupt:
        logging.info("[ALL] Stopped by user")
