from dotenv import load_dotenv

load_dotenv()
import os
import logging
from devices import APC40, SY1000, Recorder
from bridge import Bridge

DEBUG = int(os.environ.get("DEBUG", logging.INFO))
SYNTH_DEVICE_NAME = os.environ.get("SYNTH_DEVICE", "SY-1000 MIDI 1")
CONTROL_DEVICE_NAME = os.environ.get("CONTROL_DEVICE", "Akai APC40 MIDI 1")
AUDIO_DEVICE_NAME = os.environ.get("AUDIO_DEVICE", "SY-1000")
logging.basicConfig(
    level=DEBUG,
    format="%(asctime)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


if __name__ == "__main__":
    try:
        control = APC40(CONTROL_DEVICE_NAME)
        synth = SY1000(SYNTH_DEVICE_NAME)
        audio = Recorder(AUDIO_DEVICE_NAME)
        Bridge.start(control, synth, audio).wait()
    except KeyboardInterrupt:
        logging.info("[ALL] Stopped by user")
