import time
import logging
import reactivex as rx
from typing import Iterable


def minmax(n: float, smallest=0., largest=1.):
    return max(smallest, min(n, largest))


def clip(n: float, smallest=0., largest=127.):
    return round(minmax(n, smallest, largest))


def split(v: float):
    value = minmax(v, 0, 1)
    return value, 1 - value


def scroll(n: int, smallest=0, largest=127):
    if n < smallest:
        return largest
    if n > largest:
        return smallest
    return n


def t2i(values):
    return values[0] if isinstance(values, tuple) else values


def split_hex(val: int):
    return [int(h, 16) for h in hex(val)[2:]]



class MaxByteException(Exception):
    def __init__(self, index, value) -> None:
        super().__init__("First byte MUST be below 127")
        self.index = index
        self.value = value


def checksum(head, body=[]):
    try:
        max_i = len(body) - 1
        for i, val in enumerate(reversed(body)):
            if val > 127:
                if i == max_i: # first byte/cannot set next byte!
                    raise MaxByteException(i, val)
                offset, new_value = divmod(val, 128)
                body[i + 1] += offset
                body[i] = new_value
        result = 128 - sum(x if x is not None else 0 for x in [*head, *body]) % 128
        return [*head, *body, 0 if result == 128 else result]
    except Exception as e:
        if isinstance(e, MaxByteException):
            logging.error(e, e.index, e.value)
        else:
            logging.exception(e)
        return [*head, *body, 0]


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


def retry(action, args, timeout=3):
    """Retry mechanism for connecting hardware"""

    try:
        return action(*args)
    except Exception as e:
        logging.warn(e)
        time.sleep(timeout)
        return retry(action, args, timeout)


def to_observable(messages):
    if isinstance(messages, rx.Observable):
        return messages
    if isinstance(messages, Iterable):
        return rx.from_iterable(messages)
    if messages is not None:
        return rx.of(messages)
    return rx.never()
