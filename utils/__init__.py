import time
from typing import Any, Callable, Generator
from reactivex import operators as ops, from_iterable, timer, empty


def minmax(n: float, smallest=0, largest=1):
    return max(smallest, min(n, largest))


def clip(n: float, smallest=0, largest=127):
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


def t2i(values):
    if isinstance(values, tuple):
        return values[0]
    return values


def throttle(timespan=0.2):
    def decorate(func):
        last = None

        def set_last(m):
            nonlocal last
            last = m

        def wrapped(*args, **kwargs):
            msg = args[1]

            def is_last():
                if last and last.channel == msg.channel and last.control == msg.control:
                    return timer(timespan)
                return empty()

            return from_iterable(func(*args, **kwargs)).pipe(
                ops.buffer_when(is_last),
                ops.map(lambda b: b.pop()),
                ops.do_action(set_last),
            )

        return wrapped

    return decorate


def suspend_when(selector: Callable[[Any], bool]):
    def decorate(func: Callable[[Any, Any], Generator]):
        def wrapped(*args, **kwargs):
            self, msg = args
            if selector(msg):
                is_cc = lambda m: m.is_cc()
                cc = self.messages.pipe(ops.filter(is_cc))
                last = (
                    lambda m: m.control == msg.control - 1 and m.channel == msg.channel
                )
                mapper = lambda m: cc.pipe(ops.filter(last)) if selector(m) else empty()
                gate = lambda obs: obs.pipe(ops.throttle_with_mapper(mapper))

                return self.messages.pipe(ops.filter(is_cc), ops.map(gate))
            return func(*args, **kwargs)

        return wrapped

    return decorate
