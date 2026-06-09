from app.monitoring.prometheus import increment_counter as _inc


def increment_counter(name: str, tags: dict = None):
    _inc(name, tags=tags)
