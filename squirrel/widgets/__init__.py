import qtawesome as qta

import squirrel.color
from squirrel.model import Severity, Status

from .data_widget import DataWidget  # noqa
from .display import Display  # noqa
from .flow_layout import FlowLayout
from .namedesctags import NameDescTagsWidget  # noqa
from .qsingleton import QtSingleton  # noqa
from .squirrel_table_view import SquirrelTableView  # noqa
from .tag import TagChip, TagsWidget

__all__ = [
    "FlowLayout",
    "TagChip",
    "TagsWidget",
]


class SeverityIcons:
    cache = {}
    scale = 1.3

    def __getitem__(self, key):
        try:
            return self.cache[key]
        except KeyError:
            if key == Severity.NO_ALARM or key == Status.NO_ALARM:
                icon = None
            elif key == Severity.MINOR:
                icon = qta.icon(
                    "ph.warning-fill",
                    color=squirrel.color.YELLOW,
                    scale_factor=self.scale,
                )
            elif key == Severity.MAJOR:
                icon = qta.icon(
                    "ph.x-square-fill",
                    color=squirrel.color.RED,
                    scale_factor=self.scale,
                )
            elif key == Severity.INVALID:
                icon = qta.icon(
                    "ph.question-fill",
                    color=squirrel.color.MAGENTA,
                    scale_factor=self.scale,
                )
            elif isinstance(key, Status):  # not Status.NO_ALARM
                icon = qta.icon(
                    "mdi.disc",
                    color=squirrel.color.GREY,
                    scale_factor=self.scale,
                )
            else:
                raise
            self.cache[key] = icon
            return icon


SEVERITY_ICONS = SeverityIcons()


def get_window():
    """
    Return the window singleton if it already exists, to allow other widgets to
    access its members.
    Must not be called in the code path that results from Window.__init__.
    A good (safe) rule of thumb is to make sure this function cannot be reached
    from any widget's __init__ method.
    Hides import in __init__ to avoid circular imports.
    """
    from .window import Window
    if Window._instance is None:
        return
    return Window()
