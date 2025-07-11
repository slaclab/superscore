from typing import TYPE_CHECKING, Callable, Dict, Protocol, Union

if TYPE_CHECKING:
    from superscore.model import Entry
    from superscore.widgets.core import DataWidget

AnyEpicsType = Union[None, float, str, bool, int]  # this order is important for apischema coercion
TagDef = dict[int, list[Union[str, str, dict[int, str]]]]  # the definition of available tag groups
TagSet = dict[int, set[int]]  # a set of active tags and tag groups attached to an entry


class AnyDataclass(Protocol):
    """
    Protocol stub shamelessly lifted from stackoverflow to hint at dataclass
    """
    __dataclass_fields__: Dict


OpenPageSlot = Callable[["Entry"], "DataWidget"]
