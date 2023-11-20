import time
import logging
import reactivex as rx
from typing import Iterable


def minmax(n: float, smallest=0.0, largest=1.0):
    return max(smallest, min(n, largest))


def clip(n: float, smallest=0.0, largest=127.0):
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
    def __init__(self, value) -> None:
        super().__init__("First byte MUST be below 128, received %i" % value)


def flatten_bytes(limit: int, *args: list[int]):
    """Ensures all bytes are below 128"""
    lists = list(args)
    results = []
    while len(lists) > 0:
        body = lists.pop()
        i = len(body) - 1
        while i >= 0:
            if body[i] >= limit:
                offset, new_value = divmod(body[i], limit)
                body[i] = int(new_value)
                if i == 0:
                    if len(lists) < 1:
                        raise MaxByteException(body[i])
                    lists[-1][-1] += offset
                else:
                    body[i - 1] += offset
            results.insert(0, body[i])
            i -= 1
    return results


def checksum(head, body=[]):
    # print(head, body)
    safe_bytes = flatten_bytes(128, head, body)
    result = 128 - sum(x if x is not None else 0 for x in safe_bytes) % 128
    # print([*safe_bytes, 0 if result == 128 else result])
    return [*safe_bytes, 0 if result == 128 else result]


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


def retry(action, args, timeout=3, retries=5):
    """Retry mechanism for connecting hardware"""
    try:
        return action(*args)
    except Exception as e:
        if retries > 0:
            time.sleep(timeout)
            return retry(action, args, timeout, retries - 1)
        raise e


def to_observable(messages):
    if isinstance(messages, rx.Observable):
        return messages
    if isinstance(messages, Iterable):
        return rx.from_iterable(messages)
    if messages is not None:
        return rx.of(messages)
    return rx.never()
