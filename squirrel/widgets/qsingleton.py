from qtpy import QtCore


class QtSingleton(type(QtCore.QObject), type):
    """
    Qt specific singleton implementation, needed to ensure signals are shared
    between instances.  Adapted from
    https://stackoverflow.com/questions/59459770/receiving-pyqtsignal-from-singleton

    The more common __new__ - based singleton pattern does result in the QObject
    being a singleton, but the bound signals lose their connections whenever the
    instance is re-acquired.  I do not understand but this works

    To use this, specify `QtSingleton` as a metaclass:

    .. code-block:: python

        class SingletonClass(QtCore.QObject, metaclass=QtSingleton):
            shared_signal: ClassVar[QtCore.Signal] = QtCore.Signal()

    """
    def __init__(cls, name, bases, dict):
        super().__init__(name, bases, dict)
        cls._instance = None

    def __call__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__call__(*args, **kwargs)
        return cls._instance
