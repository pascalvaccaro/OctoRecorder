import time


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
