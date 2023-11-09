# OctoRecorder

Record individual string signals from a SY-1000 guitar synthetizer


## Features

- 8-channels audio recording/playing from/to SY-1000
- 8-channels mixer (volume, crossfading)
- MIDI messages from/to SY-1000 (synth)
- MIDI messages from/to Akai APC40 (control)
- MIDI clock synchronization


## Install

```bash
python3 -m pip install -r requirements.txt
```

### Dependencies

- [mido](https://mido.readthedocs.io/en/stable/installing.html) 
- [sounddevice](https://python-sounddevice.readthedocs.io/en/0.4.6/installation.html). 

Refer to these packages documentation to configure them accordingly

### Environment Variables

To run this project, you will need to add the following environment variables to your .env file

`SYNTH_DEVICE`: full synth MIDI device name, ex: `"SY-1000 MIDI 1"`

`CONTROL_DEVICE`: full control MIDI device name, ex: `"Akai APC40 MIDI 1"`

`AUDIO_DEVICE_NAME`: full audio device name, ex; `"SY-1000"`

`__MIDO_BACKEND__`: mido backend name, ex: `"mido.backends.portmidi"`


## Usage

- Connect both devices via USB
- Launch the main script using python3


```bash
python3 main.py
```

### Debug mode

```bash
DEBUG=10 python3 main.py
```
## License

[MIT](https://choosealicense.com/licenses/mit/)

