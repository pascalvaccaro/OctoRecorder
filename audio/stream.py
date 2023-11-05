from numpy import frombuffer, float32
from numpy.typing import NDArray
from sounddevice import Stream as SdStream
from audioop import mul, tostereo, tomono
from utils import split

class Stream(SdStream):
    def __init__(self, faders, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.faders = faders

    def write(self, data: NDArray[float32]):
        faders, big_x = self.faders
        for ch, values in enumerate(faders):
            vol, x = values
            stereo = tostereo(data[:, ch].tobytes(), 4, *split(x))
            mono = tomono(stereo, 4, *split(big_x))
            data[:, ch] = frombuffer(mul(mono, 4, vol), dtype=float32)
        return super().write(data)
