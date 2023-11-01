from sounddevice import query_devices
from audio.mixer import Mixer
from midi import Sequencer
from utils import retry


class AudioDevice(Mixer):
    _playing = False
    _recording = False

    @property
    def playing(self):
        return self._playing

    @property
    def recording(self):
        return self._recording

    @playing.setter
    def playing(self, value: bool):
        def wrapped(_, __):
            self._playing = value
            self._recording = False if value else self._recording

        Sequencer._start.schedule(wrapped)

    @recording.setter
    def recording(self, value: bool):
        def wrapped(_, __):
            self._recording = value
            self._playing = False if value else self._playing

        Sequencer._start.schedule(wrapped)

    @property
    def samplerate(self):
        return self.device.get("default_samplerate", 48000.0)

    @property
    def channels(self):
        input_channels = self.device.get("max_input_channels", 8)
        output_channels = self.device.get("max_output_channels", 8)
        return input_channels, output_channels

    @property
    def external_message(self):
        return lambda msg: msg.type in [
            "volume",
            "xfade",
            "xfader",
            "play",
            "rec",
            "stop",
            "toggle",
            "phrase",
            "bars",
        ]

    @property
    def state(self):
        if self.playing:
            return "Playing"
        if self.recording:
            return "Recording"
        return "Streaming"

    @property
    def is_closed(self):
        return True

    def __init__(self, name: str, tracks: int):
        super(AudioDevice, self).__init__(name, tracks)
        device = retry(query_devices, [name])
        if isinstance(device, dict):
            self.device = device
        else:
            self.device = dict(
                name=name,
                max_input_channels=tracks,
                max_output_channels=tracks,
                default_samplerate=48000.0,
            )
