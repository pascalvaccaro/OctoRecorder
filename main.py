from dotenv import load_dotenv

load_dotenv()
import os
import logging

SYNTH_DEVICE_NAME = os.environ.get("SYNTH_DEVICE", "SY-1000 MIDI 1")
CONTROL_DEVICE_NAME = os.environ.get("CONTROL_DEVICE", "Akai APC40 MIDI 1")
logging.basicConfig(
    level=int(os.environ.get("DEBUG", logging.INFO)),
    format="%(asctime)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from devices import OctoRecorder, SY1000, APC40

if __name__ == "__main__":
    try:
        control = APC40(CONTROL_DEVICE_NAME)
        synth = SY1000(SYNTH_DEVICE_NAME, control)
        audio = OctoRecorder(synth, control)
        for device in (control, synth):
            device.start()
        while True:
            continue
    except Exception as e:
        logging.error(e)
        logging.debug("Stacktrace %s", e.with_traceback(None))
