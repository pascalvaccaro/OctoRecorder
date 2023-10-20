from dotenv import load_dotenv

load_dotenv()
import os
import logging

DEBUG=int(os.environ.get("DEBUG", logging.INFO))
SYNTH_DEVICE_NAME = os.environ.get("SYNTH_DEVICE", "SY-1000 MIDI 1")
CONTROL_DEVICE_NAME = os.environ.get("CONTROL_DEVICE", "Akai APC40 MIDI 1")
logging.basicConfig(
    level=DEBUG,
    format="%(asctime)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from devices import OctoRecorder, SY1000, APC40

if __name__ == "__main__":
    try:
        audio = OctoRecorder()
        control = APC40(CONTROL_DEVICE_NAME)
        synth = SY1000(SYNTH_DEVICE_NAME, control)
        audio.bind(synth, control)
        logging.info("[ALL] Connected & started")
        while True:
            continue
    except KeyboardInterrupt:
        print("")
    except Exception as e:
        logging.error(e)
        if DEBUG <= 10:
            raise e
