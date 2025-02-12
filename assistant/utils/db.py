from contextlib import contextmanager
from django.db.models.signals import (
    pre_save, post_save, pre_delete, post_delete,
    m2m_changed, pre_init, post_init
)


@contextmanager
def disable_signals(model=None, signals=None):
    """
    Context manager to temporarily disable Django signals.

    :param model: optional model to restrict signal disabling to.
    :param signals: optional list of signals to disable. If None, all common Django signals will be disabled.

    :example:
    with disable_signals([pre_save, post_save], model=MyModel):
        # do something

    :example:
    with disable_signals(model=MyModel):
        # do something
    """
    if signals is None:
        signals = [pre_save, post_save, pre_delete, post_delete, m2m_changed, pre_init, post_init]

    old_receivers = {}

    for signal in signals:
        old_receivers[signal] = signal.receivers
        if model:
            signal.receivers = [
                receiver for receiver in signal.receivers
                if not (receiver[0][1] == id(model))
            ]
        else:
            signal.receivers = []

    try:
        yield
    finally:
        for signal in signals:
            signal.receivers = old_receivers[signal]
