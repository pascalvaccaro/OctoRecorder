from audio.recorder import Recorder
import numpy as np
from audioop import tostereo, tomono
from utils import split, minmax

def fade(data, value, x=None):
    if isinstance(x, float):
      stereo = tostereo(data, 4, *split(value))
      return tomono(stereo, 4, *split(x))
    return np.multiply(data, minmax(value))
